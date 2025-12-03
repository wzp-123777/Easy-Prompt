"""
Automated WebSocket test using a real OpenAI-compatible API key.

Usage (PowerShell):

# 1) Export the values into environment variables (do not commit them)
$Env:OPENAI_API_KEY = 'sk-...'
$Env:OPENAI_BASE_URL = 'https://api.openai.com/v1'
$Env:OPENAI_MODEL = 'gpt-3.5-turbo'

# 2) Run the script
& .venv\Scripts\python.exe .\.scripts\ws_test_openai_real.py

The script reads values from environment variables and sends an `api_config` message
to ws://127.0.0.1:8010/ws/prompt. It then waits for a response and prints it.

Note: This script will NOT print your key. It only shows connection/result status.
"""
import os
import asyncio
import json
import websockets


async def run_test():
    ws_uri = os.environ.get('EASYPROMPT_WEBSOCKET', 'ws://127.0.0.1:8010/ws/prompt')

    api_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('EASYPROMPT_OPENAI_KEY')
    base_url = os.environ.get('OPENAI_BASE_URL') or os.environ.get('EASYPROMPT_OPENAI_BASE_URL')
    model = os.environ.get('OPENAI_MODEL') or os.environ.get('EASYPROMPT_OPENAI_MODEL')

    if not api_key or not base_url or not model:
        print('Missing required environment variables. Set OPENAI_API_KEY, OPENAI_BASE_URL and OPENAI_MODEL.')
        return

    # Do not echo the key
    print('Using websocket:', ws_uri)
    print('Using base_url and model (masked):', base_url[:20] + '...' if len(base_url) > 20 else base_url, model)

    async with websockets.connect(ws_uri) as ws:
        msg = {
            'type': 'api_config',
            'payload': {
                'api_type': 'openai',
                'api_key': api_key,
                'base_url': base_url,
                'model': model,
                'temperature': 0.7,
                'max_tokens': 4000,
                'nsfw_mode': False
            }
        }

        await ws.send(json.dumps(msg))
        print('Sent api_config, waiting for api_config_result...')

        try:
            reply = await asyncio.wait_for(ws.recv(), timeout=15)
            print('Reply from server:')
            print(reply)
        except asyncio.TimeoutError:
            print('No reply received (timeout). Check backend logs and network connectivity.')


if __name__ == '__main__':
    asyncio.run(run_test())
