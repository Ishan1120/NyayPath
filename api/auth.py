"""
NyayPath Authentication & Role-Based Access Control (RBAC) Module
Provides backend token signing, verification, institutional security,
and row-level authorization guards for campus proctorial governance.
"""

import os
import time
import hmac
import hashlib
import json
import base64
import secrets
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from fastapi import Request, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security_bearer = HTTPBearer(auto_error=False)

JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("SUPABASE_KEY") or "nyaypath-secure-proctor-secret-key-2026-auth"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Salt for verification keys and password hashing
AUTH_SALT = "nyaypath_verification_salt_2026"

class UserRole(str, Enum):
    STUDENT = "student"
    PROCTOR = "proctor"
    COMMITTEE_MEMBER = "committee_member"
    INSTITUTION_ADMIN = "institution_admin"
    PLATFORM_ADMIN = "platform_admin"

class AuthUser(BaseModel):
    user_id: str
    role: UserRole
    institution_id: str
    name: Optional[str] = "Authorized User"
    email: Optional[str] = None
    exp: Optional[int] = None

class LoginRequest(BaseModel):
    institution_id: str = "INST_DEFAULT"
    access_key: str
    role: UserRole = UserRole.PROCTOR
    email: Optional[str] = None

# =====================================================================
# Cryptographic Verification Key Utilities for Students & Anonymous Cases
# =====================================================================

def generate_secure_verification_key() -> str:
    """Generates a high-entropy secret verification token for student tracking."""
    return f"SEC-{secrets.token_hex(6).upper()}"

def hash_verification_key(key: str) -> str:
    """Computes a SHA-256 hash of a verification token with constant-time protection."""
    clean_key = (key or "").strip().upper()
    return hashlib.sha256(f"{AUTH_SALT}:{clean_key}".encode("utf-8")).hexdigest()

def verify_tracking_credential(provided_key: str, stored_hash: str) -> bool:
    """Constant-time verification of student access key against stored hash."""
    if not provided_key or not stored_hash:
        return False
    computed = hash_verification_key(provided_key)
    return hmac.compare_digest(computed, stored_hash)

# =====================================================================
# JWT Token Signing & Verification (HS256)
# =====================================================================

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def _b64url_decode(data: str) -> bytes:
    padding = '=' * (4 - (len(data) % 4)) if len(data) % 4 != 0 else ''
    return base64.urlsafe_b64decode((data + padding).encode('utf-8'))

