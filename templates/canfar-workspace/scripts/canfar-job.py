#!/usr/bin/env python3
"""CANFAR Headless Job Launcher for AstroAI.

Launches reproducible batch, training, or pipeline jobs on CANFAR compute from
either your Mac laptop or an interactive session.

Features:
- Automatic code staging to /scratch/src on the job pod (never touches $HOME).
- Git ref pinning (records exact commit SHA for provenance).
- Automated pixi environment installation.
- Strict environment hygiene (PYTHONNOUSERSITE=1, scratch-backed caches).
- Single-token execution wrapper immune to Skaha whitespace-splitting.
- Live log tailing (--follow).

Usage:
  canfar-job.py run --repo torchsky --cpu 8 --memory 32 -- pixi run python train.py
  canfar-job.py run --repo uspm --branch topic --gpu 1 -- pixi run python test.py
  canfar-job.py status [session-id]
  canfar-job.py logs <session-id> [-f]
"""

from __future__ import annotations

import argparse
import base64
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Colors
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"


def c(text: str, color: str) -> str:
    if not (sys.stdout.isatty() and os.environ.get("NO_COLOR") is None):
        return text
    return f"{color}{text}{RESET}"


IMAGE_ALIASES = {
    "base": "images.canfar.net/astroai/base:latest",
    "improc": "images.canfar.net/astroai/improc:latest",
    "ray-worker": "images.canfar.net/astroai/ray-worker:latest",
    "notebook": "images.canfar.net/astroai/notebook:latest",
    "terminal": "images.canfar.net/astroai/terminal:latest",
}


def resolve_image(image_arg: str) -> str:
    alias = IMAGE_ALIASES.get(image_arg.lower())
    if alias:
        return alias
    if image_arg.startswith("images.canfar.net/astroai/"):
        return image_arg
    if image_arg.startswith("astroai/"):
        return f"images.canfar.net/{image_arg}"
    if "/" not in image_arg:
        return f"images.canfar.net/astroai/{image_arg}:latest"
    return image_arg


CONTAINER_RUNNER_SCRIPT = """
import os, sys, subprocess, shutil, time

print("=" * 65)
print("  AstroAI CANFAR Headless Runner")
print("=" * 65)

# 1. Environment & Storage Hygiene
work_dir = os.environ.get("WORK", "/scratch/src")
scratch = os.environ.get("SCRATCH", "/scratch")
os.makedirs(work_dir, exist_ok=True)
os.makedirs(os.path.join(scratch, ".cache"), exist_ok=True)

os.environ["PYTHONNOUSERSITE"] = "1"
os.environ.pop("PYTHONPATH", None)
os.environ["PIXI_CACHE_DIR"] = os.path.join(scratch, ".cache", "pixi")
os.environ["UV_CACHE_DIR"] = os.path.join(scratch, ".cache", "uv")
os.environ["HF_HOME"] = os.path.join(scratch, ".cache", "huggingface")
os.environ["TORCH_HOME"] = os.path.join(scratch, ".cache", "torch")

repo_spec = os.environ.get("JOB_REPO", "")
ref = os.environ.get("JOB_REF", "main")
cmd_raw = base64.b64decode(os.environ.get("JOB_CMD_B64", "")).decode("utf-8")

if not repo_spec:
    print("ERROR: JOB_REPO not specified.")
    sys.exit(1)

# Parse org / name
if "/" in repo_spec:
    org, name = repo_spec.split("/", 1)
else:
    org, name = "astroai", repo_spec

repo_dest = os.path.join(work_dir, org, name)
os.makedirs(os.path.dirname(repo_dest), exist_ok=True)

# 2. Stage Code
if not os.path.isdir(os.path.join(repo_dest, ".git")):
    print(f"Staging code: {repo_spec} (ref={ref}) -> {repo_dest}")
    # Try fork first, fallback to canonical
    fork_url = f"https://github.com/sfabbro/{name}.git"
    canon_url = f"https://github.com/{org}/{name}.git"
    
    clone_cmd = ["git", "clone", "--depth", "50", "-b", ref, fork_url, repo_dest]
    res = subprocess.run(clone_cmd)
    if res.returncode != 0:
        print(f"Fork clone failed, trying canonical: {canon_url}")
        clone_cmd = ["git", "clone", "--depth", "50", "-b", ref, canon_url, repo_dest]
        res = subprocess.run(clone_cmd)
        if res.returncode != 0:
            print("ERROR: git clone failed.")
            sys.exit(res.returncode)

# Wire upstream if astroai
if org == "astroai":
    subprocess.run(["git", "-C", repo_dest, "remote", "add", "upstream", f"https://github.com/astroai/{name}.git"], stderr=subprocess.DEVNULL)

sha = subprocess.run(["git", "-C", repo_dest, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
branch = subprocess.run(["git", "-C", repo_dest, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
print(f"Code ready: {org}/{name} @ {branch} ({sha[:10]})")

# 3. Prepare Environment
pixi_cmd = shutil.which("pixi")
if pixi_cmd and (os.path.isfile(os.path.join(repo_dest, "pixi.toml")) or os.path.isfile(os.path.join(repo_dest, "pixi.lock"))):
    print("Running pixi install ...")
    subprocess.run([pixi_cmd, "install"], cwd=repo_dest, check=True)

# 4. Execute Payload Command
print(f"Executing: {cmd_raw}")
print("-" * 65)
start_time = time.time()

res = subprocess.run(cmd_raw, cwd=repo_dest, shell=True)
elapsed = time.time() - start_time

print("-" * 65)
print(f"Execution finished with exit code {res.returncode} in {elapsed:.1f}s.")
sys.exit(res.returncode)
"""


