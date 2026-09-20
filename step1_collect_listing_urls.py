# ---------------------------------------------------------------
# Web Scraping Script by Talha
# Fiverr Profile: https://www.fiverr.com/talhapythoneer/
# Need custom scraping? Contact me!
# ---------------------------------------------------------------
#
# STEP 1
# Opens the "Prema datumu donosenja odluka" (by decision date) page,
# clicks every "+" icon (year, then category inside each year) until
# the whole accordion tree is expanded, then saves every decision
# "listing" URL (with its year/category) to a CSV file.
#
# Output: step1_listing_urls.csv
#         columns -> year, category, title, url, document_id

import csv
import os
import time
from urllib.parse import urlparse, parse_qs

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)
from scrapy import Selector

from common_utils import BASE_URL, bot_initialization, configure_console_utf8

configure_console_utf8()

OUTPUT_CSV = "step1_listing_urls.csv"

# Matches only the clickable "+" header divs (year headers AND category
# headers use the same pattern), never their Container/Content/CallbackHolder
# siblings.
HEADER_XPATH = (
    "//div[contains(@id, ':divCategory') "
    "and not(contains(@id, ':divCategoryContainer')) "
    "and not(contains(@id, ':divContent')) "
    "and not(contains(@id, ':divCallbackHolder'))]"
)

# The main page (the one listing years) is itself paginated via a single
# xspPagerContainer - e.g. page 1 shows some years, page 2 shows others. The
# "Next page" arrow is only rendered as a clickable <a> when a next page
# actually exists - on the last page it's a plain (non-link) <img>. So this
# xpath naturally yields nothing once we're on the last page.
NEXT_PAGE_XPATH = (
    "//span[contains(@id, 'pager__NextImage')]"
    "/a[contains(@id, 'pager__NextImage__img')]"
)


def _click_header(driver, hid, clicked_ids, click_timeout):
    """Clicks a single '+' header and waits for its AJAX partial-refresh."""
    try:
        el = driver.find_element(By.ID, hid)
    except Exception:
        clicked_ids.add(hid)
        return

    base = hid.rsplit(":divCategory", 1)[0]
    callback_id = base + ":divCallbackHolder"

    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        el.click()
    except ElementClickInterceptedException:
        try:
            driver.execute_script("arguments[0].click();", el)
        except Exception as e:
            print(f"  ! could not click {hid}: {e}")
            clicked_ids.add(hid)
            return
    except StaleElementReferenceException:
        clicked_ids.add(hid)
        return
    except Exception as e:
        print(f"  ! could not click {hid}: {e}")
        clicked_ids.add(hid)
        return

    clicked_ids.add(hid)
    print(f"  clicked ({len(clicked_ids)}): {hid}")

    try:
        WebDriverWait(driver, click_timeout).until(
            EC.presence_of_element_located((By.ID, callback_id))
        )
    except TimeoutException:
        # Some categories legitimately have zero documents/subcategories.
        pass

    time.sleep(1)


def expand_all(driver, max_rounds=500, click_timeout=15):
    """Repeatedly clicks every unexpanded '+' icon until no new ones show up.

    New headers keep appearing as parents finish their AJAX partial-refresh
    (year -> category -> ...), so we loop, re-scanning the DOM each round,
    until two consecutive passes find nothing new to click. Once that settles,
    we do a final re-scan pass to catch any '+' icon that rendered too slowly
    to be picked up by the main loop.
    """
    clicked_ids = set()
    stable_rounds = 0
    rounds = 0

    while stable_rounds < 2 and rounds < max_rounds:
        rounds += 1
        headers = driver.find_elements(By.XPATH, HEADER_XPATH)
        header_ids = [h.get_attribute("id") for h in headers]
        new_ids = [hid for hid in header_ids if hid and hid not in clicked_ids]

        if not new_ids:
            stable_rounds += 1
            time.sleep(1)
            continue

        stable_rounds = 0
        for hid in new_ids:
            _click_header(driver, hid, clicked_ids, click_timeout)

    print(f"Done expanding: {rounds} rounds, {len(clicked_ids)} headers clicked.")

    # Final safety pass: re-scan in case any '+' icon still hasn't been
    # clicked (e.g. it rendered right as the stability check above passed).
    for check_num in range(1, 6):
        headers = driver.find_elements(By.XPATH, HEADER_XPATH)
        header_ids = [h.get_attribute("id") for h in headers]
        missed_ids = [hid for hid in header_ids if hid and hid not in clicked_ids]

        if not missed_ids:
            print("Final check: no unloaded '+' icons remaining.")
            break

        print(f"Final check #{check_num}: found {len(missed_ids)} unloaded '+' icon(s), clicking now...")
        for hid in missed_ids:
            _click_header(driver, hid, clicked_ids, click_timeout)
    else:
        print("Final check: reached retry limit, some '+' icons may remain unclicked.")


