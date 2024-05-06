import json
import os
import socket
from time import sleep
from pika.spec import Basic, BasicProperties
from pika.adapters.blocking_connection import BlockingChannel
import pika
from env import FILES_FOLDER, REDIS_HOST, REDIS_PORT
import redis
import docker
from pika.exceptions import (
    ChannelClosedByBroker,
    ChannelWrongStateError,
)


class Job:
    def __init__(self, args: str, uuid: str):
        self.args = args
        self.uuid = uuid

    def __str__(self):
        return f"Job ({self.uuid}): {self.args}"


def worker(
    ch: BlockingChannel, method: Basic.Deliver, prop: BasicProperties, body: bytes
):
    """Worker function that runs the nmap container and writes the stdout to
    a file

    Args:
        uuid (str): UUID of the job
        args (str): Arguments to pass to nmap
    """
    res = json.loads(body)
    job = Job(**res)

    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

    client = docker.from_env()
    redis_client.set(job.uuid, "Started")
    try:
        container = client.containers.run(
            "instrumentisto/nmap", f"-oX - {job.args}", detach=False, remove=True
        )

    except docker.errors.ContainerError as e:
        print(e)
        redis_client.set(job.uuid, str(e))
        return
    except Exception as e:
        print(e)
        redis_client.set(job.uuid, f"Unhandled container exception: {str(e)}")
        return

    # Set in the database.
    try:
        res = container.decode("utf-8")
    except UnicodeDecodeError as e:
        print(e)
        redis_client.set(job.uuid, f"Nmap returned format unknown to UTF-8: {str(e)}")
        return
    except Exception as e:
        print(e)
        redis_client.set(job.uuid, f"Unhandled decode exception: {str(e)}")

    # write to S3 bucket/cdn or alternative
    path = os.path.join(FILES_FOLDER, f"{job.uuid}.xml")
    with open(path, "w") as f:
        f.write(res)

    redis_client.set(job.uuid, "Completed")
    redis_client.close()
    print("Job completed")


def main():
    credentials = pika.PlainCredentials("guest", "guest")
    parameters = pika.ConnectionParameters(
        host="localhost",
        port="5672",
        credentials=credentials,
        heartbeat=0,
        socket_timeout=7,
    )
    while True:
        try:
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            channel.queue_declare(queue="job_queue")
            break
        except pika.AMQPConnectionWorkflow as err:
            print("Connection failed, trying again in 5 seconds", err)
            sleep(0.1)
        except socket.gaierror as err:
            print("Connection failed, trying again in 5 seconds", err)
            sleep(0.1)
    while True:
        try:
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue="job_queue",
                on_message_callback=worker,
                auto_ack=True,
            )

            try:
                print("Consuming...")
                channel.start_consuming()
            except KeyboardInterrupt:
                channel.stop_consuming()
            connection.close()
        except (ChannelClosedByBroker, ChannelWrongStateError) as err:
            print(err)
            break

    if connection.is_open:
        connection.close()


if __name__ == "__main__":
    main()
