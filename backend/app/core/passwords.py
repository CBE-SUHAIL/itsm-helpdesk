"""Local password hashing shared by the demo seed and future auth routes.

The stored format is versioned by algorithm name and includes its own random
salt and work factor. A01/A02 should call ``verify_password`` for seeded users.
"""

import hashlib
import hmac
import secrets


ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000


def hash_password(password: str) -> str:
    if not password or not password.strip():
        raise ValueError("Password must not be blank")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, ITERATIONS
    )
    return f"{ALGORITHM}${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_hex, expected_hex = stored_hash.split("$")
        if algorithm != ALGORITHM:
            return False
        iterations = int(iterations_text)
        if not 1 <= iterations <= 2_000_000:
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
        if len(salt) != 16 or len(expected) != hashlib.sha256().digest_size:
            return False
    except (AttributeError, ValueError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)
