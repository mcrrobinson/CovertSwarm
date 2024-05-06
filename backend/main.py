import json
import os
from time import sleep
from typing import Generator
import fastapi
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uuid
import redis
import logging
from env import FILES_FOLDER, RABBITMQ_HOST, REDIS_HOST, REDIS_PORT, MAX_ARG_LENGTH
import pika

app = fastapi.FastAPI()
api = fastapi.APIRouter()

origins = ["*"]
logger = logging.getLogger("uvicorn")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Job(BaseModel):
    args: str


def get_redis():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)


# Dependency to get RabbitMQ connection
def get_rabbit_connection() -> Generator[pika.BlockingConnection, None, None]:
    # Connect to the RabbitMQ server
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    try:
        yield connection
    finally:
        connection.close()


def get_redis_client() -> Generator[redis.Redis, None, None]:
    redis_client = get_redis()
    try:
        yield redis_client
    finally:
        redis_client.close()


@api.get("/job/status")
def status(
    uuid: str,
    redis_client: redis.Redis = fastapi.Depends(get_redis_client),
):
    """Gets the status of the job with the given UUID

    Args:
        uuid (str): UUID of the job
        request (fastapi.Request): Request object
        response (fastapi.Response): Response object

    Returns:
        str: Status of the job
    """
    job_status = redis_client.get(uuid)
    return job_status


@api.delete("/jobs")
def delete_jobs(
    redis_client: redis.Redis = fastapi.Depends(get_redis_client),
):
    """Deletes all files in the files folder

    Args:
        request (fastapi.Request): Request object
        response (fastapi.Response): Response object

    Returns:
        list[str]: The empty list of files
    """
    files = [file for file in os.listdir(FILES_FOLDER)]
    for file in files:
        os.remove(os.path.join(FILES_FOLDER, file))

    # Don't delete the tasks that are running to avoid deadlocks
    keys = redis_client.keys()
    processing_keys = []
    for key in keys:
        value = redis_client.get(key).decode()
        if value == "Completed":
            redis_client.delete(key)
        else:
            processing_keys.append({"uuid": key.decode(), "value": value})

    return processing_keys


def validation_checks(arg: str):
    """Validates the argument to make sure it doesn't contain any disallowed
    characters and is not too long.

    Args:
        arg (str): User input argument

    Raises:
        fastapi.HTTPException: Upon disallowed characters or too long argument
    """

    # Iterating by character as opposed to doing a loop of index or replace
    # checks to avoid unnecessary O(n^2) complexity.
    disallowed_chars_used = set()
    for char in arg:
        if char in ["&", "|", ";", "$", ">", "<", "`", "\\", "!"]:
            disallowed_chars_used.add(char)

    if disallowed_chars_used:
        raise fastapi.HTTPException(
            status_code=400,
            detail="Disallowed character '{}' in argument".format(
                ", ".join(disallowed_chars_used)
            ),
        )

    if len(arg) > MAX_ARG_LENGTH:
        raise fastapi.HTTPException(
            status_code=400, detail="Argument too long, max 1000 characters"
        )

    if arg.startswith("file://"):
        raise fastapi.HTTPException(
            status_code=400, detail="Illegal protocol used in argument"
        )


@api.post("/job/create")
def read_root(
    job: Job,
    rabbit_connection: pika.BlockingConnection = fastapi.Depends(get_rabbit_connection),
    redis_client: redis.Redis = fastapi.Depends(get_redis_client),
):
    """Creates a new job and returns the UUID of the job

    Args:
        request (fastapi.Request): Request object
        response (fastapi.Response): Response object
        job (Job): Job object, contains the arguments.

    Returns:
        str: UUID of the job
    """

    # Realistically you don't need these checks as the security is in the hands
    # of the nmap command as this pipes the command directly into the "nmap"
    # command line tool. However, for sanity sake I will disallow certain
    # offenders like bash special characters.
    validation_checks(job.args)

    worker_id = str(uuid.uuid4())
    redis_client.set(worker_id, "Queued")

    # Send the job to the queue and then close the connection for cleanup.
    channel = rabbit_connection.channel()
    channel.queue_declare(queue="job_queue")
    message = json.dumps({"uuid": worker_id, "args": job.args})
    channel.basic_publish(exchange="", routing_key="job_queue", body=message)
    return worker_id


@api.get("/job/download")
def download(uuid: str, response: fastapi.Response) -> fastapi.responses.FileResponse:
    """Downloads the file with the given UUID

    Args:
        uuid (str): UUID of file
        request (fastapi.Request): Request object
        response (fastapi.Response): Response object

    Returns:
        fastapi.responses.FileResponse: File response object
    """

    file = os.path.join(FILES_FOLDER, f"{uuid}.xml")
    if not os.path.exists(file):
        response.status_code = 404
        return {"error": "File not found"}

    return fastapi.responses.FileResponse(
        file, media_type="application/xml", filename=f"{uuid}.xml"
    )


def get_keys_and_values(redis_client: redis.Redis = fastapi.Depends(get_redis_client)):
    keys = redis_client.keys()
    values = [
        {"uuid": key.decode(), "value": redis_client.get(key).decode()} for key in keys
    ]
    return values


@api.get("/job/list")
def list(
    redis_client: redis.Redis = fastapi.Depends(get_redis_client),
):
    """Gets the list of files in the files folder

    Args:
        request (fastapi.Request): Request object
        response (fastapi.Response): Response object

    Returns:
        list[str]: List of files in the files from the redis database
    """
    return get_keys_and_values(redis_client)


@api.on_event("startup")
async def startup_event():
    """Startup event that does preliminary checks including;
    - Making sure the files folder exists
    - Making sure redis is running
    """

    # Make sure folder "files" exists
    if not os.path.exists(FILES_FOLDER):
        os.makedirs(FILES_FOLDER)

    # Make sure redis is running
    while True:
        try:
            redis_client = get_redis()
            redis_client.set("test", "test")
            assert redis_client.get("test") == b"test"
            redis_client.delete("test")
            redis_client.close()
            break

        except redis.exceptions.ConnectionError as e:
            logger.error("Cannot connect to redis, {}".format(str(e)))
            sleep(1)
        except Exception as e:
            logger.error("Unhandled redis exception {}".format(str(e)))
            sleep(1)

    print("Startup complete")


app.include_router(api, prefix="/api", tags=["api"])

# Either host it on the API where you can have a collection of APIs that also do
# the work in something like threads. In this circumstance the API would have
# realtime response.

# Or you could setup a queue with something like RabbitMQ where there would have
# to be some kind of polling.

# If the queues are going to be a long time then you should have a dedicated
# queue based system like Rabbit. Otherwise, if you're expecting quick response
# time then you can use the API method.

# Personally I like the polling solution, it's slightly more expensive because
# it's constantly creating a new connection with the API as opposed to a
# a websocket or SSE but it takes the load off of the API which would need to do
# the work. If it becomes a long task with a big backlog that would be a long
# connection between the client and the server which could become a problem.
