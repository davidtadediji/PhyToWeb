import redis
import boto3

# Create a Redis connection pool
pool = redis.ConnectionPool(host="localhost", port=6379, db=0)

# Create a Redis client using the connection pool
r = redis.Redis(connection_pool=pool)

# Use Redis normally
r.set("foo", "bar")
print(r.get("foo"))  # Output: b'bar'
