"""
PII-Shield - Django package for selective data synchronization between secure networks.
"""

__version__ = "0.1.0"

default_app_config = "pii_shield.apps.PIIShieldConfig"

# Convenience import for common operations
from pii_shield.sync.publisher import sync_data
