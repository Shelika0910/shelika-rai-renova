from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        import accounts.models
<<<<<<< HEAD
=======
        from . import groups
        from django.db.models.signals import post_migrate
        post_migrate.connect(groups.create_user_groups, sender=self)

>>>>>>> parent of 482fd21 (Admin portal)
