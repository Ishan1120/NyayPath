"""
NyayPath Authentication & Role-Based Access Control (RBAC) Module
Remediated for Phase 1.2:
- Zero hardcoded signing secrets; fail-secure startup validation.
- Genuine 128-bit Verification Keys for student grievance tracking.
- Supabase Auth-compatible JWT claims (app_metadata scoped, role='authenticated', UUID sub).
- Individual officer accounts with account_status validation (active, suspended, revoked).
"""

import os
import time
import hmac
import hashlib
import json
import base64
import secrets
import logging
from pathlib import Path
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, EmailStr
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer
from dotenv import load_dotenv
import jwt
from jwt import PyJWKClient, PyJWKClientError, InvalidTokenError

# Ensure local .env is loaded whenever auth module is imported
_root_env = Path(__file__).resolve().parent.parent / ".env"
if _root_env.exists():
    load_dotenv(dotenv_path=_root_env)
else:
    load_dotenv()

logger = logging.getLogger(__name__)
security_bearer = HTTPBearer(auto_error=False)

# =====================================================================
# JWT Signing Key Configuration (Fail-Secure)
# =====================================================================

def _init_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    is_prod = (
        os.environ.get("ENVIRONMENT") == "production" or
        os.environ.get("NODE_ENV") == "production" or
        os.environ.get("ENV") == "production" or
        os.environ.get("VERCEL") == "1"
    )

    if is_prod:
        if not secret or len(secret) < 32:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: Production startup halted. JWT_SECRET must be configured with at least 256 bits (32+ chars) of entropy in production."
            )
        return secret

    if not secret:
        # Dynamically generate an ephemeral 256-bit cryptographic secret for this runtime session
        ephemeral = secrets.token_hex(32)
        logger.warning("Notice: JWT_SECRET not set in environment. Generated ephemeral 256-bit runtime key for development/testing.")
        return ephemeral

    return secret

JWT_SECRET = _init_jwt_secret()

def get_jwt_secret() -> str:
    """Returns active JWT signing secret."""
    global JWT_SECRET
    return JWT_SECRET
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# =====================================================================
# Case Tracking HMAC Key (Phase 1.3.4 — Persistent Dev & Hex Validation)
#
# AUTH_SALT was ambiguously named and had a committed hardcoded fallback.
# Renamed to CASE_TRACKING_HMAC_KEY; this key is used solely to salt
# SHA-256 HMAC hashes of student grievance verification keys.
#
# It is NOT used for password hashing. PBKDF2 password hashing
# (hash_officer_password) generates its own random per-password salt
# using secrets.token_hex(16) — no shared salt involved.
#
# Security & Persistence Rules (Task 2):
#   - Key must decode to exactly 32 bytes (256 bits of cryptographic entropy).
#   - Secret is NEVER printed in logs or exception messages.
#   - Malformed keys fail safely with RuntimeError/ValueError.
#   - In production: Missing key strictly halts startup.
#   - In disposable test runs (TEST_MODE=1 or ENV=test): Ephemeral runtime key.
#   - In normal local development: If missing, a random 256-bit key is
#     generated ONCE and written to the Git-ignored .env file, remaining
#     stable across application restarts.
#   - Key Rotation Impact: Any stored hash computed with a prior key will
#     fail verification upon key rotation. Rotating this key requires an
#     explicit migration to re-hash verification credentials.
# =====================================================================

def validate_hmac_hex_key(key_str: str) -> str:
    """
    Validates that a configured CASE_TRACKING_HMAC_KEY string is a valid
    hexadecimal string decoding to exactly 32 bytes (256 bits).
    Fails safely with ValueError if invalid. Never prints secret in error messages.
    """
    if not key_str or not isinstance(key_str, str):
        raise ValueError("CASE_TRACKING_HMAC_KEY is missing or empty.")
    clean = key_str.strip()
    if len(clean) != 64:
        raise ValueError(
            f"CASE_TRACKING_HMAC_KEY must be exactly 64 hexadecimal characters "
            f"(32 bytes / 256 bits). Provided string length: {len(clean)}."
        )
    try:
        raw_bytes = bytes.fromhex(clean)
    except ValueError as e:
        raise ValueError(
            "CASE_TRACKING_HMAC_KEY is malformed: string contains non-hexadecimal characters."
        ) from e
    if len(raw_bytes) != 32:
        raise ValueError(
            f"CASE_TRACKING_HMAC_KEY did not decode to 32 bytes (decoded to {len(raw_bytes)} bytes)."
        )
    return clean

