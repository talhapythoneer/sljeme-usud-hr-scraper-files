# ---------------------------------------------------------------
# Shared helpers for the sljeme.usud.hr scraping scripts
# Web Scraping Script by Talha
# Fiverr Profile: https://www.fiverr.com/talhapythoneer/
# Need custom scraping? Contact me!
# ---------------------------------------------------------------

import re
import sys

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "https://sljeme.usud.hr/usud/praksaw.nsf/vPremaDatumuDonos.xsp"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
}

_INVALID_CHARS = re.compile(r'[\\/:*?"<>|]')


def configure_console_utf8():
    """Titles/categories contain Croatian diacritics (c, s, z...); the default
    Windows console codepage can't print them and would crash mid-run. Force
    stdout/stderr to UTF-8 so logging never kills a long scrape."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def bot_initialization(headless=False):
    """Initialize the Chrome Selenium bot."""
    chrome_options = Options()
    chrome_options.add_argument("start-maximized")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    if headless:
        chrome_options.add_argument("--headless=new")

    chromedriver_path = ChromeDriverManager().install()
    driver = webdriver.Chrome(
        service=webdriver.chrome.service.Service(chromedriver_path),
        options=chrome_options,
    )
    driver.maximize_window()
    return driver


def extract_listing_text(html):
    """Pull the readable text (signatura, odluka, datum, zakljucak, and the
    full decision body) out of a listing page. Used for cases that have no
    downloadable files listed, so their content still gets saved as .txt."""
    soup = BeautifulSoup(html, "lxml")

    def field(id_suffix):
        el = soup.find(id=lambda i: i and i.endswith(id_suffix))
        return el.get_text(strip=True) if el else ""

    signatura = field(":cfSignatura")
    odluka = field(":cfOdluka")
    datum = field(":cfDatum")
    zakljucak = field(":cfZakljucak")

    body_el = soup.find(id=lambda i: i and i.endswith(":inputRichText1"))
    body_text = ""
    if body_el:
        for br in body_el.find_all("br"):
            br.replace_with("\n")
        body_text = body_el.get_text()
        body_text = re.sub(r"[ \t]+\n", "\n", body_text)
        body_text = re.sub(r"\n{3,}", "\n\n", body_text)
        body_text = body_text.strip()

    lines = []
    if signatura:
        lines.append(signatura)
    header = " - ".join(x for x in (odluka, datum) if x)
    if header:
        lines.append(header)
    if zakljucak:
        lines.append("")
        lines.append("Zaključak:")
        lines.append(zakljucak)
    if body_text:
        lines.append("")
        lines.append(body_text)

    return "\n".join(lines).strip()


def safe_name(value, max_length=150):
    """Sanitize a string so it can be used as a Windows file/folder name."""
    if value is None:
        value = ""
    value = value.strip()
    value = _INVALID_CHARS.sub("-", value)
    value = re.sub(r"\s+", " ", value)
    value = value.strip(" .")
    if not value:
        value = "unknown"
    return value[:max_length]
