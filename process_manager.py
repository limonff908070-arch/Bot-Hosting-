"""
process_manager.py
------------------
Tracks running sub-bot processes in a JSON file (active_processes.json)
so the master bot remembers which bots are alive after it restarts.

Schema of active_processes.json:
{
  "bot_<uid>_<ts>": {
    "pid":     12345,
    "folder":  "C:\\bots\\<uid>_<ts>",
    "user_id": "123456789"
  },
  ...
}
"""

import json
import os

import psutil

# Always store the JSON file next to this module (inside bot/)
_BASE = os.path.dirname(os.path.abspath(__file__))
PROCS_FILE = os.path.join(_BASE, "active_processes.json")


# ─── Internal I/O ─────────────────────────────────────────────────────────────

def _load() -> dict:
    if not os.path.exists(PROCS_FILE):
        return {}
    try:
        with open(PROCS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    """Atomic write: write to .tmp then rename so we never corrupt the file."""
    tmp = PROCS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PROCS_FILE)


# ─── Public helpers ────────────────────────────────────────────────────────────

def is_alive(pid: int) -> bool:
    """Return True if the process with the given PID is currently running."""
    try:
        p = psutil.Process(pid)
        return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return False


def register(bot_name: str, pid: int, folder: str, user_id: int | str) -> None:
    """Add or update a tracked bot process."""
    data = _load()
    data[bot_name] = {
        "pid":     pid,
        "folder":  folder,
        "user_id": str(user_id),
    }
    _save(data)


def unregister(bot_name: str) -> None:
    """Remove a bot from the tracking file."""
    data = _load()
    data.pop(bot_name, None)
    _save(data)


def update_pid(bot_name: str, new_pid: int) -> None:
    """Update only the PID for an existing entry (used after restart)."""
    data = _load()
    if bot_name in data:
        data[bot_name]["pid"] = new_pid
        _save(data)


def get_user_procs(user_id: int | str) -> list[dict]:
    """
    Return all tracked bots belonging to user_id.
    Each dict: {name, pid, folder, alive}
    """
    data = _load()
    result = []
    for name, entry in data.items():
        if str(entry.get("user_id")) == str(user_id):
            pid = entry.get("pid", -1)
            result.append({
                "name":   name,
                "pid":    pid,
                "folder": entry.get("folder", ""),
                "alive":  is_alive(pid),
            })
    return result


def get_all_procs() -> list[dict]:
    """
    Return all tracked bots (admin view).
    Each dict: {name, pid, folder, user_id, alive}
    """
    data = _load()
    result = []
    for name, entry in data.items():
        pid = entry.get("pid", -1)
        result.append({
            "name":    name,
            "pid":     pid,
            "folder":  entry.get("folder", ""),
            "user_id": entry.get("user_id", "?"),
            "alive":   is_alive(pid),
        })
    return result


def load_raw() -> dict:
    """Return the raw JSON dict — used by System Restart."""
    return _load()
