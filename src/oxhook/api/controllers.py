"""
Webhook API controllers for managing webhooks, topics, events, and related operations.
"""
from typing import List, Optional
from uuid import UUID
from django.http import HttpRequest
from django.core.exceptions import ValidationError
from ninja_extra.pagination import (
    paginate, PageNumberPaginationExtra, PaginatedResponseSchema
)
from ninja_extra import (
    ControllerBase,
    api_controller, http_delete, 
    http_get, http_post, http_put
)
from ninja_extra.permissions import IsAuthenticated

from oxhook.api.services import (
    WebhookService,
    WebhookTopicService,
    WebhookSecretService,
    WebhookEventService,
    WebhookValidationService
)
from oxhook.api.schemas import (
    WebhookSchema,
    WebhookCreateSchema,
    WebhookUpdateSchema,
    WebhookDetailSchema,
    WebhookTopicSchema,
    WebhookTopicCreateSchema,
    WebhookSecretSchema,
    WebhookSecretGenerateSchema,
    WebhookEventSchema,
    WebhookEventDetailSchema,
    WebhookEventCreateSchema,
    WebhookStatsSchema,
    WebhookHealthSchema,
    WebhookTestSchema,
    WebhookTestResultSchema,
    WebhookValidationSchema,
    WebhookOperationResponseSchema,
    WebhookEventRetrySchema,
    WebhookCleanupSchema,
    WebhookCleanupResultSchema,
    WebhookBulkCreateSchema,
    WebhookBulkUpdateSchema,
    WebhookBulkDeleteSchema
)


@api_controller('/webhooks', tags=['Webhooks'], permissions=[IsAuthenticated])
class WebhookController(ControllerBase):
    """Controller for managing webhooks and their configurations."""

    @http_get('', response=PaginatedResponseSchema[WebhookSchema])
    @paginate(PageNumberPaginationExtra, page_size=20)
    def list_webhooks(self, request: HttpRequest, active_only: Optional[bool] = True):
        """List all webhooks with optional filtering."""
        return WebhookService.list_webhooks(active_only=active_only)

    @http_get('/{webhook_id}', response=WebhookDetailSchema)
    def get_webhook(self, request: HttpRequest, webhook_id: UUID):
        """Get detailed information about a specific webhook."""
        return WebhookService.get_webhook(webhook_id)

    @http_post('', response={201: WebhookDetailSchema})
    def create_webhook(self, request: HttpRequest, payload: WebhookCreateSchema):
        """Create a new webhook."""
        webhook = WebhookService.create_webhook(
            url=payload.url,
            topics=payload.topics,
            user=request.user
        )
        return 201, webhook

    @http_put('/{webhook_id}', response=WebhookDetailSchema)
    def update_webhook(self, request: HttpRequest, webhook_id: UUID, payload: WebhookUpdateSchema):
        """Update an existing webhook."""
        return WebhookService.update_webhook(
            webhook_id=webhook_id,
            url=payload.url,
            topics=payload.topics,
            active=payload.active
        )

    @http_delete('/{webhook_id}', response=WebhookOperationResponseSchema)
    def delete_webhook(self, request: HttpRequest, webhook_id: UUID):
        """Delete a webhook."""
        success = WebhookService.delete_webhook(webhook_id)
        return WebhookOperationResponseSchema(
            success=success,
            message="Webhook deleted successfully",
            webhook_id=webhook_id
        )

    # Webhook Health and Statistics
    @http_get('/{webhook_id}/health', response=WebhookHealthSchema)
    def get_webhook_health(self, request: HttpRequest, webhook_id: UUID):
        """Get health status and statistics for a webhook."""
        webhook = WebhookService.get_webhook(webhook_id)
        return WebhookValidationService.get_webhook_health(webhook)

    @http_get('/{webhook_id}/stats', response=WebhookStatsSchema)
    def get_webhook_stats(self, request: HttpRequest, webhook_id: UUID, days: int = 30):
        """Get statistics for a webhook."""
        webhook = WebhookService.get_webhook(webhook_id)
        stats = WebhookEventService.get_event_stats(webhook, days)
        
        # Calculate success rate
        total = stats['total']
        success_rate = (stats['success'] / total * 100) if total > 0 else 0
        
        return WebhookStatsSchema(
            total=stats['total'],
            success=stats['success'],
            failed=stats['failed'],
            pending=stats['pending'],
            success_rate=round(success_rate, 2)
        )

    # Webhook Testing
    @http_post('/{webhook_id}/test', response=WebhookTestResultSchema)
    def test_webhook(self, request: HttpRequest, webhook_id: UUID, payload: WebhookTestSchema):
        """Test a webhook with sample data."""
        webhook = WebhookService.get_webhook(webhook_id)
        return WebhookValidationService.test_webhook(webhook, payload.test_data)

    @http_post('/validate-url', response=WebhookValidationSchema)
    def validate_webhook_url(self, request: HttpRequest, url: str):
        """Validate if a webhook URL is reachable."""
        import time
        start_time = time.time()
        
        is_reachable = WebhookValidationService.validate_webhook_url(url)
        response_time = time.time() - start_time
        
        return WebhookValidationSchema(
            url=url,
            is_reachable=is_reachable,
            response_time=round(response_time, 3),
            status_code=200 if is_reachable else None
        )


