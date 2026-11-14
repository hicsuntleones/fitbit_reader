"""Autorizzazione OAuth 2.0 (client di tipo "App desktop")."""

from __future__ import annotations

from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

_PREFIX = "https://www.googleapis.com/auth/googlehealth."
SCOPES = [
    _PREFIX + "health_metrics_and_measurements.readonly",
    _PREFIX + "activity_and_fitness.readonly",
    _PREFIX + "sleep.readonly",
    _PREFIX + "ecg.readonly",
]


class AuthError(RuntimeError):
    pass


def authorize(client_secret: Path, token_path: Path) -> Credentials:
    """Apre il browser per il consenso e salva il token (con refresh token) in locale."""
    if not client_secret.exists():
        raise AuthError(
            f"File delle credenziali non trovato: {client_secret}\n"
            "Scaricalo dalla Google Cloud console (Client OAuth > App desktop > Scarica JSON)."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    # prompt=consent garantisce che Google restituisca sempre un refresh token
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    _save(creds, token_path)
    return creds


def load_credentials(token_path: Path) -> Credentials:
    """Carica il token salvato e lo rinnova se scaduto."""
    if not token_path.exists():
        raise AuthError("Nessun token salvato: esegui prima  fitbit_reader auth")
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds.valid:
        if not creds.refresh_token:
            raise AuthError("Token senza refresh token: esegui di nuovo  fitbit_reader auth")
        try:
            creds.refresh(Request())
        except RefreshError as e:
            raise AuthError(
                "Il refresh token non è più valido (in modalità Test Google lo fa scadere "
                f"dopo 7 giorni). Esegui di nuovo  fitbit_reader auth\nDettaglio: {e}"
            ) from e
        _save(creds, token_path)
    return creds


def _save(creds: Credentials, token_path: Path) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
