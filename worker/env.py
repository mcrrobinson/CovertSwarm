import os


FILES_FOLDER = "files"
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")

try:
    REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
except ValueError as e:
    print("REDIS_PORT must be an integer, {}".format(e))
    exit(1)

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = os.environ.get("RABBITMQ_PORT", "5672")