@api_controller('/webhooks/{webhook_id}/secrets', tags=['Webhook Secrets'], permissions=[IsAuthenticated])
class WebhookSecretController(ControllerBase):
    """Controller for managing webhook secrets."""

    @http_get('', response=WebhookSecretSchema)
    def get_webhook_secret(self, request: HttpRequest, webhook_id: UUID):
        """Get the current secret for a webhook."""
        webhook = WebhookService.get_webhook(webhook_id)
        secret = WebhookSecretService.get_active_secret(webhook)
        if not secret:
            raise ValidationError("No active secret found for this webhook")
        return secret

    @http_post('/generate', response=WebhookSecretSchema)
    def generate_webhook_secret(self, request: HttpRequest, webhook_id: UUID, payload: WebhookSecretGenerateSchema):
        """Generate a new secret for a webhook."""
        webhook = WebhookService.get_webhook(webhook_id)
        return WebhookSecretService.generate_secret(webhook, payload.length)

    @http_post('/rotate', response=WebhookSecretSchema)
    def rotate_webhook_secret(self, request: HttpRequest, webhook_id: UUID):
        """Rotate the secret for a webhook."""
        webhook = WebhookService.get_webhook(webhook_id)
        return WebhookSecretService.rotate_secret(webhook)


@api_controller('/webhook-topics', tags=['Webhook Topics'], permissions=[IsAuthenticated])
class WebhookTopicController(ControllerBase):
    """Controller for managing webhook topics."""

    @http_get('', response=PaginatedResponseSchema[WebhookTopicSchema])
    @paginate(PageNumberPaginationExtra, page_size=50)
    def list_topics(self, request: HttpRequest):
        """List all available webhook topics."""
        return WebhookTopicService.list_available_topics()

    @http_get('/{topic_name}', response=WebhookTopicSchema)
    def get_topic(self, request: HttpRequest, topic_name: str):
        """Get details about a specific topic."""
        return WebhookTopicService.get_topic_by_name(topic_name)

    @http_post('', response={201: WebhookTopicSchema})
    def create_topic(self, request: HttpRequest, payload: WebhookTopicCreateSchema):
        """Create a new webhook topic."""
        topic = WebhookTopicService.create_topic(payload.name)
        return 201, topic

    @http_get('/{topic_name}/webhooks', response=PaginatedResponseSchema[WebhookSchema])
    @paginate(PageNumberPaginationExtra, page_size=20)
    def get_topic_webhooks(self, request: HttpRequest, topic_name: str):
        """Get all webhooks subscribed to a specific topic."""
        return WebhookTopicService.get_webhooks_for_topic(topic_name)


