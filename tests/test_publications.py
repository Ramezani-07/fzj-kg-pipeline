from __future__ import annotations

import responses as responses_lib

from publications import (
    fetch_publications,
    DATACITE_API_BASE,
    RESOURCE_TYPE_MAP,
    DEFAULT_TYPE,
    Publication,
)
from tests.conftest import MOCK_DATACITE_RESPONSE, MOCK_DATACITE_EMPTY_RESPONSE


ORCID_IRI = "https://orcid.org/0000-0002-2307-1354"
DOIS_ENDPOINT = f"{DATACITE_API_BASE}/dois"


@responses_lib.activate
def test_returns_publication_dataclass_list():
    """A successful DataCite response must return a list of Publication dataclasses."""
    responses_lib.add(
        responses_lib.GET, DOIS_ENDPOINT, json=MOCK_DATACITE_RESPONSE, status=200
    )

    pubs = fetch_publications(ORCID_IRI)

    assert isinstance(pubs, list)
    assert len(pubs) == 2
    assert all(isinstance(p, Publication) for p in pubs)
    assert pubs[0].doi == "10.5281/zenodo.7661399"
    assert pubs[0].title == "DataCite Metadata Schema 4.4 to Schema.org Mapping"
    assert pubs[0].publication_year == 2022


@responses_lib.activate
def test_rate_limit_retry():
    """HTTP 429 must trigger a retry; the second response (200) must be used."""
    responses_lib.add(
        responses_lib.GET, DOIS_ENDPOINT, json={}, status=429
    )
    responses_lib.add(
        responses_lib.GET, DOIS_ENDPOINT, json=MOCK_DATACITE_RESPONSE, status=200
    )

    pubs = fetch_publications(ORCID_IRI)

    assert len(responses_lib.calls) == 2
    assert len(pubs) == 2


@responses_lib.activate
def test_empty_response_returns_empty_list():
    """An empty DataCite response must return an empty list, not raise."""
    responses_lib.add(
        responses_lib.GET, DOIS_ENDPOINT, json=MOCK_DATACITE_EMPTY_RESPONSE, status=200
    )

    pubs = fetch_publications(ORCID_IRI)
    assert pubs == []


def test_resource_type_mapping_all_defined_types():
    """Every key in RESOURCE_TYPE_MAP must map to a valid schema.org HTTPS IRI."""
    for datacite_type, schema_type in RESOURCE_TYPE_MAP.items():
        assert schema_type.startswith("https://schema.org/"), (
            f"Type mapping for '{datacite_type}' uses wrong namespace: {schema_type}\n"
            "Must be https://schema.org/ (not http://)"
        )


def test_unknown_resource_type_defaults_to_creative_work():
    """An unmapped DataCite resource type must fall back to schema:CreativeWork."""
    assert DEFAULT_TYPE == "https://schema.org/CreativeWork"
    assert "AnUnknownType" not in RESOURCE_TYPE_MAP
    fallback = RESOURCE_TYPE_MAP.get("AnUnknownType", DEFAULT_TYPE)
    assert fallback == "https://schema.org/CreativeWork"


@responses_lib.activate
def test_publisher_schema_45_object_parsed():
    """Publisher as a schema 4.5 dict {"name": ...} must be parsed correctly."""
    response_with_obj_publisher = {
        "data": [
            {
                "id": "https://doi.org/10.5281/zenodo.9999999",
                "attributes": {
                    "doi": "10.5281/zenodo.9999999",
                    "titles": [{"title": "Test Dataset"}],
                    "publicationYear": 2024,
                    "types": {"resourceTypeGeneral": "Dataset"},
                    "creators": [],
                    "publisher": {"name": "Zenodo"},  # schema 4.5 object form
                    "url": None,
                },
            }
        ]
    }
    responses_lib.add(
        responses_lib.GET, DOIS_ENDPOINT, json=response_with_obj_publisher, status=200
    )

    pubs = fetch_publications(ORCID_IRI)
    assert len(pubs) == 1
    assert pubs[0].publisher == "Zenodo"


@responses_lib.activate
def test_doi_url_construction():
    """Publication DOI must be stored as bare DOI, not full URL."""
    responses_lib.add(
        responses_lib.GET, DOIS_ENDPOINT, json=MOCK_DATACITE_RESPONSE, status=200
    )

    pubs = fetch_publications(ORCID_IRI)
    # The doi field must be the bare DOI (full URL is constructed in graph_builder)
    assert pubs[0].doi == "10.5281/zenodo.7661399"
    assert not pubs[0].doi.startswith("https://")
