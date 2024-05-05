import typing
import docker.errors
import fastapi
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uuid
import docker
import redis
import multiprocessing
import psycopg2
app = fastapi.FastAPI()

origins = [
    "http://localhost:4200",
]


class HTTPBearerAndKeyAuthentication(HTTPBearer):
    def __init__(self, auto_error: bool = False, **kwargs):
        # Pass the auto_error argument to the parent class constructor
        super().__init__(**kwargs)
        self.auto_error = auto_error

    async def __call__(self, request: fastapi.Request) -> typing.Optional[str]:
        # Get the value of the Authorization header
        authorization: str = request.headers.get("Authorization")
        token: str = request.query_params.get("token")

        # Check if the value is empty
        if not authorization:
            if not token:
                if self.auto_error:
                    raise fastapi.HTTPException(
                        status_code=403, detail="Not authenticated")
                else:
                    return None
            else:
                if token == "someauthbearertoken":
                    return token

        # Check if the value is a bearer token
        scheme, param = authorization.split()
        if not scheme.lower() == "bearer":
            if self.auto_error:
                raise fastapi.HTTPException(
                    status_code=403, detail="Invalid authentication scheme"
                )

            else:
                return None

        if param == "someauthbearertoken":
            return param

        raise fastapi.HTTPException(status_code=403, detail="Invalid token")


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Job(BaseModel):
    args: str


@app.get("/job/status")
def status(
    uuid: str,
    request: fastapi.Request,
    response: fastapi.Response,
    authorization: str = fastapi.Depends(
        HTTPBearerAndKeyAuthentication(auto_error=True)
    ),
):

    client = redis.Redis(host="localhost", port=6379, db=0)
    job_status = client.get(uuid)
    print(job_status)
    return job_status
    # while job_status == "Started":
    #     job_status = client.get(uuid)
    #     yield job_status

    # yield job_status


def worker(uuid: str):
    redis_client = redis.Redis(host="localhost", port=6379, db=0)
    conn_string = "host='localhost' dbname='covertswarm' user='postgres' password='mysecretpassword'"
    postgres_client = psycopg2.connect(conn_string)

    client = docker.from_env()

    print("Docker client started...")
    try:
        container = client.containers.run(
            "instrumentisto/nmap", f"{uuid}", detach=False
        )

    except docker.errors.ContainerError as e:
        print(e)
        redis_client.set(uuid, str(e))
        return
    except Exception as e:
        print(e)
        redis_client.set(uuid, f"Unhandled container exception: {str(e)}")
        return

    # Set in the database.

    try:
        res = container.decode("utf-8")
    except UnicodeDecodeError as e:
        print(e)
        redis_client.set(
            uuid, f"Nmap returned format unknown to UTF-8: {str(e)}")
        return
    except Exception as e:
        print(e)
        redis_client.set(uuid, f"Unhandled decode exception: {str(e)}")

    cursor = postgres_client.cursor()
    cursor.execute(
        "INSERT INTO jobs (uuid, result) VALUES (%s, %s)", (uuid, res)
    )
    postgres_client.commit()
    postgres_client.close()
    redis_client.set(uuid, "Completed")
    redis_client.close()
    print("DONE!")


@app.post("/job/create")
def read_root(
    request: fastapi.Request,
    response: fastapi.Response,
    job: Job,
    authorization: str = fastapi.Depends(
        HTTPBearerAndKeyAuthentication(auto_error=True)
    ),
):

    worker_id = str(uuid.uuid4())

    redis_client = redis.Redis(host="localhost", port=6379, db=0)
    redis_client.set(worker_id, "Started")
    redis_client.close()
    multiprocessing.Process(target=worker, args=(worker_id,)).start()
    return worker_id


@app.get("/job/download")
def download(
    uuid: str,
    request: fastapi.Request,
    response: fastapi.Response,
    authorization: str = fastapi.Depends(
        HTTPBearerAndKeyAuthentication(auto_error=True)
    ),
):

    conn_string = "host='localhost' dbname='covertswarm' user='postgres' password = 'mysecretpassword'"
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()
    cursor.execute("SELECT result FROM jobs WHERE uuid = %s", (uuid,))
    result = cursor.fetchone()
    conn.close()
    return result[0]


@app.get("/job/list")
def list(
    request: fastapi.Request,
    response: fastapi.Response,
    authorization: str = fastapi.Depends(
        HTTPBearerAndKeyAuthentication(auto_error=True)
    ),
):

    conn_string = "host='localhost' dbname='covertswarm' user='postgres' password = 'mysecretpassword'"
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()
    cursor.execute("SELECT uuid FROM jobs")
    result = cursor.fetchall()
    conn.close()
    return result


class Login(BaseModel):
    username: str
    password: str


@app.post("/login")
def login(
    login: Login,
    request: fastapi.Request,
    response: fastapi.Response
):
    if login.username != "admin" or login.password != "admin":
        raise fastapi.HTTPException(
            status_code=403, detail="Invalid credentials")

    res = fastapi.responses.JSONResponse(
        content={"token": "someauthbearertoken"}, status_code=200)
    res.set_cookie(key="token", value="someauthbearertoken",
                   httponly=True, samesite="none")
    return res


@app.on_event("startup")
async def startup_event():
    # Make sure postgres tasks database exists
    conn_string = "host='localhost' dbname='covertswarm' user='postgres' password='mysecretpassword'"
    conn = psycopg2.connect(conn_string)

    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS jobs (uuid TEXT PRIMARY KEY, result TEXT)")
    conn.commit()
    conn.close()

    # Make sure redis is running
    redis_client = redis.Redis(host="localhost", port=6379, db=0)
    redis_client.set("test", "test")
    assert redis_client.get("test") == b"test"
    redis_client.delete("test")
    redis_client.close()

    print("Startup complete")

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