@api_controller('/webhook-events', tags=['Webhook Events'], permissions=[IsAuthenticated])
class WebhookEventController(ControllerBase):
    """Controller for managing webhook events."""

    @http_post('/fire', response=WebhookOperationResponseSchema)
    def fire_webhook_event(self, request: HttpRequest, payload: WebhookEventCreateSchema):
        """Manually fire a webhook event."""
        try:
            WebhookEventService.fire_webhook_event(
                topic=payload.topic,
                data=payload.data,
                webhook_id=payload.webhook_id
            )
            return WebhookOperationResponseSchema(
                success=True,
                message=f"Webhook event fired successfully for topic: {payload.topic}",
                webhook_id=payload.webhook_id
            )
        except Exception as e:
            return WebhookOperationResponseSchema(
                success=False,
                message=f"Failed to fire webhook event: {str(e)}",
                webhook_id=payload.webhook_id
            )

    @http_get('/{webhook_id}', response=PaginatedResponseSchema[WebhookEventSchema])
    @paginate(PageNumberPaginationExtra, page_size=50)
    def get_webhook_events(self, request: HttpRequest, webhook_id: UUID, limit: int = 100):
        """Get events for a specific webhook."""
        webhook = WebhookService.get_webhook(webhook_id)
        return WebhookEventService.get_webhook_events(webhook, limit)

    @http_get('/detail/{event_id}', response=WebhookEventDetailSchema)
    def get_event_detail(self, request: HttpRequest, event_id: int):
        """Get detailed information about a specific event."""
        from oxhook.models import WebhookEvent
        from django.shortcuts import get_object_or_404
        return get_object_or_404(WebhookEvent, id=event_id)

    @http_post('/retry', response=WebhookOperationResponseSchema)
    def retry_failed_event(self, request: HttpRequest, payload: WebhookEventRetrySchema):
        """Retry a failed webhook event."""
        try:
            success = WebhookEventService.retry_failed_event(payload.event_id)
            return WebhookOperationResponseSchema(
                success=success,
                message=f"Event {payload.event_id} retried successfully"
            )
        except Exception as e:
            return WebhookOperationResponseSchema(
                success=False,
                message=f"Failed to retry event: {str(e)}"
            )

    @http_post('/cleanup', response=WebhookCleanupResultSchema)
    def cleanup_old_events(self, request: HttpRequest, payload: WebhookCleanupSchema):
        """Clean up old webhook events."""
        deleted_count = WebhookEventService.cleanup_old_events(payload.days)
        return WebhookCleanupResultSchema(
            deleted_count=deleted_count,
            message=f"Successfully cleaned up {deleted_count} old webhook events"
        )


@api_controller('/webhooks/bulk', tags=['Webhook Bulk Operations'], permissions=[IsAuthenticated])
class WebhookBulkController(ControllerBase):
    """Controller for bulk webhook operations."""

    @http_post('/create', response=List[WebhookDetailSchema])
    def bulk_create_webhooks(self, request: HttpRequest, payload: WebhookBulkCreateSchema):
        """Create multiple webhooks at once."""
        created_webhooks = []
        for webhook_data in payload.webhooks:
            try:
                webhook = WebhookService.create_webhook(
                    url=webhook_data.url,
                    topics=webhook_data.topics,
                    user=request.user
                )
                created_webhooks.append(webhook)
            except Exception as e:
                # Log error but continue with other webhooks
                import logging
                logging.error(f"Failed to create webhook {webhook_data.url}: {str(e)}")
                continue
        
        return created_webhooks

    @http_put('/update', response=WebhookOperationResponseSchema)
    def bulk_update_webhooks(self, request: HttpRequest, payload: WebhookBulkUpdateSchema):
        """Update multiple webhooks at once."""
        updated_count = 0
        failed_count = 0
        
        for webhook_id in payload.webhook_ids:
            try:
                WebhookService.update_webhook(
                    webhook_id=webhook_id,
                    url=payload.updates.url,
                    topics=payload.updates.topics,
                    active=payload.updates.active
                )
                updated_count += 1
            except Exception as e:
                import logging
                logging.error(f"Failed to update webhook {webhook_id}: {str(e)}")
                failed_count += 1
                continue
        
        return WebhookOperationResponseSchema(
            success=failed_count == 0,
            message=f"Updated {updated_count} webhooks, {failed_count} failed"
        )

    @http_delete('/delete', response=WebhookOperationResponseSchema)
    def bulk_delete_webhooks(self, request: HttpRequest, payload: WebhookBulkDeleteSchema):
        """Delete multiple webhooks at once."""
        deleted_count = 0
        failed_count = 0
        
        for webhook_id in payload.webhook_ids:
            try:
                WebhookService.delete_webhook(webhook_id)
                deleted_count += 1
            except Exception as e:
                import logging
                logging.error(f"Failed to delete webhook {webhook_id}: {str(e)}")
                failed_count += 1
                continue
        
        return WebhookOperationResponseSchema(
            success=failed_count == 0,
            message=f"Deleted {deleted_count} webhooks, {failed_count} failed"
        )
