"""
Webhook services for managing webhook operations, validation, and event handling.
"""
import secrets
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from oxhook.models import (
    Webhook,
    WebhookTopic,
    WebhookSecret,
    WebhookEvent
)
from oxhook.registry import TOPIC_REGISTRY, get_handler
from oxhook.settings import get_settings
from oxhook.signals import fire_webhook
from oxhook.exceptions import TopicNotFound


logger = logging.getLogger(__name__)


class WebhookService:
    """Service for managing webhook CRUD operations."""

    @staticmethod
    def create_webhook(url: str, topics: List[str], user=None) -> Webhook:
        """Create a new webhook with specified topics."""
        with transaction.atomic():
            # Validate topics exist
            WebhookService.validate_topics(topics)
            
            webhook = Webhook.objects.create(url=url)
            
            # Add topics
            topic_objects = WebhookTopic.objects.filter(name__in=topics)
            webhook.topics.set(topic_objects)
            
            # Generate initial secret
            WebhookSecretService.generate_secret(webhook)
            
            logger.info(f"Created webhook {webhook.id} for URL {url} with topics {topics}")
            return webhook

    @staticmethod
    def update_webhook(webhook_id: UUID, url: Optional[str] = None, 
                      topics: Optional[List[str]] = None, 
                      active: Optional[bool] = None) -> Webhook:
        """Update an existing webhook."""
        webhook = get_object_or_404(Webhook, uuid=webhook_id)
        
        with transaction.atomic():
            if url is not None:
                webhook.url = url
            
            if active is not None:
                webhook.active = active
            
            if topics is not None:
                WebhookService.validate_topics(topics)
                topic_objects = WebhookTopic.objects.filter(name__in=topics)
                webhook.topics.set(topic_objects)
            
            webhook.save()
            logger.info(f"Updated webhook {webhook.id}")
            return webhook

    @staticmethod
    def delete_webhook(webhook_id: UUID) -> bool:
        """Delete a webhook."""
        webhook = get_object_or_404(Webhook, uuid=webhook_id)
        webhook.delete()
        logger.info(f"Deleted webhook {webhook.id}")
        return True

    @staticmethod
    def get_webhook(webhook_id: UUID) -> Webhook:
        """Get a webhook by UUID."""
        return get_object_or_404(Webhook, uuid=webhook_id)

    @staticmethod
    def list_webhooks(active_only: bool = True) -> List[Webhook]:
        """List all webhooks."""
        queryset = Webhook.objects.all()
        if active_only:
            queryset = queryset.filter(active=True)
        return queryset.order_by('-created')

    @staticmethod
    def validate_topics(topics: List[str]) -> None:
        """Validate that all topics exist in the registry."""
        available_topics = set(TOPIC_REGISTRY.keys())
        invalid_topics = set(topics) - available_topics
        
        if invalid_topics:
            raise ValidationError(
                f"Invalid topics: {', '.join(invalid_topics)}. "
                f"Available topics: {', '.join(available_topics)}"
            )


class WebhookTopicService:
    """Service for managing webhook topics."""

    @staticmethod
    def list_available_topics():
        """List all available webhook topics."""
        return WebhookTopic.objects.all().order_by('name')

    @staticmethod
    def get_topic_by_name(name: str) -> WebhookTopic:
        """Get a topic by name."""
        return get_object_or_404(WebhookTopic, name=name)

    @staticmethod
    def create_topic(name: str) -> WebhookTopic:
        """Create a new topic (usually done automatically)."""
        topic, created = WebhookTopic.objects.get_or_create(name=name)
        if created:
            logger.info(f"Created new topic: {name}")
        return topic

    @staticmethod
    def get_webhooks_for_topic(topic_name: str):
        """Get all active webhooks subscribed to a specific topic."""
        return Webhook.objects.filter(
            active=True,
            topics__name=topic_name
        ).distinct()


class WebhookSecretService:
    """Service for managing webhook secrets and authentication."""

    @staticmethod
    def generate_secret(webhook: Webhook, length: int = 32) -> WebhookSecret:
        """Generate a new secret for a webhook."""
        token = secrets.token_urlsafe(length)
        
        # Deactivate old secrets by deleting them
        webhook.secrets.all().delete()
        
        secret = WebhookSecret.objects.create(
            webhook=webhook,
            token=token
        )
        
        logger.info(f"Generated new secret for webhook {webhook.id}")
        return secret

    @staticmethod
    def get_active_secret(webhook: Webhook) -> Optional[WebhookSecret]:
        """Get the active secret for a webhook."""
        return webhook.secrets.first()

    @staticmethod
    def validate_secret(webhook: Webhook, provided_token: str) -> bool:
        """Validate a provided token against the webhook's secret."""
        active_secret = WebhookSecretService.get_active_secret(webhook)
        if not active_secret:
            return False
        
        return secrets.compare_digest(active_secret.token, provided_token)

    @staticmethod
    def rotate_secret(webhook: Webhook) -> WebhookSecret:
        """Rotate the secret for a webhook."""
        return WebhookSecretService.generate_secret(webhook)


