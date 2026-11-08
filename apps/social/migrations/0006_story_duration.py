from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('social', '0005_post_story_thumbnail'),
    ]

    operations = [
        migrations.AddField(
            model_name='story',
            name='duration',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
