import os
import json
import requests

WALLET_ADDRESS = "87rRdssFiTJKY4MGARa4G5vQ31hmR7MxSmhzeaJ5AAxJ"
RPC_URL = "https://api.mainnet-beta.solana.com"
CACHE_FILE = "wallet_cache.json"

def get_latest_wallet_state():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [WALLET_ADDRESS, {"limit": 1}]
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(RPC_URL, json=payload, headers=headers)
    data = response.json()
    
    if "result" in data and len(data["result"]) > 0:
        latest_tx = data["result"][0]
        return {
            "signature": latest_tx.get("signature"),
            "slot": latest_tx.get("slot"),
            "err": latest_tx.get("err")
        }
    return None

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(state):
    with open(CACHE_FILE, "w") as f:
        json.dump(state, f)

def main():
    current_state = get_latest_wallet_state()
    if not current_state:
        print("Failed to fetch wallet state from RPC.")
        return

    cached_state = load_cache()
    last_signature = cached_state.get("signature")

    print(f"Current Latest Signature: {current_state['signature']}")
    print(f"Cached Signature: {last_signature}")

    if last_signature is None:
        save_cache(current_state)
        print("Initialized cache with current signature. No alert sent.")
    elif current_state["signature"] != last_signature:
        print("CHANGE DETECTED! New spot activity found.")
        with open("changed.flag", "w") as f:
            f.write(f"New activity detected on your Jupiter wallet!\n\nSignature: {current_state['signature']}\n\nView on Solscan: https://solscan.io/tx/{current_state['signature']}\nView on Jupiter Portfolio: https://jup.ag/portfolio/{WALLET_ADDRESS}")
        save_cache(current_state)
    else:
        print("No changes detected.")

if __name__ == "__main__":
    main()