def create_access_token(user: AuthUser, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a signed HS256 JWT access token with role and institution claims."""
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=JWT_EXPIRATION_HOURS))
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": user.user_id,
        "role": user.role.value,
        "institution_id": user.institution_id,
        "name": user.name,
        "email": user.email,
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "iss": "nyaypath-auth"
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

def decode_access_token(token: str) -> Optional[AuthUser]:
    """Validates JWT signature, expiration, and deserializes AuthUser."""
    if not token:
        return None
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts

        # Verify Signature
        expected_sig = hmac.new(
            JWT_SECRET.encode('utf-8'),
            f"{header_b64}.{payload_b64}".encode('utf-8'),
            hashlib.sha256
        ).digest()
        actual_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            # Try decoding with Supabase Key if different
            supabase_key = os.environ.get("SUPABASE_KEY")
            if supabase_key and supabase_key != JWT_SECRET:
                sup_sig = hmac.new(
                    supabase_key.encode('utf-8'),
                    f"{header_b64}.{payload_b64}".encode('utf-8'),
                    hashlib.sha256
                ).digest()
                if not hmac.compare_digest(sup_sig, actual_sig):
                    return None
            else:
                return None

        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))

        # Check Expiration
        exp = payload.get("exp")
        if exp and exp < int(datetime.now(timezone.utc).timestamp()):
            return None

        # Parse Role & Institution claims (supports custom NyayPath claims or Supabase app_metadata)
        app_meta = payload.get("app_metadata", {})
        raw_role = payload.get("role") or app_meta.get("role") or "student"
        raw_inst = payload.get("institution_id") or app_meta.get("institution_id") or "INST_DEFAULT"

        try:
            role_enum = UserRole(raw_role)
        except ValueError:
            role_enum = UserRole.STUDENT

        return AuthUser(
            user_id=payload.get("sub", "anon"),
            role=role_enum,
            institution_id=raw_inst,
            name=payload.get("name") or payload.get("user_metadata", {}).get("full_name") or "Authorized User",
            email=payload.get("email"),
            exp=exp
        )
    except Exception:
        return None

# =====================================================================
# Institutional Security & Passkey Verification Engine
# =====================================================================

INSTITUTION_CREDENTIALS: Dict[str, Dict[str, str]] = {
    "INST_DEFAULT": {
        "proctor_passkey": os.environ.get("PROCTOR_DEFAULT_KEY", "proctor-nyaypath-2026"),
        "committee_passkey": os.environ.get("COMMITTEE_DEFAULT_KEY", "committee-nyaypath-2026"),
        "admin_passkey": os.environ.get("INST_ADMIN_DEFAULT_KEY", "admin-nyaypath-2026")
    },
    "INST_UP_TECH": {
        "proctor_passkey": os.environ.get("PROCTOR_UP_TECH_KEY", "uptech-proctor-2026"),
        "committee_passkey": os.environ.get("COMMITTEE_UP_TECH_KEY", "uptech-committee-2026"),
        "admin_passkey": os.environ.get("INST_ADMIN_UP_TECH_KEY", "uptech-admin-2026")
    }
}

PLATFORM_ADMIN_SECRET = os.environ.get("CRON_SECRET", "nyaypath-platform-admin-master-key-2026")

def authenticate_institutional_user(payload: LoginRequest) -> Optional[AuthUser]:
    """
    Verifies institutional credentials on the backend.
    Enforces strict role validation so users cannot self-assign higher roles.
    """
    clean_inst = (payload.institution_id or "INST_DEFAULT").strip().upper()
    provided_key = (payload.access_key or "").strip()

    # Platform Admin validation
    if payload.role == UserRole.PLATFORM_ADMIN:
        cron_secret = os.environ.get("CRON_SECRET")
        if (cron_secret and provided_key == cron_secret) or provided_key == PLATFORM_ADMIN_SECRET:
            return AuthUser(
                user_id="usr_platform_admin",
                role=UserRole.PLATFORM_ADMIN,
                institution_id="*",
                name="Platform Administrator"
            )
        return None

    # Retrieve Institution Credential Profile
    inst_keys = INSTITUTION_CREDENTIALS.get(clean_inst)
    if not inst_keys:
        # Check environment dynamic institution key
        env_key = os.environ.get(f"INSTITUTION_KEY_{clean_inst}")
        if env_key and hmac.compare_digest(provided_key, env_key):
            return AuthUser(
                user_id=f"usr_proctor_{clean_inst.lower()}",
                role=payload.role,
                institution_id=clean_inst,
                name=f"{clean_inst} Proctorial Authority"
            )
        return None

    expected_key = None
    display_title = "Institutional Officer"

    if payload.role == UserRole.PROCTOR:
        expected_key = inst_keys.get("proctor_passkey")
        display_title = f"Chief Proctor ({clean_inst})"
    elif payload.role == UserRole.COMMITTEE_MEMBER:
        expected_key = inst_keys.get("committee_passkey")
        display_title = f"Grievance Committee Member ({clean_inst})"
    elif payload.role == UserRole.INSTITUTION_ADMIN:
        expected_key = inst_keys.get("admin_passkey")
        display_title = f"Institution Administrator ({clean_inst})"
    elif payload.role == UserRole.STUDENT:
        # Student login
        return AuthUser(
            user_id=f"stu_{secrets.token_hex(4)}",
            role=UserRole.STUDENT,
            institution_id=clean_inst,
            name="Student Complainant",
            email=payload.email
        )

    if expected_key and hmac.compare_digest(provided_key, expected_key):
        return AuthUser(
            user_id=f"usr_{payload.role.value}_{clean_inst.lower()}",
            role=payload.role,
            institution_id=clean_inst,
            name=display_title,
            email=payload.email
        )

    return None

# =====================================================================
# FastAPI Authorization Dependencies
# =====================================================================

def get_current_user_optional(request: Request) -> Optional[AuthUser]:
    """Extracts and verifies Bearer token if present in Authorization or custom header."""
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
            detail="Authentication required. Please log in with valid institutional credentials."
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
        return  # Platform admin has global oversight
    if user.institution_id != case_institution_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You are authorized for '{user.institution_id}' but this case belongs to '{case_institution_id}'."
        )
