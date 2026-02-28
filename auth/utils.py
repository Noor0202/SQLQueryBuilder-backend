# backend/auth/utils.py
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
from passlib.exc import MissingBackendError
from passlib.utils import saslprep
from jose import jwt, JWTError, ExpiredSignatureError

from settings import settings
from logger import logger

# =========================
# PASSWORD CONTEXT (robust)
# =========================

_pwd_context: Optional[CryptContext] = None

def _init_password_context() -> CryptContext:
    global _pwd_context
    if _pwd_context:
        return _pwd_context

    # 1. Define configuration for all schemes we want to support
    # We always want pbkdf2 (as a fallback/legacy)
    schemes = ["pbkdf2_sha256"]
    
    # We place params in a single dict to pass to CryptContext
    context_params = {
        "pbkdf2_sha256__rounds": 30000,
        "bcrypt_sha256__rounds": settings.BCRYPT_SALT_ROUNDS
    }

    # 2. Check if bcrypt is available on this system
    bcrypt_working = False
    try:
        # Dry-run check for bcrypt
        test_ctx = CryptContext(schemes=["bcrypt_sha256"], **context_params)
        test_ctx.hash("test")
        bcrypt_working = True
    except Exception as e:
        logger.warning(f"Bcrypt backend check failed: {e}. Falling back to pbkdf2 only.")

    # 3. If bcrypt works, insert it at the START of the list (making it the default)
    if bcrypt_working:
        schemes.insert(0, "bcrypt_sha256")

    # 4. Create the final context with ALL supported schemes
    # passlib will use the first scheme for hashing new passwords,
    # but can verify passwords using ANY scheme in the list.
    try:
        ctx = CryptContext(
            schemes=schemes,
            deprecated="auto",
            **context_params
        )
        logger.info(f"Password context initialized. Supported schemes: {schemes}")
        _pwd_context = ctx
        return _pwd_context
    except Exception as exc:
        logger.exception("Critical error initializing password context.")
        raise exc

# initialize at import
pwd_context = _init_password_context()


# =========================
# PASSWORD HELPERS
# =========================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against the hashed password.
    Returns False on any error to avoid throwing during auth checks.
    """
    try:
        normalized = saslprep(plain_password) if isinstance(plain_password, str) else plain_password
        return pwd_context.verify(normalized, hashed_password)
    except Exception:
        logger.exception("Password verification failed.")
        return False


def get_password_hash(password: str) -> str:
    """
    Hash the provided password using the configured CryptContext.
    """
    try:
        normalized = saslprep(password) if isinstance(password, str) else password
        return pwd_context.hash(normalized)
    except Exception:
        logger.exception("Password hashing failed.")
        raise


# =========================
# JWT HELPERS (Keep existing code below)
# =========================

def create_access_token(data: Dict[str, Any]) -> str:
    try:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        payload = {
            **data,
            "iat": now,
            "exp": expire,
            "token_type": "access",
        }

        secret = settings.JWT_SECRET.get_secret_value() if hasattr(settings.JWT_SECRET, "get_secret_value") else settings.JWT_SECRET

        token = jwt.encode(payload, secret, algorithm=settings.ALGORITHM)
        return token
    except Exception:
        logger.exception("Access token creation failed.")
        raise


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        secret = settings.JWT_SECRET.get_secret_value() if hasattr(settings.JWT_SECRET, "get_secret_value") else settings.JWT_SECRET
        payload = jwt.decode(token, secret, algorithms=[settings.ALGORITHM])

        if payload.get("token_type") != "access":
            logger.warning("Token rejected due to invalid token_type.")
            return None

        return payload

    except ExpiredSignatureError:
        logger.warning("JWT token expired.")
        return None
    except JWTError:
        logger.warning("Invalid JWT token.")
        return None
    except Exception:
        logger.exception("Token decoding failed.")
        return None