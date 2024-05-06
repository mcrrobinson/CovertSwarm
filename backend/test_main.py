from fastapi.testclient import TestClient

from .main import app

client = TestClient(app)

# /job/status
# /jobs
# /job/create
# /job/download
# /job/list


def test_job_list():
    response = client.get("/job/list")
    assert response.status_code == 200
    assert response.json() == {"jobs": []}


def test_job_create():
    response = client.post("/job/create")
    assert response.status_code == 200
    assert response.json() == {"job_id": 1}
