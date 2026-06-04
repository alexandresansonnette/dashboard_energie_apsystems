"""
Script de diagnostic — à lancer UNE FOIS depuis le dossier du projet :
    python debug_signature.py

Il teste 3 variantes de construction de la signature pour trouver celle
qui fait passer le code=4000.
Chaque variante affiche le code retourné par l'API.
"""
import base64
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID     = os.getenv("APS_APP_ID", "")
APP_SECRET = os.getenv("APS_APP_SECRET", "")
SID        = os.getenv("APS_SYSTEM_ID", "")
BASE_URL   = "https://api.apsystemsema.com:9282"
PATH       = f"/user/api/v2/systems/details/{SID}"
METHOD     = "GET"
SIG_METHOD = "HmacSHA256"

print(f"APP_ID     : {APP_ID}")
print(f"APP_SECRET : {APP_SECRET}")
print(f"SID        : {SID}")
print(f"PATH       : {PATH}")
print()

def sign(string_to_sign: str) -> str:
    digest = hmac.digest(
        APP_SECRET.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    )
    return base64.b64encode(digest).decode("utf-8")

def call(label: str, string_to_sign: str) -> None:
    ts    = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    nonce = uuid.uuid4().hex
    sig   = sign(string_to_sign.replace("{ts}", ts).replace("{nonce}", nonce))

    headers = {
        "X-CA-AppId": APP_ID,
        "X-CA-Timestamp": ts,
        "X-CA-Nonce": nonce,
        "X-CA-Signature-Method": SIG_METHOD,
        "X-CA-Signature": sig,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    r = requests.get(f"{BASE_URL}{PATH}", headers=headers, timeout=15)
    try:
        code = r.json().get("code", "?")
    except Exception:
        code = f"non-JSON ({r.status_code})"
    print(f"[{label}]")
    print(f"  stringToSign : {string_to_sign.replace('{ts}', ts).replace('{nonce}', nonce)}")
    print(f"  → code API   : {code}")
    print(f"  → réponse    : {r.text[:200]}")
    print()

# Variante 1 : path complet (implémentation actuelle)
call(
    "V1 — path complet",
    "{ts}/{nonce}/" + APP_ID + "/" + PATH + "/" + METHOD + "/" + SIG_METHOD,
)

# Variante 2 : path sans le SID (juste /user/api/v2/systems/details)
path_sans_sid = PATH.rsplit("/", 1)[0]
call(
    "V2 — path sans SID",
    "{ts}/{nonce}/" + APP_ID + "/" + path_sans_sid + "/" + METHOD + "/" + SIG_METHOD,
)

# Variante 3 : uniquement le dernier segment (le SID lui-même)
last_segment = PATH.rsplit("/", 1)[-1]
call(
    "V3 — dernier segment seulement",
    "{ts}/{nonce}/" + APP_ID + "/" + last_segment + "/" + METHOD + "/" + SIG_METHOD,
)

# Variante 4 : path complet sans le slash initial
path_no_leading_slash = PATH.lstrip("/")
call(
    "V4 — path sans slash initial",
    "{ts}/{nonce}/" + APP_ID + "/" + path_no_leading_slash + "/" + METHOD + "/" + SIG_METHOD,
)