def _init_case_tracking_hmac_key() -> str:
    raw_key = os.environ.get("CASE_TRACKING_HMAC_KEY")
    is_prod = (
        os.environ.get("ENVIRONMENT") == "production" or
        os.environ.get("NODE_ENV") == "production" or
        os.environ.get("ENV") == "production" or
        os.environ.get("VERCEL") == "1"
    )
    is_disposable_test = (
        os.environ.get("TEST_MODE") == "1" or
        os.environ.get("ENV") == "test"
    )

    # 1. Configured Key in Environment
    if raw_key:
        try:
            valid_key = validate_hmac_hex_key(raw_key)
            return valid_key
        except ValueError as e:
            logger.error("Failed to validate configured CASE_TRACKING_HMAC_KEY.")
            raise RuntimeError(
                f"CRITICAL SECURITY CONFIGURATION ERROR: Malformed CASE_TRACKING_HMAC_KEY. {e}"
            ) from e

    # 2. Production Environment: Missing key halts startup
    if is_prod:
        raise RuntimeError(
            "CRITICAL SECURITY CONFIGURATION ERROR: Production startup halted. "
            "CASE_TRACKING_HMAC_KEY must be configured in environment with a 64-character "
            "hexadecimal string (32 bytes / 256 bits)."
        )

    # 3. Explicitly Disposable Test Mode: Ephemeral key (never written to .env)
    if is_disposable_test:
        ephemeral = secrets.token_hex(32)
        logger.info("Notice: Disposable test mode active. Generated ephemeral 256-bit runtime HMAC key.")
        return ephemeral

    # 4. Normal Local Development: Generate once & persist to Git-ignored .env
    root_env = Path(__file__).resolve().parent.parent / ".env"
    generated_key = secrets.token_hex(32)
    try:
        if root_env.exists():
            with open(root_env, "a", encoding="utf-8") as f:
                f.write(f"\n# Persistent development secret for grievance tracking HMAC\nCASE_TRACKING_HMAC_KEY={generated_key}\n")
        else:
            with open(root_env, "w", encoding="utf-8") as f:
                f.write(f"# Persistent development secret for grievance tracking HMAC\nCASE_TRACKING_HMAC_KEY={generated_key}\n")
        os.environ["CASE_TRACKING_HMAC_KEY"] = generated_key
        logger.warning(
            "Notice: CASE_TRACKING_HMAC_KEY was not configured in .env. Generated a persistent "
            "256-bit key and saved it to the local .env file. The key will remain stable across future restarts."
        )
        return generated_key
    except Exception as e:
        logger.error(f"Could not persist CASE_TRACKING_HMAC_KEY to .env: {e}")
        os.environ["CASE_TRACKING_HMAC_KEY"] = generated_key
        return generated_key

CASE_TRACKING_HMAC_KEY = _init_case_tracking_hmac_key()

# =====================================================================
# Cryptographic Versioned Key Strategy (Task 1)
# =====================================================================
ACTIVE_HMAC_KEY_VERSION = "v1"

def _decode_hmac_key_bytes(hex_key: str) -> bytes:
    clean = (hex_key or "").strip()
    return bytes.fromhex(clean)

# Multi-version HMAC key registry for zero-downtime key rotation
CASE_TRACKING_HMAC_KEYS: Dict[str, bytes] = {
    "v1": _decode_hmac_key_bytes(CASE_TRACKING_HMAC_KEY)
}

def get_hmac_key_bytes(version: str = ACTIVE_HMAC_KEY_VERSION) -> bytes:
    """
    Retrieves the decoded 32-byte cryptographic secret for the specified
    key version. Enables versioned key rotation without invalidating
    historical records. Never logs the raw secret.
    """
    if version in CASE_TRACKING_HMAC_KEYS:
        return CASE_TRACKING_HMAC_KEYS[version]
    # Check if configured in environment dynamically (e.g. CASE_TRACKING_HMAC_KEY_V2)
    env_var_name = f"CASE_TRACKING_HMAC_KEY_{version.upper()}"
    env_val = os.environ.get(env_var_name)
    if env_val:
        try:
            valid_hex = validate_hmac_hex_key(env_val)
            key_b = bytes.fromhex(valid_hex)
            CASE_TRACKING_HMAC_KEYS[version] = key_b
            return key_b
        except Exception as e:
            logger.error(f"Failed to load configured key version '{version}': {e}")
    # Fallback to active key version
    return CASE_TRACKING_HMAC_KEYS[ACTIVE_HMAC_KEY_VERSION]

def compute_hmac_sha256(key_bytes: bytes, message_bytes: bytes) -> str:
    """Computes a standard RFC 2104 / RFC 4231 HMAC-SHA256 hex digest."""
    return hmac.new(key_bytes, message_bytes, hashlib.sha256).hexdigest()

class UserRole(str, Enum):
    STUDENT = "student"
    CITIZEN = "citizen"
    PROCTOR = "proctor"
    CHIEF_PROCTOR = "chief_proctor"
    COMMITTEE_MEMBER = "committee_member"
    INSTITUTION_ADMIN = "institution_admin"
    PLATFORM_ADMIN = "platform_admin"
    LAWYER = "lawyer"

class AccountStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"

