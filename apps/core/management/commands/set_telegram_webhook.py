"""Set or delete the Telegram bot webhook through the Cloudflare proxy."""
from django.core.management.base import BaseCommand, CommandError

from apps.core.telegram import api, delete_webhook, set_webhook, webhook_url


class Command(BaseCommand):
    help = 'Set Telegram webhook on the public site URL via TELEGRAM_API_BASE_URL.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            default='',
            help='Override webhook URL. Defaults to TELEGRAM_WEBHOOK_URL or PUBLIC_SITE_URL.',
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Remove the webhook instead of setting it.',
        )

    def handle(self, *args, **options):
        if options['delete']:
            result = delete_webhook()
            self._report(result, 'Webhook deleted.')
            return
        target = (options.get('url') or webhook_url()).strip()
        if not target:
            raise CommandError(
                'Set PUBLIC_SITE_URL or TELEGRAM_WEBHOOK_URL, or pass --url.'
            )
        result = set_webhook(target)
        self._report(result, f'Webhook set to {target}')
        info = api('getWebhookInfo')
        description = info.get('description') or info.get('result') or info
        self.stdout.write(self.style.NOTICE(str(description)))

    def _report(self, result: dict, success_message: str) -> None:
        if not result.get('ok'):
            raise CommandError(result.get('description') or 'Telegram API call failed.')
        self.stdout.write(self.style.SUCCESS(success_message))
