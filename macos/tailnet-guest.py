"""Configure a tailnet domain while the guest router is stopped."""

import os
import secrets
import sqlite3
import sys
import tomllib
from pathlib import Path

import tomli_w

from compute_space.config import load_config
from compute_space.core.domains import DomainCertStatus
from compute_space.core.domains import DomainRecord
from compute_space.core.domains import set_primary_domain
from compute_space.core.domains import upsert_record
from compute_space.core.settings_store import CLAIM_TOKEN_KEY
from compute_space.core.settings_store import get_setting
from compute_space.core.settings_store import set_setting


def configure(domain: str) -> str:
    config = load_config()
    path = Path(os.environ["OPENHOST_ROUTER_CONFIG"])
    original = path.read_bytes()
    document = tomllib.loads(original.decode())
    # Back up the original config and SQLite database once, before the first change.
    backup = path.with_suffix(".before-tailnet.toml")
    if not backup.exists():
        backup.write_bytes(original)
        backup.chmod(0o600)
    with sqlite3.connect(config.db_path) as db:
        db.row_factory = sqlite3.Row
        database_backup = Path(config.db_path + ".before-tailnet")
        if not database_backup.exists():
            with sqlite3.connect(database_backup) as target:
                db.backup(target)
            database_backup.chmod(0o600)
        token = ""
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            token = get_setting(db, CLAIM_TOKEN_KEY) or secrets.token_urlsafe(32)
            set_setting(db, CLAIM_TOKEN_KEY, token)
        document.pop("claim_token_required", None)
        document["openhost"]["claim_token_required"] = True
        temporary = path.with_suffix(".tailnet.tmp")
        temporary.write_text(tomli_w.dumps(document))
        temporary.chmod(0o600)
        temporary.replace(path)
        upsert_record(db, DomainRecord(domain, tls=False, mdns=False, cert_status=DomainCertStatus.ACTIVE))
        set_primary_domain(db, domain)
    return f"http://{domain}/setup?claim={token}" if token else f"http://{domain}/"


if __name__ == "__main__":
    print(configure(sys.argv[1]))
