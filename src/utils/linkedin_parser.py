import logging
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

@dataclass
class JobRecord:
    id: Optional[str]
    link: Optional[str]
    title: Optional[str]
    companyName: Optional[str]
    companyLinkedinUrl: Optional[str]
    companyLogo: Optional[str]
    location: Optional[str]
    salaryInfo: Optional[List[str]]
    postedAt: Optional[str]
    benefits: Optional[List[str]]
    applicantsCount: Optional[str]
    jobPosterName: Optional[str]
    jobPosterTitle: Optional[str]
    jobPosterPhoto: Optional[str]
    jobPosterProfileUrl: Optional[str]
    seniorityLevel: Optional[str]
    employmentType: Optional[str]
    jobFunction: Optional[str]
    industries: Optional[List[str]]
    companyDescription: Optional[str]
    companyWebsite: Optional[str]
    companyEmployeesCount: Optional[str]

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch_page(url: str, headers: Dict[str, str] = None, timeout: int = 20) -> str:
    hdrs = DEFAULT_HEADERS.copy()
    if headers:
        hdrs.update(headers)
    logging.debug("Fetching URL: %s", url)
    resp = requests.get(url, headers=hdrs, timeout=timeout)
    resp.raise_for_status()
    logging.debug("Fetched %d bytes from %s", len(resp.text), url)
    return resp.text

def _text(el) -> str:
    return (el.get_text(separator=" ", strip=True) if el else "").strip()

def _safe_attr(el, attr: str) -> Optional[str]:
    if not el:
        return None
    return el.get(attr) or None

def extract_jobs_from_html(html: str, base_url: str = "") -> List[Dict[str, Any]]:
    """
    Parse public LinkedIn Jobs search HTML.
    The HTML structure may vary by locale. We try to be defensive and find cards by common patterns.
    """
    soup = BeautifulSoup(html, "html5lib")

    # LinkedIn often uses <ul class="jobs-search__results-list"> with <li> cards
    results_container = soup.find("ul", class_=re.compile(r"(jobs-search__results-list|jobs-search-results)"))
    if not results_container:
        # Try alternative containers
        results_container = soup.find("div", attrs={"data-search-id": True}) or soup

    cards = results_container.find_all(["li", "div"], class_=re.compile(r"(base-card|jobs-search-results__list-item|job-card)"))
    logging.info("Found %d job card candidates", len(cards))

    records: List[Dict[str, Any]] = []
    for card in cards:
        # Link to detail
        link_el = card.find("a", href=True, class_=re.compile(r"(base-card__full-link|job-card-list__title)"))
        link = _safe_attr(link_el, "href")
        if link:
            link = urljoin(base_url, link.split("?")[0])

        # ID guess from link
        job_id = None
        if link:
            m = re.search(r"jobs/view/(\d+)", link)
            if m:
                job_id = m.group(1)

        title_el = card.find(["h3", "a"], class_=re.compile(r"(base-search-card__title|job-card-list__title)"))
        title = _text(title_el)

        company_el = card.find(["h4", "a", "span"], class_=re.compile(r"(base-search-card__subtitle|job-card-container__company-name)"))
        company_name = _text(company_el)
        company_link_el = company_el if company_el and company_el.name == "a" else card.find("a", href=True, class_=re.compile("company-name"))
        company_link = _safe_attr(company_link_el, "href")
        if company_link:
            company_link = urljoin(base_url, company_link.split("?")[0])

        logo_el = card.find("img", class_=re.compile(r"(artdeco-entity-image|base-search-card__logo)"))
        logo = _safe_attr(logo_el, "src") or _safe_attr(logo_el, "data-delayed-url")

        location_el = card.find("span", class_=re.compile(r"(job-search-card__location|job-card-container__metadata-item)"))
        location = _text(location_el)

        # Salary & benefits (best-effort)
        salary = []
        salary_el = card.find("div", class_=re.compile("salary"))
        if salary_el:
            raw = _text(salary_el)
            salary = re.findall(r"[\$€£]\s?\d[\d,\.]*", raw)

        benefits = []
        benefit_badges = card.find_all("span", class_=re.compile("(actively-hiring|benefit-badge|insight)"))
        for b in benefit_badges:
            val = _text(b)
            if val and val not in benefits:
                benefits.append(val)

        # Posted at
        posted_el = card.find("time")
        posted_at = posted_el.get("datetime") if posted_el and posted_el.get("datetime") else _text(posted_el)

        record = JobRecord(
            id=job_id,
            link=link,
            title=title or None,
            companyName=company_name or None,
            companyLinkedinUrl=company_link,
            companyLogo=logo,
            location=location or None,
            salaryInfo=salary or None,
            postedAt=posted_at or None,
            benefits=benefits or None,
            applicantsCount=None,
            jobPosterName=None,
            jobPosterTitle=None,
            jobPosterPhoto=None,
            jobPosterProfileUrl=None,
            seniorityLevel=None,
            employmentType=None,
            jobFunction=None,
            industries=None,
            companyDescription=None,
            companyWebsite=None,
            companyEmployeesCount=None,
        )

        # Try to glean applicants/employment type in metadata spans
        meta_spans = card.find_all("span", class_=re.compile("(metadata|job-posting)"))
        for s in meta_spans:
            txt = _text(s).lower()
            if "applicant" in txt:
                m = re.search(r"(\d[\d,]*)\+?", txt)
                if m:
                    record.applicantsCount = m.group(1)
            if "full-time" in txt or "contract" in txt or "part-time" in txt or "intern" in txt:
                record.employmentType = s.get_text(strip=True)

        records.append({k: getattr(record, k) for k in record.__dataclass_fields__.keys()})

    return records