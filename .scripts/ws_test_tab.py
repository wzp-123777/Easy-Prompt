import asyncio
import json
import websockets


async def test_tab_config():
    uri = "ws://127.0.0.1:8010/ws/prompt"
    async with websockets.connect(uri) as ws:
        payload = {
            "type": "api_config",
            "payload": {
                "api_type": "openai",
                "api_key": "\tabc",
                "base_url": "\thttps://api.openai.com/v1",
                "model": " gpt-3.5-turbo "
            }
        }
        await ws.send(json.dumps(payload))
        reply = await ws.recv()
        print('reply:', reply)

if __name__ == '__main__':
    asyncio.run(test_tab_config())
