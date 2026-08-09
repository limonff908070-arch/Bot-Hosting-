import json
import os
from datetime import datetime

# users.json lives alongside this script so the path is stable regardless
# of which working directory the process is launched from.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")


def load_users() -> dict:
    """Return the full user dict from disk; empty dict on any error."""
    if not os.path.exists(DB_PATH):
        return {}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_users(users: dict) -> None:
    """Atomically persist the user dict to disk."""
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def register_user(user_id: int, username: str) -> None:
    """Insert a new user or refresh their username. Never overwrites is_blocked."""
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "user_id": user_id,
            "username": username or "",
            "is_blocked": False,
            "registered_at": datetime.utcnow().isoformat(),
        }
        save_users(users)
    elif users[uid].get("username") != (username or ""):
        users[uid]["username"] = username or ""
        save_users(users)


def is_blocked(user_id: int) -> bool:
    users = load_users()
    return users.get(str(user_id), {}).get("is_blocked", False)


def get_user(user_id: int) -> dict | None:
    return load_users().get(str(user_id))


def get_all_users() -> dict:
    return load_users()


def block_user(user_id: int) -> bool:
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        return False
    users[uid]["is_blocked"] = True
    save_users(users)
    return True


def unblock_user(user_id: int) -> bool:
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        return False
    users[uid]["is_blocked"] = False
    save_users(users)
    return True
