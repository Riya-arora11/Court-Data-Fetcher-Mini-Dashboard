from __future__ import annotations
import json
import os
import sqlite3
import importlib.util
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from flask import Flask, render_template, request, url_for  
except ImportError:
    Flask = None  
    render_template = None  
    request = None 
    url_for = None  

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
PCASE_SCRIPT = BASE_DIR / "2nd scrap.py"
DATA_EXTRACT_SCRIPT = BASE_DIR / "data extract.py"
TESSERACT_BUNDLE = BASE_DIR / "external" / "tesseract" / "tesseract.exe"
DB_FILE = BASE_DIR / "queries.db"


def init_db() -> None:
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_type TEXT NOT NULL,
                case_number TEXT NOT NULL,
                year TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                party1 TEXT,
                party2 TEXT,
                filing_date TEXT,
                next_hearing_date TEXT,
                pdf_link TEXT
            )
            """
        )


def log_query(result: Dict[str, Any]) -> None:
    timestamp = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO queries (
                case_type, case_number, year, timestamp,
                party1, party2, filing_date, next_hearing_date, pdf_link
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.get("case_type"),
                result.get("case_number"),
                result.get("year"),
                timestamp,
                result.get("party1"),
                result.get("party2"),
                result.get("filing_date"),
                result.get("next_hearing_date"),
                result.get("pdf_link"),
            ),
        )


def load_external_function(file_path: Path, func_name: str):
    spec = importlib.util.spec_from_file_location(func_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, func_name):
        raise ImportError(f"Function {func_name} not found in {file_path}")
    return getattr(module, func_name)


def run_scrapers(case_type: str, case_number: str, year: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    get_date_of_filing = load_external_function(PCASE_SCRIPT, "get_date_of_filing")
    fetch_case_details_external = load_external_function(DATA_EXTRACT_SCRIPT, "fetch_case_details")
    print(fetch_case_details_external)
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_pcase = executor.submit(get_date_of_filing, case_type, case_number, year)
        future_data = executor.submit(
            fetch_case_details_external,
            case_type=case_type,
            case_number=case_number,
            year_text=year
        )
        pcase_result = future_pcase.result()
        data_result = future_data.result()
    return pcase_result, data_result


def create_app() -> Flask:
    
    if Flask is None:
        raise ImportError(
            "Flask is not installed. Install it or use the standalone server to run the app."
        )
    app = Flask(__name__, static_folder=str(STATIC_DIR), template_folder=str(TEMPLATE_DIR))
    init_db()

    DEFAULT_CASE_TYPES = [
        "FAO", "LPA", "WPC", "CRL", "RCREV", "CM", "MACA", "RFA"
    ]

    @app.route("/", methods=["GET", "POST"])
    def index():
        error_message: Optional[str] = None
        result_data: Optional[Dict[str, Any]] = None
        available_case_types = DEFAULT_CASE_TYPES

        if request.method == "POST":
            case_type = request.form.get("case_type", "").strip().upper()
            case_number = request.form.get("case_number", "").strip()
            year = request.form.get("year", "").strip()
            if not (case_type and case_number and year):
                error_message = "Please enter all fields."
            else:
                try:
                    pcase_result, data_result = run_scrapers(case_type, case_number, year)
                except Exception as e:
                    error_message = f"Error invoking scrapers: {e}"
                    pcase_result = None
                    data_result = None

                if data_result is None:
                    error_message = "No case found for the given details. Please verify the case number and year."
                elif isinstance(pcase_result, str):
                    error_message = pcase_result
                else:
                    result_data = {
                        "case_type": case_type,
                        "case_number": case_number,
                        "year": year,
                        "party1": pcase_result.get("petitioner"),
                        "party2": pcase_result.get("respondent"),
                        "filing_date": pcase_result.get("date_of_filing"),
                        "next_hearing_date": data_result.get("next_hearing_date"),
                        "pdf_link": data_result.get("first_order_pdf"),
                    }
                    log_query(result_data)

        return render_template(
            "index.html",
            available_case_types=available_case_types,
            error_message=error_message,
            result=result_data,
        )

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
