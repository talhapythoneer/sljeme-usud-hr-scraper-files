# ---------------------------------------------------------------
# Web Scraping Script by Talha
# Fiverr Profile: https://www.fiverr.com/talhapythoneer/
# Need custom scraping? Contact me!
# ---------------------------------------------------------------
#
# STEP 2
# Reads step1_listing_urls.csv, visits every listing page and collects
# the downloadable file URLs (PDF/DOCX/etc.) shown in its file table.
# Tries a plain HTTP request first (fast); only falls back to Selenium
# for a given page if the request fails or comes back without the
# expected content.
#
# Listings are processed concurrently (MAX_WORKERS at a time). Listings
# already present in the output CSV from a previous run are skipped, so
# the script can be re-run to resume an interrupted scrape.
#
# Output: step2_file_urls.csv
#         columns -> year, category, title, listing_url, document_id,
#                    signatura, file_url, file_name

import concurrent.futures
import csv
import os
import threading
import time

import requests
from scrapy import Selector

from common_utils import REQUEST_HEADERS, bot_initialization, configure_console_utf8

configure_console_utf8()

INPUT_CSV = "step1_listing_urls.csv"
OUTPUT_CSV = "step2_file_urls.csv"
MAX_WORKERS = 100

FIELDNAMES = [
    "year",
    "category",
    "title",
    "listing_url",
    "document_id",
    "signatura",
    "file_url",
    "file_name",
]


def fetch_via_requests(url, session, timeout=20):
    try:
        resp = session.get(url, headers=REQUEST_HEADERS, timeout=timeout)
        if resp.status_code == 200 and resp.text.strip():
            return resp.text
    except requests.RequestException as e:
        print(f"  request failed for {url}: {e}")
    return None


def fetch_via_selenium(url, driver):
    driver.get(url)
    time.sleep(1.5)
    return driver.page_source


def looks_valid(html):
    return bool(html) and ("cfSignatura" in html or "fileDokumenti" in html)


def parse_listing(html):
    sel = Selector(text=html)
    signatura = (sel.xpath("//span[contains(@id, ':cfSignatura')]/text()").get() or "").strip()

    file_rows = []
    for a in sel.xpath("//a[contains(@class, 'xspLinkFileDownload')]"):
        file_url = a.xpath("./@href").get()
        file_name = "".join(a.xpath(".//text()").getall()).strip()
        if file_url:
            file_rows.append((file_url, file_name))

    return signatura, file_rows


def load_done_listings():
    """Listing URLs that already have a row in the output CSV from a prior run."""
    if not os.path.exists(OUTPUT_CSV):
        return set()
    with open(OUTPUT_CSV, newline="", encoding="utf-8-sig") as f:
        return {row["listing_url"] for row in csv.DictReader(f)}


def process_listing(row, session, selenium_state, selenium_lock):
    """Runs in a worker thread. Selenium access is serialized via selenium_lock
    since a single shared webdriver instance can't handle concurrent calls."""
    url = row["url"]

    html = fetch_via_requests(url, session)

    if not looks_valid(html):
        with selenium_lock:
            if selenium_state["driver"] is None:
                selenium_state["driver"] = bot_initialization()
            html = fetch_via_selenium(url, selenium_state["driver"])

    if not looks_valid(html):
        return None, []

    return parse_listing(html)


def main():
    with open(INPUT_CSV, newline="", encoding="utf-8-sig") as f_in:
        rows = list(csv.DictReader(f_in))

    print(f"Loaded {len(rows)} listing URLs from {INPUT_CSV}")

    done_listings = load_done_listings()
    pending_rows = [row for row in rows if row["url"] not in done_listings]
    skipped = len(rows) - len(pending_rows)
    if skipped:
        print(f"Skipping {skipped} listing(s) already recorded in {OUTPUT_CSV}")
    print(f"{len(pending_rows)} listing(s) left to process")

    if not pending_rows:
        print("Nothing to do.")
        return

    file_exists = os.path.exists(OUTPUT_CSV)

    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    selenium_state = {"driver": None}
    selenium_lock = threading.Lock()
    write_lock = threading.Lock()

    total = len(pending_rows)
    completed = 0

    with open(OUTPUT_CSV, "a" if file_exists else "w", newline="", encoding="utf-8-sig") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(process_listing, row, session, selenium_state, selenium_lock): row
                for row in pending_rows
            }

            for future in concurrent.futures.as_completed(futures):
                row = futures[future]
                url = row["url"]
                completed += 1

                try:
                    signatura, file_rows = future.result()
                except Exception as e:
                    print(f"[{completed}/{total}] {url} -> ERROR: {e}")
                    continue

                if signatura is None:
                    print(f"[{completed}/{total}] !! giving up on {url}")
                    continue

                base_row = {
                    "year": row.get("year", ""),
                    "category": row.get("category", ""),
                    "title": row.get("title", ""),
                    "listing_url": url,
                    "document_id": row.get("document_id", ""),
                    "signatura": signatura,
                }

                with write_lock:
                    if not file_rows:
                        # Still record the case so step 3 can flag it as having no files.
                        writer.writerow({**base_row, "file_url": "", "file_name": ""})
                    else:
                        for file_url, file_name in file_rows:
                            writer.writerow({**base_row, "file_url": file_url, "file_name": file_name})
                    f_out.flush()

                print(f"[{completed}/{total}] {url} -> {len(file_rows)} file(s)")

    if selenium_state["driver"] is not None:
        selenium_state["driver"].quit()

    print(f"Saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
    print("Script by Talha | Fiverr: https://www.fiverr.com/talhapythoneer/")
