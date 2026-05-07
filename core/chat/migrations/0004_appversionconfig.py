from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0003_communitypost"),
    ]

    operations = [
        migrations.CreateModel(
            name="AppVersionConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("platform", models.CharField(choices=[("android", "Android"), ("ios", "iOS")], max_length=20, unique=True)),
                ("latest_version", models.CharField(max_length=20)),
                ("minimum_supported_version", models.CharField(max_length=20)),
                ("force_update", models.BooleanField(default=False)),
                ("update_message", models.CharField(blank=True, max_length=255)),
                ("store_url", models.URLField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["platform"],
            },
        ),
    ]
