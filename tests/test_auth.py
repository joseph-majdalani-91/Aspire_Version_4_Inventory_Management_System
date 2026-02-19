import hashlib
import hmac

from app.auth import hash_password, verify_password


def test_hash_password_uses_pbkdf2_format() -> None:
    hashed = hash_password("manager123")
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password("manager123", hashed)
    assert not verify_password("wrong", hashed)


def test_verify_password_supports_legacy_hash() -> None:
    legacy = hashlib.sha256("test-pepper:admin123".encode("utf-8")).hexdigest()
    assert hmac.compare_digest(legacy, legacy)
    assert verify_password("admin123", legacy)
