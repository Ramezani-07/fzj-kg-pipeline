from __future__ import annotations

import pytest

from harvester import Repository, Contributor
from publications import Publication


MOCK_REPOS_RAW = [
    {
        "name": "metastore2",
        "full_name": "Materials-Data-Science-and-Informatics/metastore2",
        "description": "Generic metadata repository service based on schema.org",
        "html_url": "https://github.com/Materials-Data-Science-and-Informatics/metastore2",
        "language": "Java",
        "topics": ["metadata", "fair-data", "schema-org"],
        "stargazers_count": 12,
        "created_at": "2021-03-15T10:00:00Z",
        "updated_at": "2024-11-01T08:30:00Z",
    },
    {
        "name": "PIDA",
        "full_name": "Materials-Data-Science-and-Informatics/PIDA",
        "description": "Persistent Identifier Distribution Architecture",
        "html_url": "https://github.com/Materials-Data-Science-and-Informatics/PIDA",
        "language": "Python",
        "topics": ["pid", "linked-data"],
        "stargazers_count": 8,
        "created_at": "2022-06-01T09:00:00Z",
        "updated_at": "2025-01-10T11:00:00Z",
    },
    {
        "name": "FDO2RDF",
        "full_name": "Materials-Data-Science-and-Informatics/FDO2RDF",
        "description": "Convert FAIR Digital Object metadata to RDF using SSSOM",
        "html_url": "https://github.com/Materials-Data-Science-and-Informatics/FDO2RDF",
        "language": "Python",
        "topics": ["rdf", "fdo", "sssom", "fair"],
        "stargazers_count": 5,
        "created_at": "2023-09-15T14:00:00Z",
        "updated_at": "2026-05-20T16:00:00Z",
    },
]

MOCK_CONTRIBUTOR_RAW = {
    "login": "volkerh",
    "html_url": "https://github.com/volkerh",
    "contributions": 47,
}

MOCK_USER_PROFILE_RAW = {
    "login": "volkerh",
    "name": "Volker Hofmann",
    "email": None,
    "html_url": "https://github.com/volkerh",
    "avatar_url": "https://avatars.githubusercontent.com/u/12345?v=4",
}

MOCK_CONTRIBUTOR_NO_NAME_RAW = {
    "login": "anon-dev",
    "html_url": "https://github.com/anon-dev",
    "contributions": 3,
}

MOCK_USER_PROFILE_NO_NAME_RAW = {
    "login": "anon-dev",
    "name": None,
    "email": None,
    "html_url": "https://github.com/anon-dev",
}

# ORCID mock data

MOCK_ORCID_RESPONSE = {
    "result": [
        {
            "orcid-identifier": {
                "uri": "https://orcid.org/0000-0002-2307-1354",
                "path": "0000-0002-2307-1354",
                "host": "orcid.org",
            }
        }
    ],
    "num-found": 1,
}

MOCK_ORCID_EMPTY_RESPONSE = {
    "result": [],
    "num-found": 0,
}

# DataCite mock data

MOCK_DATACITE_RESPONSE = {
    "data": [
        {
            "id": "https://doi.org/10.5281/zenodo.7661399",
            "attributes": {
                "doi": "10.5281/zenodo.7661399",
                "titles": [{"title": "DataCite Metadata Schema 4.4 to Schema.org Mapping"}],
                "publicationYear": 2022,
                "types": {"resourceTypeGeneral": "Text"},
                "creators": [
                    {
                        "name": "Volker Hofmann",
                        "nameIdentifiers": [
                            {
                                "nameIdentifier": "0000-0002-2307-1354",
                                "nameIdentifierScheme": "ORCID",
                            }
                        ],
                    }
                ],
                "publisher": "Zenodo",
                "url": "https://zenodo.org/record/7661399",
            },
        },
        {
            "id": "https://doi.org/10.5281/zenodo.9999999",
            "attributes": {
                "doi": "10.5281/zenodo.9999999",
                "titles": [{"title": "The Helmholtz Knowledge Graph"}],
                "publicationYear": 2023,
                "types": {"resourceTypeGeneral": "Dataset"},
                "creators": [{"name": "Volker Hofmann", "nameIdentifiers": []}],
                "publisher": {"name": "Zenodo"},  # schema 4.5 publisher object
                "url": "https://zenodo.org/record/9999999",
            },
        },
    ]
}

MOCK_DATACITE_EMPTY_RESPONSE = {"data": []}

# Dataclass fixtures


@pytest.fixture
def sample_repo() -> Repository:
    """A single Repository dataclass instance for testing."""
    return Repository(
        name="metastore2",
        full_name="Materials-Data-Science-and-Informatics/metastore2",
        description="Generic metadata repository service",
        html_url="https://github.com/Materials-Data-Science-and-Informatics/metastore2",
        language="Java",
        topics=["metadata", "fair-data"],
        stargazers_count=12,
        created_at="2021-03-15T10:00:00Z",
        updated_at="2024-11-01T08:30:00Z",
    )


@pytest.fixture
def sample_contributor_with_name() -> Contributor:
    """A Contributor with a resolved display name."""
    return Contributor(
        login="volkerh",
        html_url="https://github.com/volkerh",
        name="Volker Hofmann",
        email=None,
        contributions=47,
    )


@pytest.fixture
def sample_contributor_no_name() -> Contributor:
    """A Contributor whose GitHub profile has no display name set."""
    return Contributor(
        login="anon-dev",
        html_url="https://github.com/anon-dev",
        name=None,
        email=None,
        contributions=3,
    )


@pytest.fixture
def sample_publication() -> Publication:
    """A single Publication dataclass instance for testing."""
    return Publication(
        doi="10.5281/zenodo.7661399",
        title="DataCite Metadata Schema 4.4 to Schema.org Mapping",
        publication_year=2022,
        resource_type="Text",
        publisher="Zenodo",
        url="https://zenodo.org/record/7661399",
    )


@pytest.fixture
def sample_publication_dataset() -> Publication:
    """A Dataset-type Publication for testing type mapping."""
    return Publication(
        doi="10.5281/zenodo.9999999",
        title="The Helmholtz Knowledge Graph",
        publication_year=2023,
        resource_type="Dataset",
        publisher="Zenodo",
        url="https://zenodo.org/record/9999999",
    )
