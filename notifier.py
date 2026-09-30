import time

import requests

from config import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN


def _fmt_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"


def _send(text: str, reply_markup: dict = None) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[notifier] TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[notifier] Failed to send message: {_redact(e)}")
        return False


def _redact(error: Exception) -> str:
    # requests puts the full URL (with the bot token) into HTTP errors.
    return str(error).replace(TELEGRAM_TOKEN, "<token>") if TELEGRAM_TOKEN else str(error)


def _keyboard(result: dict, vote_pubkey: str) -> dict:
    from mute import keyboard
    from state import get_mute_until

    return keyboard(_label(result), get_mute_until(vote_pubkey))


def edit_keyboard(chat_id: str, message_id: int, reply_markup: dict) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageReplyMarkup"
    payload = {"chat_id": chat_id, "message_id": message_id, "reply_markup": reply_markup}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        # 400 "message is not modified" is harmless (double tap on the same button).
        return resp.ok or "not modified" in resp.text
    except Exception as e:
        print(f"[notifier] Failed to edit keyboard: {_redact(e)}")
        return False


def _label(result: dict) -> str:
    cluster = result.get("cluster", "mainnet-beta")
    return "mainnet" if cluster == "mainnet-beta" else "testnet"


def send_alert(result: dict, vote_pubkey: str) -> bool:
    remaining = result.get("remaining_seconds", 0)
    epoch = result.get("epoch", "?")
    req_epoch = result.get("required_epoch", "?")
    cur_ver = result.get("current_version", "unknown")
    req_ver = result.get("required_version", "unknown")
    error = result.get("error")
    time_left = _fmt_time(remaining)
    net = _label(result)

    if error:
        failures = result.get("consecutive_failures")
        failures_line = (
            f"\n<b>Consecutive failures:</b> {failures}"
            if failures
            else ""
        )
        text = (
            f"🔴 <b>[{net}] Validator check error</b>\n"
            f"<code>{vote_pubkey}</code>\n\n"
            f"<b>Error:</b> {error}\n"
            f"<b>Epoch:</b> {epoch} | Time left: {time_left}"
            f"{failures_line}"
        )
    else:
        text = (
            f"⚠️ <b>[{net}] Version not updated!</b>\n\n"
            f"<b>Validator:</b> <code>{vote_pubkey}</code>\n"
            f"<b>Current version:</b> <code>{cur_ver}</code>\n"
            f"<b>Required by epoch {req_epoch}:</b> <code>{req_ver}</code>\n\n"
            f"<b>Current epoch:</b> {epoch}\n"
            f"<b>Time left in epoch:</b> {time_left}"
        )

    return _send(text, _keyboard(result, vote_pubkey))


def send_ok(result: dict, vote_pubkey: str) -> bool:
    cur_ver = result.get("current_version", "unknown")
    epoch = result.get("epoch", "?")
    req_epoch = result.get("required_epoch", "?")
    req_ver = result.get("required_version", "unknown")
    net = _label(result)

    text = (
        f"✅ <b>[{net}] Version is up to date</b>\n\n"
        f"<b>Validator:</b> <code>{vote_pubkey}</code>\n"
        f"<b>Current version:</b> <code>{cur_ver}</code>\n"
        f"<b>Required by epoch {req_epoch}:</b> <code>{req_ver}</code>\n"
        f"<b>Epoch:</b> {epoch}"
    )

    return _send(text, _keyboard(result, vote_pubkey))


def send_status(result: dict, vote_pubkey: str) -> bool:
    remaining = result.get("remaining_seconds", 0)
    epoch = result.get("epoch", "?")
    req_epoch = result.get("required_epoch", "?")
    cur_ver = result.get("current_version", "unknown")
    req_ver = result.get("required_version", "unknown")
    ok = result.get("ok", False)
    error = result.get("error")
    time_left = _fmt_time(remaining)
    net = _label(result)

    status_icon = "✅" if ok else "⚠️"
    status_text = "OK" if ok else "NEEDS UPDATE"

    if error:
        text = (
            f"🔴 <b>[{net}] Status: ERROR</b>\n\n"
            f"<b>Validator:</b> <code>{vote_pubkey}</code>\n"
            f"<b>Error:</b> {error}\n\n"
            f"<b>Epoch:</b> {epoch} | Time left: {time_left}"
        )
    else:
        text = (
            f"{status_icon} <b>[{net}] Status: {status_text}</b>\n\n"
            f"<b>Validator:</b> <code>{vote_pubkey}</code>\n"
            f"<b>Current version:</b> <code>{cur_ver}</code>\n"
            f"<b>Required by epoch {req_epoch}:</b> <code>{req_ver}</code>\n\n"
            f"<b>Current epoch:</b> {epoch}\n"
            f"<b>Time left in epoch:</b> {time_left}"
        )

    from mute import fmt_until
    from state import get_mute_until

    mute_until = get_mute_until(vote_pubkey)
    if mute_until > time.time():
        text += f"\n\n🔕 <b>Alerts muted until</b> {fmt_until(mute_until)}"

    return _send(text, _keyboard(result, vote_pubkey))


def answer_callback(callback_query_id: str, text: str = "") -> None:
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        requests.post(url, json=payload, timeout=5)
    except Exception:
        pass
