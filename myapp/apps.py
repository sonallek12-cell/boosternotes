from django.apps import AppConfig


class MyappConfig(AppConfig):
    name = 'myapp'

    def ready(self):
        # ── Auto-create superuser on first run ─────────────────────────────
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if not User.objects.filter(is_superuser=True).exists():
                User.objects.create_superuser(
                    username='admin',
                    email='admin@gmail.com',
                    password='123456',
                )
        except Exception:
            pass

        # ── Register auto-backup signals ───────────────────────────────────
        try:
            import myapp.signals  # noqa: F401  (side-effect import)
        except Exception:
            pass