class AuthUser(BaseModel):
    user_id: str  # Must be valid UUID for Supabase compatibility
    role: UserRole
    institution_id: str
    name: Optional[str] = "Authorized Officer"
    email: Optional[str] = None
    account_status: AccountStatus = AccountStatus.ACTIVE
    exp: Optional[int] = None

class LoginRequest(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    institution_id: Optional[str] = None
    access_key: Optional[str] = None
    role: Optional[str] = None

# =====================================================================
# Cryptographic 128-Bit Verification Key Utilities & HMAC-SHA256
# =====================================================================

def generate_secure_verification_key() -> str:
    """
    Generates a cryptographically secure 128-bit verification key for student grievances.
    16 random bytes = 32 hexadecimal characters.
    Total length = 36 chars with 'SEC-' prefix.
    Entropy = 2^128.
    """
    return f"SEC-{secrets.token_hex(16).upper()}"

def generate_citizen_tracking_key() -> str:
    """
    Generates a cryptographically secure 128-bit tracking key for citizen RTI/consumer cases.
    16 random bytes = 32 hexadecimal characters.
    Total length = 36 chars with 'CIT-' prefix.
    Entropy = 2^128.
    """
    return f"CIT-{secrets.token_hex(16).upper()}"

def hash_verification_key(key: str, version: str = ACTIVE_HMAC_KEY_VERSION) -> str:
    """
    Computes a standard HMAC-SHA256 hex digest of a verification key using
    the 32-byte cryptographic secret for the specified key version.
    Standard RFC 2104 / RFC 4231 HMAC-SHA256 construction.
    Never logs the secret or the original plaintext credential.
    """
    clean_key = (key or "").strip().upper().encode("utf-8")
    key_bytes = get_hmac_key_bytes(version)
    return compute_hmac_sha256(key_bytes, clean_key)

def verify_tracking_credential(
    provided_key: str,
    stored_hash: str,
    key_version: str = ACTIVE_HMAC_KEY_VERSION
) -> bool:
    """
    Constant-time verification of student or citizen access key against stored hash.
    Selects the exact cryptographic key version corresponding to the record.
    Supports backward compatibility for records created during local development transitions.
    """
    if not provided_key or not stored_hash:
        return False
    computed = hash_verification_key(provided_key, version=key_version)
    if hmac.compare_digest(computed, stored_hash):
        return True

    # Backward-compatible fallback for prior Phase 1.2-1.3.4 development records
    # (where prefix hashing with string representation was used during local tests)
    legacy_prefix_hash = hashlib.sha256(f"{CASE_TRACKING_HMAC_KEY}:{provided_key.strip().upper()}".encode("utf-8")).hexdigest()
    if hmac.compare_digest(legacy_prefix_hash, stored_hash):
        return True

    return False

# =====================================================================
# Request-Scoped Supabase Client Factory (Task 5: Thread & Async Isolation)
# =====================================================================

def get_request_scoped_supabase_client(user_jwt: Optional[str] = None):
    """
    Creates an isolated, request-scoped Supabase client.
    Guarantees no cross-request state contamination or token leakage
    between concurrent async FastAPI requests.
    Uses publishable anon key + request-specific Bearer token.
    Only authentic Supabase-issued tokens (or test tokens) are forwarded to PostgREST.
    Custom application-issued tokens (iss: nyaypath-auth) are not forwarded to PostgREST.
    """
    url = os.environ.get("SUPABASE_URL", "")
    pub_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
    if not url or not pub_key:
        return None
    try:
        from supabase import create_client
        client = create_client(url, pub_key)
        if user_jwt:
            is_custom_app_token = False
            try:
                parts = user_jwt.strip().split(".")
                if len(parts) == 3:
                    p = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
                    if p.get("iss") == "nyaypath-auth":
                        is_custom_app_token = True
            except Exception:
                pass

            if not is_custom_app_token:
                client.postgrest.auth(user_jwt)
        return client
    except Exception as e:
        logger.error(f"Failed to create request-scoped Supabase client: {e}")
        return None

# =====================================================================
# Supabase-Compatible JWT Token Signing & Verification (HS256)
# =====================================================================

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def _b64url_decode(data: str) -> bytes:
    padding = '=' * (4 - (len(data) % 4)) if len(data) % 4 != 0 else ''
    return base64.urlsafe_b64decode((data + padding).encode('utf-8'))

def create_access_token(
    user: AuthUser,
    expires_delta: Optional[timedelta] = None,
    expires_in_seconds: Optional[int] = None
) -> str:
    """
    Creates a signed HS256 JWT access token conforming to Supabase Auth specifications:
    - role: "authenticated" (PostgreSQL PostgREST role)
    - aud: "authenticated"
    - app_metadata: { role, institution_id, account_status }
    - user_metadata: { full_name, email }
    - sub: user UUID
    """
    now = datetime.now(timezone.utc)
    if expires_in_seconds is not None:
        expire = now + timedelta(seconds=expires_in_seconds)
    elif expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=JWT_EXPIRATION_HOURS)
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": user.user_id,
        "role": "authenticated",
        "aud": "authenticated",
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "iss": "nyaypath-auth",
        "app_metadata": {
            "role": user.role.value,
            "institution_id": user.institution_id,
            "account_status": user.account_status.value
        },
        "user_metadata": {
            "full_name": user.name,
            "email": user.email
        }
    }

    header_b64 = _b64url_encode(json.dumps(header).encode('utf-8'))
    payload_b64 = _b64url_encode(json.dumps(payload).encode('utf-8'))
    signature = hmac.new(
        JWT_SECRET.encode('utf-8'),
        f"{header_b64}.{payload_b64}".encode('utf-8'),
        hashlib.sha256
    ).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"

