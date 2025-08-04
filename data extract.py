import io
import re
import sys
import time
import base64
import subprocess
import cv2
import pytesseract
import numpy as np
from PIL import Image
from typing import Optional, Dict, Any
from pathlib import Path
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
    WebDriverException,
)

URL= "https://delhihighcourt.nic.in/app/get-case-type-status"
MAX_CAPTCHA_TRIES = 3
WAIT_SECS= 20
BASE_DIR = Path(__file__).resolve().parent
TESSERACT_BUNDLE = BASE_DIR / "external" / "tesseract" / "tesseract.exe"
def _read_captcha(png_bytes: bytes) -> Optional[str]:
    img  = Image.open(io.BytesIO(png_bytes))
    gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    _, bw = cv2.threshold(gray, 150, 255,
                          cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    txt  = pytesseract.image_to_string(bw, config="--psm 7 digits")
    m    = re.search(r"\b\d{4}\b", txt)
    return m.group(0) if m else None


def _get_captcha_bytes(driver, wait) -> bytes:
    img = driver.find_element(By.ID, "captcha-code")
    try:
        wait.until(lambda d: img.get_attribute("src"))
    except TimeoutException:
        pass

    src = img.get_attribute("src") or ""
    if src.startswith("data:image"):
        return base64.b64decode(src.split(",", 1)[1])

    if src.startswith("/"):
        src = "https://delhihighcourt.nic.in" + src

    if src:
        try:
            return requests.get(src, timeout=10).content
        except requests.RequestException:
            pass

    return img.screenshot_as_png


def _safe_click(driver, locator, wait, scroll=True):
    el = wait.until(EC.element_to_be_clickable(locator))
    if scroll:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.15)
    try:
        el.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", el)

def fetch_case_details(
    *,
    case_type: str,
    case_number: str,
    year_text: str,
) -> Optional[Dict[str, Any]]:
    
    pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_BUNDLE)

    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--log-level=3")
    opts.add_experimental_option("excludeSwitches", ["enable-logging"])

    svc = Service()
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        svc.creationflags = subprocess.CREATE_NO_WINDOW

    try:
        driver = webdriver.Chrome(service=svc, options=opts)
    except WebDriverException as e:
        print("No Case Found")
        return None

    wait = WebDriverWait(driver, WAIT_SECS)

    try:
        driver.get(URL)
        time.sleep(1.2)

        Select(driver.find_element(By.ID, "case_type")).select_by_value(case_type)
        driver.find_element(By.ID, "case_number").send_keys(case_number)
        Select(driver.find_element(By.ID, "case_year")).select_by_visible_text(year_text)

        solved = False
        for _ in range(MAX_CAPTCHA_TRIES):
            code = _read_captcha(_get_captcha_bytes(driver, wait))
            if code:
                cap_inp = driver.find_element(By.ID, "captchaInput")
                cap_inp.clear()
                cap_inp.send_keys(code)
                _safe_click(driver, (By.ID, "search"), wait)
                solved = True
                break
            time.sleep(1)

        if not solved:
            print("No Case Found")
            return None

        try:
            wait.until(
                lambda d: (
                    (rows := d.find_elements(By.CSS_SELECTOR, "#caseTable tbody tr"))
                    and "No data available" not in rows[0].text
                )
            )
        except TimeoutException:
            print("No Case Found")
            return None

        table      = driver.find_element(By.ID, "caseTable")
        rows       = table.find_elements(By.TAG_NAME, "tr")
        raw_rows   = [" | ".join(td.text.strip() for td in r.find_elements(By.TAG_NAME, "td"))
                      for r in rows if r.find_elements(By.TAG_NAME, "td")]

        first_row  = raw_rows[0] if raw_rows else ""
        next_date  = None
        order_link = None

        for r in rows:
            for a in r.find_elements(By.TAG_NAME, "a"):
                href = a.get_attribute("href") or ""
                if not href:
                    onclick = a.get_attribute("onclick") or ""
                    m = re.search(r"https?://[^'\"]+", onclick)
                    href = m.group(0) if m else ""
                if href and "order" in (a.text.lower() + href.lower()):
                    order_link = href

            m = re.search(
                r'next\s*date\s*:\s*([0-9]{2}/[0-9]{2}/[0-9]{4})', r.text, flags=re.I
            )
            if m:
                next_date = m.group(1)

        # drill into order page (optional)
        first_pdf = None
        if order_link:
            driver.get(order_link)
            wait.until(
                lambda d: (
                    (tbody := d.find_element(By.XPATH, '//*[@id="caseTable"]/tbody'))
                    and "Loading..." not in tbody.text
                    and "No data available" not in tbody.text
                )
            )
            try:
                first_row = driver.find_element(By.XPATH, '//*[@id="caseTable"]/tbody/tr[1]')
                for el in first_row.find_elements(By.XPATH, ".//*[@href]"):
                    first_pdf = el.get_attribute("href")
                    if first_pdf:
                        break
                if not first_pdf:
                    for el in first_row.find_elements(By.XPATH, ".//*[@onclick]"):
                        m = re.search(r"https?://[^'\"]+", el.get_attribute("onclick") or "")
                        if m:
                            first_pdf = m.group(0)
                            break
            except Exception:
                pass

        return {
            "next_hearing_date" : next_date,
            "first_order_pdf"   : first_pdf,
        }

    except Exception as e:
        print("No Case Found")
        return None

    finally:
        driver.quit()


