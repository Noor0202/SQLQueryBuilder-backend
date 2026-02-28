# backend/auth/encryption.py
from cryptography.fernet import Fernet
import os

# --- CRITICAL FIX ---
# We use a FIXED key for development if the environment variable is missing.
# This prevents passwords from becoming unreadable when the server restarts.
# In production, you MUST set ENCRYPTION_KEY in your .env file.
DEFAULT_DEV_KEY = "epdZ6_u5F9x0_d3Hk9y7b4J5c2W1a8L0n3Q6r9v8x4z=" 

# Try to load from .env, otherwise use the stable dev key
_key = os.getenv("ENCRYPTION_KEY", DEFAULT_DEV_KEY)

try:
    # Initialize the cipher with the key
    cipher_suite = Fernet(_key.encode())
except Exception as e:
    print(f"Encryption Key Error: {e}")
    # Fallback to a random key only if the provided key is malformed (safety net)
    cipher_suite = Fernet(Fernet.generate_key())

def encrypt_password(password: str) -> str:
    """Encrypts a plain text password."""
    return cipher_suite.encrypt(password.encode()).decode()

def decrypt_password(encrypted_password: str) -> str:
    """Decrypts a password back to plain text."""
    try:
        return cipher_suite.decrypt(encrypted_password.encode()).decode()
    except Exception as e:
        # Log the specific error to help debugging
        print(f"Decryption failed. Reason: {e}")
        # Re-raise a clean error that the API can handle
        raise ValueError("Could not decrypt password. The encryption key has changed.")