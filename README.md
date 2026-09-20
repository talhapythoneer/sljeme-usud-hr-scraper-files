# sljeme.usud.hr Files Downloader

Scrapes decisions from the Croatian Constitutional Court's "Prema datumu
donosenja odluka" (by decision date) archive and downloads all attached
files locally.

## Pipeline

Run in order:

1. **`step1_collect_listing_urls.py`** — expands the year/category accordion
   tree and saves every decision listing URL to `step1_listing_urls.csv`
   (`year, category, title, url, document_id`).
2. **`step2_collect_file_urls.py`** — visits each listing from step 1 and
   collects its downloadable file URLs into `step2_file_urls.csv`
   (`year, category, title, listing_url, document_id, signatura, file_url,
   file_name`). Resumable — already-processed listings are skipped on rerun.
3. **`step3_download_files.py`** — downloads every file from step 2, plus a
   saved copy of the listing page itself, into:
   ```
   downloads/<Year>/<Category>/<DocumentID_Year_Category>/<file>
   ```

## Requirements

- Python 3
- `selenium`, `scrapy`, `requests`

## Usage

```powershell
python step1_collect_listing_urls.py
python step2_collect_file_urls.py
python step3_download_files.py
```
