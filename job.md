Project: Crypto Design Job Sentinel

1. Objective

Create a Smart Job Dashboard that automatically aggregates and updates job listings from decentralized finance (DeFi), Web3, and Crypto companies. The tool must filter specifically for Design roles and Remote-only positions without using restricted social media APIs (Twitter/X, LinkedIn).

1.1 Local Deployment Baseline

This project should target a local-first deployment model so it can run on a developer machine with Docker before any cloud deployment is considered.

    Recommended Stack: Streamlit dashboard + Python scraping workers.

    Local Runtime: Docker Compose with one web service and one scheduled refresh worker.

    Storage: Persist job data and status labels in a mounted local volume using SQLite or JSON files.

    Access: The dashboard must be reachable in a browser 

    Configuration: All runtime settings must be controlled with environment variables in a local .env file.

    Startup Requirement: A new developer must be able to start the full project locally with a single docker compose up --build command.

2. Core Technical Requirements

    Architecture: A lightweight Streamlit web dashboard backed by Python scraping services. Avoid no-code platforms for the primary implementation so the app remains portable and locally deployable.

    Data Sourcing (Non-API):

        RSS/XML Feeds: Utilize public RSS feeds from boards like CryptocurrencyJobs.co or Web3.career.

        Headless Scraping: Use Playwright, Selenium, or BeautifulSoup to scrape public listings from Crypto.jobs and CryptoJobsList.

        Structured Data Extraction: Target sites using JobPosting schema (JSON-LD) to ensure high data accuracy without needing an API key.

    Update Frequency: Auto-refresh every 6 hours using a scheduler that works locally in Docker. GitHub Actions can be an optional cloud fallback, not the primary refresh mechanism.

3. Targeted Filtering Logic

The dashboard must only display listings that match ALL these criteria:

    Keywords: "UI/UX", "Product Design", "Advertising Designer", "Graphic Designer", "Visual Designer".

    Location: Must contain "Remote", "Anywhere", or "Distributed".

    Industry: Must be tagged or categorized under "Crypto", "Web3", "Blockchain", or "DeFi".

4. Dashboard Features

    Centralized List: A table or card view showing: [Job Title], [Company], [Source Site], [Date Posted], and a direct [Apply Link].

    "New" Indicator: Highlight jobs posted within the last 24 hours.

    Status Tracker: Ability to mark jobs as "Applied", "Saved", or "Ignored" (storing data in a local SQLite database or JSON file).

    Direct Link Generation: Ensure the "Apply" link leads directly to the original job post, bypassing intermediate trackers where possible.

5. Deployment Constraints

    No Big Tech APIs: Do not include integrations for Twitter, LinkedIn, or Indeed official APIs.

    Local or Cloud-Based: Must run on a local machine with Docker Compose and may optionally be deployed later to a free-tier hosting service.

    Containerization: Include a Dockerfile, docker-compose.yml, and .env.example in the implementation.

    Persistence: Local deployment must preserve saved job states across container restarts.

    Health Check: The web container should expose a simple health endpoint or startup check so local deployment issues are easy to diagnose.
