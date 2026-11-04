import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[2]
KEY_FILE = ROOT / "data" / "secret.key"


def _key():
    env = os.environ.get("RIAYA_DATA_KEY")
    if env:
        return env.encode()
    KEY_FILE.parent.mkdir(exist_ok=True)
    if not KEY_FILE.exists():
        KEY_FILE.write_bytes(Fernet.generate_key())
        os.chmod(KEY_FILE, 0o600)
    return KEY_FILE.read_bytes()


_fernet = None


def fernet():
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_key())
    return _fernet


def seal(obj):
    return None if obj is None else fernet().encrypt(json.dumps(obj, ensure_ascii=False).encode())


def unseal(blob):
    return None if blob is None else json.loads(fernet().decrypt(blob))


def new_token():
    return secrets.token_urlsafe(32)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def share_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
    return "".join(secrets.choice(alphabet) for _ in range(8))


def hash_password(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 310_000)
    return salt, dk.hex()


def check_password(pw, salt, expected):
    return hmac.compare_digest(hash_password(pw, salt)[1], expected)
