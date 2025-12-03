"""
Test flow: POST API config to /api/config then open websocket and send a user message WITHOUT sending api_config.

Usage: set environment variables or edit values below; run from repo root:
    .venv\Scripts\python.exe .\.scripts\ws_test_post_only.py

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


async def ws_flow(ws_uri):
    async with websockets.connect(ws_uri) as ws:
        # directly send a user message to create session (without sending api_config)
        await ws.send(json.dumps({'type': 'user_response', 'payload': {'answer': '这是来自 POST-only 测试的消息'}}))
        print('sent user_response, waiting for a few messages (10s)')

        try:
            for _ in range(12):
                r = await asyncio.wait_for(ws.recv(), timeout=5)
                print('ws message:', r)
        except asyncio.TimeoutError:
            print('done receiving (timeout)')


if __name__ == '__main__':
    test_api_key = os.environ.get('OPENAI_API_KEY', None)
    api_model = os.environ.get('OPENAI_MODEL', None)
    api_base = os.environ.get('OPENAI_BASE_URL', None)

    if not (test_api_key and api_model and api_base):
        print('Please set OPENAI_API_KEY, OPENAI_BASE_URL and OPENAI_MODEL in your environment before running this script')
        # still try with whatever is on server

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

    if test_api_key and api_model and api_base:
        post_result = post_config(config, session_id=session_id)
        print('post result:', post_result)

    asyncio.run(ws_flow(os.environ.get('EASYPROMPT_WEBSOCKET', 'ws://127.0.0.1:8010/ws/prompt')))
