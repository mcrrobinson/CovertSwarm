import asyncio
import os
from typing import AsyncIterator
from unittest import mock
from aioredis import Redis
import fakeredis
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import pytest_asyncio
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


@pytest_asyncio.fixture(scope="function")
async def redis_conn() -> AsyncIterator[Redis]:
    async with fakeredis.aioredis.FakeRedis(
        decode_responses=True, version=(6,)
    ) as redis_conn:
        await redis_conn.flushdb()
        yield redis_conn


@pytest_asyncio.fixture(scope="function")
async def client(redis_conn: Redis) -> AsyncIterator[TestClient]:
    get_redis_client_mock = mock.patch(
        "main.get_redis_client", return_value=redis_conn
    ).start()
    app.dependency_overrides[get_redis_client] = get_redis_client_mock
    app.dependency_overrides[get_rabbit_connection] = get_rabbit_connection_mock

    with TestClient(app) as client:
        # Startup code doesn't get called so doing it manually.
        if not os.path.exists(FILES_FOLDER):
            os.makedirs(FILES_FOLDER)
        yield client

    get_redis_client_mock.stop()
    app.dependency_overrides.pop(get_redis_client)


@pytest.mark.asyncio
async def test_job_list(client: TestClient):
    response = client.get("/api/job/list")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_job_create(client: TestClient):

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


@pytest.mark.asyncio
async def test_download(client: TestClient):
    response = client.post("/api/job/create", json={"args": "localhost"})
    assert response.status_code == 200

    uuid = response.json()
    assert len(uuid) == 36  # e.g. 417b0f97-882e-4a1b-8408-d90c061c283b

    # File isn't done processing should return 404
    response = client.get(f"/api/job/download?uuid={uuid}")
    assert response.status_code == 404

    response = client.patch(
        "/api/job/update", json={"uuid": uuid, "task": "update", "status": "Completed"}
    )
    assert response.status_code == 200

    # Simulating a nmap output file
    with open(os.path.join(FILES_FOLDER, f"{uuid}.xml"), "w") as f:
        f.write("")

    response = client.get(f"/api/job/download?uuid={uuid}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_jobs(client: TestClient):
    # Create a job
    response = client.post("/api/job/create", json={"args": "localhost"})
    assert response.status_code == 200

    response = client.get("/api/job/list")
    assert response.json() != []

    response = client.delete("/api/jobs")
    assert response.status_code == 200

    response = client.get("/api/job/list")
    assert response.json() == []

    assert os.listdir(FILES_FOLDER) == []