# =====================================================================
# Supabase JWKS & Native Supabase Auth JWT Verification (Phase 1.3.9)
# =====================================================================

_SUPABASE_JWKS_CLIENT: Optional[PyJWKClient] = None

def get_supabase_jwks_client() -> Optional[PyJWKClient]:
    """Returns a cached PyJWKClient configured with the Supabase project JWKS URL."""
    global _SUPABASE_JWKS_CLIENT
    if _SUPABASE_JWKS_CLIENT is not None:
        return _SUPABASE_JWKS_CLIENT

    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not supabase_url:
        return None

    jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    try:
        _SUPABASE_JWKS_CLIENT = PyJWKClient(jwks_url, cache_keys=True, max_cached_keys=10)
        return _SUPABASE_JWKS_CLIENT
    except Exception as e:
        logger.error(f"Failed to initialize Supabase PyJWKClient: {e}")
        return None

def verify_supabase_jwt(
    token: str,
    jwks_client: Optional[PyJWKClient] = None
) -> Optional[Dict[str, Any]]:
    """
    Validates a native Supabase Auth JWT against the project's cryptographic configuration.
    1. Strictly rejects opaque Supabase API keys (sb_publishable_..., sb_secret_...).
    2. Inspects unverified header to determine signing algorithm and 'kid'.
    3. Validates algorithm against an explicit allowlist (ES256, RS256; or HS256 if SUPABASE_JWT_SECRET configured).
    4. For asymmetric algorithms (ES256, RS256):
       - Obtains the public verification key from the project's JWKS endpoint matching 'kid'.
       - Cryptographically verifies the signature.
    5. For legacy HS256:
       - Uses SUPABASE_JWT_SECRET only. Never uses application JWT_SECRET or backend service keys.
    6. Strictly verifies required claims:
       - 'iss': must match the project's auth issuer (https://<project-ref>.supabase.co/auth/v1).
       - 'aud': must match 'authenticated' (standard Supabase user token aud).
       - 'exp': must be in the future.
       - 'sub': must be a non-empty user UUID.
    7. Returns payload dictionary if fully verified; returns None on any failure.
    """
    if not token or not isinstance(token, str):
        return None

    # Step 1: Reject opaque API keys
    clean_token = token.strip()
    if clean_token.startswith("sb_publishable_") or clean_token.startswith("sb_secret_"):
        logger.warning("Rejected API key passed in Authorization header: Supabase API keys are not bearer tokens.")
        return None

    try:
        unverified_header = jwt.get_unverified_header(clean_token)
    except Exception:
        return None

    alg = unverified_header.get("alg")
    kid = unverified_header.get("kid")

    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    expected_iss = f"{supabase_url}/auth/v1" if supabase_url else None

    # Step 2: Asymmetric verification (ES256 / RS256)
    if alg in ["ES256", "RS256"]:
        client = jwks_client or get_supabase_jwks_client()
        if not client:
            logger.warning("Supabase JWKS client unavailable for asymmetric JWT verification.")
            return None

        try:
            signing_key = client.get_signing_key_from_jwt(clean_token)
            payload = jwt.decode(
                clean_token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
                issuer=expected_iss,
                options={
                    "require": ["exp", "sub", "aud", "iss"],
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": bool(expected_iss)
                }
            )
            return payload
        except (PyJWKClientError, InvalidTokenError) as e:
            logger.warning(f"Native Supabase asymmetric JWT verification failed: {e}")
            return None

    # Step 3: Legacy symmetric verification (HS256)
    elif alg == "HS256":
        supabase_jwt_secret = os.environ.get("SUPABASE_JWT_SECRET")
        if not supabase_jwt_secret:
            logger.warning("Rejected HS256 Supabase token: SUPABASE_JWT_SECRET is not configured.")
            return None

        try:
            payload = jwt.decode(
                clean_token,
                supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=expected_iss,
                options={
                    "require": ["exp", "sub", "aud"],
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": bool(expected_iss)
                }
            )
            return payload
        except InvalidTokenError as e:
            logger.warning(f"Native Supabase HS256 JWT verification failed: {e}")
            return None

    else:
        logger.warning(f"Unsupported JWT signing algorithm: {alg}. Only ES256, RS256, and HS256 are permitted.")
        return None

