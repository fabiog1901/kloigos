import json
import os
import secrets
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from hmac import compare_digest
from hmac import new as hmac_new
from typing import Any

import jwt
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    Security,
    status,
)
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyCookie, APIKeyHeader

from .dep import get_repo
from .models import Event, KloigosRole, LogMsg
from .repos.base import BaseRepo
from .util import (
    as_bool,
    decrypt_api_key_secret,
    request_id_ctx,
    safe_csv_set,
    safe_json_string_dict,
    safe_next_path,
    validate_api_key_crypto_config,
)


def _claim_groups(claim_value: Any) -> set[str]:
    """Normalize a groups claim into a trimmed set of group names."""
    if claim_value is None:
        return set()
    if isinstance(claim_value, str):
        return (
            safe_csv_set(claim_value)
            if "," in claim_value
            else ({claim_value.strip()} if claim_value.strip() else set())
        )
    if isinstance(claim_value, (list, tuple, set)):
        return {str(v).strip() for v in claim_value if str(v).strip()}
    return set()


def _claims_groups(
    claims: dict[str, Any], groups_claim_name: str = "groups"
) -> set[str]:
    """Extract the configured groups claim from a JWT or synthetic claims payload."""
    return _claim_groups(claims.get(groups_claim_name))


def _jsonable_role_groups(role_groups: dict[str, Any]) -> dict[str, list[str]]:
    """Convert role-to-groups mappings into JSON-friendly sorted lists."""
    normalized: dict[str, list[str]] = {}
    for role_name, groups in role_groups.items():
        normalized[str(role_name)] = sorted(_claim_groups(groups))
    return normalized


def _cookie_secure_default() -> bool:
    """Return the configured secure-cookie default for OIDC session cookies."""
    return as_bool(os.getenv("OIDC_COOKIE_SECURE"), default=False)


def _api_key_signature_ttl_seconds() -> int:
    """Return the maximum allowed age for signed API key requests."""
    try:
        return max(0, int(os.getenv("API_KEY_SIGNATURE_TTL_SECONDS", "300")))
    except ValueError:
        return 300


def _parse_api_key_timestamp(timestamp: str) -> datetime:
    """Parse either epoch seconds or an ISO-8601 timestamp into UTC."""
    raw_timestamp = timestamp.strip()
    if not raw_timestamp:
        raise ValueError("empty timestamp")

    try:
        parsed = datetime.fromtimestamp(float(raw_timestamp), tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        normalized = (
            f"{raw_timestamp[:-1]}+00:00"
            if raw_timestamp.endswith("Z")
            else raw_timestamp
        )
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)

    return parsed


def _request_target_bytes(request: Request) -> bytes:
    """Return the exact path and query bytes that are covered by the request signature."""
    raw_path = request.scope.get("raw_path")
    if isinstance(raw_path, bytes) and raw_path:
        path = raw_path
    else:
        path = request.url.path.encode("utf-8")

    query_string = request.scope.get("query_string")
    if isinstance(query_string, bytes) and query_string:
        return path + b"?" + query_string
    return path


def _build_api_key_signature_payload(
    request: Request, timestamp: str, body: bytes
) -> bytes:
    """Build the canonical payload used for HMAC request signing."""
    return b"\n".join(
        [
            request.method.upper().encode("utf-8"),
            _request_target_bytes(request),
            timestamp.strip().encode("utf-8"),
            body,
        ]
    )


