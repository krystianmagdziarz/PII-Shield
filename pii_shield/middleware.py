import logging

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class PIIShieldMiddleware(MiddlewareMixin):
    """
    Middleware that checks for existence of required user data in frontend database.
    Initiates synchronization when data is missing or expiring.
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.pii_settings = getattr(settings, "PII_SHIELD", {})

    def process_request(self, request):
        """
        Process the request before view.
        Check if required PII data is available, and initiate sync if needed.
        """
        # Skip for non-authenticated users or paths in the exclusion list
        if not request.user.is_authenticated:
            return None

        # Get excluded paths from settings
        excluded_paths = self.pii_settings.get("ADVANCED", {}).get("excluded_paths", [])

        # Skip for excluded paths
        for path in excluded_paths:
            if request.path.startswith(path):
                return None

        # Check if sync is already in progress
        if getattr(request.session, "pii_sync_in_progress", False):
            waiting_view = self.pii_settings.get("ADVANCED", {}).get("waiting_view")
            if waiting_view and request.path != reverse(waiting_view):
                # Store the original path in session for redirect after sync
                request.session[
                    self.pii_settings.get("ADVANCED", {}).get(
                        "redirect_session_key", "redirect_after_sync"
                    )
                ] = request.path
                return redirect(waiting_view)
            return None

        # Check if data is available and not expiring
        if not self._check_pii_data(request):
            # Initiate sync
            self._initiate_sync(request)

            # Redirect to waiting page if configured
            waiting_view = self.pii_settings.get("ADVANCED", {}).get("waiting_view")
            if waiting_view:
                # Store the original path in session for redirect after sync
                request.session[
                    self.pii_settings.get("ADVANCED", {}).get(
                        "redirect_session_key", "redirect_after_sync"
                    )
                ] = request.path
                return redirect(waiting_view)

        return None

    def _check_pii_data(self, request):
        """
        Check if required PII data is available and not expiring.
        Returns True if data is available and not expiring, False otherwise.
        """
        try:
            from pii_shield.sync.publisher import get_registered_models

            # Get registered models
            models = get_registered_models()
            if not models:
                # No models registered for sync, nothing to check
                return True

            # Get refresh threshold from settings
            refresh_threshold = self.pii_settings.get("SESSION", {}).get(
                "refresh_threshold", 300
            )  # 5 minutes
            threshold_time = timezone.now() + timezone.timedelta(
                seconds=refresh_threshold
            )

            # Check if data is available and not expiring
            session_id = request.session.session_key

            for model_class in models:
                # Check if data exists for this session
                if not model_class.objects.filter(session_id=session_id).exists():
                    # Data not available
                    return False

                # Check if data is expiring
                if model_class.objects.filter(
                    session_id=session_id, data_expires_at__lt=threshold_time
                ).exists():
                    # Data is expiring
                    return False

            # All data is available and not expiring
            return True

        except Exception as e:
            # Log error and assume data is not available
            logger.exception("Error checking PII data: %s", e)
            return False

    def _initiate_sync(self, request):
        """
        Initiate data synchronization for the current user session.
        """
        try:
            # Import here to avoid circular imports
            from pii_shield.sync.publisher import sync_data

            # Mark sync as in progress
            request.session["pii_sync_in_progress"] = True

            # Get session ID
            session_id = request.session.session_key

            # Sync data for all registered models
            sync_data(request.user, session_id)

            # Note: sync will be completed by the consumer

        except Exception as e:
            # Log error
            logger.exception("Error initiating PII data sync: %s", e)
            # Clear sync in progress flag
            request.session.pop("pii_sync_in_progress", None)
