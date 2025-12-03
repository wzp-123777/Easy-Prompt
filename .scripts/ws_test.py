import asyncio
import json
import websockets


async def test_connect():
    uri = "ws://127.0.0.1:8010/ws/prompt"
    print(f"Connecting to {uri} ...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected — sending test api_config with empty fields")
            msg = {
                "type": "api_config",
                "payload": {
                    "api_type": "openai",
                    "api_key": "",
                    "base_url": "",
                    "model": "",
                    "temperature": 0.7,
                    "max_tokens": 4000,
                    "nsfw_mode": False
                }
            }
            await websocket.send(json.dumps(msg))

            # Wait for a response (server should answer with api_config_result)
            try:
                reply = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                print("Received reply:")
                print(reply)
            except asyncio.TimeoutError:
                print("No reply received within timeout — server may be waiting for valid config")

    except Exception as e:
        print("WebSocket test failed:", e)


if __name__ == "__main__":
    asyncio.run(test_connect())
