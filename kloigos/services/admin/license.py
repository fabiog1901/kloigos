"""Offline license validation and non-blocking compliance reporting."""

import datetime as dt
import logging
from typing import Any

import jwt
from cpkit.audit import log_event
from jwt import DecodeError
from jwt import ExpiredSignatureError as JwtExpiredSignatureError
from jwt import InvalidSignatureError as JwtInvalidSignatureError
from pydantic import ValidationError

from ...models import (
    Event,
    ExpiredLicenseError,
    InvalidSignatureError,
    InvalidTokenError,
    LicenseCompliance,
    LicenseLimits,
    LicenseStatusResponse,
    MissingLicenseError,
    UnknownSigningKeyError,
    ValidatedLicense,
)
from ...repos import Repo

logger = logging.getLogger(__name__)

LICENSE_SETTING_KEY = "license.jwt"
FREE_SERVER_LIMIT = 10
FREE_CPU_LIMIT = 500

# Ed25519 public keys trusted for offline Kloigos license verification.
# Add PEM-encoded public keys here as Clojos LLC rotates signing keys.
TRUSTED_LICENSE_KEYS: dict[str, str] = {
    "kloigos-2026-0": """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAMbjmJxG0lRyuaExPNsHMsfxiRyE3FROFDwCQdrFQ/ZI=
-----END PUBLIC KEY-----
""",
    "kloigos-2026-1": """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAveX8xwBGd37M/Y4eSgsmTJ8S9DfPtKtbnGdsk5dsxJM=
-----END PUBLIC KEY-----
""",
}


class LicenseService:
    """Validate offline licenses and report usage compliance without blocking Kloigos."""

    def __init__(self, repo: Repo):
        self.repo = repo

    def status(self) -> LicenseStatusResponse:
        """Return license validation and current usage compliance status."""
        setting = self.repo.get_setting(LICENSE_SETTING_KEY)
        token = setting.value if setting else None
        valid = False
        reason: str | None = "MissingLicense"
        license_data: ValidatedLicense | None = None

        if token:
            try:
                license_data = self._validate_token(token)
                valid = True
                reason = None
            except (
                InvalidTokenError,
                UnknownSigningKeyError,
                InvalidSignatureError,
                ExpiredLicenseError,
            ) as exc:
                logger.warning("Kloigos license validation failed: %s", exc)
                reason = exc.__class__.__name__.removesuffix("Error")
        else:
            logger.info("Kloigos license is not installed.")

        usage = self.repo.get_license_usage()
        license_limits = license_data.limits if valid and license_data else {}
        limits = LicenseLimits(
            servers=self._positive_int(
                license_limits.get("servers"), FREE_SERVER_LIMIT
            ),
            cpus=self._positive_int(
                license_limits.get("cpus", license_limits.get("compute_units")),
                FREE_CPU_LIMIT,
            ),
        )
        over_servers = usage.servers > limits.servers
        over_cpus = usage.cpus > limits.cpus
        compliant = not over_servers and not over_cpus
        license_required = not valid and (
            usage.servers > FREE_SERVER_LIMIT or usage.cpus > FREE_CPU_LIMIT
        )

        if compliant:
            message = (
                f"Kloigos is compliant: {usage.servers}/{limits.servers} servers "
                f"and {usage.cpus}/{limits.cpus} CPUs are under management."
            )
        elif license_required:
            message = (
                "A Kloigos license is required because usage exceeds the community "
                f"limit: {usage.servers}/{FREE_SERVER_LIMIT} servers and "
                f"{usage.cpus}/{FREE_CPU_LIMIT} CPUs are under management."
            )
        else:
            message = (
                "Kloigos usage exceeds the installed license limits: "
                f"{usage.servers}/{limits.servers} servers and "
                f"{usage.cpus}/{limits.cpus} CPUs are under management."
            )

        return LicenseStatusResponse(
            licensed=bool(valid and license_data),
            valid=valid,
            reason=reason,
            license=license_data if valid else None,
            compliance=LicenseCompliance(
                compliant=compliant,
                license_required=license_required,
                message=message,
                usage=usage,
                limits=limits,
            ),
        )

    def check_compliance(self, actor_id: str = "system") -> LicenseStatusResponse:
        """Log non-compliance to journald and the audit event log."""
        status = self.status()
        if status.compliance.compliant:
            logger.info(
                "Kloigos license compliance check passed: servers=%s/%s cpus=%s/%s",
                status.compliance.usage.servers,
                status.compliance.limits.servers,
                status.compliance.usage.cpus,
                status.compliance.limits.cpus,
            )
            return status

        details = status.model_dump(mode="json")
        logger.warning(
            "Kloigos license compliance warning: %s", status.compliance.message
        )
        log_event(
            self.repo,
            actor_id,
            Event.LICENSE_NON_COMPLIANT,
            details,
        )
        return status

    def _positive_int(self, value: Any, default: int) -> int:
        try:
            parsed = int(value)
        except TypeError, ValueError:
            return default
        return parsed if parsed > 0 else default

    def _validate_token(self, token: str | None) -> ValidatedLicense:
        if not token:
            raise MissingLicenseError("Kloigos license is not installed.")

        try:
            header = jwt.get_unverified_header(token)
        except DecodeError as exc:
            raise InvalidTokenError("Kloigos license is not a valid JWT.") from exc

        key_id = header.get("kid")
        if not key_id or key_id not in TRUSTED_LICENSE_KEYS:
            raise UnknownSigningKeyError(
                f"Kloigos license signing key '{key_id}' is not trusted."
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
                "Kloigos license signature is invalid."
            ) from exc
        except JwtExpiredSignatureError as exc:
            raise ExpiredLicenseError("Kloigos license has expired.") from exc
        except Exception as exc:
            raise InvalidTokenError("Kloigos license could not be decoded.") from exc

        try:
            license_data = ValidatedLicense(
                license_id=str(payload["license_id"]),
                customer=str(payload["customer"]),
                issued_at=dt.datetime.combine(
                    dt.date.fromisoformat(payload["issued_at"]),
                    dt.time.min,
                    tzinfo=dt.UTC,
                ),
                expires_at=dt.datetime.combine(
                    dt.date.fromisoformat(payload["expires_at"]),
                    dt.time.min,
                    tzinfo=dt.UTC,
                ),
                limits=dict(payload.get("limits") or {}),
                key_id=key_id,
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise InvalidTokenError(
                "Kloigos license payload is missing required fields."
            ) from exc

        if license_data.expires_at <= dt.datetime.now(dt.UTC):
            raise ExpiredLicenseError("Kloigos license has expired.")

        return license_data
