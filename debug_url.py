"""
Script de diagnostic URL — lance depuis le dossier du projet :
    python debug_url.py

Teste différentes combinaisons host:port pour trouver celle qui répond.
N'utilise PAS la signature — on veut juste voir ce que le serveur retourne.
"""
import os
import base64
import hashlib
import hmac
import uuid
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID     = os.getenv("APS_APP_ID", "")
APP_SECRET = os.getenv("APS_APP_SECRET", "")
SID        = os.getenv("APS_SYSTEM_ID", "")
SIG_METHOD = "HmacSHA256"
METHOD     = "GET"

print(f"APP_ID     : {APP_ID}")
print(f"APP_SECRET : {APP_SECRET}")
print(f"SID        : {SID}")
print()

def sign(app_id, app_secret, path):
    ts    = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    nonce = uuid.uuid4().hex
    string_to_sign = f"{ts}/{nonce}/{app_id}/{path}/{METHOD}/{SIG_METHOD}"
    digest = hmac.digest(
        app_secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    )
    sig = base64.b64encode(digest).decode("utf-8")
    headers = {
        "X-CA-AppId": app_id,
        "X-CA-Timestamp": ts,
        "X-CA-Nonce": nonce,
        "X-CA-Signature-Method": SIG_METHOD,
        "X-CA-Signature": sig,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    return headers

# Combinaisons à tester
BASE_URLS = [
    "https://api.apsystemsema.com:9282",
    "https://api.apsystemsema.com",
    "https://api.apsystemsema.com:443",
    "http://api.apsystemsema.com:9282",
]

PATHS = [
    f"/user/api/v2/systems/details/{SID}",
    f"/user/api/v2/systems/summary/{SID}",
]

for base in BASE_URLS:
    for path in PATHS:
        url = f"{base}{path}"
        try:
            headers = sign(APP_ID, APP_SECRET, path)
            r = requests.get(url, headers=headers, timeout=8)
            try:
                body = r.json()
                code = body.get("code", "?")
                result = f"code={code} | {str(body)[:150]}"
            except Exception:
                result = f"non-JSON | {r.text[:150]}"
            print(f"[{r.status_code}] {url}")
            print(f"  → {result}")
        except requests.exceptions.ConnectionError as e:
            print(f"[CONN ERR] {url}")
            print(f"  → {str(e)[:120]}")
        except Exception as e:
            print(f"[ERR] {url} → {e}")
        print()
