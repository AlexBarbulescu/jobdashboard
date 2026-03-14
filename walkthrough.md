# Crypto Design Job Sentinel

🚀 **Project Setup Complete**

The complete scaffolding, logic, and infrastructure for the Crypto Design Job Sentinel have been implemented exactly according to your requirements.

## Changes Made
- **Scraping Worker ([worker/](file:///d:/jobdashboard/Dockerfile.worker))**: Implemented Python scraper for parsing CryptocurrencyJobs.co and Web3.career to filter specifically for "Design" and "Remote" roles matching the target keywords.
- **Streamlit Dashboard ([web/](file:///d:/jobdashboard/Dockerfile.web))**: Created [app.py](file:///d:/jobdashboard/web/app.py) for displaying listings. It includes a "New (24h) 🟢" indicator and an editable status tracker (Applied, Saved, Ignored).
- **Database Layer (`shared/`)**: Added SQLite database handler for data persistence via Docker volumes.
- **Docker Infrastructure**: Added [Dockerfile.web](file:///d:/jobdashboard/Dockerfile.web), [Dockerfile.worker](file:///d:/jobdashboard/Dockerfile.worker), and [docker-compose.yml](file:///d:/jobdashboard/docker-compose.yml).
- **Environment & Config**: Set up [requirements.txt](file:///d:/jobdashboard/requirements.txt) and [.env.example](file:///d:/jobdashboard/.env.example).

## Status

Since Docker is not available on this machine, I am running it using Python natively (`venv`). The Streamlit dashboard and the scraping worker will run as background processes and you will be able to access the dashboard on `http://localhost:8501`.
