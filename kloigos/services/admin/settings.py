from ...models import Event, LogMsg, SettingKey, SettingNotFoundError, SettingRecord
from ...util import request_id_ctx
from .base import AdminServiceBase


class SettingsAdminService(AdminServiceBase):
    def list_settings(self) -> list[SettingRecord]:
        return self.repo.list_settings()

    def get_setting(self, key: SettingKey) -> SettingRecord:
        setting = self.repo.get_setting(key)
        if setting is None:
            raise SettingNotFoundError()
        return setting

    def update_setting(
        self,
        actor_id: str,
        key: SettingKey,
        value,
    ) -> SettingRecord:
        setting = self.repo.update_setting(key, value, updated_by=actor_id)
        if setting is None:
            raise SettingNotFoundError()

        self.repo.log_event(
            LogMsg(
                user_id=actor_id,
                action=Event.SETTING_UPDATE,
                details={
                    "key": setting.key,
                    "category": setting.category,
                    "is_secret": setting.is_secret,
                },
                request_id=request_id_ctx.get(),
            )
        )
        return setting

    def reset_setting(self, actor_id: str, key: SettingKey) -> SettingRecord:
        setting = self.repo.reset_setting(key, updated_by=actor_id)
        if setting is None:
            raise SettingNotFoundError()

        self.repo.log_event(
            LogMsg(
                user_id=actor_id,
                action=Event.SETTING_RESET,
                details={
                    "key": setting.key,
                    "category": setting.category,
                    "is_secret": setting.is_secret,
                },
                request_id=request_id_ctx.get(),
            )
        )
        return setting
