"""
Management command to populate webhook topics from settings.
This replaces the database queries that were previously done during app initialization.
"""
import logging
from django.core.management.base import BaseCommand
from django.db.utils import OperationalError, ProgrammingError

from oxhook.models import WebhookTopic
from oxhook.registry import TOPIC_REGISTRY


class Command(BaseCommand):
    help = 'Populate webhook topics from settings configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force population even if database connection issues exist',
        )

    def handle(self, *args, **options):
        try:
            # Test database connection
            WebhookTopic.objects.count()
        except (OperationalError, ProgrammingError) as ex:
            if not options['force']:
                if "Connection refused" in str(ex):
                    self.stdout.write(
                        self.style.WARNING('Database connection refused. Use --force to override.')
                    )
                    return
                if "could not translate host name" in str(ex):
                    self.stdout.write(
                        self.style.WARNING('Database host name resolution failed. Use --force to override.')
                    )
                    return
                if "no such table" in str(ex):
                    self.stdout.write(
                        self.style.WARNING('Database tables not found. Run migrations first.')
                    )
                    return
                if "relation" in str(ex) and "does not exist" in str(ex):
                    self.stdout.write(
                        self.style.WARNING('Database relations not found. Run migrations first.')
                    )
                    return
            raise ex

        allowed_topics = set(TOPIC_REGISTRY.keys())
        
        if not allowed_topics:
            self.stdout.write(
                self.style.WARNING('No topics found in registry.')
            )
            return

        # Remove topics that are no longer allowed
        deleted_count = WebhookTopic.objects.exclude(name__in=allowed_topics).count()
        if deleted_count > 0:
            WebhookTopic.objects.exclude(name__in=allowed_topics).delete()
            self.stdout.write(
                self.style.SUCCESS(f'Removed {deleted_count} obsolete webhook topics.')
            )

        # Add new topics
        created_count = 0
        for topic in allowed_topics:
            if not WebhookTopic.objects.filter(name=topic).exists():
                WebhookTopic.objects.create(name=topic)
                created_count += 1
                logging.info(f"Adding topic: {topic}")

        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Created {created_count} new webhook topics.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('All webhook topics are up to date.')
            )

        total_topics = WebhookTopic.objects.count()
        self.stdout.write(
            self.style.SUCCESS(f'Total webhook topics: {total_topics}')
        )
