import requests # type: ignore
import aiohttp
import asyncio
import os
import json
from dotenv import load_dotenv
from typing import Dict, Optional
import re
import time
import threading

load_dotenv()

LOGIN_URL = os.getenv('PALLETIQ_API_LOGIN_URL')
DATA_URL_TEMPLATE = os.getenv('PALLETIQ_API_DATA_URL_TEMPLATE')
EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('PASSWORD')

_session = None
_session_lock = threading.Lock()
_async_session = None
_async_session_lock = threading.Lock()
_async_sessions = {}
_token = None
_token_lock = threading.Lock()

_api_cache: Dict[str, tuple] = {}
_cache_ttl = 300

SETTINGS_FILE = 'settings.json'
try:
    with open(SETTINGS_FILE, 'r') as f:
        SETTINGS = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    SETTINGS = {}

def init_session():
    global _session
    _session = requests.Session()
    _session.timeout = 10
    return

def init_token():
    global _token

    login_payload = {
        "wl_team_id": 0,
        "user_email": EMAIL,
        "user_password": PASSWORD,
    }
    
    if not LOGIN_URL:
        return
    
    response = _session.post(LOGIN_URL, json=login_payload, timeout=10)
    if response.status_code == 200:
        data = response.json()
        with _token_lock:
            _token = data.get('token')
            return

    return

def get_pusher_number(label: str):
    for pusher, config in SETTINGS.items():
        if config.get('label') == label:
            match = re.search(r'\d+', pusher)
            if match:
                return {
                    "pusher": int(match.group(0)),
                    "label": config.get('label'),
                    "distance": config.get('distance')
                }

    return {
        "pusher": 8,
        "label": "Extra",
        "distance": 0
    }

async def _get_async_session():
    global _async_sessions
    current_loop = asyncio.get_event_loop()
    loop_id = id(current_loop)
    
    if loop_id not in _async_sessions:
        _async_sessions[loop_id] = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10, connect=5),
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=30)
        )
    else:
        session = _async_sessions[loop_id]
        if session.closed:
            _async_sessions[loop_id] = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10, connect=5),
                connector=aiohttp.TCPConnector(limit=100, limit_per_host=30)
            )
    
    return _async_sessions[loop_id]

async def request_palletiq(barcode: str) -> Optional[Dict]: 
    if not DATA_URL_TEMPLATE:
        return None
    
    current_time = time.time()
    
    if barcode in _api_cache:
        cached_data, cached_time = _api_cache[barcode]
        if current_time - cached_time < _cache_ttl:
            return cached_data
        else:
            del _api_cache[barcode]
    
    try:
        if not _token:
            return None
        
        async_session = await _get_async_session()
        if not async_session or async_session.closed:
            return None
        
        data_url = DATA_URL_TEMPLATE.format(scan=barcode, token=_token)

        try:
            async with async_session.get(data_url, timeout=aiohttp.ClientTimeout(total=10, connect=5)) as response:
                if response.status == 200:
                    product_data = await response.json()
                    winner = product_data.get('winner')
                    meta = product_data.get('meta')
                    label = 'Extra'
                    
                    if winner and winner.get('winnerModule'):
                        label = winner.get('winnerSubModule', 'Extra')
                    elif meta:
                        group = meta.get('product_group')
                        if group == 'Book':
                            label = 'Reject Book'
                        elif group == 'Music':
                            label = 'Reject Music'
                        elif group == 'DVD':
                            label = 'Reject DVD'
                        elif group == 'Video Game':
                            label = 'Reject Video Game'
                    
                    pusher_data = get_pusher_number(label)
                    _api_cache[barcode] = (pusher_data, current_time)
                    
                    return pusher_data
                else:
                    return None
        except (asyncio.TimeoutError, aiohttp.ClientError):
            return None
    except Exception:
        return None

from promise import Promise

def request_palletiq_async(barcode: str):
    coro = request_palletiq(barcode)
    promise = Promise(coro)
    return promise

def request_palletiq_sync(barcode: str):
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(request_palletiq(barcode))
        return result
    finally:
        loop.close()
