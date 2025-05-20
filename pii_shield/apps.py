from django.apps import AppConfig
from django.conf import settings


class PIIShieldConfig(AppConfig):
    name = "pii_shield"
    verbose_name = "PII Shield"

    def ready(self):
        """Initialize the application when Django is ready."""
        # Import signal handlers and initializers
        try:
            mode = getattr(settings, "PII_SHIELD", {}).get("MODE", "frontend")
            if mode == "frontend":
                from pii_shield.sync import consumer

                # Start consumer if auto_reconnect is enabled in settings
                consumer.initialize()
        except ImportError:
            # Log warning but don't crash on import error
            import logging

            logger = logging.getLogger(__name__)
            logger.warning("Could not initialize PII Shield consumer")

        # Import models module to register models for synchronization
