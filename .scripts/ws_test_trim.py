import asyncio
import json
import websockets


async def test_trim_config():
    uri = "ws://127.0.0.1:8010/ws/prompt"
    print(f"Connecting to {uri} ...")
    async with websockets.connect(uri) as ws:
        payload = {
            "type": "api_config",
            "payload": {
                "api_type": "openai",
                "api_key": "  sk-test-key  ",
                "base_url": "  https://api.deepseek.com/v1  ",
                "model": "  deepseek-chat  "
            }
        }
        await ws.send(json.dumps(payload))
        reply = await ws.recv()
        print('reply:', reply)

if __name__ == '__main__':
    asyncio.run(test_trim_config())
