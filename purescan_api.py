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
_refresh_lock = threading.Lock()

def set_pushers_purescan():
    global pushers
    with open("settings.json", "r") as f:
        pushers = json.load(f)['pushers']

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
    global pushers

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

_async_session = None
_request_timeout = aiohttp.ClientTimeout(total=5)

def _get_async_session():
    global _async_session
    if _async_session is None or _async_session.closed:
        _async_session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=50)
        )
    return _async_session

def _refresh_token_once():
    with _token_lock:
        if _token:
            return True
    with _refresh_lock:
        with _token_lock:
            if _token:
                return True
        init_token()
    with _token_lock:
        return bool(_token)

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
        if category != 'Book' and category != 'DVD' and category != 'Video Game' and category != 'Music' and category != 'Blu-ray':
            return 'Extra'
        else:
            return f'Reject {category}'


async def request_purescan(barcode: str) -> Optional[Dict]:
    global _token, pushers

    if not DATA_URL:
        return None

    try:
        with _token_lock:
            token = _token
        if not token:
            logger.warning(f"⚠️ No token available for barcode {barcode}")
            return None

        async_session = _get_async_session()
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
        }
        payload = {'barcode': barcode}
        result = None

        try:
            async with async_session.post(DATA_URL, json=payload, headers=headers, timeout=_request_timeout) as response:
                if response.status == 200:
                    product_data = await response.json()
                    label = _label_from_purescan_response(product_data)
                    pusher_data = get_pusher_number(label)
                    result = pusher_data
                elif response.status == 401:
                    logger.warning(f"⚠️ Token expired (401), refreshing token for barcode {barcode}")
                    with _token_lock:
                        _token = None
                    try:
                        ok = await asyncio.to_thread(_refresh_token_once)
                        with _token_lock:
                            if ok and _token:
                                logger.info(f"✅ Token refreshed successfully, retrying request")
                                headers_retry = {
                                    'Content-Type': 'application/json',
                                    'Authorization': f'Bearer {_token}',
                                }
                                async with async_session.post(DATA_URL, json=payload, headers=headers_retry, timeout=_request_timeout) as retry_response:
                                    if retry_response.status == 200:
                                        product_data = await retry_response.json()
                                        label = _label_from_purescan_response(product_data)
                                        pusher_data = get_pusher_number(label)
                                        result = pusher_data
                    except Exception as e:
                        logger.error(f"❌ Error refreshing token: {e}", exc_info=True)
                elif response.status == 404:
                    try:
                        error_body = await response.text()
                        logger.warning(f"⚠️ Purescan API returned status {response.status} for barcode {barcode}. Response: {error_body}")
                        if "Extra" in pushers:
                            result = get_pusher_number("Extra")
                    except Exception:
                        logger.warning(f"⚠️ Purescan API returned status {response.status} for barcode {barcode}")
                elif response.status == 500:
                    try:
                        error_body = await response.text()
                        logger.warning(f"⚠️ Purescan API returned status {response.status} for barcode {barcode}. Response: {error_body}")
                    except Exception:
                        logger.warning(f"⚠️ Purescan API returned status {response.status} for barcode {barcode}")
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Timeout requesting Purescan API for barcode {barcode}")
        except aiohttp.ClientError as e:
            logger.error(f"❌ Client error requesting Purescan API for barcode {barcode}: {e}")
        except Exception as e:
            logger.error(f"❌ Unexpected error in request_purescan for barcode {barcode}: {e}", exc_info=True)

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