def cmd_run(args: argparse.Namespace, extra_cmd: list[str]) -> int:
    canfar = shutil.which("canfar")
    if not canfar:
        print(c("canfar CLI not found on PATH. Install via OpenCADC and login first.", RED))
        return 1

    if not extra_cmd:
        print(c("Error: No command specified to run. Pass command after '--'.", RED))
        print("Example: canfar-job.py run --repo torchsky -- pixi run python train.py")
        return 1

    cmd_str = " ".join(extra_cmd)
    image = resolve_image(args.image)

    # Resolve repo & ref
    repo = args.repo
    ref = args.branch
    if not ref:
        # Check current local branch if inside a git repo matching name
        curr_dir = Path.cwd()
        if (curr_dir / ".git").is_dir() and curr_dir.name == repo.split("/")[-1]:
            b_res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
            if b_res.returncode == 0 and b_res.stdout.strip() != "HEAD":
                ref = b_res.stdout.strip()
    ref = ref or "main"

    job_name = args.name or f"job-{repo.split('/')[-1]}-{int(time.time()) % 10000}"

    runner_b64 = base64.b64encode(CONTAINER_RUNNER_SCRIPT.strip().encode("utf-8")).decode("ascii")
    eval_arg = "exec(__import__('base64').b64decode(__import__('os').environ['RUNNER_SCRIPT']).decode())"

    create_cmd = [
        canfar,
        "create",
        "headless",
        image,
        "--name",
        job_name,
        "--cpu",
        str(args.cpu),
        "--memory",
        str(args.memory),
        "-e",
        f"JOB_REPO={repo}",
        "-e",
        f"JOB_REF={ref}",
        "-e",
        f"JOB_CMD_B64={base64.b64encode(cmd_str.encode('utf-8')).decode('ascii')}",
        "-e",
        f"RUNNER_SCRIPT={runner_b64}",
        "-e",
        "PYTHONNOUSERSITE=1",
    ]

    if args.gpu > 0:
        create_cmd.extend(["--gpu", str(args.gpu)])

    create_cmd.extend(["--", "python3", "-c", eval_arg])

    print(f"\n{BOLD}Submitting CANFAR Headless Job:{RESET}")
    print(f"  Job Name:    {job_name}")
    print(f"  Repository:  {repo} (ref: {ref})")
    print(f"  Resources:   {args.cpu} CPU cores, {args.memory} GB RAM, {args.gpu} GPUs")
    print(f"  Image:       {image}")
    print(f"  Command:     {cmd_str}")

    if args.dry_run:
        print(f"\n{c('Dry-run command:', YELLOW)}")
        print(" ".join(create_cmd))
        return 0

    res = subprocess.run(create_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(c(f"\nFailed to create job: {res.stderr.strip()}", RED))
        return 1

    output = res.stdout.strip()
    print(f"\n{c('✓ Headless job submitted.', GREEN)}")
    print(output)

    # Extract session ID from output if possible
    m = re.search(r"([a-z0-9]{8})", output)
    session_id = m.group(1) if m else None

    if session_id:
        print(f"\nSession ID: {BOLD}{session_id}{RESET}")
        print(f"Logs:       canfar logs {session_id} -f")
        print(f"Status:     canfar info {session_id}")
        print(f"Delete:     canfar delete {session_id}")

        if args.follow:
            print(f"\n{BOLD}Tailing logs (Ctrl+C to stop watching)...{RESET}\n")
            time.sleep(2)
            try:
                subprocess.run([canfar, "logs", session_id, "-f"])
            except KeyboardInterrupt:
                print("\nStopped following logs. Job continues running.")

    return 0


def cmd_status() -> int:
    canfar = shutil.which("canfar")
    if not canfar:
        print(c("canfar CLI not found on PATH.", RED))
        return 1
    return subprocess.run([canfar, "ps"]).returncode


def cmd_logs(session_id: str, follow: bool = False) -> int:
    canfar = shutil.which("canfar")
    if not canfar:
        print(c("canfar CLI not found on PATH.", RED))
        return 1
    cmd = [canfar, "logs", session_id]
    if follow:
        cmd.append("-f")
    return subprocess.run(cmd).returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Launch and manage headless compute jobs on CANFAR."
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Command to run")

    # run
    run_p = subparsers.add_parser("run", help="Launch a headless job.")
    run_p.add_argument("--repo", required=True, help="Repository name (e.g. torchsky or astroai/torchsky).")
    run_p.add_argument("--branch", "--ref", dest="branch", help="Git branch, tag, or SHA (default: current or main).")
    run_p.add_argument("--image", default="base", help="Container image alias or full name (default: base).")
    run_p.add_argument("--cpu", type=int, default=4, help="CPU cores (default: 4).")
    run_p.add_argument("--memory", type=int, default=16, help="RAM in GB (default: 16).")
    run_p.add_argument("--gpu", type=int, default=0, help="Number of GPUs (default: 0).")
    run_p.add_argument("--name", help="Session name.")
    run_p.add_argument("-f", "--follow", action="store_true", help="Follow logs after submission.")
    run_p.add_argument("--dry-run", action="store_true", help="Print command without submitting.")

    # status
    subparsers.add_parser("status", help="List active CANFAR sessions.")

    # logs
    logs_p = subparsers.add_parser("logs", help="View logs for a session.")
    logs_p.add_argument("session_id", help="Session ID to inspect.")
    logs_p.add_argument("-f", "--follow", action="store_true", help="Follow logs live.")

    # Parse known args to permit passing '-- <cmd>' cleanly
    argv = sys.argv[1:]
    extra_cmd = []
    if "--" in argv:
        idx = argv.index("--")
        extra_cmd = argv[idx + 1 :]
        argv = argv[:idx]

    args = parser.parse_args(argv)
    cmd = args.subcommand or "run"

    if cmd == "run":
        return cmd_run(args, extra_cmd)
    elif cmd == "status":
        return cmd_status()
    elif cmd == "logs":
        return cmd_logs(args.session_id, follow=args.follow)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
