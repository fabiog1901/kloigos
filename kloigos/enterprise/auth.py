import json
import logging
import os
import secrets
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

import jwt
from fastapi import APIRouter, HTTPException, Request, Response, Security, status
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyCookie, HTTPAuthorizationCredentials, HTTPBearer


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _safe_json_loads(
    value: str | None, *, default: dict[str, str] | None = None
) -> dict[str, str]:
    if not value:
        return default or {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("OIDC_EXTRA_AUTH_PARAMS must be a JSON object")
    return {str(k): str(v) for k, v in parsed.items()}


def _safe_next_path(next_path: str | None) -> str:
    if not next_path:
        return "/"
    if not next_path.startswith("/"):
        return "/"
    if next_path.startswith("//"):
        return "/"
    return next_path


def _safe_csv_set(raw_value: str | None) -> set[str]:
    if not raw_value:
        return set()
    return {part.strip() for part in raw_value.split(",") if part and part.strip()}


def _claim_groups(claim_value: Any) -> set[str]:
    if claim_value is None:
        return set()
    if isinstance(claim_value, str):
        return (
            _safe_csv_set(claim_value)
            if "," in claim_value
            else ({claim_value.strip()} if claim_value.strip() else set())
        )
    if isinstance(claim_value, (list, tuple, set)):
        return {str(v).strip() for v in claim_value if str(v).strip()}
    return set()


def _cookie_secure_default() -> bool:
    # secure-by-default in production
    return _as_bool(os.getenv("OIDC_COOKIE_SECURE"), default=False)


def _license_key_value() -> str:
    return os.getenv("KLOIGOS_ENTERPRISE_LICENSE_KEY", "").strip()


@dataclass(frozen=True)
class OIDCConfig:
    enabled: bool = field(
        default_factory=lambda: _as_bool(os.getenv("OIDC_ENABLED"), default=False)
    )
    enterprise_license_key: str = field(default_factory=_license_key_value)
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
        default_factory=lambda: _as_bool(
            os.getenv("OIDC_VERIFY_AUDIENCE"), default=False
        )
    )
    ui_username_claim: str = field(
        default_factory=lambda: os.getenv(
            "OIDC_UI_USERNAME_CLAIM", "preferred_username"
        ).strip()
    )
    allowed_groups_raw: str = field(
        default_factory=lambda: os.getenv("OIDC_AUTHZ_ALLOWED_GROUPS", "")
    )
    groups_claim_name: str = field(
        default_factory=lambda: os.getenv("OIDC_AUTHZ_GROUPS_CLAIM", "groups").strip()
    )

    @property
    def license_is_valid(self) -> bool:
        return bool(self.enterprise_license_key)

    @property
    def allowed_groups(self) -> set[str]:
        return _safe_csv_set(self.allowed_groups_raw)

    def validate(self) -> None:
        if not self.enabled or not self.license_is_valid:
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

        if not self.allowed_groups:
            raise RuntimeError(
                "OIDC_AUTHZ_ALLOWED_GROUPS must include at least one group when OIDC is enabled"
            )

        # Validate this once at startup instead of on first auth request.
        self.extra_auth_params()

    def extra_auth_params(self) -> dict[str, str]:
        return _safe_json_loads(self.extra_auth_params_raw, default={})


