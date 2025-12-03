"""
Test flow: POST API config to /api/config then open websocket and send api_config and a user message.

Usage: set environment variables or edit values below; run from repo root:
    .venv\Scripts\python.exe .\.scripts\ws_test_rest_and_ws.py

This script is safe — it won't print API keys.
"""
import os
import json
import asyncio
import websockets
import requests


def post_config(config, session_id=None):
    url = os.environ.get('API_ROOT', 'http://127.0.0.1:8010') + '/api/config'
    if session_id:
        url = f"{url}?session_id={session_id}"
    print('POST', url)
    resp = requests.post(url, json=config, timeout=10)
    print('status', resp.status_code, 'body', resp.text)
    return resp.json()


async def ws_flow(ws_uri, api_config):
    async with websockets.connect(ws_uri) as ws:
        # send api_config over websocket (mimic frontend)
        await ws.send(json.dumps({'type': 'api_config', 'payload': api_config}))
        print('sent api_config, waiting for result...')
        try:
            reply = await asyncio.wait_for(ws.recv(), timeout=10)
            print('ws reply:', reply)
        except asyncio.TimeoutError:
            print('no ws reply (timeout)')

        # send a user message to create session
        await ws.send(json.dumps({'type': 'user_response', 'payload': {'answer': '测试 from automated script'}}))
        print('sent user_response, waiting for a few messages (5s)')

        try:
            for _ in range(8):
                r = await asyncio.wait_for(ws.recv(), timeout=5)
                print('ws message:', r)
        except asyncio.TimeoutError:
            print('done receiving (timeout)')


if __name__ == '__main__':
    test_api_key = os.environ.get('OPENAI_API_KEY', 'sk-test')
    api_model = os.environ.get('OPENAI_MODEL', 'gpt-test')
    api_base = os.environ.get('OPENAI_BASE_URL', 'https://api.example.com/v1')

    config = {
        'api_type': 'openai',
        'api_key': test_api_key,
        'base_url': api_base,
        'model': api_model,
        'temperature': 0.7,
        'max_tokens': 1000,
        'nsfw_mode': False
    }

    # optional: persist to a specific session ID
    session_id = os.environ.get('TEST_SESSION_ID')

    post_result = post_config(config, session_id=session_id)
    print('post result:', post_result)

    asyncio.run(ws_flow(os.environ.get('EASYPROMPT_WEBSOCKET', 'ws://127.0.0.1:8010/ws/prompt'), config))
