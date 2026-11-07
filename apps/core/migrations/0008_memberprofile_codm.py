from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_liveroom'),
    ]

    operations = [
        migrations.AddField(
            model_name='memberprofile',
            name='codm_level',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='memberprofile',
            name='codm_nickname',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='memberprofile',
            name='codm_uid',
            field=models.CharField(blank=True, default='', max_length=24),
        ),
    ]
