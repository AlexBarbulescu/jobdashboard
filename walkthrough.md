# Deploy Walkthrough

This project can be run in two ways:

1. Docker Compose
2. Native Windows Python using the included `venv`

The error you hit:

```powershell
docker : The term 'docker' is not recognized
```

means Docker Desktop is not installed or not available on `PATH` yet. The application code is not the cause of that error.

## Option A: Docker Compose on Windows

### 1. Install Docker Desktop

You can install it from the Docker website or with `winget`:

```powershell
winget install -e --id Docker.DockerDesktop
```

After installation:

1. Start Docker Desktop.
2. Let it finish initial setup.
3. Restart PowerShell.
4. Verify Docker is available:

```powershell
docker version
docker compose version
```

### 2. Configure environment

Copy `.env.example` to `.env` if you want to tune the scrape interval.

Example `.env`:

```env
SCRAPE_INTERVAL_HOURS=6
```

For Docker, `DB_PATH` is set inside `docker-compose.yml` and does not need to be changed.

### 3. Start the stack

From the repo root:

```powershell
docker compose up --build
```

### 4. Open the dashboard

Open:

```text
http://localhost:8501
```

### 5. Stop the stack

```powershell
docker compose down
```

Data persists in the mounted `data/` folder.

## Option B: Native Windows Deployment

This works on your current machine even without Docker.

### 1. Confirm Python is available

This repo already includes `venv/`, so you can use that directly.

### 2. Configure environment

Copy `.env.example` to `.env`.

Recommended native `.env`:

```env
DB_PATH=data/jobs.db
SCRAPE_INTERVAL_HOURS=6
```

The app now loads `.env` automatically.

### 3. Start the worker and dashboard

From the repo root:

```powershell
.\scripts\start-local.ps1
```

That script:

1. Uses `venv\Scripts\python.exe` when available.
2. Starts the worker in the background.
3. Starts the Streamlit web app in the background.
4. Writes logs to `data/logs/`.
5. Writes PID files to `data/run/`.

### 4. Open the dashboard

Open:

```text
http://localhost:8501
```

### 5. Stop the native services

```powershell
.\scripts\stop-local.ps1
```

## Health Checks

Once the web app is running, verify the health endpoint:

```text
http://localhost:8501/_stcore/health
```

## Logs

Native run logs are written to:

1. `data/logs/web.out.log`
2. `data/logs/web.err.log`
3. `data/logs/worker.out.log`
4. `data/logs/worker.err.log`

## Troubleshooting

### Docker still not found after install

1. Restart PowerShell.
2. Start Docker Desktop manually once.
3. Run `docker version` again.

### Port 8501 already in use

Stop the existing process using port 8501 or update the Streamlit port in the startup command.

### Worker runs but no jobs appear

1. Check `data/logs/worker.err.log`.
2. Confirm the source sites are reachable.
3. Confirm the scraper still matches the current HTML structure.

### Dashboard opens but shows no data

1. Wait for the first scrape to complete.
2. Check that `data/jobs.db` exists.
3. Review worker logs for scraping errors.
