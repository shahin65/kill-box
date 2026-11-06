from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_avatar_and_site_settings'),
    ]

    operations = [
        migrations.AddField(
            model_name='memberprofile',
            name='xp',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='memberprofile',
            name='gems',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='memberprofile',
            name='wallet',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
