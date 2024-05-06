import json
import os
from time import sleep
import docker.errors
import fastapi
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uuid
import docker
import redis
import multiprocessing
import logging
from env import FILES_FOLDER, RABBITMQ_HOST, REDIS_HOST, REDIS_PORT
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


@api.get("/job/status")
def status(uuid: str, request: fastapi.Request, response: fastapi.Response) -> str:
    """Gets the status of the job with the given UUID

    Args:
        uuid (str): UUID of the job
        request (fastapi.Request): Request object
        response (fastapi.Response): Response object

    Returns:
        str: Status of the job
    """

    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    job_status = client.get(uuid)
    return job_status


@api.delete("/jobs")
def delete_jobs(request: fastapi.Request, response: fastapi.Response) -> list[str]:
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

    # Delete all keys in redis
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    redis_client.flushdb()
    redis_client.close()

    return []


@api.post("/job/create")
def read_root(request: fastapi.Request, response: fastapi.Response, job: Job):
    """Creates a new job and returns the UUID of the job

    Args:
        request (fastapi.Request): Request object
        response (fastapi.Response): Response object
        job (Job): Job object, contains the arguments.

    Returns:
        str: UUID of the job
    """

    worker_id = str(uuid.uuid4())

    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    redis_client.set(worker_id, "Queued")
    redis_client.close()

    # Send over rabbitmq
    # Connect to RabbitMQ
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    channel = connection.channel()

    # Declare the queue
    channel.queue_declare(queue="job_queue")

    # Send the UUID and job arguments

    message = json.dumps({"uuid": worker_id, "args": job.args})
    channel.basic_publish(exchange="", routing_key="job_queue", body=message)

    # Close the connection
    connection.close()
    # multiprocessing.Process(target=worker, args=(worker_id, job.args)).start()
    return worker_id


@api.get("/job/download")
def download(
    uuid: str, request: fastapi.Request, response: fastapi.Response
) -> fastapi.responses.FileResponse:
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


def get_keys_and_values():
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    keys = redis_client.keys()
    values = [
        {"uuid": key.decode(), "value": redis_client.get(key).decode()} for key in keys
    ]
    redis_client.close()
    return values


@api.get("/job/list")
def list(request: fastapi.Request, response: fastapi.Response):
    """Gets the list of files in the files folder

    Args:
        request (fastapi.Request): Request object
        response (fastapi.Response): Response object

    Returns:
        list[str]: List of files in the files folder without the .xml extension
    """

    files = [
        file.rstrip(".xml")
        for file in os.listdir(FILES_FOLDER)
        if file.endswith(".xml")
    ]

    # Get entire redis list
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    keys = redis_client.keys()

    redis_client.close()

    return get_keys_and_values()
    return files


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
            redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
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
