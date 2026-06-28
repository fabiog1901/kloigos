"""Offline enterprise license validation and feature gating.

A networking service would receive or construct LicenseService the same way other services do, then call:

if not self.license_service.has_feature("networking"):
    # hide/disable the behavior, return community fallback, etc.

For example:

class NetworkingService:
    def __init__(self, repo):
        self.repo = repo
        self.license_service = LicenseService(repo)

    def configure_networking(self):
        if not self.license_service.has_feature("networking"):
            return {"enabled": False}

        return {"enabled": True}

has_feature() is for branching.

require() is for hard-gating. It raises FeatureNotLicensedError if the feature is not enabled:

def create_overlay_network(self, req):
    self.license_service.require("networking")
    ...

So API code could catch that and return 403, or service code can stop immediately.

limits() is for future numeric caps in the license, like:

"limits": {
  "hosts": 20,
  "networks": 5
}

Usage:

limits = self.license_service.limits()
max_networks = limits.get("networks")

if max_networks is not None and current_network_count >= max_networks:
    raise FeatureNotLicensedError("Licensed network limit reached.")

So in short:
- has_feature("networking"): “May I show/use this feature?”
- require("networking"): “Stop unless this feature is licensed.”
- limits(): “What licensed caps apply?”
"""

import datetime as dt
import logging
import threading
from typing import Any

import jwt
from jwt import DecodeError
from jwt import ExpiredSignatureError as JwtExpiredSignatureError
from jwt import InvalidSignatureError as JwtInvalidSignatureError
from pydantic import ValidationError

from ...models import (
    ExpiredLicenseError,
    FeatureNotLicensedError,
    InvalidSignatureError,
    InvalidTokenError,
    LicenseStatusResponse,
    MissingLicenseError,
    UnknownSigningKeyError,
    ValidatedLicense,
)
from ...repos import Repo

LICENSE_SETTING_KEY = "enterprise.license"
LICENSE_CACHE_SECONDS = 300

# Ed25519 public keys trusted for offline enterprise license verification.
# Add PEM-encoded public keys here as Clojos LLC rotates signing keys.
TRUSTED_LICENSE_KEYS: dict[str, str] = {}


class LicenseService:
    """Validate offline enterprise licenses and expose feature gates."""

    _cache_lock = threading.Lock()
    _cached_status: LicenseStatusResponse | None = None
    _cache_expires_at: dt.datetime | None = None

    def __init__(self, repo: Repo):
        self.repo = repo

    def status(self) -> LicenseStatusResponse:
        """Return cached enterprise license status, refreshing after five minutes."""
        now = dt.datetime.now(dt.UTC)
        with self._cache_lock:
            if (
                self._cached_status is not None
                and self._cache_expires_at is not None
                and self._cache_expires_at > now
            ):
                return self._cached_status

        setting = self.repo.get_setting(LICENSE_SETTING_KEY)
        token = setting.value if setting else None
        try:
            license_data = self._validate_token(token)
            status = LicenseStatusResponse(
                edition="enterprise",
                valid=True,
                license=license_data,
            )
        except MissingLicenseError:
            logging.info("Enterprise license is not installed.")
            status = LicenseStatusResponse(
                edition="community",
                valid=False,
                reason="MissingLicense",
            )
        except (
            InvalidTokenError,
            UnknownSigningKeyError,
            InvalidSignatureError,
            ExpiredLicenseError,
        ) as exc:
            logging.warning("Enterprise license validation failed: %s", exc)
            status = LicenseStatusResponse(
                edition="community",
                valid=False,
                reason=exc.__class__.__name__.removesuffix("Error"),
            )

        with self._cache_lock:
            self._cached_status = status
            self._cache_expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(
                seconds=LICENSE_CACHE_SECONDS
            )
        return status

    def has_feature(self, feature: str) -> bool:
        """Return whether the installed enterprise license enables a feature."""
        status = self.status()
        return bool(
            status.valid and status.license and feature in status.license.features
        )

    def require(self, feature: str) -> None:
        """Raise FeatureNotLicensedError unless a feature is enabled."""
        if not self.has_feature(feature):
            logging.warning("Enterprise feature is not licensed: %s", feature)
            raise FeatureNotLicensedError(
                f"Feature '{feature}' is not enabled by the enterprise license."
            )

    def limits(self) -> dict[str, Any]:
        """Return configured enterprise license limits, or an empty mapping."""
        status = self.status()
        if not status.valid or status.license is None:
            return {}
        return status.license.limits

    def _validate_token(self, token: str | None) -> ValidatedLicense:
        if not token:
            raise MissingLicenseError("Enterprise license is not installed.")

        try:
            header = jwt.get_unverified_header(token)
        except DecodeError as exc:
            raise InvalidTokenError("Enterprise license is not a valid JWT.") from exc

        key_id = header.get("kid")
        if not key_id or key_id not in TRUSTED_LICENSE_KEYS:
            raise UnknownSigningKeyError(
                f"Enterprise license signing key '{key_id}' is not trusted."
            )

        try:
            payload = jwt.decode(
                token,
                TRUSTED_LICENSE_KEYS[key_id],
                algorithms=["EdDSA"],
                options={
                    "verify_aud": False,
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_nbf": False,
                },
            )
        except JwtInvalidSignatureError as exc:
            raise InvalidSignatureError(
                "Enterprise license signature is invalid."
            ) from exc
        except JwtExpiredSignatureError as exc:
            raise ExpiredLicenseError("Enterprise license has expired.") from exc
        except Exception as exc:
            raise InvalidTokenError("Enterprise license could not be decoded.") from exc

        try:
            license_data = ValidatedLicense(
                license_id=str(payload["license_id"]),
                customer=str(payload["customer"]),
                issued_at=dt.datetime.fromtimestamp(payload["issued_at"], tz=dt.UTC),
                expires_at=dt.datetime.fromtimestamp(payload["expires_at"], tz=dt.UTC),
                features=list(payload.get("features") or []),
                limits=dict(payload.get("limits") or {}),
                key_id=key_id,
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise InvalidTokenError(
                "Enterprise license payload is missing required fields."
            ) from exc

        if license_data.expires_at <= dt.datetime.now(dt.UTC):
            raise ExpiredLicenseError("Enterprise license has expired.")

        return license_data
