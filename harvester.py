from __future__ import annotations
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GITHUB_ORG = "Materials-Data-Science-and-Informatics"
GITHUB_API_BASE = "https://api.github.com"
PROFILE_LOOKUP_DELAY = 0.3


class RateLimitError(Exception):
    pass


@dataclass
class Repository:
    name: str
    full_name: str
    description: Optional[str]
    html_url: str
    language: Optional[str]
    topics: list[str] = field(default_factory=list)
    stargazers_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class Contributor:
    login: str
    html_url: str
    name: Optional[str]
    email: Optional[str]
    contributions: int = 0


def _get_token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN not set. Create a .env file from env.example"
        )
    return token


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get(url: str, token: str, params: Optional[dict] = None) -> requests.Response:
    response = requests.get(url, headers=_headers(token), params=params, timeout=15)
    if response.status_code == 403:
        logger.warning(
            "GitHub rate limit hit. URL: %s — reduce --max-repos.", url
        )
        raise RateLimitError(f"GitHub rate limit exceeded: {url}")
    return response


def fetch_repos(max_repos: int = 10) -> list[Repository]:
    token = _get_token()
    repos: list[Repository] = []
    page = 1

    while len(repos) < max_repos:
        url = f"{GITHUB_API_BASE}/orgs/{GITHUB_ORG}/repos"
        response = _get(url, token, params={"per_page": 100, "page": page})

        if response.status_code != 200:
            logger.warning(
                "Unexpected status %d fetching repos page %d — stopping.",
                response.status_code, page
            )
            break

        page_data = response.json()
        if not page_data:
            break

        for item in page_data:
            if len(repos) >= max_repos:
                break
            repos.append(Repository(
                name=item["name"],
                full_name=item["full_name"],
                description=item.get("description"),
                html_url=item["html_url"],
                language=item.get("language"),
                topics=item.get("topics", []),
                stargazers_count=item.get("stargazers_count", 0),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
            ))

        logger.debug("Fetched %d repos so far (page %d)", len(repos), page)
        page += 1

    logger.info("Harvested %d repositories from %s", len(repos), GITHUB_ORG)
    return repos


def fetch_contributors(repo: Repository) -> list[Contributor]:
    token = _get_token()
    url = f"{GITHUB_API_BASE}/repos/{repo.full_name}/contributors"
    response = _get(url, token, params={"per_page": 100})

    if response.status_code == 404:
        logger.debug(
            "HTTP 404 on contributors for %s — likely empty.",
            repo.full_name
        )
        return []

    if response.status_code != 200:
        logger.warning(
            "HTTP %d fetching contributors for %s — skipping.",
            response.status_code, repo.full_name
        )
        return []

    raw_contributors = response.json()
    contributors: list[Contributor] = []

    for raw in raw_contributors:
        login = raw["login"]
        profile = _fetch_user_profile(login, token)
        contributors.append(Contributor(
            login=login,
            html_url=raw["html_url"],
            name=profile.get("name"),       # None is handled downstream
            email=profile.get("email"),
            contributions=raw.get("contributions", 0),
        ))
        time.sleep(PROFILE_LOOKUP_DELAY)

    logger.debug(
        "Fetched %d contributors for %s", len(contributors), repo.full_name
    )
    return contributors


def _fetch_user_profile(login: str, token: str) -> dict:
    url = f"{GITHUB_API_BASE}/users/{login}"
    try:
        response = _get(url, token)
        if response.status_code == 200:
            return response.json()
        logger.debug(
            "HTTP %d fetching profile for %s", response.status_code, login
        )
    except RateLimitError:
        raise
    except Exception as exc:
        logger.warning("Error fetching profile for %s: %s", login, exc)
    return {}


def harvest_all(max_repos: int = 10) -> tuple[list[Repository], dict[str, list[Contributor]]]:
    repos = fetch_repos(max_repos)
    contributors_map: dict[str, list[Contributor]] = {}

    for repo in repos:
        contributors_map[repo.full_name] = fetch_contributors(repo)

    total_contributors = sum(len(v) for v in contributors_map.values())
    logger.info(
        "Harvesting complete, %d total contributor records", total_contributors
    )
    return repos, contributors_map