@dataclass(frozen=True)
class OIDCConfig:
    """Configuration derived from environment variables for OIDC login and authz."""

    enabled: bool = field(
        default_factory=lambda: as_bool(os.getenv("OIDC_ENABLED"), default=False)
    )
    issuer_url: str = field(
        default_factory=lambda: os.getenv("OIDC_ISSUER_URL", "").strip().rstrip("/")
    )
    client_id: str = field(
        default_factory=lambda: os.getenv("OIDC_CLIENT_ID", "").strip()
    )
    client_secret: str = field(
        default_factory=lambda: os.getenv("OIDC_CLIENT_SECRET", "").strip()
    )
    scopes: str = field(
        default_factory=lambda: os.getenv("OIDC_SCOPES", "openid profile email").strip()
    )
    audience: str = field(
        default_factory=lambda: os.getenv("OIDC_AUDIENCE", "").strip()
    )
    extra_auth_params_raw: str = field(
        default_factory=lambda: os.getenv("OIDC_EXTRA_AUTH_PARAMS", "{}")
    )
    redirect_uri: str = field(
        default_factory=lambda: os.getenv("OIDC_REDIRECT_URI", "").strip()
    )
    login_path: str = field(
        default_factory=lambda: os.getenv("OIDC_LOGIN_PATH", "/api/auth/login").strip()
    )
    session_cookie_name: str = field(
        default_factory=lambda: os.getenv(
            "OIDC_SESSION_COOKIE_NAME", "kloigos_session"
        ).strip()
    )
    state_cookie_name: str = field(
        default_factory=lambda: os.getenv(
            "OIDC_STATE_COOKIE_NAME", "kloigos_oidc_state"
        ).strip()
    )
    nonce_cookie_name: str = field(
        default_factory=lambda: os.getenv(
            "OIDC_NONCE_COOKIE_NAME", "kloigos_oidc_nonce"
        ).strip()
    )
    next_cookie_name: str = field(
        default_factory=lambda: os.getenv(
            "OIDC_NEXT_COOKIE_NAME", "kloigos_oidc_next"
        ).strip()
    )
    cookie_secure: bool = field(default_factory=_cookie_secure_default)
    cookie_samesite: str = field(
        default_factory=lambda: os.getenv("OIDC_COOKIE_SAMESITE", "lax").strip().lower()
    )
    cookie_domain: str | None = field(
        default_factory=lambda: os.getenv("OIDC_COOKIE_DOMAIN")
    )
    verify_audience: bool = field(
        default_factory=lambda: as_bool(
            os.getenv("OIDC_VERIFY_AUDIENCE"), default=False
        )
    )
    ui_username_claim: str = field(
        default_factory=lambda: os.getenv(
            "OIDC_UI_USERNAME_CLAIM", "preferred_username"
        ).strip()
    )
    readonly_groups_raw: str = field(
        default_factory=lambda: os.getenv("OIDC_AUTHZ_READONLY_GROUPS", "")
    )
    user_groups_raw: str = field(
        default_factory=lambda: os.getenv("OIDC_AUTHZ_USER_GROUPS", "")
    )
    admin_groups_raw: str = field(
        default_factory=lambda: os.getenv("OIDC_AUTHZ_ADMIN_GROUPS", "")
    )
    groups_claim_name: str = field(
        default_factory=lambda: os.getenv("OIDC_AUTHZ_GROUPS_CLAIM", "groups").strip()
    )

    @property
    def role_groups(self) -> dict[KloigosRole, set[str]]:
        """Map each application role to the configured OIDC groups that grant it."""
        return {
            KloigosRole.KLOIGOS_READONLY: safe_csv_set(self.readonly_groups_raw),
            KloigosRole.KLOIGOS_USER: safe_csv_set(self.user_groups_raw),
            KloigosRole.KLOIGOS_ADMIN: safe_csv_set(self.admin_groups_raw),
        }

    @property
    def authorized_groups(self) -> set[str]:
        """Return the union of all OIDC groups allowed to access the application."""
        role_groups = self.role_groups
        if not role_groups:
            return set()
        groups: set[str] = set()
        for values in role_groups.values():
            groups.update(values)
        return groups

    def validate(self) -> None:
        """Validate startup configuration before the app begins serving requests."""
        if not self.enabled:
            return

        missing = []
        if not self.issuer_url:
            missing.append("OIDC_ISSUER_URL")
        if not self.client_id:
            missing.append("OIDC_CLIENT_ID")
        if not self.client_secret:
            missing.append("OIDC_CLIENT_SECRET")

        if missing:
            raise RuntimeError(
                f"OIDC is enabled but missing required env vars: {', '.join(missing)}"
            )

        if self.cookie_samesite not in {"lax", "strict", "none"}:
            raise RuntimeError("OIDC_COOKIE_SAMESITE must be one of: lax, strict, none")

        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise RuntimeError(
                "OIDC_COOKIE_SECURE must be true when OIDC_COOKIE_SAMESITE=none"
            )

        if not self.ui_username_claim:
            raise RuntimeError(
                "OIDC_UI_USERNAME_CLAIM must be set when OIDC is enabled"
            )

        if not self.groups_claim_name:
            raise RuntimeError(
                "OIDC_AUTHZ_GROUPS_CLAIM must be set when OIDC is enabled"
            )

        if not self.authorized_groups:
            raise RuntimeError(
                "At least one of OIDC_AUTHZ_READONLY_GROUPS, OIDC_AUTHZ_USER_GROUPS, OIDC_AUTHZ_ADMIN_GROUPS must include a group when OIDC is enabled"
            )

        # Validate this once at startup instead of on first auth request.
        self.extra_auth_params()

    def extra_auth_params(self) -> dict[str, str]:
        """Return extra authorization request parameters as a string dictionary."""
        try:
            return safe_json_string_dict(self.extra_auth_params_raw, default={})
        except ValueError as exc:
            raise ValueError("OIDC_EXTRA_AUTH_PARAMS must be a JSON object") from exc


