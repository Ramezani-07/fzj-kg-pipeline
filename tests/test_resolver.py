from __future__ import annotations

import responses as responses_lib

from resolver import lookup_orcid, get_resolution_stats, ORCID_SEARCH_BASE
import resolver as resolver_module
from tests.conftest import MOCK_ORCID_RESPONSE, MOCK_ORCID_EMPTY_RESPONSE


def _reset_stats():
    """Reset the module-level stats dict between tests."""
    resolver_module._stats.update({"attempted": 0, "resolved": 0, "failed": 0})


@responses_lib.activate
def test_successful_lookup_returns_orcid_iri():
    """A valid name search must return a full https://orcid.org/... IRI."""
    _reset_stats()
    responses_lib.add(
        responses_lib.GET,
        ORCID_SEARCH_BASE,
        json=MOCK_ORCID_RESPONSE,
        status=200,
    )

    result = lookup_orcid("Volker Hofmann")

    assert result is not None
    assert result.startswith("https://orcid.org/")
    assert result == "https://orcid.org/0000-0002-2307-1354"


@responses_lib.activate
def test_empty_result_returns_none():
    """An ORCID search with zero results must return None without raising."""
    _reset_stats()
    responses_lib.add(
        responses_lib.GET,
        ORCID_SEARCH_BASE,
        json=MOCK_ORCID_EMPTY_RESPONSE,
        status=200,
    )

    result = lookup_orcid("Nonexistent Person")

    assert result is None


def test_none_name_returns_none():
    """lookup_orcid(None) must return None immediately without an API call."""
    _reset_stats()
    # No responses mock needed — must not make a network call
    result = lookup_orcid(None)
    assert result is None


def test_single_word_name_returns_none():
    """A single-token name (no space) must return None — cannot split given/family."""
    _reset_stats()
    result = lookup_orcid("mononym")
    assert result is None


@responses_lib.activate
def test_resolution_stats_tracked():
    """After 3 lookups (2 success, 1 fail), stats must reflect the counts."""
    _reset_stats()

    # Two successful
    responses_lib.add(
        responses_lib.GET, ORCID_SEARCH_BASE, json=MOCK_ORCID_RESPONSE, status=200
    )
    responses_lib.add(
        responses_lib.GET, ORCID_SEARCH_BASE, json=MOCK_ORCID_RESPONSE, status=200
    )
    # One empty (fail)
    responses_lib.add(
        responses_lib.GET, ORCID_SEARCH_BASE, json=MOCK_ORCID_EMPTY_RESPONSE, status=200
    )

    lookup_orcid("Volker Hofmann")
    lookup_orcid("Lucas Lamparter")
    lookup_orcid("Unknown Person")

    stats = get_resolution_stats()
    assert stats["attempted"] == 3
    assert stats["resolved"] == 2
    assert stats["failed"] == 1


@responses_lib.activate
def test_http_error_returns_none():
    """An HTTP error from ORCID must return None without raising an exception."""
    _reset_stats()
    responses_lib.add(
        responses_lib.GET,
        ORCID_SEARCH_BASE,
        json={"error": "server error"},
        status=500,
    )

    result = lookup_orcid("Any Person")
    assert result is None


@responses_lib.activate
def test_orcid_iri_format():
    """The returned ORCID IRI must use https:// and have the correct path structure."""
    _reset_stats()
    responses_lib.add(
        responses_lib.GET,
        ORCID_SEARCH_BASE,
        json=MOCK_ORCID_RESPONSE,
        status=200,
    )

    result = lookup_orcid("Volker Hofmann")

    assert result is not None
    # Must be https (not http)
    assert result.startswith("https://")
    # Must have the standard ORCID 4×4 segment format
    orcid_path = result.replace("https://orcid.org/", "")
    segments = orcid_path.split("-")
    assert len(segments) == 4
    assert all(len(s) == 4 for s in segments)
