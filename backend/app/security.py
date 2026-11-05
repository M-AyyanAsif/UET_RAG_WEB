import base64
import hashlib
import hmac
import secrets
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from . import config


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return "pbkdf2_sha256$310000$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(hashed).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, digest = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(iterations))
        return hmac.compare_digest(check, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


def get_serializer():
    if len(config.SESSION_SECRET) < 32:
        raise RuntimeError("SESSION_SECRET must contain at least 32 characters; run deploy.sh")
    return URLSafeTimedSerializer(config.SESSION_SECRET, salt="cloudrag-v1")


def create_session(user_id: int):
    return get_serializer().dumps({"uid": user_id})


def decode_session(token: str):
    try:
        return get_serializer().loads(token, max_age=8 * 3600).get("uid")
    except (BadSignature, SignatureExpired, AttributeError, TypeError):
        return None
