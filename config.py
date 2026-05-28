import os

from dotenv import load_dotenv

load_dotenv()

SOLANA_BIN = os.getenv("SOLANA_BIN", "solana")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

MAINNET_VOTE_PUBKEY = os.getenv("MAINNET_VOTE_PUBKEY", "")
TESTNET_VOTE_PUBKEY = os.getenv("TESTNET_VOTE_PUBKEY", "")

CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", 60 * 60))
RPC_ERROR_ALERT_ATTEMPTS = int(os.getenv("RPC_ERROR_ALERT_ATTEMPTS", 3))

ALERT_INTERVALS = {
    "critical": 10 * 60,
    "warning": 60 * 60,
    "daily": 24 * 60 * 60,
}

THRESHOLD_CRITICAL = 3 * 60 * 60
THRESHOLD_WARNING = 24 * 60 * 60

NETWORKS = {
    "mainnet-beta": {
        "rpc_flag": "-um",
        "pubkey_env": "MAINNET_VOTE_PUBKEY",
        "label": "mainnet",
    },
    "testnet": {
        "rpc_flag": "-ut",
        "pubkey_env": "TESTNET_VOTE_PUBKEY",
        "label": "testnet",
    },
}
