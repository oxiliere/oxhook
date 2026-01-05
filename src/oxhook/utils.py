"""
Utilitaires pour gérer les modèles Webhook avec configuration par settings.
"""

from django.apps import apps
from django.db import models
from django.conf import settings
from django.utils.module_loading import import_string
from typing import Type


def get_webhook_model_string():
    return getattr(settings, 'WEBHOOK_MODEL', 'oxhook.Webhook')

def get_webhook_model() -> Type[models.Model]:
    """
    Retourne le modèle Webhook à utiliser.
    
    Ordre de priorité :
    1. WEBHOOK_MODEL dans settings (ex: 'organisations.OrganizationWebhook')
    2. Modèle Webhook de base ('oxhook.Webhook')
    """
    # Vérifier si un modèle personnalisé est défini dans les settings
    custom_model = getattr(settings, 'WEBHOOK_MODEL', None)
    
    if custom_model:
        try:
            # Parse 'app_label.ModelName'
            app_label, model_name = custom_model.split('.')
            return apps.get_model(app_label, model_name)
        except (ValueError, LookupError) as e:
            raise ValueError(
                f"WEBHOOK_MODEL='{custom_model}' is invalid. "
                f"Use format 'app_label.ModelName'. Error: {e}"
            )
    
    # Utiliser le modèle de base par défaut
    return apps.get_model('oxhook', 'Webhook')


def is_using_custom_webhook_model() -> bool:
    """
    Vérifie si un modèle Webhook personnalisé est configuré.
    """
    return hasattr(settings, 'WEBHOOK_MODEL') and settings.WEBHOOK_MODEL is not None


def get_webhook_model_string() -> str:
    """
    Retourne la chaîne du modèle Webhook configuré.
    """
    if is_using_custom_webhook_model():
        return settings.WEBHOOK_MODEL
    return 'oxhook.Webhook'


def validate_webhook_model_setting() -> bool:
    """
    Valide que le modèle WEBHOOK_MODEL configuré existe et est valide.
    """
    if not is_using_custom_webhook_model():
        return True
    
    try:
        get_webhook_model()
        return True
    except (ValueError, LookupError):
        return False


def get_webhook_schema_class(default_schema=None):
    """
    Retourne la classe de schéma configurée pour les webhooks.
    """
    schema_path = getattr(settings, 'WEBHOOK_MODEL_SCHEMA', None)
    
    if not schema_path:
        if default_schema:
            return default_schema
        raise ValueError("WEBHOOK_MODEL_SCHEMA is not configured and no default_schema provided")
    
    try:
        return import_string(schema_path)
    except (ImportError, AttributeError) as e:
        if default_schema:
            return default_schema
        raise ValueError(
            f"WEBHOOK_MODEL_SCHEMA='{schema_path}' is invalid. "
            f"Use format 'app.module.ClassName'. Error: {e}"
        )


def get_webhook_permissions():
    """
    Retourne les classes de permissions configurées pour les webhooks.
    """
    permission_paths = getattr(settings, 'WEBHOOK_PERMISSIONS', [])
    
    if not permission_paths:
        return []
    
    permissions = []
    for permission_path in permission_paths:
        if not permission_path:  # Skip empty strings
            continue
            
        try:
            permission_class = import_string(permission_path)
            permissions.append(permission_class)
        except (ImportError, AttributeError) as e:
            raise ValueError(
                f"WEBHOOK_PERMISSIONS contains invalid permission '{permission_path}'. "
                f"Use format 'module.ClassName'. Error: {e}"
            )
    
    return permissions


def create_webhook(**kwargs):
    """
    Crée une instance de webhook en utilisant le bon modèle.
    """
    WebhookModel = get_webhook_model()
    return WebhookModel.objects.create(**kwargs)


def get_all_webhooks():
    """
    Retourne tous les webhooks du modèle concret.
    """
    WebhookModel = get_webhook_model()
    return WebhookModel.objects.all()


def get_active_webhooks():
    """
    Retourne tous les webhooks actifs.
    """
    WebhookModel = get_webhook_model()
    return WebhookModel.objects.filter(active=True)


class WebhookModelMixin:
    """
    Mixin pour ajouter des fonctionnalités aux modèles qui héritent de Webhook.
    """
    
    @classmethod
    def get_webhook_model_name(cls):
        """Retourne le nom du modèle webhook"""
        return f"{cls._meta.app_label}.{cls.__name__}"
    
    @classmethod
    def is_base_webhook(cls):
        """Vérifie si c'est le modèle Webhook de base"""
        return cls.__name__ == 'Webhook' and cls._meta.app_label == 'oxhook'
    
    @classmethod
    def is_webhook_subclass(cls):
        """Vérifie si c'est une sous-classe de Webhook"""
        return (hasattr(cls, '__bases__') and 
                any(base.__name__ == 'Webhook' for base in cls.__bases__))
