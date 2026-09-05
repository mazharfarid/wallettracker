import os
import json
import requests

WALLET_ADDRESS = "87rRdssFiTJKY4MGARa4G5vQ31hmR7MxSmhzeaJ5AAxJ"
RPC_URL = "https://api.mainnet-beta.solana.com"
CACHE_FILE = "wallet_cache.json"

# DEX & Jupiter Swap Program IDs
DEX_PROGRAM_IDS = {
    'JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4',  # Jupiter v6
    'JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB',  # Jupiter v4
    'JUP3c2Uh3WA4Ng34tw6Tpd2GgCfkEJkzypBEwjZaAJa',  # Jupiter v3
    'jitoo358D76r9d68F9qC1jZc1z6T6C2W2C5Z',         # Jupiter Limit Order
    'DCA265ViqfvCvZwxmFywsUZYzOSCKmZFueLh4qvhE6L',  # Jupiter DCA
    '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8',  # Raydium AMM
    'CAMMCazo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWq',  # Raydium CLMM
    'whirLMiicVdio4qvUfM5KAgZ5CDEG5WK84mTX62f64w',  # Orca Whirlpool
    '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P',  # Pump.fun
    'routeUGWgWzqBWFcrCfv8tritsqukccEfrYhhNijD2b',  # Raydium Router
    'LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo',  # Meteora DLMM
    '24Uqj9JCLxUeoC3hGfh5W3s9FM9uCHDS2SG3LYwBpyTX'   # Meteora Pools
}

def is_spot_activity(tx):
    """Determines whether a Solana transaction represents a Spot DEX trade/swap."""
    if not tx or "meta" not in tx:
        return False
    
    meta = tx.get("meta", {})
    if meta.get("err") is not None:
        return False

    logs = meta.get("logMessages", []) or []
    logs_str = " ".join(logs)
    
    # 1. Program ID or Log string check for DEX / Jupiter Swaps
    for prog in DEX_PROGRAM_IDS:
        if prog in logs_str:
            return True
            
    if any(keyword in logs_str for keyword in ["Instruction: Swap", "Instruction: ExecuteSwap", "Instruction: Route", "Instruction: Buy", "Instruction: Sell"]):
        return True

    # 2. Multi-token balance change check (Swap signature: asset exchange)
    pre_balances = meta.get("preTokenBalances", []) or []
    post_balances = meta.get("postTokenBalances", []) or []
    
    wallet_pre = [b for b in pre_balances if b.get("owner") == WALLET_ADDRESS]
    wallet_post = [b for b in post_balances if b.get("owner") == WALLET_ADDRESS]
    
    if wallet_pre or wallet_post:
        pre_mints = {b.get("mint"): float(b.get("uiTokenAmount", {}).get("uiAmount") or 0) for b in wallet_pre}
        post_mints = {b.get("mint"): float(b.get("uiTokenAmount", {}).get("uiAmount") or 0) for b in wallet_post}
        
        all_mints = set(pre_mints.keys()).union(set(post_mints.keys()))
        increased = any(post_mints.get(m, 0) - pre_mints.get(m, 0) > 0 for m in all_mints)
        decreased = any(post_mints.get(m, 0) - pre_mints.get(m, 0) < 0 for m in all_mints)
        
        if increased and decreased:
            return True

    return False

def get_latest_spot_activity():
    """Fetches recent wallet signatures and returns the newest Spot DEX Activity signature."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [WALLET_ADDRESS, {"limit": 25}]
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(RPC_URL, json=payload, headers=headers, timeout=10)
        data = response.json()
    except Exception as e:
        print(f"Error fetching signatures from RPC: {e}")
        return None
        
    if "result" not in data or len(data["result"]) == 0:
        return None

    signatures_info = data["result"]
    chunk_size = 5
    
    # Process signatures in small RPC batch requests
    for i in range(0, len(signatures_info), chunk_size):
        chunk = signatures_info[i:i+chunk_size]
        batch_payload = [
            {
                "jsonrpc": "2.0",
                "id": idx,
                "method": "getTransaction",
                "params": [s["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
            }
            for idx, s in enumerate(chunk)
        ]
        try:
            batch_res = requests.post(RPC_URL, json=batch_payload, headers=headers, timeout=15).json()
            if isinstance(batch_res, list):
                for item in batch_res:
                    idx = item.get("id", 0)
                    tx = item.get("result")
                    if is_spot_activity(tx):
                        sig_info = chunk[idx]
                        return {
                            "signature": sig_info.get("signature"),
                            "slot": sig_info.get("slot"),
                            "err": sig_info.get("err")
                        }
        except Exception as e:
            print(f"Error processing transaction batch: {e}")
            continue

    return None

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(state):
    with open(CACHE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def main():
    if os.path.exists("changed.flag"):
        os.remove("changed.flag")
        
    current_spot_state = get_latest_spot_activity()
    
    cached_state = load_cache()
    last_spot_signature = cached_state.get("spot_signature") or cached_state.get("signature")

    if not current_spot_state:
        print("No spot activity found in recent transactions.")
        if last_spot_signature:
            print(f"Last recorded spot signature: {last_spot_signature}")
        return

    print(f"Current Latest Spot Signature: {current_spot_state['signature']}")
    print(f"Cached Spot Signature: {last_spot_signature}")

    if last_spot_signature is None:
        cache_data = {
            "spot_signature": current_spot_state["signature"],
            "slot": current_spot_state["slot"]
        }
        save_cache(cache_data)
        print("Initialized cache with current spot signature. No alert sent.")
    elif current_spot_state["signature"] != last_spot_signature:
        print("SPOT ACTIVITY CHANGE DETECTED! New Jupiter Spot activity found.")
        with open("changed.flag", "w") as f:
            f.write(
                f"New Spot Activity detected on Jupiter Portfolio!\n\n"
                f"Signature: {current_spot_state['signature']}\n\n"
                f"View on Solscan: https://solscan.io/tx/{current_spot_state['signature']}\n"
                f"View on Jupiter Spot Portfolio: https://jup.ag/portfolio/{WALLET_ADDRESS}/spot"
            )
        save_cache({
            "spot_signature": current_spot_state["signature"],
            "slot": current_spot_state["slot"]
        })
    else:
        print("No new spot activity detected.")

if __name__ == "__main__":
    main()
