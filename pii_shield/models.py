from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class PIIModel(models.Model):
    """Abstract base model for PII data synchronized between networks"""

    session_id = models.CharField(max_length=100, db_index=True)
    data_expires_at = models.DateTimeField(db_index=True)

    class Meta:
        abstract = True

    @staticmethod
    def get_expiration_time():
        """Calculate the expiration time based on settings."""
        pii_settings = getattr(settings, "PII_SHIELD", {})
        session_timeout = pii_settings.get("SESSION", {}).get(
            "timeout", 1800
        )  # Default 30 minutes
        return timezone.now() + timedelta(seconds=session_timeout)

    def refresh_expiration(self):
        """Refresh the expiration time of this instance."""
        self.data_expires_at = self.get_expiration_time()
        self.save(update_fields=["data_expires_at"])

    @classmethod
    def cleanup_expired(cls, batch_size=1000):
        """Delete expired instances of this model."""
        return (
            cls.objects.filter(data_expires_at__lt=timezone.now())
            .order_by("data_expires_at")[:batch_size]
            .delete()
        )
