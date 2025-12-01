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
import logging

logger = logging.getLogger(__name__)

load_dotenv()

LOGIN_URL = os.getenv('PALLETIQ_API_LOGIN_URL')
DATA_URL_TEMPLATE = os.getenv('PALLETIQ_API_DATA_URL_TEMPLATE')
EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('PASSWORD')

_session = None
_session_lock = threading.Lock()
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
    loop = asyncio.get_event_loop()
    try:
        if loop.is_closed():
            return None
    except RuntimeError:
        return None
    
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
    session = aiohttp.ClientSession(connector=connector)
    return session

async def request_palletiq(barcode: str) -> Optional[Dict]: 
    global _token
    if not DATA_URL_TEMPLATE:
        return None
    
    current_time = time.time()
    
    if barcode in _api_cache:
        cached_data, cached_time = _api_cache[barcode]
        if current_time - cached_time < _cache_ttl:
            await asyncio.sleep(0)
            return cached_data
        else:
            del _api_cache[barcode]
    
    try:
        with _token_lock:
            token = _token
        if not token:
            logger.warning(f"⚠️ No token available for barcode {barcode}")
            return None
        
        async_session = await _get_async_session()
        if not async_session:
            logger.error(f"❌ Failed to get async session for barcode {barcode}")
            return None
        
        data_url = DATA_URL_TEMPLATE.format(scan=barcode, token=token)
        result = None

        try:
            async with async_session.get(data_url) as response:
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
                    result = pusher_data
                elif response.status == 401:
                    logger.warning(f"⚠️ Token expired (401), refreshing token for barcode {barcode}")
                    with _token_lock:
                        _token = None
                    try:
                        init_token()
                        with _token_lock:
                            if _token:
                                logger.info(f"✅ Token refreshed successfully, retrying request")
                                retry_url = DATA_URL_TEMPLATE.format(scan=barcode, token=_token)
                                async with async_session.get(retry_url) as retry_response:
                                    if retry_response.status == 200:
                                        product_data = await retry_response.json()
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
                                        result = pusher_data
                                    else:
                                        logger.error(f"❌ Retry after token refresh failed with status {retry_response.status}")
                                        result = None
                            else:
                                logger.error(f"❌ Failed to refresh token")
                                result = None
                    except Exception as e:
                        logger.error(f"❌ Error refreshing token: {e}", exc_info=True)
                        result = None
                elif response.status == 400:
                    try:
                        error_body = await response.text()
                        error_data = json.loads(error_body) if error_body else {}
                        error_msg = error_data.get('error', '')
                        
                        if error_msg == "No results":
                            logger.info(f"ℹ️ PalletIQ API: No results found for barcode {barcode}, using default pusher")
                            pusher_data = get_pusher_number('Extra')
                            _api_cache[barcode] = (pusher_data, current_time)
                            result = pusher_data
                        else:
                            logger.error(f"❌ PalletIQ API returned status 400 (Bad Request) for barcode {barcode}. Error: {error_body}")
                            result = None
                    except json.JSONDecodeError:
                        logger.error(f"❌ PalletIQ API returned status 400 (Bad Request) for barcode {barcode}. Response: {error_body}")
                        result = None
                    except Exception as e:
                        logger.error(f"❌ PalletIQ API returned status 400 (Bad Request) for barcode {barcode}. URL: {data_url}. Exception: {e}")
                        result = None
                else:
                    try:
                        error_body = await response.text()
                        logger.warning(f"⚠️ PalletIQ API returned status {response.status} for barcode {barcode}. Response: {error_body}")
                    except:
                        logger.warning(f"⚠️ PalletIQ API returned status {response.status} for barcode {barcode}")
                    result = None
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Timeout requesting PalletIQ API for barcode {barcode}")
            result = None
        except aiohttp.ClientError as e:
            logger.error(f"❌ Client error requesting PalletIQ API for barcode {barcode}: {e}")
            result = None
        except Exception as e:
            logger.error(f"❌ Unexpected error in request_palletiq for barcode {barcode}: {e}", exc_info=True)
            result = None
        finally:
            if async_session:
                try:
                    await async_session.close()
                except:
                    pass
        
        return result
    except Exception as e:
        logger.error(f"❌ Fatal error in request_palletiq for barcode {barcode}: {e}", exc_info=True)
        return None

from promise import Promise

def request_palletiq_async(barcode: str):
    return Promise(request_palletiq(barcode))

def request_palletiq_sync(barcode: str):
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(request_palletiq(barcode))
        return result
    finally:
        loop.close()
