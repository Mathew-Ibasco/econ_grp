from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0035_auditlog"),
    ]

    operations = [
        migrations.AlterField(
            model_name="blogpost",
            name="featured_image_url",
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
