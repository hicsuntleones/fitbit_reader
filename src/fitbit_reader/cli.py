"""Riga di comando:  fitbit_reader {auth,check,sync,types}"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from .api import ApiError, HealthApi
from .auth import AuthError, authorize, load_credentials
from .datatypes import DATA_TYPES
from .store import Store
from .sync import sync


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="fitbit_reader", description=__doc__)
    p.add_argument("--client-secret", type=Path, default=Path("client_secret.json"))
    p.add_argument("--token", type=Path, default=Path(".secrets/token.json"))
    p.add_argument("--data-dir", type=Path, default=Path("data"))
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("auth", help="autorizza l'accesso dal browser (una volta)")
    sub.add_parser("check", help="verifica token, collegamento a Google Health e dispositivi")
    sub.add_parser("types", help="elenca i tipi di dato scaricati")
    s = sub.add_parser("sync", help="scarica i giorni mancanti")
    s.add_argument("--since", type=date.fromisoformat, help="primo giorno (YYYY-MM-DD)")
    s.add_argument("--until", type=date.fromisoformat, help="ultimo giorno (default: oggi)")
    s.add_argument("--types", nargs="+", choices=sorted(DATA_TYPES), metavar="TIPO")

    a = p.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if a.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log = logging.getLogger("fitbit_reader")

    try:
        if a.cmd == "types":
            for t in DATA_TYPES.values():
                print(f"{t.name:38s} {t.kind}")
            return 0

        if a.cmd == "auth":
            creds = authorize(a.client_secret, a.token)
            log.info("Token salvato in %s", a.token)
            _check(HealthApi(creds))
            return 0

        api = HealthApi(load_credentials(a.token))
        if a.cmd == "check":
            _check(api)
            return 0
        if a.cmd == "sync":
            ok = sync(api, Store(a.data_dir), a.types, a.since, a.until)
            log.info("Sync %s", "completata" if ok else "completata CON ERRORI")
            return 0 if ok else 2
    except (AuthError, ApiError) as e:
        log.error("%s", e)
        return 1
    return 0


def _check(api: HealthApi) -> None:
    print("Identità:", json.dumps(api.identity(), indent=2, ensure_ascii=False))
    try:
        print("Dispositivi:", json.dumps(api.paired_devices(), indent=2, ensure_ascii=False))
    except ApiError as e:
        if e.status != 403:
            raise
        # L'elenco dispositivi richiede uno scope che non chiediamo: non serve per i dati.
        print("Dispositivi: non disponibili con i permessi attuali (non serve per il sync)")


if __name__ == "__main__":
    sys.exit(main())