class OIDCManager:
    """Coordinate OIDC metadata loading, token validation, and request auth resolution."""

    def __init__(self) -> None:
        self.config = OIDCConfig()
        self._metadata: dict[str, Any] | None = None
        self._jwks: dict[str, Any] | None = None
        self._meta_loaded_at = 0.0
        self._jwks_loaded_at = 0.0
        self._cache_ttl_seconds = int(os.getenv("OIDC_CACHE_TTL_SECONDS", "300"))

    @property
    def enabled(self) -> bool:
        """Expose whether OIDC-backed authentication is enabled for the app."""
        return self.config.enabled

    def validate_config(self) -> None:
        """Validate auth configuration at startup, including API key crypto settings."""
        self.config.validate()
        validate_api_key_crypto_config()

    def _http_json(
        self,
        url: str,
        *,
        method: str = "GET",
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        req_headers = {"Accept": "application/json"}
        if headers:
            req_headers.update(headers)

        payload = None
        if data is not None:
            payload = urllib.parse.urlencode(data).encode("utf-8")
            req_headers["Content-Type"] = "application/x-www-form-urlencoded"

        req = urllib.request.Request(
            url,
            data=payload,
            headers=req_headers,
            method=method,
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise RuntimeError(f"Expected JSON object from {url}")
            return parsed

    def _metadata_url(self) -> str:
        return f"{self.config.issuer_url}/.well-known/openid-configuration"

    def get_metadata(self) -> dict[str, Any]:
        """Return cached OIDC discovery metadata, refreshing it when the cache expires."""
        if (
            self._metadata
            and (time.time() - self._meta_loaded_at) < self._cache_ttl_seconds
        ):
            return self._metadata
        self._metadata = self._http_json(self._metadata_url())
        self._meta_loaded_at = time.time()
        return self._metadata

    def get_jwks(self) -> dict[str, Any]:
        """Return cached provider signing keys, refreshing them when needed."""
        if (
            self._jwks
            and (time.time() - self._jwks_loaded_at) < self._cache_ttl_seconds
        ):
            return self._jwks

        metadata = self.get_metadata()
        jwks_uri = str(metadata.get("jwks_uri") or "")
        if not jwks_uri:
            raise RuntimeError("OIDC provider metadata missing 'jwks_uri'")

        self._jwks = self._http_json(jwks_uri)
        self._jwks_loaded_at = time.time()
        return self._jwks

    def build_authorization_url(self, redirect_uri: str, state: str, nonce: str) -> str:
        """Build the provider authorization URL for starting the OIDC login flow."""
        metadata = self.get_metadata()
        auth_endpoint = str(metadata.get("authorization_endpoint") or "")
        if not auth_endpoint:
            raise RuntimeError(
                "OIDC provider metadata missing 'authorization_endpoint'"
            )

        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.config.scopes,
            "state": state,
            "nonce": nonce,
        }

        if self.config.audience:
            params["audience"] = self.config.audience

        params.update(self.config.extra_auth_params())

        return f"{auth_endpoint}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange an OIDC authorization code for a token response."""
        metadata = self.get_metadata()
        token_endpoint = str(metadata.get("token_endpoint") or "")
        if not token_endpoint:
            raise RuntimeError("OIDC provider metadata missing 'token_endpoint'")

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "redirect_uri": redirect_uri,
        }
        payload.update(self.config.extra_auth_params())

        return self._http_json(
            token_endpoint,
            method="POST",
            data=payload,
        )

    def _select_jwk(self, token: str) -> Any:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            raise HTTPException(status_code=401, detail="Token header is missing 'kid'")

        keys = self.get_jwks().get("keys", [])
        for jwk in keys:
            if jwk.get("kid") == kid:
                return jwt.PyJWK.from_dict(jwk).key

        # One forced refresh for key rotation.
        self._jwks = None
        keys = self.get_jwks().get("keys", [])
        for jwk in keys:
            if jwk.get("kid") == kid:
                return jwt.PyJWK.from_dict(jwk).key

        raise HTTPException(
            status_code=401, detail="Unable to find a matching JWKS key for token"
        )

    def validate_jwt(
        self,
        token: str,
        *,
        expected_nonce: str | None = None,
        strict_client_audience: bool = False,
    ) -> dict[str, Any]:
        """Validate a JWT against the provider configuration and optional nonce."""
        key = self._select_jwk(token)

        options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": True,
            "verify_nbf": True,
            "verify_iss": True,
            "verify_aud": strict_client_audience
            or self.config.verify_audience
            or bool(self.config.audience),
        }

        audience = None
        if strict_client_audience:
            audience = self.config.client_id
        elif self.config.audience:
            audience = self.config.audience

        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
                issuer=self.config.issuer_url,
                audience=audience,
                options=options,
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=401, detail=f"Invalid token: {exc}"
            ) from exc

        if expected_nonce is not None and claims.get("nonce") != expected_nonce:
            raise HTTPException(status_code=401, detail="Invalid token nonce")

        return claims

    def ensure_authorized(self, claims: dict[str, Any]) -> dict[str, Any]:
        """Ensure the caller belongs to at least one configured application group."""
        if claims.get("auth_disabled"):
            return claims

        groups_claim_name = str(
            claims.get("_groups_claim_name", self.config.groups_claim_name)
        )
        user_groups = _claims_groups(claims, groups_claim_name)
        if not user_groups:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: no groups found in claim '{groups_claim_name}'.",
            )

        if self.config.authorized_groups.isdisjoint(user_groups):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: user is not in any allowed group.",
            )

        return claims

    def enrich_claims(self, claims: dict[str, Any]) -> dict[str, Any]:
        """Add Kloigos-specific metadata that helps the webapp render auth state."""
        payload = dict(claims)
        payload["_groups_claim_name"] = str(
            claims.get("_groups_claim_name", self.config.groups_claim_name)
        )
        effective_role_groups = (
            claims.get("_role_groups")
            if isinstance(claims.get("_role_groups"), dict)
            else self.config.role_groups
        )
        payload["_role_groups"] = _jsonable_role_groups(effective_role_groups)

        existing_meta = (
            claims.get("_kloigos") if isinstance(claims.get("_kloigos"), dict) else {}
        )
        payload["_kloigos"] = {
            **existing_meta,
            "display_name_claim": self.config.ui_username_claim,
            "session_cookie_name": self.config.session_cookie_name,
        }
        return payload

    def ensure_any_role(
        self, claims: dict[str, Any], *roles: KloigosRole
    ) -> dict[str, Any]:
        """Ensure the caller has at least one of the requested application roles."""

        if claims.get("auth_disabled"):
            return claims

        groups_claim_name = str(
            claims.get("_groups_claim_name", self.config.groups_claim_name)
        )
        user_groups = _claims_groups(claims, groups_claim_name)
        if not user_groups:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: no groups found in claim '{groups_claim_name}'.",
            )

        effective_roles = (
            claims.get("_role_groups")
            if isinstance(claims.get("_role_groups"), dict)
            else self.config.role_groups
        )
        for role in roles:
            role_groups = effective_roles.get(role, set())
            if role_groups and not role_groups.isdisjoint(user_groups):
                return claims

        role_list = ", ".join(role.value for role in roles)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: requires one of roles [{role_list}].",
        )

    async def validate_api_key(
        self,
        request: Request,
        repo: BaseRepo,
        access_key: str,
        signature: str,
        timestamp: str,
    ) -> dict[str, Any]:
        """Authenticate an API request using the HMAC-signed API key headers."""
        api_key = repo.get_api_key(access_key)
        if api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key.",
            )

        if datetime.now(timezone.utc) >= api_key.valid_until:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key is expired.",
            )

        try:
            signed_at = _parse_api_key_timestamp(timestamp)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid X-Timestamp header.",
            ) from exc

        max_age_seconds = _api_key_signature_ttl_seconds()
        age_seconds = abs((datetime.now(timezone.utc) - signed_at).total_seconds())
        if age_seconds > max_age_seconds:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API request timestamp is expired.",
            )

        body = await request.body()
        secret_key = decrypt_api_key_secret(api_key.encrypted_secret_access_key)

        expected_signature = hmac_new(
            secret_key,
            _build_api_key_signature_payload(request, timestamp, body),
            sha256,
        ).hexdigest()

        if not compare_digest(expected_signature, signature.strip().lower()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key signature.",
            )

        roles = set(api_key.roles or [])
        role_groups = {role: {role.value} for role in roles}
        claims = {
            "sub": api_key.owner,
            "access_key": api_key.access_key,
            "groups": [role.value for role in roles],
            "_groups_claim_name": "groups",
            "_role_groups": role_groups,
            "auth_type": "api_key",
        }
        return claims

    async def current_claims(
        self,
        request: Request,
        repo: BaseRepo,
        *,
        session_token: str | None = None,
        access_key: str | None = None,
        signature: str | None = None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        """Resolve request claims from API-key headers or the OIDC session cookie."""
        if access_key or signature or timestamp:
            if not access_key or not signature or not timestamp:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="X-Kloigos-Access-Key, X-Kloigos-Signature, and X-Timestamp are required.",
                )
            return await self.validate_api_key(
                request,
                repo,
                access_key,
                signature,
                timestamp,
            )

        if not self.enabled:
            return {"sub": "anonymous", "auth_disabled": True}

        if session_token:
            claims = self.validate_jwt(session_token)
            return self.ensure_authorized(claims)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={
                "X-Auth-Login-Url": self.config.login_path,
            },
        )


