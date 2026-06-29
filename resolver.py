from __future__ import annotations

import json
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

ORCID_SEARCH_BASE = "https://pub.orcid.org/v3.0/search/"
ORCID_DISPLAY_BASE = "https://orcid.org/"
REQUEST_TIMEOUT = 10  # seconds

_stats: dict[str, int] = {"attempted": 0, "resolved": 0, "failed": 0}


def lookup_orcid(name: Optional[str]) -> Optional[str]:
    if name is None:
        logger.debug("ORCID lookup skipped: name is None")
        _stats["attempted"] += 1
        _stats["failed"] += 1
        return None

    name = name.strip()
    parts = name.split()

    if len(parts) < 2:
        logger.debug(
            "ORCID lookup skipped: '%s' cannot be split into given/family names", name
        )
        _stats["attempted"] += 1
        _stats["failed"] += 1
        return None

    given = " ".join(parts[:-1])
    family = parts[-1]

    _stats["attempted"] += 1
    orcid_iri = _search_orcid(given=given, family=family, full_name=name)

    if orcid_iri:
        _stats["resolved"] += 1
        logger.debug("ORCID resolved: %s → %s", name, orcid_iri)
    else:
        _stats["failed"] += 1
        logger.debug("ORCID not found for: %s", name)

    return orcid_iri


def _search_orcid(given: str, family: str, full_name: str) -> Optional[str]:
    query = f"family-name:{family}+AND+given-names:{given}"
    params = {"q": f"family-name:{family} AND given-names:{given}"}

    try:
        response = requests.get(
            ORCID_SEARCH_BASE,
            params=params,
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.warning("ORCID API timeout for: %s", full_name)
        return None
    except requests.exceptions.RequestException as exc:
        logger.warning("ORCID API error for '%s': %s", full_name, exc)
        return None

    try:
        data = response.json()
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("ORCID response parse error for '%s': %s", full_name, exc)
        return None

    results = data.get("result") or []
    if not results:
        return None

    try:
        orcid_path = results[0]["orcid-identifier"]["path"]
        return f"{ORCID_DISPLAY_BASE}{orcid_path}"
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning(
            "Unexpected ORCID response structure for '%s': %s", full_name, exc
        )
        return None


def resolve_contributors(
    contributors_map: dict[str, list],
) -> dict[str, Optional[str]]:
    seen: set[str] = set()
    orcid_map: dict[str, Optional[str]] = {}

    for contributors in contributors_map.values():
        for contributor in contributors:
            if contributor.login in seen:
                continue
            seen.add(contributor.login)
            orcid_map[contributor.login] = lookup_orcid(contributor.name)

    stats = get_resolution_stats()
    pct = (
        round(stats["resolved"] / stats["attempted"] * 100)
        if stats["attempted"] > 0 else 0
    )
    logger.info(
        "ORCID resolution complete: %d/%d resolved (%d%%)",
        stats["resolved"], stats["attempted"], pct
    )
    return orcid_map


def get_resolution_stats() -> dict:
    return dict(_stats)
