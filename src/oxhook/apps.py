# pylint: disable=import-outside-toplevel

from django.apps import AppConfig


class WebhooksConfig(AppConfig):
    name = "oxhook"
    default_auto_field = "django.db.models.AutoField"

    def ready(self):
        # Import signal handlers and registry setup without database queries
        # pylint: disable=unused-import
        from oxhook import signals  # Import signals to register them
        
        self._setup_webhook_model_state()
    
    def _setup_webhook_model_state(self):
        """
        Configure l'état abstrait/concret du modèle Webhook selon les settings.
        """
        try:
            from oxhook.utils import is_using_custom_webhook_model
            from django.apps import apps
            
            # Si WEBHOOK_MODEL est défini, rendre le modèle de base abstrait
            if is_using_custom_webhook_model():
                webhook_model = apps.get_model('oxhook', 'Webhook')
                if not webhook_model._meta.abstract:
                    webhook_model._meta.abstract = True
                    
        except Exception:
            # Ignorer les erreurs pendant l'initialisation
            pass
