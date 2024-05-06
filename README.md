# CovertSwarm

## Docker installation (Windows & Mac)

[Read more](https://docs.docker.com/desktop/networking/#use-cases-and-workarounds)

1. Install docker
2. Run the following command to build the docker image
```bash
docker compose up --build
```

## Running the backend
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Using the app
1. Open your browser and go to `http://localhost
2. There will be a option to enter arguments for the nmap commands. Enter the 
arguments and click on the submit button.
3. The status of the scan will be displayed on the screen. Once the scan is
completed, a download link will be displayed to download the scan results.
