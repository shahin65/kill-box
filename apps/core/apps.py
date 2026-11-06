import os
import sys

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    label = 'core'
    verbose_name = 'هسته'

    def ready(self):
        if os.environ.get('RUN_MAIN') != 'true':
            return
        if 'test' in sys.argv:
            return
        from apps.core.bale import start_poller as start_bale_poller
        from apps.core.telegram import start_poller as start_telegram_poller

        start_bale_poller()
        start_telegram_poller()
