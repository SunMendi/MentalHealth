from django.core.management.base import BaseCommand
from django.db import transaction

from chat.models import ClinicalProtocol, MicroAction, ProblemCategory
from chat.seed_data import SEED_DATA


class Command(BaseCommand):
    help = "Seed or update production-safe clinical support data."

    @transaction.atomic
    def handle(self, *args, **options):
        categories_synced = 0
        protocols_synced = 0
        tasks_synced = 0

        for item in SEED_DATA:
            category, created = ProblemCategory.objects.update_or_create(
                name=item["name"],
                defaults={"description": item["description"]},
            )
            categories_synced += 1

            ClinicalProtocol.objects.update_or_create(
                category=category,
                defaults={
                    "technique_type": item["protocol"]["type"],
                    "content": item["protocol"]["content"],
                },
            )
            protocols_synced += 1

            for day_number, (title, description) in enumerate(item["tasks"], 1):
                MicroAction.objects.update_or_create(
                    category=category,
                    day_number=day_number,
                    defaults={
                        "title": title,
                        "description": description,
                    },
                )
                tasks_synced += 1

            status = "created/updated" if created else "updated"
            self.stdout.write(self.style.SUCCESS(f"Synced category: {category.name} ({status})"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Clinical data sync complete. Categories={categories_synced}, Protocols={protocols_synced}, Tasks={tasks_synced}"
            )
        )
