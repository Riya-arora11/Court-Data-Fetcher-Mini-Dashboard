# Court Data Fetcher & Dashboard

This repository provides a Python application that fetches case details from the Delhi High Court websites, solves CAPTCHAs automatically and presents the results via a simple Flask web interface.  
It was built as part of an internship project and demonstrates how to combine web scraping, optical character recognition (OCR) and a lightweight dashboard to streamline access to public case information.

## Features

- **Case Search Form** – Users can enter a case type (e.g. `FAO`, `LPA`), registration number and filing year to query the Delhi High Court websites.  
- **Automated CAPTCHA Solving** – The scraper detects the CAPTCHA image, takes a screenshot of it and uses [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) to read the four‑digit code.  
- **Concurrent Scraping** – Two separate scrapers run in parallel: one to fetch the filing date, petitioner and respondent (from the “pCase” site), and another to fetch the next hearing date and the first order PDF link.  
- **Data Persistence** – Successful queries are logged into a SQLite database (`queries.db`) for future reference.  
- **Dashboard** – Results are displayed in a Bootstrap‑styled HTML page (`templates/index.html`).

## Project Structure

```
.
├── app.py                # Flask application entry point
├── 2nd Scrap.py      # Scraper for the pCase site (renamed from `2nd scrap.py`)
├── data_extract.py       # Scraper for the public case status site (renamed from `data extract.py`)
├── chromedriver.exe      # ChromeDriver binary used by Selenium (Windows build)
├── queries.db            # SQLite database storing search logs
├── templates/
│   └── index.html        # HTML template for the dashboard
├── external/
│   └── tesseract/        # Place `tesseract.exe` here or adjust `TESSERACT_BUNDLE` in `app.py`
├── requirements.txt       # Python dependencies
├── .gitignore            # Files/directories to ignore in Git
└── README.md             # Project documentation (this file)
```

## CAPTCHA Bypass Approach

Many public court portals protect their search forms with simple four‑digit CAPTCHAs.  To automate requests without human intervention, the scraper implements the following strategy:

1. **Locate the CAPTCHA element** – When the page loads, Selenium locates the CAPTCHA image element and waits for its `src` attribute to be populated.  
2. **Extract the image** – If the `src` attribute contains a Base64‑encoded image, it decodes it; otherwise, it fetches the image via an HTTP request or falls back to a screenshot of the element.  
3. **Preprocess the image** – The image is converted to grayscale and then thresholded to create a high‑contrast black‑and‑white version.  This helps Tesseract to distinguish digits from the noisy background.  
4. **Run Tesseract OCR** – Using the bundled `tesseract.exe`, the code calls `pytesseract.image_to_string` with a page segmentation mode that expects a single line of digits.  A regular expression ensures that only 4‑digit results are accepted.  
5. **Retry if necessary** – If OCR fails, the scraper waits briefly and refreshes the CAPTCHA up to three times before giving up.

A simplified version of the CAPTCHA solver can be found in `data_extract.py`:

```python
# Extract the image data from the CAPTCHA element
img = driver.find_element(By.ID, "captcha-code")
src = img.get_attribute("src")
if src.startswith("data:image"):
    captcha_bytes = base64.b64decode(src.split(",", 1)[1])
else:
    captcha_bytes = img.screenshot_as_png

# Preprocess for OCR
img  = Image.open(io.BytesIO(captcha_bytes))
gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
_, bw = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

# Read using Tesseract (single line of digits)
txt  = pytesseract.image_to_string(bw, config="--psm 7 digits")
code = re.search(r"\b\d{4}\b", txt)
```

## Prerequisites

- **Python 3.8+**  
- **Google Chrome** or another Chromium‑based browser
- **[ChromeDriver](https://chromedriver.chromium.org/downloads)** – The repository includes a Windows build (`chromedriver.exe`). If you are on Linux or macOS, download the matching driver for your browser and replace the binary accordingly.
- **Tesseract OCR** – Download the appropriate Tesseract binary for your platform and place it in `external/tesseract/tesseract.exe` (or update `TESSERACT_BUNDLE` in `app.py`).

## Installation

1. **Clone this repository**:

```bash
git clone https://github.com/Riya-arora11/Court-Data-Fetcher-Mini-Dashboard.git
cd court-data-fetcher
```

2. **Create a virtual environment (optional but recommended)**:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
```

3. **Install dependencies**:

```bash
pip install -r requirements.txt
```

4. **Setup Tesseract**:

   - Download Tesseract for your operating system from [UB Mannheim builds](https://github.com/UB-Mannheim/tesseract/wiki) or your package manager.  
   - Copy the binary (`tesseract.exe` on Windows) into `external/tesseract/`, or modify the `TESSERACT_BUNDLE` path in `app.py` to point to your installation.

5. **Setup ChromeDriver**:

   - Ensure that the version of ChromeDriver matches your installed version of Google Chrome.  
   - Replace the `chromedriver.exe` in the root if necessary.

## Running the Application

```bash
# Start the Flask server
python app.py
```

Then open [http://localhost:5000](http://localhost:5000) in your browser to access the dashboard.  
Enter a case type, case number and year, and the application will fetch and display the case details.

## Notes

- **Error Handling** – If the sites are down or the CAPTCHA cannot be solved after several attempts, the application will return a "No Case Found" message.  
- **Logging** – All successful queries are appended to the `queries` table in `queries.db`.  You can explore the database using SQLite tools.
- **Legal and Ethical Considerations** – Scraping court websites should respect their terms of service.  This project is for educational purposes; you are responsible for complying with local laws and website policies.

