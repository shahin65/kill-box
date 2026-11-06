from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_memberprofile_xp_gems_wallet'),
    ]

    operations = [
        migrations.AddField(
            model_name='sitesettings',
            name='privacy_policy',
            field=models.TextField(
                blank=True,
                default='',
                help_text='متن صفحه حریم خصوصی در منوی همبرگری. می‌توانی تیتر، لینک و تصویر اضافه کنی.',
                verbose_name='سیاست حفظ حریم خصوصی',
            ),
        ),
        migrations.AddField(
            model_name='sitesettings',
            name='terms_of_service',
            field=models.TextField(
                blank=True,
                default='',
                help_text='متن صفحه شرایط استفاده در منوی همبرگری. می‌توانی تیتر، لینک و تصویر اضافه کنی.',
                verbose_name='شرایط استفاده از خدمات',
            ),
        ),
        migrations.AlterModelOptions(
            name='sitesettings',
            options={'verbose_name': 'تنظیمات سایت', 'verbose_name_plural': 'تنظیمات سایت'},
        ),
    ]
