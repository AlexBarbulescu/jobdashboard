import hashlib
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from shared.db import insert_job

KEYWORDS = [
    "UI/UX",
    "Product Design",
    "Advertising Designer",
    "Graphic Designer",
    "Visual Designer",
    "Brand Designer",
    "Content Designer",
    "Motion Designer",
    "Designer",
    "UX",
    "UI",
]
LOCATIONS = ["Remote", "Anywhere", "Distributed"]
INDUSTRIES = ["Crypto", "Web3", "Blockchain", "DeFi", "Bitcoin", "NFT"]
EMPLOYMENT_TYPES = [
    "Full-Time",
    "Part-Time",
    "Contract",
    "Internship",
    "Freelance",
    "Temporary",
]
HEADERS = {"User-Agent": "Mozilla/5.0"}


def normalize_text(value):
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def stable_job_id(prefix, apply_link):
    digest = hashlib.md5(apply_link.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def is_match(text, keywords):
    text_lower = normalize_text(text).lower()
    return any(keyword.lower() in text_lower for keyword in keywords)


def looks_like_compensation(text):
    return "$" in text or "usd" in text.lower() or "usdc" in text.lower()


def looks_like_relative_date(text):
    lowered = text.lower()
    return lowered in {"today", "yesterday", "recent"} or bool(re.fullmatch(r"\d+[hdwmy]", lowered))


def collect_tags_from_links(container, ignored_texts):
    tags = []
    ignored = {normalize_text(text).lower() for text in ignored_texts if text}
    for anchor in container.select("a[href]"):
        text = normalize_text(anchor.get_text(" ", strip=True))
        href = anchor.get("href", "")
        if not text or text.lower() in ignored:
            continue
        if href.startswith("mailto:"):
            continue
        if any(token in href for token in ["/startups/", "/remote/", "/full-time/", "/part-time/", "/internship/"]):
            continue
        if text.lower() in {"design", "apply", "open posting"}:
            continue
        if text not in tags:
            tags.append(text)
    return tags


def parse_cryptocurrencyjobs_listing(job):
    title_elem = job.select_one("h2")
    company_elem = job.select_one("h3")
    link_elem = job.select_one("h2 a, a[href]")
    if not all([title_elem, company_elem, link_elem]):
        return None

    title = normalize_text(title_elem.get_text(" ", strip=True))
    company = normalize_text(company_elem.get_text(" ", strip=True))
    apply_link = urljoin("https://cryptocurrencyjobs.co", link_elem.get("href", ""))

    detail_lines = [normalize_text(node.get_text(" ", strip=True)) for node in job.select("h4")]
    detail_lines = [line for line in detail_lines if line]

    location = ""
    employment_type = ""
    compensation = ""
    date_posted = "Unknown"
    ignored = {title, company, "Design"}

    for line in detail_lines:
        if line == "Design":
            continue
        if line in EMPLOYMENT_TYPES:
            employment_type = line
            ignored.add(line)
            continue
        if looks_like_compensation(line):
            compensation = line
            ignored.add(line)
            continue
        if looks_like_relative_date(line):
            date_posted = line
            ignored.add(line)
            continue
        if not location:
            location = line
            ignored.add(line)

    tags = collect_tags_from_links(job, ignored)
    return {
        "job_id": stable_job_id("ccj", apply_link),
        "title": title,
        "company": company,
        "source_site": "CryptocurrencyJobs",
        "date_posted": date_posted,
        "apply_link": apply_link,
        "location": location,
        "employment_type": employment_type,
        "compensation": compensation,
        "tags": tags,
        "search_blob": " ".join([title, company, location, compensation, " ".join(tags)]),
    }


def parse_web3career_listing(row):
    anchors = row.select("a[href]")
    if not anchors:
        return None

    title = ""
    company = ""
    title_elem = row.find("h2")
    company_elem = row.find("h3")
    if title_elem is not None:
        title = normalize_text(title_elem.get_text(" ", strip=True))
    if company_elem is not None:
        company = normalize_text(company_elem.get_text(" ", strip=True))

    cells = [normalize_text(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
    cells = [cell for cell in cells if cell]
    if not title and cells:
        title = cells[0]
    if not company and len(cells) > 1:
        company = cells[1]
    if not title or not company:
        return None

    apply_link = ""
    for anchor in anchors:
        href = anchor.get("href", "")
        if "/i/" in href or href.startswith("/lead-") or href.startswith("/product-"):
            apply_link = urljoin("https://web3.career", href)
            break
    if not apply_link:
        for anchor in anchors:
            href = anchor.get("href", "")
            if href and "sign_" not in href and "bondex" not in href and "/web3-companies/" not in href:
                apply_link = urljoin("https://web3.career", href)
                break
    if not apply_link:
        return None

    date_posted = cells[2] if len(cells) > 2 else "Unknown"
    location = cells[3] if len(cells) > 3 else ""
    compensation = cells[4] if len(cells) > 4 else ""
    tags_text = cells[5] if len(cells) > 5 else ""
    tags = [tag for tag in tags_text.split(" ") if tag]
    employment_type = ""
    if any(tag.lower() == "contract" for tag in tags):
        employment_type = "Contract"

    return {
        "job_id": stable_job_id("w3c", apply_link),
        "title": title,
        "company": company,
        "source_site": "Web3.career",
        "date_posted": date_posted,
        "apply_link": apply_link,
        "location": location,
        "employment_type": employment_type,
        "compensation": compensation,
        "tags": tags,
        "search_blob": " ".join([title, company, location, compensation, tags_text]),
    }


def should_keep_job(job_data):
    if not is_match(job_data["title"], KEYWORDS):
        return False

    searchable = job_data["search_blob"]
    remote_match = is_match(searchable, LOCATIONS)
    industry_match = job_data["source_site"] in {"CryptocurrencyJobs", "Web3.career"} or is_match(searchable, INDUSTRIES)
    return remote_match and industry_match


def save_job(job_data):
    return insert_job(
        job_id=job_data["job_id"],
        title=job_data["title"],
        company=job_data["company"],
        source_site=job_data["source_site"],
        date_posted=job_data["date_posted"],
        apply_link=job_data["apply_link"],
        location=job_data["location"],
        employment_type=job_data["employment_type"],
        compensation=job_data["compensation"],
        tags=job_data["tags"],
    )


def scrape_cryptocurrencyjobs():
    url = "https://cryptocurrencyjobs.co/design/"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        count = 0
        for job in soup.select("li.job-list-item"):
            parsed = parse_cryptocurrencyjobs_listing(job)
            if not parsed or not should_keep_job(parsed):
                continue
            if save_job(parsed):
                count += 1
        return count
    except Exception as exc:
        print(f"Error scraping CryptocurrencyJobs: {exc}")
        return 0


def scrape_web3career():
    url = "https://web3.career/design-jobs"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        count = 0
        for row in soup.select("tr.table_row"):
            parsed = parse_web3career_listing(row)
            if not parsed or not should_keep_job(parsed):
                continue
            if save_job(parsed):
                count += 1
        return count
    except Exception as exc:
        print(f"Error scraping Web3.career: {exc}")
        return 0


def run_all_scrapers():
    print("Starting scrapers run...")
    ccj_count = scrape_cryptocurrencyjobs()
    w3c_count = scrape_web3career()
    print(f"Finished. Upserted {ccj_count} from CCJ, {w3c_count} from W3C.")