class OIDCManager:
    def __init__(self) -> None:
        self.config = OIDCConfig()
        self._metadata: dict[str, Any] | None = None
        self._jwks: dict[str, Any] | None = None
        self._meta_loaded_at = 0.0
        self._jwks_loaded_at = 0.0
        self._cache_ttl_seconds = int(os.getenv("OIDC_CACHE_TTL_SECONDS", "300"))

    @property
    def enabled(self) -> bool:
        return self.config.enabled and self.config.license_is_valid

    def validate_config(self) -> None:
        if self.config.enabled and not self.config.license_is_valid:
            logging.warning(
                "OIDC is enabled but KLOIGOS_ENTERPRISE_LICENSE_KEY is missing or invalid. "
                "Falling back to unauthenticated mode."
            )
        self.config.validate()

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
        if (
            self._metadata
            and (time.time() - self._meta_loaded_at) < self._cache_ttl_seconds
        ):
            return self._metadata
        self._metadata = self._http_json(self._metadata_url())
        self._meta_loaded_at = time.time()
        return self._metadata

    def get_jwks(self) -> dict[str, Any]:
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
        if not self.enabled:
            return claims

        user_groups = _claim_groups(claims.get(self.config.groups_claim_name))
        if not user_groups:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: no groups found in claim '{self.config.groups_claim_name}'.",
            )

        if self.config.allowed_groups.isdisjoint(user_groups):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: user is not in any allowed group.",
            )

        return claims

    def current_claims(
        self,
        request: Request,
        *,
        bearer_credentials: HTTPAuthorizationCredentials | None = None,
        session_token: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {"sub": "anonymous", "auth_disabled": True}

        if bearer_credentials and bearer_credentials.credentials:
            claims = self.validate_jwt(bearer_credentials.credentials)
            return self.ensure_authorized(claims)

        if session_token:
            claims = self.validate_jwt(session_token)
            return self.ensure_authorized(claims)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={
                "WWW-Authenticate": "Bearer",
                "X-Auth-Login-Url": self.config.login_path,
            },
        )


oidc = OIDCManager()
router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)
cookie_scheme = APIKeyCookie(name=oidc.config.session_cookie_name, auto_error=False)


def require_authenticated(
    request: Request,
    bearer_credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    session_token: str | None = Security(cookie_scheme),
) -> dict[str, Any]:
    return oidc.current_claims(
        request,
        bearer_credentials=bearer_credentials,
        session_token=session_token,
    )


@router.get("/login")
def oidc_login(request: Request, next: str = "/"):  # noqa: A002
    if not oidc.enabled:
        raise HTTPException(
            status_code=404,
            detail="OIDC is disabled or enterprise license is missing.",
        )

    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    next_path = _safe_next_path(next)
    redirect_uri = oidc.config.redirect_uri or str(request.url_for("oidc_callback"))
    auth_url = oidc.build_authorization_url(redirect_uri, state, nonce)

    resp = RedirectResponse(auth_url, status_code=302)
    cookie_kwargs = {
        "httponly": True,
        "secure": oidc.config.cookie_secure,
        "samesite": oidc.config.cookie_samesite,
        "domain": oidc.config.cookie_domain,
        "path": "/",
    }
    resp.set_cookie(oidc.config.state_cookie_name, state, max_age=300, **cookie_kwargs)
    resp.set_cookie(oidc.config.nonce_cookie_name, nonce, max_age=300, **cookie_kwargs)
    resp.set_cookie(
        oidc.config.next_cookie_name, next_path, max_age=300, **cookie_kwargs
    )
    return resp


@router.get("/callback", name="oidc_callback")
def oidc_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    if not oidc.enabled:
        raise HTTPException(
            status_code=404,
            detail="OIDC is disabled or enterprise license is missing.",
        )

    if error:
        desc = error_description or "OIDC authorization failed."
        raise HTTPException(status_code=401, detail=f"{error}: {desc}")

    expected_state = request.cookies.get(oidc.config.state_cookie_name)
    expected_nonce = request.cookies.get(oidc.config.nonce_cookie_name)
    next_path = _safe_next_path(request.cookies.get(oidc.config.next_cookie_name))

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

    resp = RedirectResponse(next_path, status_code=302)
    cookie_kwargs = {
        "httponly": True,
        "secure": oidc.config.cookie_secure,
        "samesite": oidc.config.cookie_samesite,
        "domain": oidc.config.cookie_domain,
        "path": "/",
    }
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
def oidc_logout():
    resp = Response(status_code=204)
    resp.delete_cookie(
        oidc.config.session_cookie_name, path="/", domain=oidc.config.cookie_domain
    )
    return resp


@router.get("/me")
def oidc_me(
    request: Request, claims: dict[str, Any] = Security(require_authenticated)
) -> dict[str, Any]:
    payload = dict(claims)
    payload["cookies"] = request.cookies
    return payload
