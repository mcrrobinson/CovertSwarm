import os
import fakeredis
from fastapi.testclient import TestClient
import pytest
from main import app, get_rabbit_connection, get_redis_client
import pika
from env import FILES_FOLDER


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


def get_rabbit_connection_mock():
    return BlockingConnection()


@pytest.fixture(scope="function")
def redis_client():
    with fakeredis.FakeStrictRedis(decode_responses=True) as redis_client:
        redis_client.flushall()
        yield redis_client


@pytest.fixture(scope="function")
def client(redis_client: fakeredis.FakeStrictRedis):
    app.dependency_overrides[get_rabbit_connection] = get_rabbit_connection_mock
    app.dependency_overrides[get_redis_client] = lambda: redis_client

    # Startup code doesn't get called so doing it manually.
    if not os.path.exists(FILES_FOLDER):
        os.makedirs(FILES_FOLDER)

    return TestClient(app)


def test_job_list(client: TestClient):
    response = client.get("/api/job/list")
    assert response.status_code == 200
    assert response.json() == []

    # Test invalid methods
    response = client.post("/api/job/list")
    assert response.status_code == 405

    response = client.delete("/api/job/list")
    assert response.status_code == 405

    response = client.patch("/api/job/list")
    assert response.status_code == 405

    response = client.put("/api/job/list")
    assert response.status_code == 405


def test_job_create(client: TestClient):

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

    # Test invalid methods
    response = client.get("/api/job/create")
    assert response.status_code == 405

    response = client.delete("/api/job/create")
    assert response.status_code == 405

    response = client.patch("/api/job/create")
    assert response.status_code == 405

    response = client.put("/api/job/create")
    assert response.status_code == 405


def test_download(client: TestClient):
    response = client.post("/api/job/create", json={"args": "localhost"})
    assert response.status_code == 200

    uuid = response.json()
    assert len(uuid) == 36  # e.g. 417b0f97-882e-4a1b-8408-d90c061c283b

    # File isn't done processing should return 404
    response = client.get(f"/api/job/download?uuid={uuid}")
    assert response.status_code == 404

    # Set the status to done
    response = client.patch(
        "/api/job/update",
        json={
            "uuid": uuid,
            "task": "update",
            "status": "Completed",
        },
    )

    # Simulating a nmap output file
    with open(os.path.join(FILES_FOLDER, f"{uuid}.xml"), "w") as f:
        f.write("")

    response = client.get(f"/api/job/download?uuid={uuid}")
    assert response.status_code == 200

    # Cleanup
    os.remove(os.path.join(FILES_FOLDER, f"{uuid}.xml"))
    # clear


def test_delete_jobs(client: TestClient):
    response = client.post("/api/job/create", json={"args": "localhost"})
    assert response.status_code == 200

    uuid = response.json()

    response = client.get("/api/job/list")
    assert response.json() != []

    # Update status
    response = client.patch(
        "/api/job/update",
        json={
            "uuid": uuid,
            "task": "update",
            "status": "Completed",
        },
    )
    assert response.status_code == 200

    with open(os.path.join(FILES_FOLDER, f"{uuid}.xml"), "w") as f:
        f.write("")

    response = client.delete("/api/jobs")
    assert response.status_code == 200

    response = client.get("/api/job/list")
    print(response.json())
    assert response.json() == []

    assert os.listdir(FILES_FOLDER) == []
