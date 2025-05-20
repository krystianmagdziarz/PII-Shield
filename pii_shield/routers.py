import inspect

from django.apps import apps
from django.conf import settings


class PIIRouter:
    """
    Database router for PII models.
    Routes read/write operations for PII models to the frontend database.
    All other operations are routed to the default database.
    """

    def _is_pii_model(self, model):
        """Check if a model is a PII model (inherits from PIIModel)."""
        from pii_shield.models import PIIModel

        # Get all base classes
        bases = inspect.getmro(model)
        # Check if PIIModel is in the bases, but not the same class
        return PIIModel in bases and model != PIIModel

    def db_for_read(self, model, **hints):
        """Route read operations for PII models to 'frontend'."""
        if self._is_pii_model(model):
            return "frontend"
        return None  # Use default database

    def db_for_write(self, model, **hints):
        """Route write operations for PII models to 'frontend'."""
        if self._is_pii_model(model):
            return "frontend"
        return None  # Use default database

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between PII models.
        Allow relations between PII models and non-PII models if configured.
        """
        from pii_shield.models import PIIModel

        # Always allow relations between two PII models
        if isinstance(obj1, PIIModel) and isinstance(obj2, PIIModel):
            return True

        # For mixed relations, check settings
        pii_settings = getattr(settings, "PII_SHIELD", {})
        allow_mixed = pii_settings.get("ADVANCED", {}).get(
            "allow_mixed_relations", False
        )

        if allow_mixed:
            return True

        # By default, don't allow relations between PII and non-PII models
        if isinstance(obj1, PIIModel) or isinstance(obj2, PIIModel):
            return False

        # Let Django decide for other models
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Allow migrations for PIIModel subclasses on the frontend database.
        Allow migrations for all other models on the default database.
        """
        # If we don't have a model name, let Django handle it
        if model_name is None:
            return None

        # Get the model class
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            # If model doesn't exist yet, let Django handle it
            return None

        # For PII models, only allow migrations on frontend database
        if self._is_pii_model(model):
            return db == "frontend"

        # For non-PII models, only allow migrations on default database
        return db != "frontend"
