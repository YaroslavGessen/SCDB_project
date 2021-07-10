from django.apps import AppConfig


class UserMgmtConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user_mgmt'

    def ready(self):
        import user_mgmt.signals
