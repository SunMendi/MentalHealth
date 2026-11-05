from django.db import migrations


def seed_release_versions(apps, schema_editor):
    config = apps.get_model("chat", "AppVersionConfig")
    for platform in ("android", "ios"):
        config.objects.using(schema_editor.connection.alias).get_or_create(
            platform=platform,
            defaults={
                "latest_version": "1.0.0",
                "minimum_supported_version": "1.0.0",
                "force_update": False,
                "update_message": "",
                "store_url": "",
            },
        )


class Migration(migrations.Migration):
    dependencies = [("chat", "0005_specialistwaitlistregistration_communitypostreport")]
    operations = [migrations.RunPython(seed_release_versions, migrations.RunPython.noop)]