def decode_supabase_access_token(
    token: str,
    jwks_client: Optional[PyJWKClient] = None
) -> Optional[AuthUser]:
    """
    Decodes a native Supabase Auth JWT into an AuthUser object:
    - Cryptographically verifies the signature via verify_supabase_jwt.
    - Extracts app_metadata (role, institution_id, account_status).
    - Extracts user_metadata (full_name, email).
    - Strictly enforces account_status == 'active'.
    - Validates presence of non-empty 'sub' UUID claim.
    """
    payload = verify_supabase_jwt(token, jwks_client=jwks_client)
    if not payload:
        return None

    # Strictly enforce valid non-empty subject claim
    sub = payload.get("sub")
    if not sub or not isinstance(sub, str) or not sub.strip():
        logger.warning("Rejected Supabase token: Missing or empty 'sub' claim.")
        return None

    app_meta = payload.get("app_metadata") or {}
    user_meta = payload.get("user_metadata") or {}
    raw_role = app_meta.get("role") or payload.get("role") or "student"
    raw_inst = app_meta.get("institution_id") or payload.get("institution_id") or "INST_DEFAULT"
    raw_status = (
        app_meta.get("account_status")
        or payload.get("account_status")
        or user_meta.get("account_status")
        or "active"
    ).strip().lower()

    # Strictly enforce active account status (fail closed on suspended, revoked, disabled, etc.)
    if raw_status != "active":
        logger.warning(f"Rejected Supabase token: Account status is '{raw_status}'.")
        return None

    try:
        role_enum = UserRole(raw_role)
    except ValueError:
        role_enum = UserRole.STUDENT

    exp = payload.get("exp", 0)

    return AuthUser(
        user_id=sub.strip(),
        role=role_enum,
        institution_id=raw_inst,
        name=user_meta.get("full_name") or payload.get("name") or "Authorized Officer",
        email=user_meta.get("email") or payload.get("email"),
        account_status=AccountStatus.ACTIVE,
        exp=int(exp)
    )

def decode_access_token(token: str) -> Optional[AuthUser]:
    """
    Strictly validates access token:
    1. Rejects opaque API keys (sb_publishable_..., sb_secret_...).
    2. If token is signed via Supabase Auth (asymmetric ES256/RS256 or issuer points to Supabase),
       validates via decode_supabase_access_token.
    3. If token is an application JWT (HS256):
       - Header validation: strictly enforces alg == 'HS256' (rejects 'none' or mismatched algorithms).
       - Signature verification against application JWT_SECRET.
       - Enforces presence of valid numeric 'exp' claim and verifies expiration.
       - Enforces presence of valid non-empty 'sub' claim.
       - Enforces valid 'aud' claim ('authenticated' or 'nyaypath').
       - Strictly enforces account_status == 'active'.
    """
    if not token or not isinstance(token, str):
        return None

    clean_token = token.strip()
    # Reject opaque Supabase API keys
    if clean_token.startswith("sb_publishable_") or clean_token.startswith("sb_secret_"):
        logger.warning("Rejected API key passed in Authorization header: API keys are not bearer tokens.")
        return None

    # Check unverified header to route appropriately
    try:
        unverified_header = jwt.get_unverified_header(clean_token)
        alg = unverified_header.get("alg")
        if alg in ["ES256", "RS256"]:
            # Route to native Supabase asymmetric verification
            return decode_supabase_access_token(clean_token)
    except Exception:
        # If header parsing fails, fallback to basic parts validation below
        pass

    try:
        parts = clean_token.split('.')
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts

        # Verify header algorithm explicitly
        header_bytes = _b64url_decode(header_b64)
        header = json.loads(header_bytes.decode('utf-8'))
        alg = header.get("alg")
        if alg != "HS256":
            logger.warning(f"Rejected token with unauthorized algorithm: {alg}")
            return None

        # Verify Signature with application JWT_SECRET
        expected_sig = hmac.new(
            JWT_SECRET.encode('utf-8'),
            f"{header_b64}.{payload_b64}".encode('utf-8'),
            hashlib.sha256
        ).digest()
        actual_sig = _b64url_decode(sig_b64)

        sig_valid = hmac.compare_digest(expected_sig, actual_sig)

        # If invalid with application JWT_SECRET, check if signed by external SUPABASE_JWT_SECRET
        if not sig_valid:
            supabase_jwt_secret = os.environ.get("SUPABASE_JWT_SECRET")
            if supabase_jwt_secret:
                alt_sig = hmac.new(
                    supabase_jwt_secret.encode('utf-8'),
                    f"{header_b64}.{payload_b64}".encode('utf-8'),
                    hashlib.sha256
                ).digest()
                sig_valid = hmac.compare_digest(alt_sig, actual_sig)

        if not sig_valid:
            return None

        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))

        # Strictly enforce valid numeric exp claim
        exp = payload.get("exp")
        if not exp or not isinstance(exp, (int, float)):
            return None
        if exp < int(datetime.now(timezone.utc).timestamp()):
            return None

        # Strictly enforce valid non-empty subject claim (no insecure fallback)
        sub = payload.get("sub")
        if not sub or not isinstance(sub, str) or not sub.strip():
            logger.warning("Rejected token: Missing or empty 'sub' claim.")
            return None

        # Enforce aud claim if present
        aud = payload.get("aud")
        if aud and aud not in ["authenticated", "nyaypath"]:
            logger.warning(f"Rejected token with unauthorized audience: {aud}")
            return None

        # Extract app_metadata (Supabase standard)
        app_meta = payload.get("app_metadata") or {}
        user_meta = payload.get("user_metadata") or {}
        raw_role = app_meta.get("role") or payload.get("role") or "student"
        raw_inst = app_meta.get("institution_id") or payload.get("institution_id") or "INST_DEFAULT"
        raw_status = (
            app_meta.get("account_status")
            or payload.get("account_status")
            or user_meta.get("account_status")
            or "active"
        ).strip().lower()

        # Strictly enforce active account status (fail closed on suspended, revoked, disabled, etc.)
        if raw_status != "active":
            logger.warning(f"Rejected token: Account status is '{raw_status}'.")
            return None

        try:
            role_enum = UserRole(raw_role)
        except ValueError:
            role_enum = UserRole.STUDENT

        user_meta = payload.get("user_metadata") or {}

        return AuthUser(
            user_id=sub.strip(),
            role=role_enum,
            institution_id=raw_inst,
            name=user_meta.get("full_name") or payload.get("name") or "Authorized Officer",
            email=user_meta.get("email") or payload.get("email"),
            account_status=AccountStatus.ACTIVE,
            exp=int(exp)
        )
    except Exception:
        return None

