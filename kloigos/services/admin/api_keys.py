import secrets
from datetime import datetime, timezone

from ...models import (
    ApiKeyCreateRequest,
    ApiKeyCreateRequestInDB,
    ApiKeyCreateResponse,
    ApiKeyNotFoundError,
    ApiKeySummary,
    Event,
    InvalidApiKeyValidityError,
    LogMsg,
)
from ...util import encrypt_api_key_secret, request_id_ctx
from .base import AdminServiceBase


class ApiKeysAdminService(AdminServiceBase):
    def list_api_keys(self, access_key: str | None = None) -> list[ApiKeySummary]:
        return self.repo.list_api_keys(access_key)

    def create_api_key(
        self,
        actor_id: str,
        request: ApiKeyCreateRequest,
    ) -> ApiKeyCreateResponse:

        valid_until = self._normalize_valid_until(request.valid_until)

        if valid_until <= datetime.now(timezone.utc):
            raise InvalidApiKeyValidityError()

        secret_access_key = secrets.token_urlsafe(32)

        access_key = "kloigos-" + secrets.token_urlsafe(16)

        created = self.repo.create_api_key(
            ApiKeyCreateRequestInDB(
                access_key=access_key,
                valid_until=valid_until,
                roles=request.roles,
            ),
            owner=actor_id,
            encrypted_secret_access_key=encrypt_api_key_secret(secret_access_key),
        )

        self.repo.log_event(
            LogMsg(
                user_id=actor_id,
                action=Event.API_KEY_CREATE,
                details={
                    "access_key": created.access_key,
                    "valid_until": created.valid_until.isoformat(),
                    "roles": [role.value for role in created.roles or []],
                },
                request_id=request_id_ctx.get(),
            )
        )

        return ApiKeyCreateResponse(
            access_key=created.access_key,
            owner=created.owner,
            valid_until=created.valid_until,
            roles=created.roles,
            secret_access_key=secret_access_key,
        )

    def delete_api_key(self, actor_id: str, access_key: str) -> None:
        existing_key = self.repo.get_api_key(access_key)
        if existing_key is None:
            raise ApiKeyNotFoundError()

        self.repo.delete_api_key(access_key)
        self.repo.log_event(
            LogMsg(
                user_id=actor_id,
                action=Event.API_KEY_DELETE,
                details={
                    "access_key": existing_key.access_key,
                    "owner": existing_key.owner,
                    "valid_until": existing_key.valid_until.isoformat(),
                    "roles": [role.value for role in existing_key.roles or []],
                },
                request_id=request_id_ctx.get(),
            )
        )

    @staticmethod
    def _normalize_valid_until(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
