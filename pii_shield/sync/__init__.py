"""
Synchronization module for PII Shield.
Provides components for synchronizing data between secure network and DMZ.
"""

# Registry for models to be synchronized
_REGISTERED_MODELS = set()


def register_model(model_class):
    """
    Register a model class for synchronization.
    This can be used as a decorator.

    Example:
        @register_model
        class UserProfile(PIIModel):
            ...
    """
    global _REGISTERED_MODELS
    _REGISTERED_MODELS.add(model_class)
    return model_class


def get_registered_models():
    """Get all registered models for synchronization."""
    return list(_REGISTERED_MODELS)