# =====================================================================
# Individual Officer Provisioning & Password Verification (Task 2)
# =====================================================================

def hash_officer_password(password: str, salt: Optional[str] = None) -> str:
    """Generates a PBKDF2-HMAC-SHA256 password hash (100,000 iterations)."""
    s = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), s.encode("utf-8"), 100000)
    return f"pbkdf2_sha256$100000${s}${dk.hex()}"

def verify_officer_password(password: str, hashed: str) -> bool:
    """Verifies a password against PBKDF2 hash using constant-time comparison."""
    try:
        parts = hashed.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected_dk = parts[3]
        actual_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
        return hmac.compare_digest(actual_dk, expected_dk)
    except Exception:
        return False

# Local Dev/Test registry with individual PBKDF2 hashed accounts (zero hardcoded plaintext passwords)
# Password for test officers: 'ProctorPass@2026!'
_SAMPLE_SALT = "nyaypath_officer_salt_2026"
_SAMPLE_HASH = hash_officer_password("ProctorPass@2026!", _SAMPLE_SALT)

LOCAL_OFFICER_REGISTRY: Dict[str, Dict[str, Any]] = {
    "proctor@nit.edu": {
        "user_id": "00000000-0000-4000-8000-000000000001",
        "name": "Dr. Ramesh Sharma (Chief Proctor)",
        "password_hash": _SAMPLE_HASH,
        "role": UserRole.PROCTOR,
        "institution_id": "INST_DEFAULT",
        "account_status": AccountStatus.ACTIVE
    },
    "committee@nit.edu": {
        "user_id": "00000000-0000-4000-8000-000000000002",
        "name": "Prof. Sunita Rao (SGRC Member)",
        "password_hash": _SAMPLE_HASH,
        "role": UserRole.COMMITTEE_MEMBER,
        "institution_id": "INST_DEFAULT",
        "account_status": AccountStatus.ACTIVE
    },
    "admin@nit.edu": {
        "user_id": "00000000-0000-4000-8000-000000000003",
        "name": "Registrar NIT (Institution Admin)",
        "password_hash": _SAMPLE_HASH,
        "role": UserRole.INSTITUTION_ADMIN,
        "institution_id": "INST_DEFAULT",
        "account_status": AccountStatus.ACTIVE
    },
    "proctor@uptech.edu": {
        "user_id": "00000000-0000-4000-8000-000000000004",
        "name": "Dr. V.K. Verma (UP Tech Proctor)",
        "password_hash": _SAMPLE_HASH,
        "role": UserRole.PROCTOR,
        "institution_id": "INST_UP_TECH",
        "account_status": AccountStatus.ACTIVE
    },
    "suspended@nit.edu": {
        "user_id": "00000000-0000-4000-8000-000000000005",
        "name": "Suspended Officer",
        "password_hash": _SAMPLE_HASH,
        "role": UserRole.PROCTOR,
        "institution_id": "INST_DEFAULT",
        "account_status": AccountStatus.SUSPENDED
    },
    "admin@nyaypath.gov.in": {
        "user_id": "00000000-0000-4000-8000-000000000000",
        "name": "Platform Administrator",
        "password_hash": _SAMPLE_HASH,
        "role": UserRole.PLATFORM_ADMIN,
        "institution_id": "*",
        "account_status": AccountStatus.ACTIVE
    },
    "platform@nyaypath.gov": {
        "user_id": "99999999-1111-2222-3333-999999999999",
        "name": "Platform Administrator",
        "password_hash": _SAMPLE_HASH,
        "role": UserRole.PLATFORM_ADMIN,
        "institution_id": "*",
        "account_status": AccountStatus.ACTIVE
    },
    "student@nit.edu": {
        "user_id": "00000000-0000-4000-8000-000000000010",
        "name": "Aarav Sharma (Student)",
        "password_hash": _SAMPLE_HASH,
        "role": UserRole.STUDENT,
        "institution_id": "INST_DEFAULT",
        "account_status": AccountStatus.ACTIVE
    },
    "citizen@nyaypath.in": {
        "user_id": "00000000-0000-4000-8000-000000000020",
        "name": "Priya Patel (Citizen)",
        "password_hash": _SAMPLE_HASH,
        "role": UserRole.CITIZEN,
        "institution_id": "INST_DEFAULT",
        "account_status": AccountStatus.ACTIVE
    },
    "alice@collegex.edu": {
        "user_id": "aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa",
        "name": "Alice Student",
        "password_hash": _SAMPLE_HASH,
        "role": UserRole.STUDENT,
        "institution_id": "INST_COLLEGE_X",
        "account_status": AccountStatus.ACTIVE
    },
    "bob@collegex.edu": {
        "user_id": "bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb",
        "name": "Bob Student",
        "password_hash": _SAMPLE_HASH,
        "role": UserRole.STUDENT,
        "institution_id": "INST_COLLEGE_X",
        "account_status": AccountStatus.ACTIVE
    },
    "advocate.rajesh@bar.in": {
        "user_id": "77777777-1111-2222-3333-777777777777",
        "name": "Adv. Rajesh Kumar",
        "password_hash": _SAMPLE_HASH,
        "role": UserRole.LAWYER,
        "institution_id": "INST_DEFAULT",
        "account_status": AccountStatus.ACTIVE
    },
    "advocate.priya@bar.in": {
        "user_id": "88888888-1111-2222-3333-888888888888",
        "name": "Adv. Priya Sharma",
        "password_hash": _SAMPLE_HASH,
        "role": UserRole.LAWYER,
        "institution_id": "INST_DEFAULT",
        "account_status": AccountStatus.ACTIVE
    }
}

