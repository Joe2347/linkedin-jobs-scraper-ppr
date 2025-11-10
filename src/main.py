import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

from utils.linkedin_parser import fetch_page, extract_jobs_from_html
from utils.company_extractor import enrich_company_profile
from utils.data_cleaner import normalize_records, apply_settings
from outputs.json_exporter import write_json
from outputs.csv_exporter import write_csv

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "input_urls.txt"
DEFAULT_SAMPLE = ROOT / "data" / "sample_jobs.json"
DEFAULT_SETTINGS = ROOT / "src" / "config" / "settings.json"

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def read_lines(path: Path) -> List[str]:
    if not path.exists():
        logging.warning("Input file '%s' not found. Proceeding with sample data.", path)
        return []
    with path.open("r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

def load_settings(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            logging.info("Loaded settings from %s", path)
            return data
    except FileNotFoundError:
        logging.warning("Settings file not found at %s. Using defaults.", path)
        return {}
    except json.JSONDecodeError as e:
        logging.error("Failed to parse settings.json: %s", e)
        return {}

def ingest_sample(path: Path) -> List[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                logging.info("Loaded %d sample records from %s", len(data), path)
                return data
    except Exception as e:
        logging.error("Failed to read sample data at %s: %s", path, e)
    return []

def process_url(url: str, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        html = fetch_page(url, headers=settings.get("http", {}).get("headers", {}), timeout=settings.get("http", {}).get("timeout", 20))
        jobs = extract_jobs_from_html(html, base_url=url)
        return jobs
    except Exception as e:
        logging.warning("Processing URL failed (%s): %s", url, e)
        return []

def enrich_companies(records: List[Dict[str, Any]], settings: Dict[str, Any]) -> None:
    enable_enrichment = settings.get("enrichment", {}).get("enable_company_enrichment", True)
    if not enable_enrichment:
        logging.info("Company enrichment disabled via settings.")
        return

    for rec in records:
        try:
            company_url = rec.get("companyLinkedinUrl") or rec.get("companyProfile") or ""
            if not company_url:
                continue
            company_profile = enrich_company_profile(
                company_url,
                headers=settings.get("http", {}).get("headers", {}),
                timeout=settings.get("http", {}).get("timeout", 20),
            )
            rec.update(company_profile)
        except Exception as e:
            logging.debug("Company enrichment failed for %s: %s", rec.get("companyName"), e)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LinkedIn Jobs Scraper - PPR (public search parser with exporters)."
    )
    parser.add_argument("--input", type=str, default=str(DEFAULT_INPUT), help="Path to a file containing LinkedIn search result URLs (one per line).")
    parser.add_argument("--settings", type=str, default=str(DEFAULT_SETTINGS), help="Path to settings.json for headers, timeouts, etc.")
    parser.add_argument("--out-json", type=str, default=str(ROOT / "jobs.json"), help="Path to write JSON output.")
    parser.add_argument("--out-csv", type=str, default=str(ROOT / "jobs.csv"), help="Path to write CSV output.")
    parser.add_argument("--no-sample-fallback", action="store_true", help="Disable fallback to bundled sample when input URLs produce no data.")
    return parser.parse_args()

def main() -> int:
    args = parse_args()
    settings = load_settings(Path(args.settings))
    apply_settings(settings)

    urls = read_lines(Path(args.input))
    all_records: List[Dict[str, Any]] = []

    if not urls:
        logging.info("No input URLs provided or file missing.")
    for url in urls:
        logging.info("Processing search URL: %s", url)
        records = process_url(url, settings)
        all_records.extend(records)

    if not all_records and not args.no_sample_fallback:
        logging.info("No records parsed from provided URLs. Falling back to sample data.")
        all_records = ingest_sample(DEFAULT_SAMPLE)

    if not all_records:
        logging.error("No job records found. Exiting with status 2.")
        return 2

    enrich_companies(all_records, settings)
    cleaned = normalize_records(all_records)

    # Write outputs
    write_json(cleaned, Path(args.out_json))
    write_csv(cleaned, Path(args.out_csv))
    logging.info("Success. Wrote %d records -> %s and %s", len(cleaned), args.out_json, args.out_csv)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logging.warning("Interrupted by user.")
        sys.exit(130)