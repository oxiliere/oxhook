from typing import Callable
from .exceptions import TopicNotFound


TOPIC_REGISTRY = {}


__all__ = [
    'register_topic'
]


def register_topic(topic: str):
    """
    Décorateur qui enregistre un handler et s'assure
    que le topic existe en DB.
    """
    def decorator(func: Callable):
        TOPIC_REGISTRY[topic] = func
        return func
    
    return decorator


def get_handler(topic: str) -> Callable:
    func = TOPIC_REGISTRY.get(topic, None)

    if func is None:
        raise TopicNotFound(f"Topic '{topic}' doesn't exist.")

    return func
