import re, time
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

URL_FORM = "https://dhcmisc.nic.in/pcase/guiCaseWise.php"
CREATE_NO_WINDOW = 0x08000000
def get_date_of_filing(case_type: str,
                       reg_number: str,
                       year_text: str,
                       attempts: int = 2,
                       timeout: int = 5
                       ) -> str:

    for attempt in range(1, attempts + 1):
        driver: Optional[webdriver.Chrome] = None
        try:
            opts = Options()
            opts.add_argument("--headless=new")
            opts.add_argument("--window-size=1920,1080")

            service = Service()
            service.creationflags = CREATE_NO_WINDOW
            driver = webdriver.Chrome(service=service, options=opts)
            wait = WebDriverWait(driver, timeout)
            driver.get(URL_FORM)
            Select(driver.find_element(By.ID, "ctype")).select_by_value(case_type)
            driver.find_element(By.ID, "regno").send_keys(reg_number)
            Select(driver.find_element(By.ID, "regyr")).select_by_visible_text(year_text)
            captcha = driver.find_element(By.ID, "cap").text.strip()
            if not re.fullmatch(r"\d{4}", captcha):
                raise ValueError("captcha digits not detected")

            cap_input = driver.find_element(
                By.XPATH, "/html/body/form/table[1]/tbody/tr[8]/td[2]/input"
            )
            cap_input.clear()
            cap_input.send_keys(captcha)
            driver.find_element(
                By.XPATH, "/html/body/form/table[1]/tbody/tr[12]/td[2]/input[2]"
            ).click()
            wait.until(EC.url_contains("case_history.php"))

            date_elem = driver.find_element(
                By.XPATH,
                "//*[contains(normalize-space(.),'Date of Filing')]/following::font[1]"
            )
            date_of_filing = date_elem.text.strip()
            pet_elem  = driver.find_element(By.XPATH,
                        "//*[@id='form3']/table[2]/tbody/tr[1]/td/font/b")
            resp_elem = driver.find_element(By.XPATH,
                        "//*[@id='form3']/table[2]/tbody/tr[2]/td/font/b")
            raw_pet   = pet_elem.text.strip()          
            petitioner = re.split(r'\b[Vv][Ss]\.?\b', raw_pet, 1)[0].strip().rstrip(".")
            respondent = resp_elem.text.strip()
            if not date_of_filing:
                raise ValueError("Date of Filing not found")

            driver.quit()
            return {
                "date_of_filing": date_of_filing,
                "petitioner"    : petitioner,
                "respondent"    : respondent
            }
        except Exception as exc:
            if driver:
                try:
                    driver.quit()
                except WebDriverException:
                    pass
            print(f"Attempt {attempt} failed:", exc)
            time.sleep(1)

    return "Government site down"


