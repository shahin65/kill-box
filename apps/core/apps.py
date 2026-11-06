import os
import sys

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    label = 'core'
    verbose_name = 'هسته'

    def ready(self):
        if 'test' in sys.argv:
            return
        # runserver loads apps twice; only the reloader child should poll.
        if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') != 'true':
            return
        # Skip migrate / collectstatic / shell and other management commands.
        script = os.path.basename(sys.argv[0] if sys.argv else '')
        if script in {'manage.py', 'django-admin'} and 'runserver' not in sys.argv:
            return
        from apps.core.bale import start_poller as start_bale_poller
        from apps.core.telegram import start_poller as start_telegram_poller

        start_bale_poller()
        start_telegram_poller()
