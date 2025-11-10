import logging
import re
from typing import Dict, Any, Optional

import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def _text(el) -> str:
    return (el.get_text(separator=" ", strip=True) if el else "").strip()

def _safe_attr(el, attr: str) -> Optional[str]:
    if not el:
        return None
    return el.get(attr) or None

def enrich_company_profile(url: str, headers: Dict[str, str] = None, timeout: int = 20) -> Dict[str, Any]:
    """
    Best-effort enrichment from a public LinkedIn company/about page.
    If network access or parsing fails, returns a minimal dict.
    """
    hdrs = DEFAULT_HEADERS.copy()
    if headers:
        hdrs.update(headers)

    try:
        resp = requests.get(url, headers=hdrs, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html5lib")

        # Attempt to parse summary / website / size
        description = None
        about_section = soup.find("section", id=re.compile("about|organization"))
        if about_section:
            p = about_section.find("p")
            description = _text(p) or None

        website = None
        link = soup.find("a", href=True, attrs={"data-tracking-control-name": re.compile("website|org-about")})
        if link:
            website = link.get("href")

        employees = None
        size_el = soup.find(string=re.compile("(employees|employee count|company size)", re.I))
        if size_el:
            parent = size_el.parent
            if parent:
                m = re.search(r"(\d[\d,\.KkMm+]*)", parent.get_text(" ", strip=True))
                if m:
                    employees = m.group(1)

        logo = None
        logo_el = soup.find("img", attrs={"alt": re.compile("logo", re.I)})
        if logo_el:
            logo = _safe_attr(logo_el, "src") or _safe_attr(logo_el, "data-delayed-url")

        return {
            "companyDescription": description,
            "companyWebsite": website,
            "companyEmployeesCount": employees,
            "companyLogo": logo,
        }
    except Exception as e:
        logging.debug("Company enrichment request failed for %s: %s", url, e)
        return {
            "companyDescription": None,
            "companyWebsite": None,
            "companyEmployeesCount": None,
        }