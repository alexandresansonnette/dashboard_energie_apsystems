import base64
import hashlib
import hmac
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests


BASE_URL = "https://api.apsystemsema.com:9282"
SIGNATURE_METHOD = "HmacSHA256"


class APSystemsError(Exception):
    pass


class APSystemsClient:
    def __init__(self, app_id: str, app_secret: str, base_url: str = BASE_URL):
        if not app_id or not app_secret:
            raise ValueError("APP ID et APP Secret obligatoires.")
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")

    # -------- Auth --------

    def _timestamp(self) -> str:
        return str(int(datetime.now(timezone.utc).timestamp() * 1000))

    def _nonce(self) -> str:
        return uuid.uuid4().hex

    def _signature(self, method: str, request_path: str, timestamp: str, nonce: str) -> str:
        # La doc dit "last segment of the path" — confirmé par test :
        # /user/api/v2/systems/details/SID → on signe "SID" (tout ce qui suit le dernier /)
        last_segment = request_path.rsplit("/", 1)[-1]
        string_to_sign = (
            f"{timestamp}/{nonce}/{self.app_id}/{last_segment}/{method.upper()}/{SIGNATURE_METHOD}"
        )
        digest = hmac.digest(
            self.app_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        )
        return base64.b64encode(digest).decode("utf-8")

    def _headers(self, method: str, request_path: str) -> Dict[str, str]:
        timestamp = self._timestamp()
        nonce = self._nonce()
        return {
            "X-CA-AppId": self.app_id,
            "X-CA-Timestamp": timestamp,
            "X-CA-Nonce": nonce,
            "X-CA-Signature-Method": SIGNATURE_METHOD,
            "X-CA-Signature": self._signature(method, request_path, timestamp, nonce),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # -------- Requête centrale --------

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        method = method.upper()
        url = f"{self.base_url}{path}"
        headers = self._headers(method, path)

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise APSystemsError(f"Erreur réseau : {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise APSystemsError(
                f"Réponse non JSON — status={response.status_code}, texte={response.text[:300]}"
            ) from exc

        if response.status_code >= 400:
            raise APSystemsError(f"Erreur HTTP {response.status_code} : {data}")

        if isinstance(data, dict) and data.get("code") not in (None, 0, "0"):
            raise APSystemsError(f"Erreur API code={data.get('code')} : {data}")

        return data

    # -------- Système --------

    def get_system_details(self, sid: str) -> Dict[str, Any]:
        return self.request("GET", f"/user/api/v2/systems/details/{sid}")

    def get_system_summary(self, sid: str) -> Dict[str, Any]:
        return self.request("GET", f"/user/api/v2/systems/summary/{sid}")

    def get_system_energy(
        self,
        sid: str,
        energy_level: str,
        date_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"energy_level": energy_level}
        if date_range:
            params["date_range"] = date_range
        return self.request("GET", f"/user/api/v2/systems/energy/{sid}", params=params)

    # -------- Appareils --------

    def get_inverters(self, sid: str) -> Dict[str, Any]:
        return self.request("GET", f"/user/api/v2/systems/inverters/{sid}")

    def get_meters(self, sid: str) -> Dict[str, Any]:
        return self.request("GET", f"/user/api/v2/systems/meters/{sid}")

    # -------- ECU --------

    def get_ecu_summary(self, sid: str, eid: str) -> Dict[str, Any]:
        return self.request("GET", f"/user/api/v2/systems/{sid}/devices/ecu/summary/{eid}")

    def get_ecu_energy(
        self,
        sid: str,
        eid: str,
        energy_level: str,
        date_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"energy_level": energy_level}
        if date_range:
            params["date_range"] = date_range
        return self.request("GET", f"/user/api/v2/systems/{sid}/devices/ecu/energy/{eid}", params=params)

    # -------- Compteur --------

    def get_meter_summary(self, sid: str, eid: str) -> Dict[str, Any]:
        return self.request("GET", f"/user/api/v2/systems/{sid}/devices/meter/summary/{eid}")

    def get_meter_period(
        self,
        sid: str,
        eid: str,
        energy_level: str,
        date_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"energy_level": energy_level}
        if date_range:
            params["date_range"] = date_range
        return self.request("GET", f"/user/api/v2/systems/{sid}/devices/meter/period/{eid}", params=params)

    # -------- Onduleur --------

    def get_inverter_summary(self, sid: str, uid: str) -> Dict[str, Any]:
        return self.request("GET", f"/user/api/v2/systems/{sid}/devices/inverter/summary/{uid}")

    def get_inverter_energy(
        self,
        sid: str,
        uid: str,
        energy_level: str,
        date_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"energy_level": energy_level}
        if date_range:
            params["date_range"] = date_range
        return self.request("GET", f"/user/api/v2/systems/{sid}/devices/inverter/energy/{uid}", params=params)

    def get_inverter_batch_energy(
        self,
        sid: str,
        eid: str,
        energy_level: str,
        date_range: str,
    ) -> Dict[str, Any]:
        params = {"energy_level": energy_level, "date_range": date_range}
        return self.request("GET", f"/user/api/v2/systems/{sid}/devices/inverter/batch/energy/{eid}", params=params)

    # -------- Stockage (endpoints /installer/api/v2 — confirmé doc) --------

    def get_storage_latest(self, sid: str, eid: str) -> Dict[str, Any]:
        return self.request("GET", f"/installer/api/v2/systems/{sid}/devices/storage/latest/{eid}")

    def get_storage_summary(self, sid: str, eid: str) -> Dict[str, Any]:
        return self.request("GET", f"/installer/api/v2/systems/{sid}/devices/storage/summary/{eid}")

    def get_storage_period(
        self,
        sid: str,
        eid: str,
        energy_level: str,
        date_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"energy_level": energy_level}
        if date_range:
            params["date_range"] = date_range
        return self.request("GET", f"/installer/api/v2/systems/{sid}/devices/storage/period/{eid}", params=params)
