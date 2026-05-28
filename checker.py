import json
import os
import subprocess

import requests
from packaging.version import Version

SOLANA_BIN = os.getenv("SOLANA_BIN", "solana")
DELEGATION_API = "https://api.solana.org/api/community/v1/sfdp_required_versions"


def get_epoch_info(rpc_flag: str) -> dict:
    result = subprocess.run(
        [SOLANA_BIN, "epoch-info", rpc_flag, "--output", "json"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    data = json.loads(result.stdout)
    slot_index = data["slotIndex"]
    slots_in_epoch = data["slotsInEpoch"]
    slot_time = 0.4
    elapsed = slot_index * slot_time
    total = slots_in_epoch * slot_time
    remaining = total - elapsed
    return {
        "epoch": data["epoch"],
        "remaining_seconds": int(remaining),
        "total_seconds": int(total),
    }


def get_required_versions(cluster: str, epoch: int) -> dict | None:
    try:
        resp = requests.get(DELEGATION_API, params={"cluster": cluster}, timeout=15)
        resp.raise_for_status()
        entries = resp.json().get("data", [])
        next_epoch = epoch + 1
        for target in (next_epoch, epoch):
            for entry in entries:
                if entry["epoch"] == target:
                    return entry
    except Exception as e:
        print(f"[checker:{cluster}] delegation API error: {e}")
    return None


def get_validator_version(rpc_flag: str, vote_pubkey: str) -> str | None:
    try:
        result = subprocess.run(
            [SOLANA_BIN, "validators", rpc_flag, "--output", "json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        data = json.loads(result.stdout)
        for v in data.get("validators", []):
            if v.get("voteAccountPubkey") == vote_pubkey:
                return v.get("version")
    except Exception as e:
        print(f"[checker] validators error: {e}")
    return None


def detect_client_type(version: str) -> str:
    parts = version.split(".")
    if parts[0] == "0" and len(parts) >= 2 and len(parts[1]) >= 3:
        return "firedancer"
    return "agave"


def is_version_ok(current: str, required_entry: dict) -> tuple[bool, str, str]:
    client = detect_client_type(current)
    if client == "firedancer":
        min_ver = required_entry.get("firedancer_min_version")
        max_ver = required_entry.get("firedancer_max_version")
    else:
        min_ver = required_entry.get("agave_min_version")
        max_ver = required_entry.get("agave_max_version")

    required_str = min_ver or "unknown"

    if not min_ver:
        return True, current, required_str

    try:
        cur = Version(current)
        if cur < Version(min_ver):
            return False, current, required_str
        if max_ver and cur > Version(max_ver):
            return False, current, f"<= {max_ver}"
    except Exception:
        return False, current, required_str

    return True, current, required_str


def run_check(cluster: str, rpc_flag: str, vote_pubkey: str) -> dict:
    base = {"cluster": cluster, "vote_pubkey": vote_pubkey}

    try:
        epoch_info = get_epoch_info(rpc_flag)
    except Exception as e:
        return {
            **base,
            "ok": False,
            "error": f"epoch-info failed: {e}",
            "epoch": None,
            "remaining_seconds": 0,
            "current_version": None,
            "required_version": None,
            "required_epoch": None,
        }

    epoch = epoch_info["epoch"]
    remaining = epoch_info["remaining_seconds"]

    current_version = get_validator_version(rpc_flag, vote_pubkey)
    if not current_version:
        return {
            **base,
            "ok": False,
            "error": "Could not fetch validator version",
            "epoch": epoch,
            "remaining_seconds": remaining,
            "current_version": None,
            "required_version": None,
            "required_epoch": None,
        }

    required = get_required_versions(cluster, epoch)
    if not required:
        return {
            **base,
            "ok": False,
            "error": "Could not fetch required versions from API",
            "epoch": epoch,
            "remaining_seconds": remaining,
            "current_version": current_version,
            "required_version": None,
            "required_epoch": None,
        }

    ok, cur_ver, req_ver = is_version_ok(current_version, required)

    return {
        **base,
        "ok": ok,
        "error": None,
        "epoch": epoch,
        "required_epoch": required["epoch"],
        "remaining_seconds": remaining,
        "current_version": cur_ver,
        "required_version": req_ver,
    }
