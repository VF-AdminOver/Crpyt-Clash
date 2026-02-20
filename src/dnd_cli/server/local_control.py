from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from dnd_cli.storage import profile_root


def _state_path() -> Path:
    return profile_root() / "local-server.json"


def _log_path() -> Path:
    return profile_root() / "local-server.log"


def _read_state() -> dict:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(payload: dict) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(path)


def _clear_state() -> None:
    path = _state_path()
    if path.exists():
        path.unlink()


def _is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def local_server_status() -> dict:
    state = _read_state()
    pid = int(state.get("pid", 0) or 0)
    if pid <= 0:
        return {"running": False}
    if not _is_pid_running(pid):
        _clear_state()
        return {"running": False}
    return {
        "running": True,
        "pid": pid,
        "host": str(state.get("host", "127.0.0.1")),
        "port": int(state.get("port", 8000)),
        "log_path": str(state.get("log_path", _log_path())),
    }


def start_local_server(host: str = "127.0.0.1", port: int = 8000) -> tuple[bool, str]:
    status = local_server_status()
    if status.get("running"):
        return False, f"Local server already running at http://{status['host']}:{status['port']} (pid {status['pid']})."

    log_path = _log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log_handle:
        process = subprocess.Popen(
            [sys.executable, "-m", "dnd_cli.main", "server", "--host", host, "--port", str(port)],
            stdout=log_handle,
            stderr=log_handle,
            start_new_session=True,
        )
    time.sleep(0.3)
    if process.poll() is not None:
        return False, f"Local server failed to start. Check logs: {log_path}"
    _write_state(
        {
            "pid": process.pid,
            "host": host,
            "port": port,
            "log_path": str(log_path),
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    return True, f"Local server started at http://{host}:{port} (pid {process.pid})."


def stop_local_server() -> tuple[bool, str]:
    status = local_server_status()
    if not status.get("running"):
        return False, "Local server is not running."
    pid = int(status["pid"])
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        _clear_state()
        return False, "Local server process was already stopped."
    _clear_state()
    return True, "Local server stopped."
