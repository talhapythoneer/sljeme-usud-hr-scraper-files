# ---------------------------------------------------------------
# Web Scraping Script by Talha
# Fiverr Profile: https://www.fiverr.com/talhapythoneer/
# Need custom scraping? Contact me!
# ---------------------------------------------------------------

from selenium import webdriver
from time import sleep
from selenium.webdriver.chrome.options import Options
from shutil import which
from scrapy import Selector
import csv
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager

# Use ChromeDriverManager to download and install the appropriate ChromeDriver
chromedriver_path = ChromeDriverManager().install()


def botInitialization():
    # Initialize the Bot
    chromeOptions = Options()
    chromeOptions.add_argument("start-maximized")
    chromeOptions.add_experimental_option("excludeSwitches", ["enable-automation"])
    chromeOptions.add_experimental_option('useAutomationExtension', False)
    chromeOptions.add_argument('--disable-blink-features=AutomationControlled')
    # chromeOptions.add_argument("--headless")
    
    # disable images loading    
    # prefs = {"profile.managed_default_content_settings.images": 2}
    # chromeOptions.add_experimental_option("prefs", prefs)
    # include chrome profile path
    # chromeOptions.add_argument("user-data-dir=C:\\Users\\User\\AppData\\Local\\Google\\Chrome\\User Data")
    # chromeOptions.add_argument("profile-directory=Default")
    
    
    # Cookies saving
    # script_directory = pathlib.Path().absolute()
    # chromeOptions.add_argument(
    #     "user-data-dir={}\\selenium_cookies".format(script_directory)
    # )  # for saving selenium cookies


    driver = webdriver.Chrome(service=webdriver.chrome.service.Service(chromedriver_path), options=chromeOptions)
    driver.maximize_window()
    return driver

driver = botInitialization()


with open('Data.csv', 'w', newline='', encoding="utf-8-sig") as csvfile: # opens the file in write mode
    fieldnames = ['Name', 'Price'] 
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames) # creates a writer object
    writer.writeheader() # writes the headers(column names) to file
    
    
    dataRow = { # creates a dictionary that will be written to the file
        'Name': 'Name',
        'Price': 'Price'
    }
    
    writer.writerow(dataRow) # writes the dictionary to the file


print("Script by Talha | Fiverr: https://www.fiverr.com/talhapythoneer/")
