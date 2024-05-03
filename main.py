import typing
import docker.errors
import fastapi
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import uuid
import docker
import redis

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

        # Check if the value is empty
        if not authorization:
            if self.auto_error:
                raise fastapi.HTTPException(status_code=403, detail="Not authenticated")
            else:
                return None

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


# @app.get("/job/status")
# def status(
#     uuid: str,
#     request: fastapi.Request,
#     response: fastapi.Response,
#     authorization: str = fastapi.Depends(
#         HTTPBearerAndKeyAuthentication(auto_error=True)
#     ),
# ):

#     client = redis.Redis(host="localhost", port=6379, db=0)
#     job_status = client.get(uuid)
#     if job_status:
#         return job_status
#     else:
#         return "Job not found"


@app.post("/job/create")
def read_root(
    request: fastapi.Request,
    response: fastapi.Response,
    job: Job,
    authorization: str = fastapi.Depends(
        HTTPBearerAndKeyAuthentication(auto_error=True)
    ),
):

    id = str(uuid.uuid4())

    client = docker.from_env()

    try:
        container = client.containers.run(
            "instrumentisto/nmap", f"{job.args}", detach=False
        )

    except docker.errors.ContainerError as e:
        return str(e)
    except Exception as e:
        return f"Unhandled container exception: {str(e)}"

    try:
        res = container.decode("utf-8")
    except UnicodeDecodeError as e:
        return f"Nmap returned format unknown to UTF-8: {str(e)}"
    except Exception as e:
        return f"Unhandled decode exception: {str(e)}"

    return res