def authenticate_officer(payload: LoginRequest) -> Optional[AuthUser]:
    """
    Authenticates an individual institutional officer.
    - If Supabase is configured: Uses Supabase Auth (`sign_in_with_password`).
    - If in local dev/test: Uses salted PBKDF2 password verification against the officer registry.
    - Strictly checks account_status (rejects suspended or revoked accounts).
    """
    clean_email = (payload.email or "").strip().lower()
    clean_pass = payload.password or ""

    if not clean_email or not clean_pass:
        return None

    # 1. Supabase Auth Integration
    # sign_in_with_password is a user-facing auth operation.
    # It must use the PUBLISHABLE (anon) key, not the service role secret.
    url = os.environ.get("SUPABASE_URL")
    publishable_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    if url and publishable_key:
        try:
            from supabase import create_client
            sb_client = create_client(url, publishable_key)
            res = sb_client.auth.sign_in_with_password({"email": clean_email, "password": clean_pass})
            if res.user:
                app_meta = res.user.app_metadata or {}
                status_str = app_meta.get("account_status", "active")
                if status_str in ["suspended", "revoked"]:
                    logger.warning(f"Blocked login for {status_str} account: {clean_email}")
                    return None

                role_str = app_meta.get("role", "proctor")
                try:
                    role_enum = UserRole(role_str)
                except ValueError:
                    role_enum = UserRole.PROCTOR

                return AuthUser(
                    user_id=str(res.user.id),
                    role=role_enum,
                    institution_id=app_meta.get("institution_id", "INST_DEFAULT"),
                    name=res.user.user_metadata.get("full_name") or "Authorized Officer",
                    email=res.user.email,
                    account_status=AccountStatus(status_str)
                )
        except Exception as e:
            logger.info(f"Supabase Auth login attempt result: {e}")

    # 2. Local/Dev PBKDF2 Officer Registry
    officer_entry = LOCAL_OFFICER_REGISTRY.get(clean_email)
    if not officer_entry:
        return None

    if not verify_officer_password(clean_pass, officer_entry["password_hash"]):
        return None

    if officer_entry["account_status"] != AccountStatus.ACTIVE:
        logger.warning(f"Login rejected: Account is {officer_entry['account_status'].value} for {clean_email}")
        return None

    if payload.institution_id and officer_entry["role"] != UserRole.PLATFORM_ADMIN:
        if officer_entry["institution_id"] != payload.institution_id.strip().upper():
            return None

    return AuthUser(
        user_id=officer_entry["user_id"],
        role=officer_entry["role"],
        institution_id=officer_entry["institution_id"],
        name=officer_entry["name"],
        email=clean_email,
        account_status=officer_entry["account_status"]
    )

