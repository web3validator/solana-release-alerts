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
        print(f"[notifier] Failed to send message: {e}")
        return False


def _status_button() -> dict:
    return {"inline_keyboard": [[{"text": "📊 Status", "callback_data": "status"}]]}


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

    return _send(text, _status_button())


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

    return _send(text, _status_button())


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

    return _send(text, _status_button())


def answer_callback(callback_query_id: str) -> None:
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
        requests.post(url, json={"callback_query_id": callback_query_id}, timeout=5)
    except Exception:
        pass
