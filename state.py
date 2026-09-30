import json
import os
import threading
import time
from pathlib import Path

STATE_FILE = Path(__file__).parent / "state.json"
# The Telegram polling thread (mute buttons) and the check loop both write state.
_LOCK = threading.RLock()


def _load() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save(state: dict):
    tmp = STATE_FILE.with_name(STATE_FILE.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, STATE_FILE)


def get_last_alert_time(pubkey: str) -> float:
    state = _load()
    return state.get(pubkey, {}).get("last_alert", 0.0)


def get_last_ok_sent(pubkey: str) -> bool:
    state = _load()
    return state.get(pubkey, {}).get("last_ok_sent", False)


def record_alert(pubkey: str):
    with _LOCK:
        state = _load()
        if pubkey not in state:
            state[pubkey] = {}
        state[pubkey]["last_alert"] = time.time()
        state[pubkey]["last_ok_sent"] = False
        _save(state)


def record_ok(pubkey: str):
    with _LOCK:
        state = _load()
        if pubkey not in state:
            state[pubkey] = {}
        state[pubkey]["last_ok_sent"] = True
        state[pubkey]["last_alert"] = 0.0
        state[pubkey]["consecutive_rpc_errors"] = 0
        state[pubkey].pop("last_rpc_error", None)
        _save(state)


def record_rpc_error(pubkey: str, error: str) -> int:
    with _LOCK:
        state = _load()
        if pubkey not in state:
            state[pubkey] = {}
        current = int(state[pubkey].get("consecutive_rpc_errors", 0)) + 1
        state[pubkey]["consecutive_rpc_errors"] = current
        state[pubkey]["last_rpc_error"] = error
        _save(state)
        return current


def reset_rpc_errors(pubkey: str):
    with _LOCK:
        state = _load()
        if pubkey not in state:
            return
        state[pubkey]["consecutive_rpc_errors"] = 0
        state[pubkey].pop("last_rpc_error", None)
        _save(state)


def get_mute_until(pubkey: str) -> float:
    return float(_load().get(pubkey, {}).get("mute_until", 0.0) or 0.0)


def is_muted(pubkey: str, now: float | None = None) -> bool:
    return get_mute_until(pubkey) > (time.time() if now is None else now)


def set_mute(pubkey: str, seconds: int, now: float | None = None) -> float:
    until = (time.time() if now is None else now) + seconds
    with _LOCK:
        state = _load()
        state.setdefault(pubkey, {})["mute_until"] = until
        _save(state)
    return until


def clear_mute(pubkey: str):
    with _LOCK:
        state = _load()
        if state.get(pubkey, {}).pop("mute_until", None) is not None:
            _save(state)


def should_alert(pubkey: str, remaining_seconds: int) -> bool:
    from config import ALERT_INTERVALS, THRESHOLD_CRITICAL, THRESHOLD_WARNING

    last = get_last_alert_time(pubkey)
    elapsed = time.time() - last

    if remaining_seconds < THRESHOLD_CRITICAL:
        return elapsed >= ALERT_INTERVALS["critical"]
    elif remaining_seconds < THRESHOLD_WARNING:
        return elapsed >= ALERT_INTERVALS["warning"]
    else:
        return elapsed >= ALERT_INTERVALS["daily"]
