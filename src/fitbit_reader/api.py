"""Client minimale per la Google Health API v4."""

from __future__ import annotations

import time
from collections.abc import Iterator

from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials

BASE_URL = "https://health.googleapis.com/v4"
_RETRY_STATUS = {429, 500, 502, 503, 504}


class ApiError(RuntimeError):
    def __init__(self, status: int, url: str, body: str):
        super().__init__(f"HTTP {status} su {url}\n{body[:2000]}")
        self.status = status


class HealthApi:
    def __init__(self, creds: Credentials, max_retries: int = 5):
        self.session = AuthorizedSession(creds)
        self.max_retries = max_retries

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{BASE_URL}/{path}"
        for attempt in range(self.max_retries + 1):
            r = self.session.get(url, params=params, timeout=60)
            if r.status_code in _RETRY_STATUS and attempt < self.max_retries:
                wait = int(r.headers.get("Retry-After", 0)) or 2**attempt
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                raise ApiError(r.status_code, url, r.text)
            return r.json()
        raise AssertionError("unreachable")

    def identity(self) -> dict:
        return self._get("users/me/identity")

    def paired_devices(self) -> dict:
        return self._get("users/me/pairedDevices")

    def list_data_points(self, data_type: str, filter_: str, page_size: int) -> Iterator[dict]:
        """Restituisce tutti i data point che soddisfano il filtro, gestendo la paginazione."""
        params = {"filter": filter_, "pageSize": page_size}
        while True:
            resp = self._get(f"users/me/dataTypes/{data_type}/dataPoints", params)
            yield from resp.get("dataPoints", [])
            token = resp.get("nextPageToken")
            if not token:
                return
            params["pageToken"] = token
