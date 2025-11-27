import aiohttp  # type: ignore
import asyncio
import os
import json
from dotenv import load_dotenv
from typing import Dict, Optional
import re
import threading
import logging

logger = logging.getLogger(__name__)

load_dotenv()

LOGIN_URL = os.getenv('PALLETIQ_API_LOGIN_URL')
DATA_URL_TEMPLATE = os.getenv('PALLETIQ_API_DATA_URL_TEMPLATE')
EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('PASSWORD')

_session: Optional[aiohttp.ClientSession] = None
_session_lock = threading.Lock()
_token = None
_token_lock = threading.Lock()

SETTINGS_FILE = 'settings.json'
try:
    with open(SETTINGS_FILE, 'r') as f:
        SETTINGS = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    SETTINGS = {}

async def get_session() -> aiohttp.ClientSession:
    global _session
    with _session_lock:
        if _session is None or _session.closed:
            _session = aiohttp.ClientSession()
        return _session


async def get_token() -> Optional[str]:
    global _token
    
    login_payload = {
        "wl_team_id": 0,
        "user_email": EMAIL,
        "user_password": PASSWORD,
    }
    
    try:
        if not LOGIN_URL:
            return None
        session = await get_session()
        async with session.post(LOGIN_URL, json=login_payload) as response:
            if response.status == 200:
                data = await response.json()
                with _token_lock:
                    _token = data.get('token')
                return _token
    except Exception as e:
        print(f"❌ Error getting token: {e}")
    
    return None

def get_pusher_number(label: str):
    for pusher, config in SETTINGS.items():
        if config.get('label') == label:
            match = re.search(r'\d+', pusher)
            if match:
                return int(match.group(0))

    return 8

async def request_palletiq(barcode: str) -> Optional[Dict]:
    if not DATA_URL_TEMPLATE:
        print(f"⚠️ DATA_URL_TEMPLATE not configured")
        return None
    
    session = None
    token = None
    
    try:
        with _token_lock:
            if not _token:
                token = await get_token()
            else:
                token = _token

        with _session_lock:
            if not _session:
                session = await get_session()
            else:
                session = _session
        
        data_url = DATA_URL_TEMPLATE.format(scan=barcode, token=token)
        
        async with session.get(data_url) as response:
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

                pusher_number = get_pusher_number(label)

                return {
                    "pusher": pusher_number,
                    "label": label,
                    "distance": SETTINGS.get(label, {}).get('distance', 0)
                }
            else:
                print(f"❌ PalletIQ API returned status {response.status} for barcode: {barcode}")
                return None
                
    except aiohttp.ClientError as e:
        print(f"❌ Network error requesting palletiq for {barcode}: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error requesting palletiq for {barcode}: {e}")
        return None

from promise import Promise

def request_palletiq_async(barcode: str):
    return Promise(request_palletiq(barcode))
