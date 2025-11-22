import requests  # type: ignore
import os
import json
from dotenv import load_dotenv
from typing import Dict, Optional
import re

load_dotenv()

LOGIN_URL = os.getenv('PALLETIQ_API_LOGIN_URL')
DATA_URL_TEMPLATE = os.getenv('PALLETIQ_API_DATA_URL_TEMPLATE')
EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('PASSWORD')

session = requests.Session()
TOKEN = None

SETTINGS_FILE = 'settings.json'
try:
    with open(SETTINGS_FILE, 'r') as f:
        SETTINGS = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    SETTINGS = {}

def get_token():
    global TOKEN

    login_payload = {
        "wl_team_id": 0,
        "user_email": EMAIL,
        "user_password": PASSWORD,
    }

    response = session.post(LOGIN_URL, json=login_payload)

    if response.status_code == 200:
        TOKEN = response.json().get('token')
        return TOKEN

    return None

def ensure_token():
    global TOKEN
    if not TOKEN:
        return get_token()

    test_url = DATA_URL_TEMPLATE.format(scan="9780140328721", token=TOKEN)
    test_response = session.get(test_url)

    if test_response.status_code == 401:
        print("🔁 Token expired, refreshing...")
        return get_token()

    return TOKEN

def get_pusher_number(label: str) -> Dict[str, int]:
    for pusher, config in SETTINGS.items():
        if config.get('label') == label:
            match = re.search(r'\d+', pusher)
            if match:
                return {
                    'pusher_number': int(match.group(0)), 
                    'distance': int(config.get('distance', 0))
                }

    return {'pusher_number': 8, 'distance': 0}

def request_palletiq(barcode: str) -> Optional[Dict]:
    if not DATA_URL_TEMPLATE:
        return None
    
    try:
        token = ensure_token()
        if not token:
            return None
        
        data_url = DATA_URL_TEMPLATE.format(scan=barcode, token=token)
        response = session.get(data_url)
        
        if response.status_code == 200:
            product_data = response.json()

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

            return pusher_data

        else:
            return None
    except requests.exceptions.RequestException:
        return None
