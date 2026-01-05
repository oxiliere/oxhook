from django import forms
from oxhook.utils import get_webhook_model



WebhookModel = get_webhook_model()

class WebhookForm(forms.ModelForm):
    class Meta:
        model = WebhookModel
        fields = [
            "url",
            "active",
            "topics",
        ]
