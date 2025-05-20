"""
Publisher module for PII Shield.
Provides components for publishing model data to Redis.
"""

import logging

import redis
from django.conf import settings
from django.core import serializers
from django.db import transaction

logger = logging.getLogger(__name__)


class Publisher:
    """
    Publisher for synchronizing model data to Redis.
    """

    def __init__(self):
        """Initialize the publisher with Redis connection from settings."""
        self.pii_settings = getattr(settings, "PII_SHIELD", {})
        self.redis_settings = self.pii_settings.get("REDIS", {})
        self.channel_settings = self.pii_settings.get("CHANNELS", {})
        self.sync_settings = self.pii_settings.get("SYNC", {})

        # Connect to Redis
        self.redis = redis.Redis(
            host=self.redis_settings.get("host", "localhost"),
            port=self.redis_settings.get("port", 6379),
            password=self.redis_settings.get("password"),
            db=self.redis_settings.get("db", 0),
            ssl=self.redis_settings.get("ssl", False),
            socket_timeout=self.redis_settings.get("socket_timeout", 5),
            socket_connect_timeout=self.redis_settings.get("socket_connect_timeout", 5),
            retry_on_timeout=self.redis_settings.get("retry_on_timeout", True),
            health_check_interval=self.redis_settings.get("health_check_interval", 30),
        )

    def publish(self, channel, message):
        """
        Publish a message to a Redis channel.

        Args:
            channel (str): Redis channel to publish to.
            message (str): Message to publish.

        Returns:
            int: Number of subscribers that received the message.
        """
        try:
            # Add channel prefix from settings
            prefix = self.channel_settings.get("prefix", "pii_shield")
            full_channel = f"{prefix}:{channel}"

            # Publish message
            result = self.redis.publish(full_channel, message)

            # Log debug info
            logger.debug(
                f"Published message to channel {full_channel}: {result} subscribers received the message"
            )

            return result
        except Exception as e:
            logger.exception(f"Error publishing message to channel {channel}: {e}")
            raise

    def publish_model(self, instance, channel=None):
        """
        Publish a model instance to Redis.

        Args:
            instance: Model instance to publish.
            channel (str, optional): Redis channel to publish to.
                If not provided, uses the model name as channel.

        Returns:
            int: Number of subscribers that received the message.
        """
        try:
            # Serialize model instance
            serialized = serializers.serialize("json", [instance])

            # Get channel name
            if channel is None:
                channel = self.channel_settings.get("default", "default")

            # Publish serialized instance
            return self.publish(channel, serialized)
        except Exception as e:
            logger.exception(
                f"Error publishing model {instance.__class__.__name__}: {e}"
            )
            raise

    def publish_batch(self, instances, channel=None):
        """
        Publish a batch of model instances to Redis.

        Args:
            instances: Iterable of model instances to publish.
            channel (str, optional): Redis channel to publish to.
                If not provided, uses the model name as channel.

        Returns:
            int: Number of subscribers that received the last message.
        """
        try:
            # Get batch size from settings
            batch_size = self.sync_settings.get("batch_size", 100)

            # Process instances in batches
            result = 0
            batch = []

            for instance in instances:
                batch.append(instance)

                if len(batch) >= batch_size:
                    # Serialize batch
                    serialized = serializers.serialize("json", batch)

                    # Get channel name
                    if channel is None:
                        channel = self.channel_settings.get("default", "default")

                    # Publish serialized batch
                    result = self.publish(channel, serialized)

                    # Clear batch
                    batch = []

            # Publish remaining instances
            if batch:
                # Serialize batch
                serialized = serializers.serialize("json", batch)

                # Get channel name
                if channel is None:
                    channel = self.channel_settings.get("default", "default")

                # Publish serialized batch
                result = self.publish(channel, serialized)

            return result
        except Exception as e:
            logger.exception(f"Error publishing batch: {e}")
            raise


# Singleton instance of Publisher
_publisher = None


def get_publisher():
    """Get singleton instance of Publisher."""
    global _publisher
    if _publisher is None:
        _publisher = Publisher()
    return _publisher


def sync_data(instance_or_instances, session_id, include_related=False, depth=1):
    """
    Synchronize data for model instances.

    Args:
        instance_or_instances: Model instance(s) to synchronize.
        session_id (str): Session ID to associate with the data.
        include_related (bool, optional): Whether to include related models.
        depth (int, optional): Depth of related models to include.
            Only used if include_related is True.

    Returns:
        int: Number of subscribers that received the message.
    """
    mode = getattr(settings, "PII_SHIELD", {}).get("MODE", "backend")
    if mode != "backend":
        logger.warning("sync_data should only be called in backend mode!")
        return False
    publisher = get_publisher()

    # Convert single instance to list
    if not isinstance(instance_or_instances, (list, tuple)):
        instances = [instance_or_instances]
    else:
        instances = instance_or_instances

    # Get expiration time
    from pii_shield.models import PIIModel

    expiration_time = PIIModel.get_expiration_time()

    # Process instances
    with transaction.atomic():
        for instance in instances:
            # Set session_id and data_expires_at
            if hasattr(instance, "session_id"):
                instance.session_id = session_id
            if hasattr(instance, "data_expires_at"):
                instance.data_expires_at = expiration_time

            # Save instance
            instance.save()

            # Publish instance
            publisher.publish_model(instance)

            # Process related models if requested
            if include_related and depth > 0:
                # Get related objects
                for field in instance._meta.get_fields():
                    if field.is_relation and field.concrete:
                        # Get related manager
                        if field.one_to_many or field.many_to_many:
                            manager = getattr(instance, field.name + "_set")
                            related_instances = manager.all()
                            sync_data(
                                related_instances,
                                session_id,
                                include_related,
                                depth - 1,
                            )
                        elif field.many_to_one or field.one_to_one:
                            related_instance = getattr(instance, field.name)
                            if related_instance:
                                sync_data(
                                    related_instance,
                                    session_id,
                                    include_related,
                                    depth - 1,
                                )

    return True
