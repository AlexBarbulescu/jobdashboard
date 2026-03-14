import time
import schedule
import os
from shared.db import init_db
from worker.scraper import run_all_scrapers

def job():
    print("Running scheduled job scraper...")
    run_all_scrapers()

if __name__ == "__main__":
    init_db()
    
    print("Worker started. Running initial scrape...")
    job()
    
    interval = int(os.environ.get("SCRAPE_INTERVAL_HOURS", 6))
    print(f"Scheduling periodic checks every {interval} hours...")
    schedule.every(interval).hours.do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(60)
