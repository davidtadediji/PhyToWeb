import redis
import os
from dotenv import load_dotenv

load_dotenv()


class RedisFacade:
    def __init__(self):
        # Load environment variables
        self.redis_host = os.getenv('REDIS_HOST', 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))

        # Initialize Redis client
        self.client = redis.StrictRedis(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db,
            decode_responses=True  # Ensure responses are in string format
        )

    def set_cache(self, key: str, value: str, ttl: int = 3600) -> bool:
        """
        Set a value in the Redis cache with an optional TTL.

        Args:
            key (str): The key to store in the cache.
            value (str): The value associated with the key.
            ttl (int): Time-to-live for the cache in seconds (default: 1 hour).

        Returns:
            bool: True if the cache was set successfully, False otherwise.
        """
        try:
            self.client.setex(key, ttl, value)
            return True
        except Exception as e:
            raise Exception(f"Error setting cache -> {e}") from e

    def get_cache(self, key: str) -> str:
        """
        Get a value from the Redis cache by key.

        Args:
            key (str): The key to look up in the cache.

        Returns:
            str: The value associated with the key, or None if not found.
        """
        try:
            value = self.client.get(key)
            return value
        except Exception as e:
            raise Exception(f"Error getting cache -> {e}") from e

    def delete_cache(self, key: str) -> bool:
        """
        Delete a key from the Redis cache.

        Args:
            key (str): The key to remove from the cache.

        Returns:
            bool: True if the key was removed successfully, False otherwise.
        """
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            raise Exception(f"Error deleting cache -> {e}") from e

    def exists_cache(self, key: str) -> bool:
        """
        Check if a key exists in the Redis cache.

        Args:
            key (str): The key to check in the cache.

        Returns:
            bool: True if the key exists, False otherwise.
        """
        try:
            return self.client.exists(key)
        except Exception as e:
            raise Exception(f"Error checking cache existence -> {e}")


redis_client = RedisFacade()