class WebhookEventService:
    """Service for managing webhook events and delivery."""

    @staticmethod
    def fire_webhook_event(topic: str, data: Dict[str, Any], 
                          webhook_id: Optional[UUID] = None) -> None:
        """Fire a webhook event for a specific topic."""
        try:
            # Validate topic exists
            get_handler(topic)
            
            fire_webhook.send_robust(
                sender=WebhookEventService,
                topic=topic,
                data=data,
                webhook_id=webhook_id
            )
            
            logger.info(f"Fired webhook event for topic: {topic}")
            
        except TopicNotFound as e:
            logger.error(f"Failed to fire webhook: {str(e)}")
            raise ValidationError(f"Invalid topic: {topic}")
        except Exception as e:
            logger.error(f"Error firing webhook for topic {topic}: {str(e)}")
            raise

    @staticmethod
    def get_webhook_events(webhook: Webhook, limit: int = 100):
        """Get recent events for a webhook."""
        return webhook.events.all().order_by('-created')[:limit]

    @staticmethod
    def get_event_stats(webhook: Webhook, days: int = 30) -> Dict[str, int]:
        """Get event statistics for a webhook."""
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=days)
        
        events = webhook.events.filter(created__gte=cutoff_date)
        
        return {
            'total': events.count(),
            'success': events.filter(status='SUCCESS').count(),
            'failed': events.filter(status='FAILURE').count(),
            'pending': events.filter(status='PENDING').count(),
        }

    @staticmethod
    def retry_failed_event(event_id: int) -> bool:
        """Retry a failed webhook event."""
        try:
            event = WebhookEvent.objects.get(id=event_id)
            
            if event.status != 'FAILURE':
                raise ValidationError("Only failed events can be retried")
            
            if not event.webhook or not event.webhook.active:
                raise ValidationError("Webhook is not active")
            
            # Fire the webhook again
            WebhookEventService.fire_webhook_event(
                topic=event.topic,
                data=event.object,
                webhook_id=event.webhook.uuid
            )
            
            logger.info(f"Retried failed event {event_id}")
            return True
            
        except WebhookEvent.DoesNotExist:
            raise ValidationError("Event not found")
        except Exception as e:
            logger.error(f"Error retrying event {event_id}: {str(e)}")
            raise

    @staticmethod
    def cleanup_old_events(days: int = None) -> int:
        """Clean up old webhook events."""
        settings = get_settings()
        retention_days = days or settings.get('EVENTS_RETENTION_DAYS', 30)
        
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        deleted_count = WebhookEvent.objects.filter(
            created__lt=cutoff_date
        ).count()
        
        WebhookEvent.objects.filter(created__lt=cutoff_date).delete()
        
        logger.info(f"Cleaned up {deleted_count} old webhook events")
        return deleted_count


class WebhookValidationService:
    """Service for webhook validation and testing."""

    @staticmethod
    def validate_webhook_url(url: str) -> bool:
        """Validate that a webhook URL is reachable."""
        import requests
        from requests.exceptions import RequestException
        
        try:
            # Send a test HEAD request
            response = requests.head(url, timeout=10)
            return response.status_code < 500
        except RequestException:
            return False

    @staticmethod
    def test_webhook(webhook: Webhook, test_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Test a webhook with sample data."""
        if not test_data:
            test_data = {
                'test': True,
                'timestamp': timezone.now().isoformat(),
                'message': 'This is a test webhook event'
            }
        
        try:
            # Fire a test event
            WebhookEventService.fire_webhook_event(
                topic='webhook.test',
                data=test_data,
                webhook_id=webhook.uuid
            )
            
            return {
                'success': True,
                'message': 'Test webhook fired successfully',
                'data': test_data
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Test webhook failed: {str(e)}',
                'error': str(e)
            }

    @staticmethod
    def get_webhook_health(webhook: Webhook) -> Dict[str, Any]:
        """Get health status of a webhook."""
        stats = WebhookEventService.get_event_stats(webhook, days=7)
        
        # Calculate success rate
        total_events = stats['total']
        success_rate = 0
        if total_events > 0:
            success_rate = (stats['success'] / total_events) * 100
        
        # Determine health status
        if success_rate >= 95:
            health_status = 'healthy'
        elif success_rate >= 80:
            health_status = 'warning'
        else:
            health_status = 'unhealthy'
        
        return {
            'webhook_id': str(webhook.uuid),
            'url': webhook.url,
            'active': webhook.active,
            'health_status': health_status,
            'success_rate': round(success_rate, 2),
            'events_last_7_days': stats,
            'last_event': webhook.events.first().created if webhook.events.exists() else None
        }
