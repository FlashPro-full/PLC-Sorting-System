import requests # type: ignore
import aiohttp # type: ignore
import asyncio
import os
import json
from dotenv import load_dotenv # type: ignore
from typing import Dict, Optional
import re
import time
import threading
import logging

logger = logging.getLogger(__name__)

load_dotenv()

LOGIN_URL = os.getenv('PURESCAN_API_LOGIN_URL')
DATA_URL = os.getenv('PURESCAN_API_DATA_URL')
EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('PASSWORD')

_session = None
_session_lock = threading.Lock()
_token = None
_token_lock = threading.Lock()

_api_cache: Dict[str, tuple] = {}
_cache_ttl = 300

def clear_cache_entry(barcode: str) -> None:
    _api_cache.pop(barcode, None)

def init_session():
    global _session
    _session = requests.Session()
    _session.timeout = 10
    return

LOGIN_TIMEOUT = 90
LOGIN_RETRIES = 3
LOGIN_RETRY_DELAY = 5

def init_token():
    global _token

    login_payload = {
        "email": EMAIL,
        "password": PASSWORD,
    }

    if not LOGIN_URL:
        return

    last_error = None
    for attempt in range(LOGIN_RETRIES):
        try:
            response = _session.post(
                LOGIN_URL, json=login_payload, timeout=LOGIN_TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('result') and data.get('token'):
                    with _token_lock:
                        _token = data.get('token')
                    return
            return
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout) as e:
            last_error = e
            logger.warning(
                f"⚠️ Login timeout (attempt {attempt + 1}/{LOGIN_RETRIES}), retrying in {LOGIN_RETRY_DELAY}s..."
            )
            if attempt < LOGIN_RETRIES - 1:
                time.sleep(LOGIN_RETRY_DELAY)
        except requests.exceptions.RequestException as e:
            last_error = e
            logger.warning(
                f"⚠️ Login request failed (attempt {attempt + 1}/{LOGIN_RETRIES}): {e}"
            )
            if attempt < LOGIN_RETRIES - 1:
                time.sleep(LOGIN_RETRY_DELAY)

    if last_error:
        logger.error(f"❌ Failed to get token after {LOGIN_RETRIES} attempts: {last_error}")

def get_pusher_number(label: str):
    pushers = {}
    with open("settings.json", "r") as f:
        pushers = json.load(f)['pushers']
    for pusher, config in pushers.items():
        if not isinstance(config, dict):
            continue
        if config.get('label') == label:
            match = re.search(r'\d+', pusher)
            if match:
                return {
                    "pusher": int(match.group(0)),
                    "label": config.get('label'),
                    "distance": config.get('distance')
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

def _label_from_purescan_response(product_data: Dict) -> str:
    if not product_data.get('result'):
        return 'Extra'
    else:
        scanResult = product_data.get('scanResult') or {}
        product = scanResult.get('product') or {}
        fba = scanResult.get('fba') or {}
        mf = scanResult.get('mf') or {}

        if fba.get('accept') is True:
            return 'FBA'
        if mf.get('accept') is True:
            return 'MF'
        category = product.get('category')
        if category != 'Book' and category != 'DVD' and category != 'Video Game' and category != 'Music':
            return 'Extra'
        else:
            return f'Reject {category}'


async def request_purescan(barcode: str) -> Optional[Dict]:
    global _token
    if not DATA_URL:
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

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
        }
        payload = {'barcode': barcode}
        result = None

        try:
            async with async_session.post(DATA_URL, json=payload, headers=headers) as response:
                if response.status == 200:
                    product_data = await response.json()
                    label = _label_from_purescan_response(product_data)
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
                                headers_retry = {
                                    'Content-Type': 'application/json',
                                    'Authorization': f'Bearer {_token}',
                                }
                                async with async_session.post(DATA_URL, json=payload, headers=headers_retry) as retry_response:
                                    if retry_response.status == 200:
                                        product_data = await retry_response.json()
                                        label = _label_from_purescan_response(product_data)
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
                else:
                    try:
                        error_body = await response.text()
                        logger.warning(f"⚠️ Purescan API returned status {response.status} for barcode {barcode}. Response: {error_body}")
                        label = "Extra"
                        pusher_data = get_pusher_number(label)
                        _api_cache[barcode] = (pusher_data, current_time)
                        result = pusher_data
                    except Exception:
                        logger.warning(f"⚠️ Purescan API returned status {response.status} for barcode {barcode}")
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Timeout requesting Purescan API for barcode {barcode}")
            result = None
        except aiohttp.ClientError as e:
            logger.error(f"❌ Client error requesting Purescan API for barcode {barcode}: {e}")
            result = None
        except Exception as e:
            logger.error(f"❌ Unexpected error in request_purescan for barcode {barcode}: {e}", exc_info=True)
            result = None
        finally:
            if async_session:
                try:
                    await async_session.close()
                except Exception:
                    pass

        return result
    except Exception as e:
        logger.error(f"❌ Fatal error in request_purescan for barcode {barcode}: {e}", exc_info=True)
        return None

from promise import Promise

def request_purescan_async(barcode: str):
    return Promise(request_purescan(barcode))

def request_purescan_sync(barcode: str):
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(request_purescan(barcode))
        return result
    finally:
        loop.close()
