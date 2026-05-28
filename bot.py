import os
import sys
import threading
import time

from dotenv import load_dotenv, set_key

ENV_FILE = os.path.join(os.path.dirname(__file__), ".env")


def setup_wizard():
    load_dotenv(ENV_FILE)

    interactive = sys.stdin.isatty()

    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not token:
        if not interactive:
            print("❌ TELEGRAM_TOKEN not set in .env")
            sys.exit(1)
        token = input("Telegram Bot Token: ").strip()
        set_key(ENV_FILE, "TELEGRAM_TOKEN", token)

    mainnet_pubkey = os.getenv("MAINNET_VOTE_PUBKEY", "").strip()
    if not mainnet_pubkey:
        if not interactive:
            print("❌ MAINNET_VOTE_PUBKEY not set in .env")
            sys.exit(1)
        mainnet_pubkey = input("Mainnet Vote Pubkey: ").strip()
        set_key(ENV_FILE, "MAINNET_VOTE_PUBKEY", mainnet_pubkey)

    testnet_pubkey = os.getenv("TESTNET_VOTE_PUBKEY", "").strip()
    if not testnet_pubkey:
        if not interactive:
            print("⚠️  TESTNET_VOTE_PUBKEY not set — testnet checks disabled")
        elif interactive:
            val = input("Testnet Vote Pubkey (Enter to skip): ").strip()
            if val:
                testnet_pubkey = val
                set_key(ENV_FILE, "TESTNET_VOTE_PUBKEY", testnet_pubkey)

    load_dotenv(ENV_FILE, override=True)
    print(
        f"✅ Config OK — mainnet: {mainnet_pubkey[:20]}... testnet: {testnet_pubkey[:20] + '...' if testnet_pubkey else 'disabled'}"
    )


def get_networks():
    from config import MAINNET_VOTE_PUBKEY, NETWORKS, TESTNET_VOTE_PUBKEY

    active = []
    for cluster, cfg in NETWORKS.items():
        pubkey = (
            MAINNET_VOTE_PUBKEY if cluster == "mainnet-beta" else TESTNET_VOTE_PUBKEY
        )
        if pubkey:
            active.append(
                {
                    "cluster": cluster,
                    "rpc_flag": cfg["rpc_flag"],
                    "label": cfg["label"],
                    "pubkey": pubkey,
                }
            )
    return active


def polling_loop(networks: list):
    import requests

    from checker import run_check
    from config import TELEGRAM_CHAT_ID, TELEGRAM_TOKEN
    from notifier import answer_callback, send_status

    offset = None
    url_updates = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"

    print("[polling] Started")

    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message", "callback_query"]}
            if offset is not None:
                params["offset"] = offset

            resp = requests.get(url_updates, params=params, timeout=40)
            resp.raise_for_status()
            updates = resp.json().get("result", [])

            for update in updates:
                offset = update["update_id"] + 1

                message = update.get("message")
                if message:
                    chat_id = str(message.get("chat", {}).get("id", ""))
                    text = message.get("text", "").strip().lower()
                    if chat_id == str(TELEGRAM_CHAT_ID) and text in (
                        "/status",
                        "/start",
                    ):
                        for net in networks:
                            result = run_check(
                                net["cluster"], net["rpc_flag"], net["pubkey"]
                            )
                            send_status(result, net["pubkey"])

                callback = update.get("callback_query")
                if callback:
                    chat_id = str(
                        callback.get("message", {}).get("chat", {}).get("id", "")
                    )
                    data = callback.get("data", "")
                    cb_id = callback.get("id")
                    if chat_id == str(TELEGRAM_CHAT_ID) and data == "status":
                        answer_callback(cb_id)
                        for net in networks:
                            result = run_check(
                                net["cluster"], net["rpc_flag"], net["pubkey"]
                            )
                            send_status(result, net["pubkey"])

        except Exception as e:
            print(f"[polling] Error: {e}")
            time.sleep(5)


def main_loop():
    from checker import run_check
    from config import CHECK_INTERVAL_SECONDS, RPC_ERROR_ALERT_ATTEMPTS
    from notifier import send_alert, send_ok
    from state import (
        get_last_ok_sent,
        record_alert,
        record_ok,
        record_rpc_error,
        reset_rpc_errors,
        should_alert,
    )

    networks = get_networks()
    if not networks:
        print("❌ No validators configured.")
        sys.exit(1)

    t = threading.Thread(target=polling_loop, args=(networks,), daemon=True)
    t.start()

    LOOP_INTERVAL = CHECK_INTERVAL_SECONDS

    print(
        f"[bot] Starting. Networks: {[n['label'] for n in networks]} Loop interval: {LOOP_INTERVAL}s"
    )

    while True:
        for net in networks:
            try:
                print(f"[bot:{net['label']}] Running check...")
                result = run_check(net["cluster"], net["rpc_flag"], net["pubkey"])

                remaining = result.get("remaining_seconds", 0)
                ok = result.get("ok", False)
                pubkey = net["pubkey"]

                print(
                    f"[bot:{net['label']}] epoch={result.get('epoch')} remaining={remaining}s "
                    f"ok={ok} cur={result.get('current_version')} req={result.get('required_version')}"
                )

                if ok:
                    reset_rpc_errors(pubkey)
                    if not get_last_ok_sent(pubkey):
                        send_ok(result, pubkey)
                        record_ok(pubkey)
                else:
                    error = result.get("error")
                    if is_retryable_rpc_error(error):
                        failures = record_rpc_error(pubkey, error)
                        result["consecutive_failures"] = failures
                        if failures < RPC_ERROR_ALERT_ATTEMPTS:
                            print(
                                f"[bot:{net['label']}] Suppressing transient RPC error "
                                f"{failures}/{RPC_ERROR_ALERT_ATTEMPTS}: {error}"
                            )
                            continue
                    else:
                        reset_rpc_errors(pubkey)

                    if should_alert(pubkey, remaining):
                        sent = send_alert(result, pubkey)
                        if sent:
                            record_alert(pubkey)

            except Exception as e:
                print(f"[bot:{net['label']}] Unexpected error: {e}")

        time.sleep(LOOP_INTERVAL)


def is_retryable_rpc_error(error: str | None) -> bool:
    if not error:
        return False
    retryable_markers = (
        "epoch-info failed",
        "Could not fetch validator version",
        "validators error",
        "timed out",
    )
    return any(marker in error for marker in retryable_markers)


if __name__ == "__main__":
    setup_wizard()
    main_loop()