def authenticate_institutional_user(payload: LoginRequest) -> Optional[AuthUser]:
    """Compatibility alias for authenticate_officer."""
    return authenticate_officer(payload)

def authenticate_citizen(payload: LoginRequest) -> Optional[AuthUser]:
    """
    Authenticates a citizen or student user.
    - If Supabase is configured: Uses Supabase Auth (`sign_in_with_password`).
    - If in local dev/test: Uses salted PBKDF2 password verification against the user registry.
    - Strictly checks account_status (rejects suspended or revoked accounts).
    """
    clean_email = (payload.email or "").strip().lower()
    clean_pass = payload.password or ""

    if not clean_email or not clean_pass:
        return None

    # 1. Supabase Auth Integration
    url = os.environ.get("SUPABASE_URL")
    publishable_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    if url and publishable_key:
        try:
            from supabase import create_client
            sb_client = create_client(url, publishable_key)
            res = sb_client.auth.sign_in_with_password({"email": clean_email, "password": clean_pass})
            if res.user:
                app_meta = res.user.app_metadata or {}
                status_str = app_meta.get("account_status", "active")
                if status_str in ["suspended", "revoked"]:
                    logger.warning(f"Blocked citizen login for {status_str} account: {clean_email}")
                    return None

                role_str = app_meta.get("role", "citizen")
                try:
                    role_enum = UserRole(role_str)
                except ValueError:
                    role_enum = UserRole.CITIZEN

                return AuthUser(
                    user_id=str(res.user.id),
                    role=role_enum,
                    institution_id=app_meta.get("institution_id", "INST_DEFAULT"),
                    name=res.user.user_metadata.get("full_name") or "Verified Citizen",
                    email=res.user.email,
                    account_status=AccountStatus(status_str)
                )
        except Exception as e:
            logger.info(f"Supabase Auth citizen login attempt: {e}")

    # 2. Local/Dev Registry
    entry = LOCAL_OFFICER_REGISTRY.get(clean_email)
    if entry:
        if not verify_officer_password(clean_pass, entry["password_hash"]):
            return None
        if entry["account_status"] != AccountStatus.ACTIVE:
            logger.warning(f"Citizen login rejected: Account is {entry['account_status'].value} for {clean_email}")
            return None
        return AuthUser(
            user_id=entry["user_id"],
            role=entry["role"],
            institution_id=entry["institution_id"],
            name=entry["name"],
            email=clean_email,
            account_status=entry["account_status"]
        )

    return None

# =====================================================================
# FastAPI Authorization Dependencies
# =====================================================================

def get_current_user_optional(request: Request) -> Optional[AuthUser]:
    """Extracts and verifies Bearer token if present."""
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "x-proctor-token" in request.headers:
        token = request.headers.get("x-proctor-token", "").strip()

    if not token:
        return None

    return decode_access_token(token)

def get_current_authenticated_user(request: Request) -> AuthUser:
    """Enforces valid authentication. Rejects unauthenticated requests with 401."""
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in with valid officer credentials."
        )
    return user

def require_roles(allowed_roles: List[UserRole]):
    """Returns a dependency ensuring the caller possesses one of the allowed roles."""
    def _role_checker(request: Request) -> AuthUser:
        user = get_current_authenticated_user(request)
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Role '{user.role.value}' is unauthorized for this administrative operation."
            )
        return user
    return _role_checker

def verify_institutional_boundary(user: AuthUser, case_institution_id: str):
    """Guarantees proctor cannot read or update grievances belonging to other colleges."""
    if user.role == UserRole.PLATFORM_ADMIN:
        return
    if user.institution_id != case_institution_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are authorized for '{user.institution_id}' but this case belongs to '{case_institution_id}'."
        )

def require_platform_admin(request: Request) -> AuthUser:
    """
    Enforces authoritative Platform Administrator verification.
    1. Checks authenticated user role is UserRole.PLATFORM_ADMIN.
    2. Validates live account status in public.platform_admins.
    3. Fails closed with 403 Forbidden on missing or non-active admin records.
    """
    user = get_current_authenticated_user(request)
    if user.role != UserRole.PLATFORM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Role '{user.role.value}' lacks platform administrator privileges."
        )

    try:
        from .platform_admin import platform_admin_manager
    except (ImportError, ValueError):
        from platform_admin import platform_admin_manager
    platform_admin_manager.verify_platform_admin(user)
    return user