def _oidc_cookie_kwargs() -> dict[str, Any]:
    """Return the shared cookie settings used across the OIDC browser flow."""
    return {
        "httponly": True,
        "secure": oidc.config.cookie_secure,
        "samesite": oidc.config.cookie_samesite,
        "domain": oidc.config.cookie_domain,
        "path": "/",
    }


oidc = OIDCManager()
router = APIRouter(prefix="/auth", tags=["auth"])
cookie_scheme = APIKeyCookie(name=oidc.config.session_cookie_name, auto_error=False)
access_key_scheme = APIKeyHeader(
    name="X-Kloigos-Access-Key",
    scheme_name="XAccessKey",
    auto_error=False,
)
signature_scheme = APIKeyHeader(
    name="X-Kloigos-Signature",
    scheme_name="XSignature",
    auto_error=False,
)
timestamp_scheme = APIKeyHeader(
    name="X-Timestamp",
    scheme_name="XTimestamp",
    auto_error=False,
)


async def require_authenticated(
    request: Request,
    repo: BaseRepo = Depends(get_repo),
    session_token: str | None = Security(cookie_scheme),
    access_key: str | None = Security(access_key_scheme),
    signature: str | None = Security(signature_scheme),
    timestamp: str | None = Security(timestamp_scheme),
) -> dict[str, Any]:
    """Return claims for the current caller, regardless of auth transport."""
    return await oidc.current_claims(
        request,
        repo,
        session_token=session_token,
        access_key=access_key,
        signature=signature,
        timestamp=timestamp,
    )


