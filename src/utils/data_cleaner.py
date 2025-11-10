import logging
import os
from datetime import datetime
from typing import List, Dict, Any

SCHEMA = [
    "id",
    "link",
    "title",
    "companyName",
    "companyLinkedinUrl",
    "companyLogo",
    "location",
    "salaryInfo",
    "postedAt",
    "benefits",
    "descriptionHtml",
    "applicantsCount",
    "jobPosterName",
    "jobPosterTitle",
    "jobPosterPhoto",
    "jobPosterProfileUrl",
    "seniorityLevel",
    "employmentType",
    "jobFunction",
    "industries",
    "companyDescription",
    "companyWebsite",
    "companyEmployeesCount",
]

def apply_settings(settings: Dict[str, Any]) -> None:
    # Currently reserved for global behaviors; can extend to concurrency, retries, etc.
    log_level = settings.get("logging", {}).get("level", "INFO").upper()
    try:
        logging.getLogger().setLevel(getattr(logging, log_level))
    except Exception:
        pass

def _coerce_date(val: str) -> str:
    if not val:
        return val
    # Try common formats (datetime or "2 days ago" left as-is)
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%b %d, %Y"):
        try:
            dt = datetime.strptime(val, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    return val

def normalize_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned = []
    for r in records:
        item = {k: r.get(k) for k in SCHEMA}
        # Normalize/clean
        if isinstance(item.get("salaryInfo"), str):
            item["salaryInfo"] = [item["salaryInfo"]]
        if isinstance(item.get("benefits"), str):
            item["benefits"] = [item["benefits"]]
        if isinstance(item.get("industries"), str):
            item["industries"] = [item["industries"]]
        item["postedAt"] = _coerce_date(item.get("postedAt"))
        # Basic trimming
        for k, v in list(item.items()):
            if isinstance(v, str):
                item[k] = v.strip()
        cleaned.append(item)
    # Deduplicate by (id or link)
    seen = set()
    unique = []
    for it in cleaned:
        key = it.get("id") or it.get("link")
        if not key or key not in seen:
            unique.append(it)
            if key:
                seen.add(key)
    logging.info("Normalized %d -> %d unique records", len(cleaned), len(unique))
    return unique