# pylint: disable=redefined-builtin
from typing import Dict, Any
import json
from uuid import UUID
from datetime import timedelta

from django.dispatch import Signal, receiver
from django.utils import timezone

from oxhook.models import Webhook

from .settings import get_settings
from .tasks import fire_webhook as task_fire_webhook
from .util import cache
from .exceptions import InvalidPayloadType
from .registry import get_handler




fire_webhook = Signal()



@receiver(fire_webhook, dispatch_uid="main_fire_webhook_handler")
def handle_fire_webhook(
    sender: Any, topic: str, 
    data: Dict | None = None, 
    webhook_id: UUID | str | None = None, 
    **kwargs
    ):
    wh_settings = get_settings()
    handler = get_handler(topic)
    payload_body = handler(data)

    if not isinstance(payload_body, (str, dict)) and payload_body is not None:
        raise InvalidPayloadType("Payload must be a string/dict/None.")
    
    if webhook_id is not None:
        webhook_ids = [webhook_id]
    else:
        webhook_ids = _find_webhooks(topic)


    for id, uuid in webhook_ids:
        payload_dict = dict(
            object=payload_body,
            topic=topic,
            timestamp=timezone.now().timestamp(),
            webhook_uuid=str(uuid),
        )
        payload = json.dumps(payload_body, cls=wh_settings['PAYLOAD_ENCODER_CLASS'])

        if wh_settings.get('MODE') == 'LIVE':
            task_fire_webhook.delay(
                id,
                payload,
                topic=topic,
            )
        else:
            print("\n" + "="*80)
            print(f"🎯 WEBHOOK FIRED (CONSOLE MODE)")
            print("="*80)
            print(f"📋 Topic: {topic}")
            print(f"🆔 Webhook UUID: {uuid}")
            print(f"⏰ Timestamp: {payload_dict['timestamp']}")
            print(f"\n📦 Payload:")
            print(json.dumps(payload_dict, indent=2, ensure_ascii=False))
            print("="*80 + "\n")



def _find_webhooks(topic: str):
    """
    In tests and for smaller setups we don't want to cache the query.
    """
    if get_settings()["USE_CACHE"]:
        return _query_webhooks_cached(topic)
    return _query_webhooks(topic)


@cache(ttl=timedelta(minutes=1))
def _query_webhooks_cached(topic: str):
    """
    Cache the calls to the database so we're not polling the db anytime a signal is triggered.
    """
    return _query_webhooks(topic)


def _query_webhooks(topic: str):
    return Webhook.objects.filter(active=True, topics__name=topic).values_list(
        "id", "uuid"
    )