def require_user(
    claims: dict[str, Any] = Security(require_authenticated),
) -> dict[str, Any]:
    """Require a role that permits mutating compute-unit operations."""
    return oidc.ensure_any_role(
        claims, KloigosRole.KLOIGOS_USER, KloigosRole.KLOIGOS_ADMIN
    )


def require_compute_access(
    request: Request,
    claims: dict[str, Any] = Security(require_authenticated),
) -> dict[str, Any]:
    """Allow read-only users on GET, and require user/admin on write operations."""
    if request.method.upper() == "GET":
        return oidc.ensure_any_role(
            claims,
            KloigosRole.KLOIGOS_READONLY,
            KloigosRole.KLOIGOS_USER,
            KloigosRole.KLOIGOS_ADMIN,
        )
    return oidc.ensure_any_role(
        claims, KloigosRole.KLOIGOS_USER, KloigosRole.KLOIGOS_ADMIN
    )


def require_admin(
    claims: dict[str, Any] = Security(require_authenticated),
) -> dict[str, Any]:
    """Require the admin role."""
    return oidc.ensure_any_role(claims, KloigosRole.KLOIGOS_ADMIN)


def get_audit_actor(
    claims: dict[str, Any] = Security(require_authenticated),
) -> str:
    """Return the identifier that should be written into audit logs."""
    if claims.get("auth_type") == "api_key":
        return str(claims.get("access_key") or "anonymous")

    username = claims.get(oidc.config.ui_username_claim) or claims.get("sub")
    return str(username or "anonymous")


