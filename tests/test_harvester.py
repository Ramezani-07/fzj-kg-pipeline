from __future__ import annotations

import pytest
import responses as responses_lib

from harvester import (
    fetch_repos,
    fetch_contributors,
    RateLimitError,
    GITHUB_API_BASE,
    GITHUB_ORG,
)
from tests.conftest import MOCK_REPOS_RAW


def _set_token(monkeypatch):
    """Inject a dummy GitHub token into the environment."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test_token_123")


@responses_lib.activate
def test_auth_header_present(monkeypatch):
    """Authorization header must be sent on every API request."""
    _set_token(monkeypatch)

    responses_lib.add(
        responses_lib.GET,
        f"{GITHUB_API_BASE}/orgs/{GITHUB_ORG}/repos",
        json=MOCK_REPOS_RAW[:1],
        status=200,
    )
    # Also mock the contributors and user profile calls triggered by harvest_all
    responses_lib.add(
        responses_lib.GET,
        f"{GITHUB_API_BASE}/repos/{MOCK_REPOS_RAW[0]['full_name']}/contributors",
        json=[],
        status=200,
    )
    # Second page returns empty (stops pagination)
    responses_lib.add(
        responses_lib.GET,
        f"{GITHUB_API_BASE}/orgs/{GITHUB_ORG}/repos",
        json=[],
        status=200,
    )

    repos = fetch_repos(max_repos=1)

    assert len(repos) >= 1
    # Verify the Authorization header was set on the first call
    first_call = responses_lib.calls[0]
    assert "Authorization" in first_call.request.headers
    assert first_call.request.headers["Authorization"].startswith("token ")


@responses_lib.activate
def test_pagination(monkeypatch):
    """Fetch repos across two pages; stop when empty page is returned."""
    _set_token(monkeypatch)

    # Page 1: two repos
    responses_lib.add(
        responses_lib.GET,
        f"{GITHUB_API_BASE}/orgs/{GITHUB_ORG}/repos",
        json=MOCK_REPOS_RAW[:2],
        status=200,
    )
    # Page 2: empty — signals end of results
    responses_lib.add(
        responses_lib.GET,
        f"{GITHUB_API_BASE}/orgs/{GITHUB_ORG}/repos",
        json=[],
        status=200,
    )

    repos = fetch_repos(max_repos=10)
    assert len(repos) == 2
    assert repos[0].name == "metastore2"
    assert repos[1].name == "PIDA"


@responses_lib.activate
def test_rate_limit_raises(monkeypatch):
    """HTTP 403 from GitHub must raise RateLimitError, not silently continue."""
    _set_token(monkeypatch)

    responses_lib.add(
        responses_lib.GET,
        f"{GITHUB_API_BASE}/orgs/{GITHUB_ORG}/repos",
        json={"message": "API rate limit exceeded"},
        status=403,
    )

    with pytest.raises(RateLimitError):
        fetch_repos(max_repos=5)


@responses_lib.activate
def test_contributor_none_name_handled(monkeypatch, sample_repo):
    """A contributor with name=None must not raise an exception."""
    _set_token(monkeypatch)

    contrib_raw = {
        "login": "anon-dev",
        "html_url": "https://github.com/anon-dev",
        "contributions": 2,
    }
    user_profile_raw = {
        "login": "anon-dev",
        "name": None,
        "email": None,
        "html_url": "https://github.com/anon-dev",
    }

    responses_lib.add(
        responses_lib.GET,
        f"{GITHUB_API_BASE}/repos/{sample_repo.full_name}/contributors",
        json=[contrib_raw],
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        f"{GITHUB_API_BASE}/users/anon-dev",
        json=user_profile_raw,
        status=200,
    )

    # Must not raise
    contributors = fetch_contributors(sample_repo)
    assert len(contributors) == 1
    assert contributors[0].name is None
    assert contributors[0].login == "anon-dev"


@responses_lib.activate
def test_repo_with_no_contributors(monkeypatch, sample_repo):
    """HTTP 404 on the contributors endpoint must return empty list, not crash."""
    _set_token(monkeypatch)

    responses_lib.add(
        responses_lib.GET,
        f"{GITHUB_API_BASE}/repos/{sample_repo.full_name}/contributors",
        json={"message": "Not Found"},
        status=404,
    )

    contributors = fetch_contributors(sample_repo)
    assert contributors == []


@responses_lib.activate
def test_repo_dataclass_fields(monkeypatch):
    """Harvested repo must have all expected dataclass fields populated."""
    _set_token(monkeypatch)

    responses_lib.add(
        responses_lib.GET,
        f"{GITHUB_API_BASE}/orgs/{GITHUB_ORG}/repos",
        json=MOCK_REPOS_RAW[:1],
        status=200,
    )
    responses_lib.add(
        responses_lib.GET,
        f"{GITHUB_API_BASE}/orgs/{GITHUB_ORG}/repos",
        json=[],
        status=200,
    )

    repos = fetch_repos(max_repos=1)
    repo = repos[0]

    assert repo.name == "metastore2"
    assert "Materials-Data-Science-and-Informatics" in repo.full_name
    assert repo.html_url.startswith("https://github.com/")
    assert isinstance(repo.topics, list)
    assert repo.language == "Java"
