import requests
from django.conf import settings
import time

_onemap_token = None
_onemap_token_expiry = 0

def get_onemap_token():
    global _onemap_token, _onemap_token_expiry
    if _onemap_token and time.time() < _onemap_token_expiry:
        return _onemap_token
    resp = requests.post(
        f"{settings.ONEMAP_BASE_URL}/api/auth/post/getToken",
        json={
            "email": settings.ONEMAP_API_EMAIL,
            "password": settings.ONEMAP_API_PASSWORD,
        }
    )
    resp.raise_for_status()
    data = resp.json()
    _onemap_token = data['access_token']
    _onemap_token_expiry = time.time() + 255600
    return _onemap_token

def get_latlng_from_postal(postal_code):
    token = get_onemap_token()
    resp = requests.get(
        f"{settings.ONEMAP_BASE_URL}/api/common/elastic/search",
        params={"token": token, "searchVal": postal_code, "returnGeom": "Y", "getAddrDetails": "Y"}
    )
    resp.raise_for_status()
    results = resp.json().get('results', [])
    if results:
        lat = results[0].get('LATITUDE')
        lng = results[0].get('LONGITUDE')
        return lat, lng
    return None, None