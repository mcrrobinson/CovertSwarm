

def worker(uuid: str):
    client = redis.Redis(host="localhost", port=6379, db=0)
    client.set(uuid, "Started")

    client = docker.from_env()
    container = client.containers.run(
        "instrumentisto/nmap", f"{job.args}", detach=False
    )
    res = container.decode("utf-8")
    client.set(uuid, res)

    return res
