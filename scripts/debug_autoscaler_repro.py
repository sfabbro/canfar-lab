#!/usr/bin/env python3
"""Reproduce suspected bugs in the new canfar-lab Ray autoscaler code."""
from __future__ import annotations

import os
import sys
import time
import types
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import MagicMock

# Stub ray NodeProvider like unit tests.
_ray = types.ModuleType("ray")
_ray_autoscaler = types.ModuleType("ray.autoscaler")
_ray_np = types.ModuleType("ray.autoscaler.node_provider")


class _NodeProvider:
    def __init__(self, provider_config, cluster_name):
        self.provider_config = provider_config
        self.cluster_name = cluster_name


_ray_np.NodeProvider = _NodeProvider
_ray_autoscaler.node_provider = _ray_np
_ray.autoscaler = _ray_autoscaler
sys.modules.setdefault("ray", _ray)
sys.modules.setdefault("ray.autoscaler", _ray_autoscaler)
sys.modules.setdefault("ray.autoscaler.node_provider", _ray_np)

os.environ["DEBUG_RUN_ID"] = "pre"
sys.path.insert(0, str(Path("/scratch/src/canfar-lab/src")))

from astroai_workload.autoscaler import CanfarNodeProvider, _session_age_seconds
from astroai_workload.dashboard import _probe_manager_url, resolve_dashboard_url, persist_connect_url
from astroai_workload.cli import cluster_start_payload
from astroai_workload.autoscaler import write_manager_autoscaling_env


def _provider(**cfg):
    base = {
        "worker_image": "img:t",
        "cores": 2,
        "ram_gb": 8,
        "gpus": 0,
        "max_workers": 4,
        "pending_timeout_minutes": 1,
        "ray_version": "2.58.0",
        **cfg,
    }
    return CanfarNodeProvider(base, "mgr-abc")


# --- H1: probe accepts 404 ---
class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"missing")

    def log_message(self, *a):
        return


srv = HTTPServer(("127.0.0.1", 0), _H)
Thread(target=srv.serve_forever, daemon=True).start()
probe_ok = _probe_manager_url(f"http://127.0.0.1:{srv.server_address[1]}/")
print("H1 probe_ok_on_404=", probe_ok)
srv.shutdown()

# --- H2: cap at max ---
p = _provider(max_workers=2)
p._ops.list_headless_sessions = MagicMock(
    return_value=[
        {"id": "a", "status": "Running", "name": "ray-as-mgr-abc-1"},
        {"id": "b", "status": "Pending", "name": "ray-as-mgr-abc-2"},
    ]
)
p._ops.create_headless = MagicMock()
out = p.create_node({}, {}, 3)
print("H2 refused_at_max=", out == {}, "create_called=", p._ops.create_headless.called)

# --- H5 replica suffix age ---
old_ms = int((time.time() - 7200) * 1000)
row = {"id": "x", "status": "Pending", "name": f"ray-as-mgr-abc-{old_ms}"}
age = _session_age_seconds(row)
print("H5 age_s=", age, "should_reap=", age is not None and age > 60)
row_rep = {"id": "y", "status": "Pending", "name": f"ray-as-mgr-abc-{old_ms}-1"}
age_rep = _session_age_seconds(row_rep)
print("H5b replica_age_s=", age_rep, "should_reap=", age_rep is not None and age_rep > 60)
p2 = _provider(pending_timeout_minutes=1)
p2._ops.list_headless_sessions = MagicMock(return_value=[row, row_rep])
p2._ops.destroy = MagicMock(return_value=True)
p2._reap_stale_pending()
print("H5 destroy_calls=", [c.args[0] for c in p2._ops.destroy.call_args_list])

# --- H3: recycle when no previous env but manager exists ---
home = Path("/tmp/astroai-debug-home-ed2a36")
if home.exists():
    import shutil

    shutil.rmtree(home)
home.mkdir(parents=True)
os.environ["HOME"] = str(home)
# no previous env file → should recycle existing manager
created = []


class _Ops:
    def find_manager(self):
        return {"id": "old", "name": "raymgr", "status": "Running"}

    def create_contributed(self, **kw):
        created.append(kw)

    def list_headless_sessions(self, **kw):
        return []

    def destroy(self, sid):
        created.append({"destroy": sid})
        return True


class _Client:
    def wait_ready(self, timeout_seconds=0):
        return True

    def status(self):
        return {"cluster": {"phase": "Running"}, "joined_workers": 0}


import astroai_workload.canfar_ops as cops
import astroai_workload.dashboard as dash
import astroai_workload.cli as cli

cops.CanfarOps = _Ops  # type: ignore
dash.resolve_dashboard_url = lambda: "https://mgr/dashboard"  # type: ignore
dash.persist_connect_url = lambda *a, **k: None  # type: ignore
cli._manager_client = lambda base: _Client()  # type: ignore

result = cluster_start_payload(max_workers=2, min_workers=0, cores=8, ram=64)
print(
    "H3 recycled=",
    result.get("recycled_manager"),
    "restart_hint=",
    result.get("restart_manager"),
    "created=",
    created,
)

# With previous env different -> should recycle
write_manager_autoscaling_env(min_workers=1, max_workers=8, cores=1, ram_gb=4, gpus=0)
created.clear()
result2 = cluster_start_payload(max_workers=2, min_workers=0, cores=8, ram=64)
print(
    "H3b recycled=",
    result2.get("recycled_manager"),
    "created=",
    created,
)

print("DONE")