def extract_listings(driver, seen_urls=None):
    """Extracts listing rows currently rendered in the DOM.

    `seen_urls` is shared across calls (one per main pager page) so that when
    called again after paging to year-list page 2/3/..., only newly-revealed
    rows are returned instead of duplicating rows already collected.
    """
    if seen_urls is None:
        seen_urls = set()

    sel = Selector(text=driver.page_source)
    results = []

    anchors = sel.xpath("//a[contains(@id, ':lnkOdluka')]")
    for a in anchors:
        href = a.xpath("./@href").get()
        if not href or href in seen_urls:
            continue
        seen_urls.add(href)

        title = "".join(a.xpath(".//text()").getall()).strip()

        # Walk up to every ancestor "divCategoryContainer" - the outermost
        # one is the year, the next one in is the category. This works no
        # matter how many accordion levels the site actually has.
        ancestors = a.xpath("ancestor::div[contains(@id, ':divCategoryContainer')]")
        labels = []
        for anc in ancestors:
            lbl = anc.xpath(".//span[contains(@id, ':lblNazivKategorije')][1]/text()").get()
            labels.append((lbl or "").strip())

        year_label = labels[0] if len(labels) > 0 else ""
        category_label = labels[1] if len(labels) > 1 else ""

        query = parse_qs(urlparse(href).query)
        document_id = query.get("documentId", [""])[0]

        results.append(
            {
                "year": year_label,
                "category": category_label,
                "title": title,
                "url": href,
                "document_id": document_id,
            }
        )

    return results


def click_next_main_page_and_collect(driver, seen_urls, max_rounds=50, settle_time=1.5):
    """Advances the main (year-list) pager page by page.

    Each new page shows a different batch of years, all collapsed again, so
    we re-run expand_all() after every page turn before extracting.
    """
    all_new = []
    page_num = 1

    while page_num < max_rounds:
        next_links = [el for el in driver.find_elements(By.XPATH, NEXT_PAGE_XPATH) if el.is_displayed()]
        if not next_links:
            break

        el = next_links[0]
        page_num += 1
        print(f"Moving to main page {page_num}...")
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            el.click()
        except ElementClickInterceptedException:
            try:
                driver.execute_script("arguments[0].click();", el)
            except Exception as e:
                print(f"  ! could not click next-page link: {e}")
                break
        except StaleElementReferenceException:
            continue
        except Exception as e:
            print(f"  ! could not click next-page link: {e}")
            break

        time.sleep(settle_time)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, HEADER_XPATH))
        )

        expand_all(driver)

        new_listings = extract_listings(driver, seen_urls)
        all_new.extend(new_listings)
        print(f"  -> page {page_num}: {len(new_listings)} new listing(s) found (running total new: {len(all_new)}).")

    print(f"Done paginating: {page_num} page(s) visited, {len(all_new)} listing(s) found beyond page 1.")
    return all_new


def load_existing_urls(csv_path):
    """Reads already-saved listing URLs from a previous run, if any."""
    existing = set()
    try:
        with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get("url")
                if url:
                    existing.add(url)
    except FileNotFoundError:
        pass
    return existing


def main():
    driver = bot_initialization()
    try:
        print(f"Opening {BASE_URL}")
        driver.get(BASE_URL)

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, HEADER_XPATH))
        )

        expand_all(driver)

        seen_urls = set()

        print("Extracting listing links from the fully expanded page (main page 1)...")
        listings = extract_listings(driver, seen_urls)
        print(f"Found {len(listings)} unique listing URLs on main page 1.")

        listings.extend(click_next_main_page_and_collect(driver, seen_urls))
        print(f"Found {len(listings)} unique listing URLs in total (all pages).")

        existing_urls = load_existing_urls(OUTPUT_CSV)
        new_listings = [row for row in listings if row["url"] not in existing_urls]
        skipped = len(listings) - len(new_listings)
        print(f"Skipping {skipped} already-saved listing URL(s); {len(new_listings)} new to save.")

        fieldnames = ["year", "category", "title", "url", "document_id"]
        write_header = not os.path.exists(OUTPUT_CSV)
        with open(OUTPUT_CSV, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            for row in new_listings:
                writer.writerow(row)

        print(f"Saved {len(new_listings)} new row(s) to {OUTPUT_CSV}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
    print("Script by Talha | Fiverr: https://www.fiverr.com/talhapythoneer/")
