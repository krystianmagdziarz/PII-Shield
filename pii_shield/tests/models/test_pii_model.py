"""
Tests for PIIModel class.
"""

import time
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from pii_shield.models import PIIModel


class TestModel(PIIModel):
    """Test model inheriting from PIIModel."""

    class Meta:
        app_label = "pii_shield"


class PIIModelTests(TestCase):
    """Tests for the PIIModel class."""

    def setUp(self):
        """Set up test data."""
        self.session_id = "test-session-id"
        self.expiration_time = timezone.now() + timedelta(minutes=30)

        # Create a test instance
        self.test_instance = TestModel.objects.create(
            session_id=self.session_id, data_expires_at=self.expiration_time
        )

    def test_get_expiration_time(self):
        """Test get_expiration_time method."""
        with mock.patch.object(
            settings,
            "PII_SHIELD",
            {
                "SESSION": {"timeout": 3600}  # 1 hour
            },
        ):
            expiration_time = TestModel.get_expiration_time()

            # Expect expiration time to be now + 1 hour (with small leeway)
            expected_time = timezone.now() + timedelta(seconds=3600)
            self.assertAlmostEqual(
                expiration_time.timestamp(),
                expected_time.timestamp(),
                delta=5,  # Allow 5 seconds leeway
            )

    def test_refresh_expiration(self):
        """Test refresh_expiration method."""
        old_expiration = self.test_instance.data_expires_at

        # Wait a short time
        time.sleep(0.1)

        # Refresh expiration
        self.test_instance.refresh_expiration()

        # Get updated instance from database
        updated_instance = TestModel.objects.get(pk=self.test_instance.pk)

        # Expect expiration time to be updated
        self.assertGreater(updated_instance.data_expires_at, old_expiration)

    def test_cleanup_expired(self):
        """Test cleanup_expired classmethod."""
        # Create an expired instance
        expired_instance = TestModel.objects.create(
            session_id="expired-session",
            data_expires_at=timezone.now() - timedelta(minutes=5),
        )

        # Verify we have 2 instances (1 expired, 1 not)
        self.assertEqual(TestModel.objects.count(), 2)

        # Run cleanup
        deleted_count, _ = TestModel.cleanup_expired()

        # Verify expired instance was deleted
        self.assertEqual(deleted_count, 1)
        self.assertEqual(TestModel.objects.count(), 1)
        self.assertEqual(TestModel.objects.first().pk, self.test_instance.pk)
