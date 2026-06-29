from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DATACITE_API_BASE = "https://api.datacite.org"
REQUEST_TIMEOUT = 15  # seconds
REQUEST_DELAY = 0.3
PAGE_SIZE = 25
MAX_RETRIES = 1
RETRY_WAIT = 10

RESOURCE_TYPE_MAP: dict[str, str] = {
    "Audiovisual":           "https://schema.org/MediaObject",
    "Book":                  "https://schema.org/Book",
    "Collection":            "https://schema.org/Collection",
    "ComputationalNotebook": "https://schema.org/SoftwareSourceCode",
    "ConferencePaper":       "https://schema.org/Article",
    "DataPaper":             "https://schema.org/Article",
    "Dataset":               "https://schema.org/Dataset",
    "JournalArticle":        "https://schema.org/ScholarlyArticle",
    "Preprint":              "https://schema.org/Article",
    "Report":                "https://schema.org/Report",
    "Software":              "https://schema.org/SoftwareSourceCode",
    "Text":                  "https://schema.org/ScholarlyArticle",
    "Other":                 "https://schema.org/CreativeWork",
}
DEFAULT_TYPE = "https://schema.org/CreativeWork"


@dataclass
class Publication:
    doi: str
    title: str
    publication_year: Optional[int]
    resource_type: str
    publisher: Optional[str]
    url: Optional[str]
    version: Optional[str]


def fetch_publications(orcid_iri: str) -> list[Publication]:
    orcid_id = orcid_iri.replace("https://orcid.org/", "")

    url = f"{DATACITE_API_BASE}/dois"
    params = {
        "query": f"creators.nameIdentifiers.nameIdentifier:{orcid_id}",
        "page[size]": PAGE_SIZE,
    }

    time.sleep(REQUEST_DELAY)

    response = _get_with_retry(url, params)
    if response is None:
        return []

    try:
        data = response.json()
    except ValueError as exc:
        logger.warning("Failed to parse DataCite response for %s: %s", orcid_id, exc)
        return []

    records = data.get("data", [])
    if not records:
        logger.debug("No publications found in DataCite for ORCID: %s", orcid_id)
        return []

    publications: list[Publication] = []
    for record in records:
        pub = _parse_record(record)
        if pub is not None:
            publications.append(pub)

    logger.debug(
        "DataCite: %d publications for ORCID %s", len(publications), orcid_id
    )
    return publications


def _get_with_retry(url: str, params: dict) -> Optional[requests.Response]:
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            logger.warning("DataCite request error: %s", exc)
            return None

        if response.status_code == 200:
            return response
        if response.status_code == 429:
            if attempt < MAX_RETRIES:
                logger.warning(
                    "DataCite rate limit (HTTP 429) — waiting %ds before retry.",
                    RETRY_WAIT
                )
                time.sleep(RETRY_WAIT)
                continue
            else:
                logger.warning("DataCite rate limit persists after retry — skipping.")
                return None
        if response.status_code == 404:
            logger.debug("DataCite HTTP 404 for query — no records found.")
            return response
        logger.warning(
            "DataCite unexpected HTTP %d — skipping.", response.status_code
        )
        return None

    return None


def _parse_record(record: dict) -> Optional[Publication]:
    try:
        attrs = record.get("attributes", {})
        doi = attrs.get("doi")
        if not doi:
            return None

        titles = attrs.get("titles", [])
        title = titles[0].get("title", "Untitled") if titles else "Untitled"

        types = attrs.get("types", {})
        resource_type = types.get("resourceTypeGeneral", "Other")

        return Publication(
            doi=doi,
            title=title,
            publication_year=attrs.get("publicationYear"),
            resource_type=resource_type,
            publisher=_extract_publisher(attrs),
            url=attrs.get("url"),
            version=attrs.get("version"),
        )
    except Exception as exc:
        logger.warning("Failed to parse DataCite record: %s", exc)
        return None


def _extract_publisher(attrs: dict) -> Optional[str]:
    publisher = attrs.get("publisher")
    if publisher is None:
        return None
    if isinstance(publisher, dict):
        return publisher.get("name")
    return str(publisher)


def fetch_all_publications(
    orcid_map: dict[str, Optional[str]],
) -> dict[str, list[Publication]]:
    publications_map: dict[str, list[Publication]] = {}
    resolved_orcids = {v for v in orcid_map.values() if v is not None}

    for orcid_iri in resolved_orcids:
        publications_map[orcid_iri] = fetch_publications(orcid_iri)

    total = sum(len(v) for v in publications_map.values())
    logger.info(
        "DataCite fetch complete: %d publications across %d ORCIDs",
        total, len(resolved_orcids)
    )
    return publications_map
