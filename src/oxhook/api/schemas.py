"""
Webhook API schemas for request/response validation.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
from ninja import ModelSchema, Schema
from pydantic import Field, field_validator

from oxhook.models import (
    Webhook,
    WebhookTopic,
    WebhookSecret,
    WebhookEvent
)


# Webhook Schemas
class WebhookSchema(ModelSchema):
    """Schema for webhook output."""
    topics: List[str] = Field(..., description="List of topic names")
    
    class Meta:
        model = Webhook
        fields = ['uuid', 'url', 'active', 'created', 'modified']

    @staticmethod
    def resolve_topics(obj):
        return [topic.name for topic in obj.topics.all()]


class WebhookCreateSchema(Schema):
    """Schema for creating a new webhook."""
    url: str = Field(..., description="Webhook URL endpoint")
    topics: List[str] = Field(..., description="List of topic names to subscribe to")
    active: bool = Field(True, description="Whether the webhook is active")

    @field_validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

    @field_validator('topics')
    def validate_topics_not_empty(cls, v):
        if not v:
            raise ValueError('At least one topic must be specified')
        return v


class WebhookUpdateSchema(Schema):
    """Schema for updating a webhook."""
    url: Optional[str] = Field(None, description="Webhook URL endpoint")
    topics: Optional[List[str]] = Field(None, description="List of topic names to subscribe to")
    active: Optional[bool] = Field(None, description="Whether the webhook is active")

    @field_validator('url')
    def validate_url(cls, v):
        if v is not None and not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class WebhookDetailSchema(WebhookSchema):
    """Detailed webhook schema with additional information."""
    secret_token: Optional[str] = Field(None, description="Current secret token")
    topics_count: int = Field(..., description="Number of subscribed topics")
    events_count: int = Field(..., description="Total number of events")
    
    @staticmethod
    def resolve_secret_token(obj):
        secret = obj.secrets.first()
        return secret.token if secret else None
    
    @staticmethod
    def resolve_topics_count(obj):
        return obj.topics.count()
    
    @staticmethod
    def resolve_events_count(obj):
        return obj.events.count()


# Webhook Topic Schemas
class WebhookTopicSchema(ModelSchema):
    """Schema for webhook topic output."""
    webhooks_count: int = Field(..., description="Number of webhooks subscribed to this topic")
    
    class Meta:
        model = WebhookTopic
        fields = ['id', 'name']

    @staticmethod
    def resolve_webhooks_count(obj):
        return obj.webhooks.filter(active=True).count()


class WebhookTopicCreateSchema(Schema):
    """Schema for creating a webhook topic."""
    name: str = Field(..., description="Topic name (format: category.action)")

    @field_validator('name')
    def validate_topic_format(cls, v):
        import re
        if not re.match(r'\w+\.\w+', v):
            raise ValueError('Topic name must follow format: category.action')
        return v


# Webhook Secret Schemas
class WebhookSecretSchema(ModelSchema):
    """Schema for webhook secret output."""
    class Meta:
        model = WebhookSecret
        fields = ['token', 'created']


class WebhookSecretGenerateSchema(Schema):
    """Schema for generating a new webhook secret."""
    length: int = Field(32, ge=16, le=64, description="Secret token length")


# Webhook Event Schemas
class WebhookEventSchema(ModelSchema):
    """Schema for webhook event output."""
    webhook_url: Optional[str] = Field(None, description="Webhook URL at time of event")
    
    class Meta:
        model = WebhookEvent
        fields = ['id', 'object', 'status', 'created', 'url', 'topic']

    @staticmethod
    def resolve_webhook_url(obj):
        return obj.webhook.url if obj.webhook else None


class WebhookEventDetailSchema(WebhookEventSchema):
    """Detailed webhook event schema."""
    webhook_uuid: Optional[UUID] = Field(None, description="Webhook UUID")
    retry_count: int = Field(0, description="Number of retry attempts")
    
    @staticmethod
    def resolve_webhook_uuid(obj):
        return obj.webhook.uuid if obj.webhook else None


class WebhookEventCreateSchema(Schema):
    """Schema for manually creating a webhook event."""
    topic: str = Field(..., description="Event topic")
    data: Dict[str, Any] = Field(..., description="Event data payload")
    webhook_id: Optional[UUID] = Field(None, description="Specific webhook UUID (optional)")


# Statistics and Health Schemas
class WebhookStatsSchema(Schema):
    """Schema for webhook statistics."""
    total: int = Field(..., description="Total number of events")
    success: int = Field(..., description="Number of successful events")
    failed: int = Field(..., description="Number of failed events")
    pending: int = Field(..., description="Number of pending events")
    success_rate: float = Field(..., description="Success rate percentage")


class WebhookHealthSchema(Schema):
    """Schema for webhook health status."""
    webhook_id: str = Field(..., description="Webhook UUID")
    url: str = Field(..., description="Webhook URL")
    active: bool = Field(..., description="Whether webhook is active")
    health_status: str = Field(..., description="Health status: healthy, warning, unhealthy")
    success_rate: float = Field(..., description="Success rate percentage")
    events_last_7_days: WebhookStatsSchema = Field(..., description="Events statistics for last 7 days")
    last_event: Optional[datetime] = Field(None, description="Timestamp of last event")


# Test and Validation Schemas
class WebhookTestSchema(Schema):
    """Schema for testing a webhook."""
    test_data: Optional[Dict[str, Any]] = Field(None, description="Custom test data (optional)")


class WebhookTestResultSchema(Schema):
    """Schema for webhook test results."""
    success: bool = Field(..., description="Whether the test was successful")
    message: str = Field(..., description="Test result message")
    data: Optional[Dict[str, Any]] = Field(None, description="Test data that was sent")
    error: Optional[str] = Field(None, description="Error message if test failed")


class WebhookValidationSchema(Schema):
    """Schema for webhook URL validation."""
    url: str = Field(..., description="URL to validate")
    is_reachable: bool = Field(..., description="Whether the URL is reachable")
    response_time: Optional[float] = Field(None, description="Response time in seconds")
    status_code: Optional[int] = Field(None, description="HTTP status code")


# Bulk Operations Schemas
class WebhookBulkCreateSchema(Schema):
    """Schema for bulk webhook creation."""
    webhooks: List[WebhookCreateSchema] = Field(..., description="List of webhooks to create")


class WebhookBulkUpdateSchema(Schema):
    """Schema for bulk webhook updates."""
    webhook_ids: List[UUID] = Field(..., description="List of webhook UUIDs to update")
    updates: WebhookUpdateSchema = Field(..., description="Updates to apply to all webhooks")


class WebhookBulkDeleteSchema(Schema):
    """Schema for bulk webhook deletion."""
    webhook_ids: List[UUID] = Field(..., description="List of webhook UUIDs to delete")


# Response Schemas
class WebhookListResponseSchema(Schema):
    """Schema for webhook list response."""
    webhooks: List[WebhookSchema]
    total: int = Field(..., description="Total number of webhooks")


class WebhookOperationResponseSchema(Schema):
    """Schema for webhook operation responses."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Operation result message")
    webhook_id: Optional[UUID] = Field(None, description="Webhook UUID if applicable")


class WebhookEventRetrySchema(Schema):
    """Schema for retrying webhook events."""
    event_id: int = Field(..., description="Event ID to retry")


class WebhookCleanupSchema(Schema):
    """Schema for webhook event cleanup."""
    days: Optional[int] = Field(None, ge=1, le=365, description="Number of days to retain events")


class WebhookCleanupResultSchema(Schema):
    """Schema for cleanup operation results."""
    deleted_count: int = Field(..., description="Number of events deleted")
    message: str = Field(..., description="Cleanup result message")
