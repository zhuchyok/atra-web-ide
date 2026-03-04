import asyncio
import httpx
import time
import json

async def send_request(client, name, model, prompt, max_tokens, is_vip=False):
    url = "http://localhost:11435/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "stream": False
    }

    headers = {}
    if is_vip:
        headers["X-Request-Priority"] = "high"

    print(f"[{name}] Starting request (model={model}, priority={'high' if is_vip else 'normal'})...")
    start_time = time.time()

    try:
        response = await client.post(url, json=payload, headers=headers, timeout=120.0)
        end_time = time.time()
        duration = end_time - start_time

        if response.status_code == 200:
            print(f"[{name}] Finished in {duration:.2f}s")
            return {
                "name": name,
                "start": start_time,
                "end": end_time,
                "duration": duration,
                "success": True
            }
        else:
            print(f"[{name}] Failed with status {response.status_code}: {response.text}")
            return {"name": name, "success": False}

    except Exception as e:
        print(f"[{name}] Error: {str(e)}")
        return {"name": name, "success": False}

async def main():
    async with httpx.AsyncClient() as client:
        # Request A: Heavy (Victoria Wisdom 30B) - VIP
        # Request B: Light (Phi-3.5 3.8B) - Normal

        task_a = send_request(client, "Heavy (A)", "victoria-wisdom-v3.5", "Write a long poem about AI", 500, is_vip=True)
        # Small delay to ensure A starts first
        await asyncio.sleep(0.5)
        task_b = send_request(client, "Light (B)", "phi3.5:3.8b", "What is 2+2?", 10, is_vip=False)

        results = await asyncio.gather(task_a, task_b)

        res_a = results[0]
        res_b = results[1]

        print("\n--- Results Analysis ---")
        if not res_a["success"] or not res_b["success"]:
            print("One or more requests failed. Check MLX API server status.")
            return

        print(f"Heavy (A) duration: {res_a['duration']:.2f}s")
        print(f"Light (B) duration: {res_b['duration']:.2f}s")

        if res_b["end"] < res_a["end"]:
            print("\nSUCCESS: Dual-Channel Brain is working!")
            print(f"Light request (B) finished {res_a['end'] - res_b['end']:.2f}s BEFORE Heavy request (A).")
        else:
            print("\nFAILURE: Requests were likely executed sequentially.")
            print(f"Light request (B) finished {res_b['end'] - res_a['end']:.2f}s AFTER Heavy request (A).")

if __name__ == "__main__":
    asyncio.run(main())