def _log_auth_event(
    repo: BaseRepo,
    actor_id: str,
    action: Event,
    details: dict[str, Any] | None = None,
) -> None:
    """Persist a login or logout event using the current request id context."""
    repo.log_event(
        LogMsg(
            user_id=actor_id,
            action=action,
            details=details,
            request_id=request_id_ctx.get(),
        )
    )


@router.get("/login")
def oidc_login(request: Request, next: str = "/"):  # noqa: A002
    """Start the browser OIDC login flow and store anti-CSRF cookies."""
    if not oidc.enabled:
        raise HTTPException(
            status_code=404,
            detail="OIDC is disabled.",
        )

    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    next_path = safe_next_path(next)
    redirect_uri = oidc.config.redirect_uri or str(request.url_for("oidc_callback"))
    auth_url = oidc.build_authorization_url(redirect_uri, state, nonce)

    resp = RedirectResponse(auth_url, status_code=302)
    cookie_kwargs = _oidc_cookie_kwargs()
    resp.set_cookie(oidc.config.state_cookie_name, state, max_age=300, **cookie_kwargs)
    resp.set_cookie(oidc.config.nonce_cookie_name, nonce, max_age=300, **cookie_kwargs)
    resp.set_cookie(
        oidc.config.next_cookie_name, next_path, max_age=300, **cookie_kwargs
    )
    return resp


@router.get("/callback", name="oidc_callback")
def oidc_callback(
    request: Request,
    repo: BaseRepo = Depends(get_repo),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    """Finish the OIDC login flow, validate the ID token, and set the session cookie."""
    if not oidc.enabled:
        raise HTTPException(
            status_code=404,
            detail="OIDC is disabled.",
        )

    if error:
        desc = error_description or "OIDC authorization failed."
        raise HTTPException(status_code=401, detail=f"{error}: {desc}")

    expected_state = request.cookies.get(oidc.config.state_cookie_name)
    expected_nonce = request.cookies.get(oidc.config.nonce_cookie_name)
    next_path = safe_next_path(request.cookies.get(oidc.config.next_cookie_name))

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")
    if not state or not expected_state or state != expected_state:
        raise HTTPException(status_code=401, detail="Invalid OIDC state.")
    if not expected_nonce:
        raise HTTPException(status_code=401, detail="Missing OIDC nonce.")

    redirect_uri = oidc.config.redirect_uri or str(request.url_for("oidc_callback"))
    token_payload = oidc.exchange_code(code, redirect_uri)

    id_token = token_payload.get("id_token")
    if not id_token or not isinstance(id_token, str):
        raise HTTPException(
            status_code=401, detail="Token endpoint response missing id_token."
        )

    claims = oidc.validate_jwt(
        id_token,
        expected_nonce=expected_nonce,
        strict_client_audience=True,
    )
    oidc.ensure_authorized(claims)
    actor_id = str(claims.get(oidc.config.ui_username_claim) or claims.get("sub"))
    _log_auth_event(repo, actor_id, Event.LOGIN, {"auth_type": "oidc"})

    resp = RedirectResponse(next_path, status_code=302)
    cookie_kwargs = _oidc_cookie_kwargs()
    resp.set_cookie(
        oidc.config.session_cookie_name, id_token, max_age=3600, **cookie_kwargs
    )
    resp.delete_cookie(
        oidc.config.state_cookie_name, path="/", domain=oidc.config.cookie_domain
    )
    resp.delete_cookie(
        oidc.config.nonce_cookie_name, path="/", domain=oidc.config.cookie_domain
    )
    resp.delete_cookie(
        oidc.config.next_cookie_name, path="/", domain=oidc.config.cookie_domain
    )
    return resp


@router.post("/logout")
def oidc_logout(
    repo: BaseRepo = Depends(get_repo),
    actor_id: str = Depends(get_audit_actor),
    claims: dict[str, Any] = Security(require_authenticated),
):
    """Clear the OIDC session cookie and write a logout audit event."""
    _log_auth_event(
        repo,
        actor_id,
        Event.LOGOUT,
        {"auth_type": str(claims.get("auth_type") or "oidc")},
    )
    resp = Response(status_code=204)
    resp.delete_cookie(
        oidc.config.session_cookie_name, path="/", domain=oidc.config.cookie_domain
    )
    return resp


@router.get("/me")
def oidc_me(
    request: Request, claims: dict[str, Any] = Security(require_authenticated)
) -> dict[str, Any]:
    """Return the current caller's claims plus Kloigos-specific auth metadata."""
    payload = oidc.enrich_claims(claims)
    payload["cookies"] = request.cookies
    return payload
