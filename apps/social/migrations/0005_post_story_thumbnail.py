import apps.social.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('social', '0004_storyview'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='thumbnail',
            field=models.ImageField(
                blank=True,
                upload_to=apps.social.models.post_thumb_upload_to,
            ),
        ),
        migrations.AddField(
            model_name='story',
            name='thumbnail',
            field=models.ImageField(
                blank=True,
                upload_to=apps.social.models.story_thumb_upload_to,
            ),
        ),
    ]
