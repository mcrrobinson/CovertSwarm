# CovertSwarm

## Docker installation
1. Install docker & docker compose
2. Run the following command to build the docker image
```bash
docker compose up --build
```

## Running a worker
```bash
cd worker
pip install -r requirements.txt
python worker.py
```

## Using the app
1. Open your browser and go to `http://localhost`
2. There will be a option to enter arguments for the nmap commands. Enter the 
arguments and click on the submit button.
3. The status of the scan will be displayed on the screen. Once the scan is
completed, a download link will be displayed to download the scan results.

## Sequence Diagrams

### Event Source
```mermaid
sequenceDiagram
    Web app ->> API: Connect to event source
    API ->> Web app: Acknowledge connection
    API ->> Redis: Wait for update
    Redis ->> API: Send update
    alt add
        API->>Web app: Draw new job card
    else update
         API->>Web app: Update existing job card
    end
    opt delete
         API->>Web app: Delete job card
    end
```

### Request all jobs
```mermaid
sequenceDiagram
    Web app ->> API: Request all jobs
    API ->> Redis: Get all jobs
    Redis ->> API: Send all jobs
    loop each job
        API ->> Web app: Draw new job card
    end
    
```

### Create job
```mermaid
sequenceDiagram
    Web app ->> API: Create job
    API ->> Web app: Acknowledge job creation
    par
        API ->> Redis: Update job status to queued
    and 
        API ->> RabbitMQ: Add job to queue
    end
    API -->> Web app: Send job update
    RabbitMQ ->> Worker: Send job to worker
    Worker ->> API: Request update job status
    API ->> Redis: Update redis job status to started
    API ->> Worker: Acknowledge job update
    API -->> Web app: Send job update
    Worker ->> OS: Run nmap and save output
    OS ->> Worker: Acknowledge nmap completed
    Worker ->> API: Request update job status
    API ->> Redis: Update redis job status to completed
    API ->> Worker: Acknowledge job update
    API -->> Web app: Send job update
```

### Delete all jobs
```mermaid
sequenceDiagram
    Web app ->> API: Delete all jobs
    API ->> Redis: Get all jobs
    Redis ->> API: Send all jobs
    
    loop delete
        alt status == completed
            API ->> Redis: Delete job
            API ->> OS: Delete job files
            API ->> Web app: Send delete update
        end
    end
```

### Download job
```mermaid
sequenceDiagram
    Web app ->> API: Download job
    API ->> OS: Get job file
    OS ->> API: Send job file
    API ->> Web app: Send job file
```

## Future considerations
I would abstract the security checks into it's own lib that can be called from the worker and backend to avoid the duplication of the command line injection checks.

Additionally, saving files to the OS could be easily replaced by an object storage like S3 bucket. This would allow for easier scaling and better performance.

Robust queue connections. Upon the rabbit queue going down the clients will automatically reconnect.