#!/usr/bin/env python3
"""CANFAR Autoscaling Ray Cluster Manager.

Provides a unified interface to launch, manage, and monitor autoscaling Ray clusters
on CANFAR compute from either your Mac laptop or an interactive session.

Features:
- Symmetrical operation: Works from Mac Laptop (via canfar CLI + headless bootstrap)
  or directly inside CANFAR interactive sessions.
- Autoscaler configuration: Writes RAY_AUTOSCALING_* variables to
  /arc/home/<user>/.config/canfar/lab/ray-manager.env so Ray automatically starts
  and terminates headless ray-worker pods on demand.
- Stock Ray Dashboard integration with one-click browser launch (--open).
- Remote Ray Jobs API submission support (ASTROAI_RAY_JOBS_ADDRESS).

Commands:
  canfar-cluster.py start      Start or configure the autoscaling Ray cluster
  canfar-cluster.py status     Inspect Ray manager and worker sessions
  canfar-cluster.py dashboard  Print or open the stock Ray Dashboard URL
  canfar-cluster.py stop       Tear down Ray manager and worker pods
  canfar-cluster.py run        Submit a Python script to the Ray cluster
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Colors
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def c(text: str, color: str) -> str:
    if not (sys.stdout.isatty() and os.environ.get("NO_COLOR") is None):
        return text
    return f"{color}{text}{RESET}"


def is_canfar_session() -> bool:
    return Path("/scratch").is_dir() and not sys.platform == "darwin"


def get_canfar_cli() -> str:
    canfar = shutil.which("canfar")
    if not canfar:
        print(c("canfar CLI not found on PATH. Install via OpenCADC and login first.", RED))
        sys.exit(1)
    return canfar


def list_canfar_sessions() -> list[dict[str, str]]:
    """List sessions using canfar ps --json or tabular fallback."""
    canfar = get_canfar_cli()
    # Try --json first
    res = subprocess.run([canfar, "ps", "--json"], capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip().startswith("["):
        try:
            return json.loads(res.stdout)
        except Exception:
            pass

    # Parse tabular canfar ps
    res = subprocess.run([canfar, "ps"], capture_output=True, text=True)
    lines = res.stdout.splitlines()
    sessions = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 5 and re.match(r"^[a-z0-9]{8}$", parts[0]):
            sessions.append({
                "id": parts[0],
                "name": parts[1],
                "kind": parts[2],
                "status": parts[3],
                "image": parts[4],
            })
    return sessions


def find_manager_session() -> dict[str, str] | None:
    sessions = list_canfar_sessions()
    for s in sessions:
        name = s.get("name", "").lower()
        image = s.get("image", "").lower()
        status = s.get("status", "").lower()
        if ("raymgr" in name or "ray-manager" in image) and status in ("running", "pending"):
            return s
    return None


def get_session_info(session_id: str) -> dict[str, str]:
    canfar = get_canfar_cli()
    res = subprocess.run([canfar, "info", session_id], capture_output=True, text=True)
    info = {}
    for line in res.stdout.splitlines():
        if "Connect URL" in line or "connect url" in line.lower():
            parts = line.split(None, 2)
            if len(parts) >= 3:
                info["connect_url"] = parts[2].strip()
        elif "Status" in line:
            parts = line.split(None, 2)
            if len(parts) >= 2:
                info["status"] = parts[-1].strip()
    return info


def resolve_dashboard_url(manager_session: dict[str, str]) -> str | None:
    sid = manager_session["id"]
    info = get_session_info(sid)
    connect_url = info.get("connect_url")
    if not connect_url:
        # Standard Skaha URL format
        connect_url = f"https://workloads.canfar.net/session/contrib/{sid}/"
    base = connect_url.rstrip("/")
    return f"{base}/dashboard/"


def cmd_start(args: argparse.Namespace) -> int:
    canfar = get_canfar_cli()

    print(f"\n{BOLD}Preparing CANFAR Autoscaling Ray Cluster:{RESET}")
    print(f"  Workers:     {args.min_workers} (min) to {args.max_workers} (max)")
    print(f"  Worker Size: {args.cores} CPUs, {args.ram} GB RAM, {args.gpus} GPUs")
    print(f"  Idle Timeout: {args.idle_timeout} min")

    manager = find_manager_session()
    if manager:
        print(c(f"\nFound active Ray manager: {manager['id']} ({manager['status']})", GREEN))
        dash_url = resolve_dashboard_url(manager)
        print(f"Ray Dashboard: {dash_url}")
        print(f"Jobs Address:  {dash_url.rstrip('/')}")
        print(f"\nTo use in current shell:")
        print(f"  export ASTROAI_RAY_JOBS_ADDRESS='{dash_url.rstrip('/')}'")
        if args.open:
            open_url(dash_url)
        return 0

    # If running from Laptop: bootstrap ray-manager.env on CANFAR $HOME via a headless micro-session
    if not is_canfar_session():
        print("\nConfiguring Ray autoscaler env on CANFAR /arc/home/<user> ...")
        bootstrap_cmd = [
            canfar,
            "create",
            "headless",
            "images.canfar.net/astroai/base:latest",
            "--name",
            f"ray-cfg-{int(time.time()) % 10000}",
            "--cpu",
            "1",
            "--memory",
            "2",
            "-e",
            "RAY_AUTOSCALING_ENABLED=1",
            "-e",
            f"RAY_AUTOSCALING_MIN_WORKERS={args.min_workers}",
            "-e",
            f"RAY_AUTOSCALING_MAX_WORKERS={args.max_workers}",
            "-e",
            f"RAY_AUTOSCALING_CORES={args.cores}",
            "-e",
            f"RAY_AUTOSCALING_RAM_GB={args.ram}",
            "-e",
            f"RAY_AUTOSCALING_GPUS={args.gpus}",
            "-e",
            f"RAY_AUTOSCALING_IDLE_TIMEOUT_MINUTES={args.idle_timeout}",
            "-e",
            "PYTHONNOUSERSITE=1",
            "--",
            "bash",
            "/opt/astroai/bin/bootstrap-ray-manager-env.sh",
        ]
        res = subprocess.run(bootstrap_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(c(f"Warning: env bootstrap returned {res.returncode}: {res.stderr.strip()}", YELLOW))
        else:
            print(c("  ✓ Ray autoscaler env written to CANFAR $HOME", GREEN))
    else:
        # On CANFAR session: write ~/.config/canfar/lab/ray-manager.env directly
        cfg_dir = Path.home() / ".config" / "canfar" / "lab"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        env_file = cfg_dir / "ray-manager.env"
        env_lines = [
            "RAY_AUTOSCALING_ENABLED=1",
            f"RAY_AUTOSCALING_MIN_WORKERS={args.min_workers}",
            f"RAY_AUTOSCALING_MAX_WORKERS={args.max_workers}",
            f"RAY_AUTOSCALING_CORES={args.cores}",
            f"RAY_AUTOSCALING_RAM_GB={args.ram}",
            f"RAY_AUTOSCALING_GPUS={args.gpus}",
            f"RAY_AUTOSCALING_IDLE_TIMEOUT_MINUTES={args.idle_timeout}",
        ]
        env_file.write_text("\n".join(env_lines) + "\n")
        print(c(f"  ✓ Written {env_file}", GREEN))

    # Launch ray-manager contributed session
    mgr_image = args.image or "images.canfar.net/astroai/ray-manager:latest"
    print(f"\nLaunching Ray Manager ({mgr_image}) ...")
    create_mgr_cmd = [
        canfar,
        "create",
        "contributed",
        mgr_image,
        "--name",
        args.name or "raymgr",
        "--cores",
        "2",
        "--ram",
        "8",
    ]
    res = subprocess.run(create_mgr_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(c(f"Failed to launch Ray manager: {res.stderr.strip()}", RED))
        return 1

    print(res.stdout.strip())
    print("\nWaiting for manager pod to initialize...")

    # Poll for manager connect URL
    dash_url = None
    for attempt in range(24):
        time.sleep(5)
        manager = find_manager_session()
        if manager:
            dash_url = resolve_dashboard_url(manager)
            if manager["status"].lower() == "running":
                break
        print("… still waiting for manager pod ...")

    if not dash_url:
        print(c("Timed out waiting for Ray manager. Check status with: canfar-cluster.py status", YELLOW))
        return 1

    print(f"\n{c('✓ Ray Manager cluster is up!', GREEN)}")
    print(f"  Manager URL:   {dash_url.replace('/dashboard/', '/')}")
    print(f"  Ray Dashboard: {dash_url}")
    print(f"  Jobs Address:  {dash_url.rstrip('/')}")
    print(f"\nShell export command:")
    print(f"  export ASTROAI_RAY_JOBS_ADDRESS='{dash_url.rstrip('/')}'")

    if args.open:
        open_url(dash_url)

    return 0


def cmd_status() -> int:
    sessions = list_canfar_sessions()
    managers = [s for s in sessions if "raymgr" in s.get("name", "") or "ray-manager" in s.get("image", "")]
    workers = [s for s in sessions if "ray-worker" in s.get("image", "") or s.get("name", "").startswith("ray-as-")]

    print(f"\n{BOLD}CANFAR Ray Cluster Status:{RESET}")
    print("-" * 65)

    if not managers:
        print(c("No active Ray manager session found.", YELLOW))
        print("Start one with: canfar-cluster.py start")
    else:
        for m in managers:
            dash = resolve_dashboard_url(m)
            print(f"Manager Pod: {BOLD}{m['id']}{RESET} ({m['name']})")
            print(f"  Status:    {c(m['status'], GREEN if m['status'] == 'Running' else YELLOW)}")
            print(f"  Dashboard: {dash}")
            print(f"  Jobs URL:  {dash.rstrip('/')}")

    print(f"\nAutoscaler Workers ({len(workers)} active):")
    if not workers:
        print(c("  No worker pods currently provisioned (autoscaler scales up on demand).", DIM))
    else:
        for w in workers:
            print(f"  - Worker {w['id']} ({w['name']}): {w['status']} [{w['image']}]")

    print("-" * 65)
    return 0


def cmd_stop() -> int:
    canfar = get_canfar_cli()
    sessions = list_canfar_sessions()
    targets = [s for s in sessions if "raymgr" in s.get("name", "") or "ray-manager" in s.get("image", "") or "ray-worker" in s.get("image", "") or s.get("name", "").startswith("ray-as-")]

    if not targets:
        print(c("No active Ray manager or worker sessions to stop.", GREEN))
        return 0

    print(f"\n{BOLD}Stopping {len(targets)} Ray cluster session(s):{RESET}")
    for t in targets:
        print(f"  Deleting {t['id']} ({t['name']} - {t['image']}) ...")
        subprocess.run([canfar, "delete", t["id"]])

    print(c("✓ Ray cluster successfully stopped.", GREEN))
    return 0


def open_url(url: str) -> None:
    print(f"Opening {url} in browser...")
    if sys.platform == "darwin":
        subprocess.run(["open", url])
    else:
        xdg = shutil.which("xdg-open")
        if xdg:
            subprocess.run([xdg, url])


def cmd_dashboard(args: argparse.Namespace) -> int:
    manager = find_manager_session()
    if not manager:
        print(c("No active Ray manager found. Run: canfar-cluster.py start", RED))
        return 1
    dash_url = resolve_dashboard_url(manager)
    print(f"Ray Dashboard: {dash_url}")
    if args.open:
        open_url(dash_url)
    return 0


def cmd_run(args: argparse.Namespace, script_args: list[str]) -> int:
    if not script_args:
        print(c("Error: No script specified to run. Pass script after '--'.", RED))
        print("Example: canfar-cluster.py run -- python train.py --epochs 10")
        return 1

    manager = find_manager_session()
    if not manager:
        print(c("No active Ray manager found. Run: canfar-cluster.py start", RED))
        return 1

    dash_url = resolve_dashboard_url(manager)
    jobs_address = dash_url.rstrip("/")

    print(f"\n{BOLD}Submitting Job to CANFAR Ray Cluster:{RESET}")
    print(f"  Jobs Address: {jobs_address}")
    print(f"  Command:      {' '.join(script_args)}")

    # Check if ray CLI is available locally
    ray_cli = shutil.which("ray")
    if ray_cli:
        cmd = [ray_cli, "job", "submit", "--address", jobs_address, "--working-dir", ".", "--"] + script_args
        print(f"\nRunning: {' '.join(cmd)}")
        return subprocess.run(cmd).returncode
    else:
        print(f"\nLocal ray CLI not found. You can submit using:")
        print(f"  export ASTROAI_RAY_JOBS_ADDRESS='{jobs_address}'")
        print(f"  ray job submit --address '{jobs_address}' --working-dir . -- {' '.join(script_args)}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="CANFAR Autoscaling Ray Cluster Manager."
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Command to run")

    # start
    start_p = subparsers.add_parser("start", help="Start or configure the autoscaling Ray cluster.")
    start_p.add_argument("--min-workers", type=int, default=0, help="Minimum worker pods kept alive (default: 0).")
    start_p.add_argument("--max-workers", type=int, default=8, help="Maximum autoscaler ceiling (default: 8).")
    start_p.add_argument("--cores", type=int, default=1, help="CPUs per worker (default: 1).")
    start_p.add_argument("--ram", type=int, default=4, help="RAM in GB per worker (default: 4).")
    start_p.add_argument("--gpus", type=int, default=0, help="GPUs per worker (default: 0).")
    start_p.add_argument("--idle-timeout", type=int, default=5, help="Idle timeout in minutes before scaling down.")
    start_p.add_argument("--name", default="raymgr", help="Session name for Ray manager.")
    start_p.add_argument("--image", help="Custom ray-manager image.")
    start_p.add_argument("-o", "--open", action="store_true", help="Open Dashboard in browser when ready.")

    # status
    subparsers.add_parser("status", help="Inspect Ray manager and worker sessions.")

    # dashboard
    dash_p = subparsers.add_parser("dashboard", help="Print or open the stock Ray Dashboard URL.")
    dash_p.add_argument("-o", "--open", action="store_true", help="Open Dashboard in browser.")

    # stop
    subparsers.add_parser("stop", help="Tear down Ray manager and worker pods.")

    # run
    run_p = subparsers.add_parser("run", help="Submit a job to the Ray cluster.")

    argv = sys.argv[1:]
    script_args = []
    if "--" in argv:
        idx = argv.index("--")
        script_args = argv[idx + 1 :]
        argv = argv[:idx]

    args = parser.parse_args(argv)
    cmd = args.subcommand or "status"

    if cmd == "start":
        return cmd_start(args)
    elif cmd == "status":
        return cmd_status()
    elif cmd == "dashboard":
        return cmd_dashboard(args)
    elif cmd == "stop":
        return cmd_stop()
    elif cmd == "run":
        return cmd_run(args, script_args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
