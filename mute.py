"""Per-network alert muting: inline keyboards and Telegram callback data.

Callback data (Telegram limit: 64 bytes):
  mm:<label>          open the duration menu
  m:<label>:<secs>    mute for one of MUTE_OPTIONS
  um:<label>          unmute
  mb:<label>          back to the normal keyboard
"""

import time
from datetime import datetime, timezone

MUTE_OPTIONS = (
    (60 * 60, "1h"),
    (6 * 60 * 60, "6h"),
    (12 * 60 * 60, "12h"),
    (24 * 60 * 60, "1d"),
    (3 * 24 * 60 * 60, "3d"),
    (7 * 24 * 60 * 60, "7d"),
)
_ALLOWED_SECONDS = {seconds for seconds, _ in MUTE_OPTIONS}
_STATUS_BUTTON = {"text": "📊 Status", "callback_data": "status"}


def fmt_until(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d %b %H:%M UTC")


def keyboard(label: str, mute_until: float = 0.0, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    if mute_until > now:
        short = datetime.fromtimestamp(mute_until, tz=timezone.utc).strftime("%d %b %H:%M")
        unmute = {"text": f"🔔 Unmute (muted till {short} UTC)", "callback_data": f"um:{label}"}
        return {"inline_keyboard": [[_STATUS_BUTTON], [unmute]]}
    mute = {"text": "🔕 Mute", "callback_data": f"mm:{label}"}
    return {"inline_keyboard": [[_STATUS_BUTTON, mute]]}


def mute_menu(label: str) -> dict:
    buttons = [
        {"text": f"🔕 {name}", "callback_data": f"m:{label}:{seconds}"}
        for seconds, name in MUTE_OPTIONS
    ]
    return {
        "inline_keyboard": [
            buttons[:3],
            buttons[3:],
            [{"text": "⬅️ Back", "callback_data": f"mb:{label}"}],
        ]
    }


def parse(data: str, labels) -> tuple[str, str, int] | None:
    """Return (action, label, seconds) for a valid mute callback, otherwise None."""
    parts = (data or "").split(":")
    if len(parts) == 2 and parts[0] in ("mm", "um", "mb") and parts[1] in labels:
        return parts[0], parts[1], 0
    if (
        len(parts) == 3
        and parts[0] == "m"
        and parts[1] in labels
        and parts[2].isdigit()
        and int(parts[2]) in _ALLOWED_SECONDS
    ):
        return "m", parts[1], int(parts[2])
    return None
