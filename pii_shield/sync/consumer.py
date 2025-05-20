"""
Consumer module for PII Shield.
Provides components for consuming model data from Redis.
"""

import logging
import threading
import time

import redis
from django.conf import settings
from django.core import serializers
from django.db import transaction

logger = logging.getLogger(__name__)


class Consumer:
    """
    Consumer for processing data from Redis.
    Subscribes to configured Redis channels and processes incoming messages.
    """

    def __init__(self):
        """Initialize the consumer with Redis connection from settings."""
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

        # Initialize subscriber
        self.pubsub = self.redis.pubsub()

        # Initialize thread
        self.thread = None
        self.running = False
        self.lock = threading.Lock()

    def subscribe(self, channels=None):
        """
        Subscribe to Redis channels.

        Args:
            channels (list, optional): List of channels to subscribe to.
                If not provided, subscribes to the default channel.

        Returns:
            bool: True if subscription was successful, False otherwise.
        """
        try:
            # Get channel names with prefix
            prefix = self.channel_settings.get("prefix", "pii_shield")

            if channels is None:
                # Subscribe to default channel
                default_channel = self.channel_settings.get("default", "default")
                channels = [f"{prefix}:{default_channel}"]
            else:
                # Add prefix to channel names
                channels = [f"{prefix}:{channel}" for channel in channels]

            # Subscribe to channels
            self.pubsub.subscribe(*channels)

            # Log debug info
            logger.debug(f"Subscribed to channels: {channels}")

            return True
        except Exception as e:
            logger.exception(f"Error subscribing to channels: {e}")
            return False

    def _process_message(self, message):
        """
        Process a message from Redis.

        Args:
            message (dict): Message from Redis pubsub.

        Returns:
            bool: True if processing was successful, False otherwise.
        """
        try:
            # Check if message is valid
            if message is None or not isinstance(message, dict):
                return False

            # Skip non-message types
            if message.get("type") != "message":
                return False

            # Get message data
            data = message.get("data")
            if data is None:
                return False

            # Convert bytes to string
            if isinstance(data, bytes):
                data = data.decode("utf-8")

            # Deserialize objects
            objects = list(serializers.deserialize("json", data))

            # Process objects
            with transaction.atomic():
                for obj in objects:
                    # Save object to database
                    obj.save()

            # Log debug info
            logger.debug(f"Processed {len(objects)} objects from message")

            return True
        except Exception as e:
            logger.exception(f"Error processing message: {e}")
            return False

    def _listen(self):
        """
        Listen for messages from Redis and process them.
        This method is run in a separate thread.
        """
        try:
            # Get max retries and retry delay from settings
            max_retries = self.sync_settings.get("max_retries", 3)
            retry_delay = self.sync_settings.get("retry_delay", 1)
            backoff_factor = self.sync_settings.get("backoff_factor", 2)

            # Process messages
            for message in self.pubsub.listen():
                # Check if thread should stop
                if not self.running:
                    break

                # Process message with retries
                success = False
                retry_count = 0
                current_delay = retry_delay

                while not success and retry_count < max_retries:
                    try:
                        success = self._process_message(message)
                    except Exception as e:
                        logger.exception(
                            f"Error processing message (retry {retry_count + 1}/{max_retries}): {e}"
                        )

                        # Increment retry count
                        retry_count += 1

                        # Sleep before retry
                        if retry_count < max_retries:
                            time.sleep(current_delay)
                            current_delay *= backoff_factor

                # Log error if processing failed after all retries
                if not success and retry_count >= max_retries:
                    logger.error(
                        f"Failed to process message after {max_retries} retries"
                    )
        except Exception as e:
            logger.exception(f"Error in listener thread: {e}")
        finally:
            # Close connection
            self.pubsub.close()

    def start(self):
        """
        Start the consumer.

        Returns:
            bool: True if consumer was started successfully, False otherwise.
        """
        mode = getattr(settings, "PII_SHIELD", {}).get("MODE", "frontend")
        if mode != "frontend":
            logger.warning(
                "PII Shield Consumer should only be started in frontend mode!"
            )
            return False
        with self.lock:
            if self.running:
                logger.warning("Consumer already running")
                return False
            self.running = True
            self.thread = threading.Thread(target=self._listen)
            self.thread.daemon = True
            self.thread.start()
            logger.debug("Consumer started")
            return True

    def stop(self):
        """
        Stop the consumer.

        Returns:
            bool: True if consumer was stopped successfully, False otherwise.
        """
        with self.lock:
            # Check if running
            if not self.running:
                logger.warning("Consumer not running")
                return False

            # Clear running flag
            self.running = False

            # Unsubscribe from all channels
            self.pubsub.unsubscribe()

            # Wait for thread to stop
            if self.thread:
                self.thread.join(timeout=5.0)

            # Log debug info
            logger.debug("Consumer stopped")

            return True

    def restart(self):
        """
        Restart the consumer.

        Returns:
            bool: True if consumer was restarted successfully, False otherwise.
        """
        # Stop consumer
        self.stop()

        # Start consumer
        return self.start()

    def status(self):
        """
        Get the status of the consumer.

        Returns:
            dict: Status information.
        """
        with self.lock:
            return {
                "running": self.running,
                "subscribed_channels": list(self.pubsub.channels.keys()),
            }


# Singleton instance of Consumer
_consumer = None


def get_consumer():
    """Get singleton instance of Consumer."""
    global _consumer
    if _consumer is None:
        _consumer = Consumer()
    return _consumer


def initialize():
    """Initialize the consumer based on settings."""
    try:
        mode = getattr(settings, "PII_SHIELD", {}).get("MODE", "frontend")
        if mode != "frontend":
            logger.info(
                "PII Shield Consumer initialization skipped (not in frontend mode)"
            )
            return
        pii_settings = getattr(settings, "PII_SHIELD", {})
        auto_reconnect = pii_settings.get("ADVANCED", {}).get("auto_reconnect", True)
        if auto_reconnect:
            consumer = get_consumer()
            consumer.subscribe()
            consumer.start()
    except Exception as e:
        logger.exception(f"Error initializing consumer: {e}")
