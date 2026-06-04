"""
python debug_signature2.py
Teste les variantes de stringToSign avec le bon APP_ID.
"""
import base64, hashlib, hmac, os, uuid, requests
from datetime import datetime, timezone
from dotenv import load_dotenv, dotenv_values

# Force lecture directe du .env sans variables d'environnement
vals       = dotenv_values(".env")
APP_ID     = vals["APS_APP_ID"]
APP_SECRET = vals["APS_APP_SECRET"]
SID        = vals["APS_SYSTEM_ID"]
BASE_URL   = "https://api.apsystemsema.com:9282"
PATH       = f"/user/api/v2/systems/details/{SID}"
METHOD     = "GET"
SM         = "HmacSHA256"

print(f"APP_ID     : {APP_ID}")
print(f"APP_SECRET : {APP_SECRET}")
print(f"SID        : {SID}")
print()

def call(label, sts_template):
    ts    = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    nonce = uuid.uuid4().hex
    sts   = sts_template.format(ts=ts, nonce=nonce)
    sig   = base64.b64encode(
        hmac.digest(APP_SECRET.encode(), sts.encode(), hashlib.sha256)
    ).decode()
    headers = {
        "X-CA-AppId": APP_ID,
        "X-CA-Timestamp": ts,
        "X-CA-Nonce": nonce,
        "X-CA-Signature-Method": SM,
        "X-CA-Signature": sig,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    r = requests.get(f"{BASE_URL}{PATH}", headers=headers, timeout=10)
    try:
        code = r.json().get("code", "?")
        body = r.json()
    except Exception:
        code = f"non-JSON"
        body = r.text[:200]
    print(f"[{label}]")
    print(f"  stringToSign : {sts}")
    print(f"  → code={code} | {body}")
    print()

# V1 : path complet avec slash initial (double slash entre appId et path)
call("V1 double slash",
     "{ts}/{nonce}/" + APP_ID + "/" + PATH + "/" + METHOD + "/" + SM)

# V2 : path sans slash initial (slash simple partout)
call("V2 path sans slash initial",
     "{ts}/{nonce}/" + APP_ID + "/" + PATH.lstrip("/") + "/" + METHOD + "/" + SM)

# V3 : dernier segment seulement
call("V3 dernier segment",
     "{ts}/{nonce}/" + APP_ID + "/" + PATH.rsplit("/",1)[-1] + "/" + METHOD + "/" + SM)

# V4 : path complet, méthode en minuscule
call("V4 méthode minuscule",
     "{ts}/{nonce}/" + APP_ID + "/" + PATH.lstrip("/") + "/get/" + SM)

# V5 : sans HTTPMethod dans le stringToSign
call("V5 sans method",
     "{ts}/{nonce}/" + APP_ID + "/" + PATH.lstrip("/") + "/" + SM)

# V6 : ordre différent — AppId en dernier
call("V6 AppId en dernier",
     "{ts}/{nonce}/" + PATH.lstrip("/") + "/" + METHOD + "/" + SM + "/" + APP_ID)
