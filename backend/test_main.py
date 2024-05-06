import os
import fakeredis
from fastapi.testclient import TestClient
from main import app, get_rabbit_connection, get_redis_client
import pika

from env import FILES_FOLDER

client = TestClient(app)


class BlockingConnection(pika.BlockingConnection):
    def __init__(self, *args, **kwargs):
        pass

    def channel(self):
        return self

    def close(self):
        pass

    def basic_publish(self, *args, **kwargs):
        pass

    def queue_declare(self, *args, **kwargs):
        pass

    def basic_consume(self, *args, **kwargs):
        pass


class RedisClientSingleton:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = fakeredis.FakeStrictRedis()
        return cls._instance


def get_rabbit_connection_mock():
    return BlockingConnection()


def get_redis_client_mock():
    return RedisClientSingleton().get_instance()


app.dependency_overrides[get_rabbit_connection] = get_rabbit_connection_mock
app.dependency_overrides[get_redis_client] = get_redis_client_mock


def test_job_list():
    response = client.get("/api/job/list")
    assert response.status_code == 200
    assert response.json() == []


def test_job_create():

    # You could put this in a loop, but I find it easier to read if it fails you
    # know exactly where it failed.
    response = client.post("/api/job/create", json={"args": "localhost"})
    assert response.status_code == 200

    response = client.post("/api/job/create", json={"args": "127.0.0.1; ls"})
    assert response.status_code == 400

    response = client.post("/api/job/create", json={"args": "127.0.0.1 | ls"})
    assert response.status_code == 400

    response = client.post("/api/job/create", json={"args": "127.0.0.1 && ls"})
    assert response.status_code == 400

    response = client.post("/api/job/create", json={"args": "127.0.0.1 || ls"})
    assert response.status_code == 400

    response = client.post("/api/job/create", json={"args": "`ls`"})
    assert response.status_code == 400

    response = client.post("/api/job/create", json={"args": "$(ls)"})
    assert response.status_code == 400

    response = client.post("/api/job/create", json={"args": "127.0.0.1`ls`"})
    assert response.status_code == 400

    response = client.post("/api/job/create", json={"args": "127.0.0.1$(ls)"})
    assert response.status_code == 400

    response = client.post("/api/job/create", json={"args": "file:///etc/passwd"})
    assert response.status_code == 400

    # Large buffer test
    large_input = "A" * 10000
    response = client.post("/api/job/create", json={"args": large_input})
    assert response.status_code == 400


def test_job_status():
    # Create the job
    response = client.post("/api/job/create", json={"args": "localhost"})
    assert response.status_code == 200

    uuid = response.json()
    assert len(uuid) == 36  # e.g. 417b0f97-882e-4a1b-8408-d90c061c283b

    response = client.get(f"/api/job/status?uuid={uuid}")
    assert response.json() == "Queued"


def test_download():
    response = client.post("/api/job/create", json={"args": "localhost"})
    assert response.status_code == 200

    uuid = response.json()
    assert len(uuid) == 36  # e.g. 417b0f97-882e-4a1b-8408-d90c061c283b

    # File isn't done processing should return 404
    response = client.get(f"/api/job/download?uuid={uuid}")
    assert response.status_code == 404

    # Set the status to done
    redis_client = RedisClientSingleton().get_instance()
    redis_client.set(uuid, "Done")

    # Simulating a nmap output file
    with open(os.path.join(FILES_FOLDER, f"{uuid}.xml"), "w") as f:
        f.write("")

    response = client.get(f"/api/job/download?uuid={uuid}")
    assert response.status_code == 200


def test_delete_jobs():
    response = client.post("/api/job/create", json={"args": "localhost"})
    assert response.status_code == 200

    response = client.get("/api/job/list")
    assert response.json() != []

    response = client.delete("/api/jobs")
    assert response.status_code == 200

    response = client.get("/api/job/list")
    assert response.json() == []

    assert os.listdir(FILES_FOLDER) == []
