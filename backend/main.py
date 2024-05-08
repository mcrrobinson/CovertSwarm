import asyncio
import json
import os
from time import sleep
from typing import AsyncGenerator, Generator
import fastapi
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uuid
import logging
from defs import Job, UpdateJob
from env import FILES_FOLDER, RABBITMQ_HOST, REDIS_HOST, MAX_ARG_LENGTH
import pika
from redis import ConnectionPool, Redis
from redis.client import PubSub
from redis.exceptions import ConnectionError

app = fastapi.FastAPI()
api = fastapi.APIRouter()

active_sse_connections: set = set()

origins = ["*"]
logger = logging.getLogger("uvicorn")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_redis_client():
    """Creates a connection to Redis and returns it as a generator.

    Yields:
        Generator[Redis, None, None]: Generator connection to Redis
    """
    pool = ConnectionPool.from_url(f"redis://{REDIS_HOST}", decode_responses=True)
    meanings = Redis(connection_pool=pool)
    try:
        yield meanings
    finally:
        meanings.close()


def get_rabbit_connection() -> Generator[pika.BlockingConnection, None, None]:
    """Creates a connection to RabbitMQ and returns it as a generator.

    Yields:
        Generator[pika.BlockingConnection, None, None]: Generator connection to RabbitMQ
    """
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    try:
        yield connection
    finally:
        connection.close()


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


async def event_stream(request: fastapi.Request, pubsub_channel: PubSub):
    """Server side event stream generator for real-time updates on jobs

    Args:
        request (fastapi.Request): Request object
        pubsub_channel (PubSub): _description_

    Yields:
        AsyncGenerator[str, None, None]: Generator of messages
    """
    active_sse_connections.add(request)
    try:
        while True:
            if await request.is_disconnected():
                break

            try:
                message = pubsub_channel.get_message(
                    ignore_subscribe_messages=True, timeout=0
                )
                if message and message["type"] == "message":
                    data = message["data"]
                    yield f"data: {data}\n\n"
            except Exception as e:
                logger.critical(f"Error: {str(e)}")
            await asyncio.sleep(0.1)
    finally:
        active_sse_connections.remove(request)
        pubsub_channel.unsubscribe("events")


@api.post("/job/create")
async def read_root(
    argsModel: Job,
    rabbit_connection: pika.BlockingConnection = fastapi.Depends(get_rabbit_connection),
    redis: Redis = fastapi.Depends(get_redis_client),
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
    validation_checks(argsModel.args)

    worker_id = str(uuid.uuid4())
    job = {
        "uuid": worker_id,
        "status": "Queued",
        "task": "create",
    }

    # Add the queued job to redis
    redis.hset(f"job:{worker_id}", mapping=job)

    # Publish the job to Redis Pub/Sub so subscribers are updated.
    redis.publish("events", json.dumps(job))

    # Send the job to the queue and then close the connection for cleanup.
    channel = rabbit_connection.channel()
    channel.queue_declare(queue="job_queue")
    message = json.dumps({"uuid": worker_id, "args": argsModel.args})
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


@api.get("/subscribe")
async def sse(
    request: fastapi.Request, redis: Redis = fastapi.Depends(get_redis_client)
):
    """Server side event stream for real-time updates on jobs

    Args:
        request (fastapi.Request): Request object
        redis (Redis, optional): Connection to redis. Defaults to fastapi.Depends(get_redis_client).

    Returns:
        StreamingResponse: Stream response object
    """
    pubsub = redis.pubsub()
    pubsub.subscribe("events")

    active_sse_connections.add(id(request))
    return StreamingResponse(
        event_stream(request, pubsub), media_type="text/event-stream"
    )


@api.patch("/job/update")
async def update_job(job: UpdateJob, redis: Redis = fastapi.Depends(get_redis_client)):
    """Updates the job in Redis and publishes the update to Redis Pub/Sub

    Args:
        job (UpdateJob): Job object containing the UUID, status and task
        redis (Redis, optional): Connection to redis. Defaults to fastapi.Depends(get_redis_client).
    """
    redis.hset(f"job:{job.uuid}", mapping=job.model_dump())

    # Also publish job to Redis Pub/Sub so subscribers are updated.
    redis.publish("events", json.dumps(job.model_dump()))


@api.delete("/jobs")
async def delete_all_completed_jobs(redis: Redis = fastapi.Depends(get_redis_client)):
    """Delete all completed jobs from Redis and the associated files from the filesystem.

    Args:
        redis (Redis, optional): Connection to redis. Defaults to fastapi.Depends(get_redis_client).
    """
    job_keys = redis.keys("job:*")
    deleted_jobs = []

    for job_key in job_keys:
        job: dict = redis.hgetall(job_key)
        if job is not None:
            # Check if the job status is 'Completed'
            if job.get("status") == "Completed":
                redis.delete(job_key)

                # Extract job_id from job_key
                job_id = job.get("uuid")

                # Delete the associated file
                file_path = os.path.join(FILES_FOLDER, f"{job_id}.xml")
                if os.path.exists(file_path):
                    os.remove(file_path)
                else:
                    logger.error(
                        f"File {file_path} not found but corresponding job entry set to be deleted in Redis"
                    )

                # Notify via Redis publish that the job has been deleted
                job["task"] = "delete"
                redis.publish("events", json.dumps(job))
                deleted_jobs.append(job_id)
            else:
                uuid = job.get("uuid")
                if not uuid:
                    logger.debug(
                        f"Job {job_key} status is not 'Completed'; it will not be deleted."
                    )
                else:
                    logger.debug(
                        f"Job {uuid} status is not 'Completed'; it will not be deleted."
                    )
        else:
            logger.error(f"Job {job_key} not found.")

    if deleted_jobs:
        logger.debug(f"Deleted jobs: {', '.join(deleted_jobs)}")
    else:
        logger.debug("No completed jobs found to delete.")


@api.get("/job/list")
async def list_jobs(redis: Redis = fastapi.Depends(get_redis_client)):
    keys = redis.keys("job:*")
    jobs = []
    for key in keys:
        job = redis.hgetall(key)
        jobs.append(job)

    return jobs


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
            # redis_client = await get_redis_client()
            break

        except ConnectionError as e:
            logger.error("Cannot connect to redis, {}".format(str(e)))
            sleep(1)
        except Exception as e:
            logger.error("Unhandled redis exception {}".format(str(e)))
            sleep(1)

    logger.debug("Startup complete")


@api.on_event("shutdown")
async def shutdown_event():
    # Attempt to close each SSE connection
    for request in list(active_sse_connections):
        active_sse_connections.remove(request)
        await request._send({"type": "http.disconnect"})


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
