# ---------------------------------------------------------------
# Web Scraping Script by Talha
# Fiverr Profile: https://www.fiverr.com/talhapythoneer/
# Need custom scraping? Contact me!
# ---------------------------------------------------------------
#
# STEP 3
# Reads step2_file_urls.csv and downloads everything locally, organized as:
#
#   downloads/<Year>/<Category>/<DocumentID_Year_Category>/<file>
#
# For every case it also saves the listing page itself (fOdluka.xsp) as an
# .html file, alongside the PDF/DOCX/etc. attachments, so "everything" for
# that case lives in one folder.

import csv
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from common_utils import REQUEST_HEADERS, extract_listing_text, safe_name, configure_console_utf8

configure_console_utf8()

INPUT_CSV = "step2_file_urls.csv"
DOWNLOAD_ROOT = "downloads"
MAX_WORKERS = 100
# Files this small are almost certainly a truncated/failed download (e.g. an
# error page saved instead of the real file), so treat them as missing.
MIN_VALID_FILE_SIZE = 1024  # bytes (1 KB)

_print_lock = threading.Lock()


def safe_print(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)


def is_already_downloaded(path):
    return os.path.exists(path) and os.path.getsize(path) > MIN_VALID_FILE_SIZE


def download_file(url, dest_path, session, timeout=60):
    if is_already_downloaded(dest_path):
        safe_print(f"    already have {os.path.basename(dest_path)}, skipping")
        return True

    try:
        with session.get(url, headers=REQUEST_HEADERS, timeout=timeout, stream=True) as resp:
            resp.raise_for_status()
            tmp_path = dest_path + ".part"
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            os.replace(tmp_path, dest_path)
        safe_print(f"    downloaded {os.path.basename(dest_path)}")
        return True
    except requests.RequestException as e:
        safe_print(f"    !! failed to download {url}: {e}")
        return False


def case_folder_name(document_id, signatura, year, category):
    doc_label = signatura.strip() if signatura.strip() else document_id
    return safe_name(f"{doc_label}_{year}_{category}")


def main():
    with open(INPUT_CSV, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    print(f"Loaded {len(rows)} file rows from {INPUT_CSV}")

    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Group rows by case (listing_url) so we only fetch/save the listing
    # HTML once per case, and can put every file for that case in one folder.
    cases = {}
    for row in rows:
        cases.setdefault(row["listing_url"], []).append(row)

    print(f"{len(cases)} unique cases to process")

    # File downloads are submitted to the pool as soon as each case is
    # scanned, so downloading overlaps with fetching the remaining listing
    # pages instead of waiting for the entire 20k-case scan to finish first.
    progress = {"queued": 0, "done": 0}
    progress_lock = threading.Lock()

    def on_download_done(future):
        with progress_lock:
            progress["done"] += 1
            done, queued = progress["done"], progress["queued"]
        if done % 50 == 0 or done == queued:
            safe_print(f"    file progress: {done}/{queued} files processed")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []

        for i, (listing_url, case_rows) in enumerate(cases.items(), 1):
            first = case_rows[0]
            year = safe_name(first.get("year", "") or "unknown_year")
            category = safe_name(first.get("category", "") or "unknown_category")
            document_id = first.get("document_id", "") or "unknown_id"
            signatura = first.get("signatura", "")

            folder = case_folder_name(document_id, signatura, year, category)
            case_dir = os.path.join(DOWNLOAD_ROOT, year, category, folder)
            os.makedirs(case_dir, exist_ok=True)

            print(f"[{i}/{len(cases)}] {folder}")

            # Save the listing page itself (contains all metadata for the case).
            listing_dest = os.path.join(case_dir, safe_name(f"{folder}_listing") + ".html")
            listing_html = None
            if is_already_downloaded(listing_dest):
                with open(listing_dest, "r", encoding="utf-8") as f:
                    listing_html = f.read()
            else:
                try:
                    resp = session.get(listing_url, headers=REQUEST_HEADERS, timeout=30)
                    resp.raise_for_status()
                    listing_html = resp.text
                    with open(listing_dest, "w", encoding="utf-8") as f:
                        f.write(listing_html)
                    print("    saved listing page HTML")
                except requests.RequestException as e:
                    print(f"    !! failed to save listing page: {e}")

            # Queue every file attached to this case for threaded download.
            has_files = False
            for row in case_rows:
                file_url = row.get("file_url", "")
                if not file_url:
                    continue
                has_files = True
                file_name = row.get("file_name") or os.path.basename(file_url)
                ext = os.path.splitext(file_name)[1]
                base_name = safe_name(os.path.splitext(file_name)[0])
                dest_path = os.path.join(case_dir, base_name + ext)

                with progress_lock:
                    progress["queued"] += 1
                fut = executor.submit(download_file, file_url, dest_path, session)
                fut.add_done_callback(on_download_done)
                futures.append(fut)

            # No files listed for this case: save its text content as a .txt instead.
            if not has_files and listing_html:
                text_dest = os.path.join(case_dir, safe_name(f"{folder}_content") + ".txt")
                if not is_already_downloaded(text_dest):
                    text = extract_listing_text(listing_html)
                    if text:
                        with open(text_dest, "w", encoding="utf-8") as f:
                            f.write(text)
                        print("    saved listing text content (no files found)")

        print(f"All cases scanned; {len(futures)} files queued, waiting for remaining downloads to finish...")
        for future in as_completed(futures):
            future.result()

    print(f"All done. Files saved under '{DOWNLOAD_ROOT}/'")


if __name__ == "__main__":
    main()
    print("Script by Talha | Fiverr: https://www.fiverr.com/talhapythoneer/")
