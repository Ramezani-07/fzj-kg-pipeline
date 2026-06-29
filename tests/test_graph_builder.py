from __future__ import annotations

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, PROV

from graph_builder import (
    build_graph,
    SDO,
)
from harvester import Repository, Contributor
from publications import Publication


def _minimal_graph(
    with_orcid: bool = True,
    include_publication: bool = True,
) -> Graph:
    """Build a minimal but complete graph for testing."""
    repo = Repository(
        name="test-repo",
        full_name="Materials-Data-Science-and-Informatics/test-repo",
        description="A test repository",
        html_url="https://github.com/Materials-Data-Science-and-Informatics/test-repo",
        language="Python",
        topics=["test"],
    )
    contributor = Contributor(
        login="volkerh",
        html_url="https://github.com/volkerh",
        name="Volker Hofmann",
        email=None,
        contributions=10,
    )
    orcid_iri = "https://orcid.org/0000-0002-2307-1354" if with_orcid else None
    orcid_map = {"volkerh": orcid_iri}
    contributors_map = {repo.full_name: [contributor]}

    pubs = []
    if include_publication and with_orcid:
        pubs = [
            Publication(
                doi="10.5281/zenodo.7661399",
                title="DataCite Metadata Schema 4.4 to Schema.org Mapping",
                publication_year=2022,
                resource_type="Text",
                publisher="Zenodo",
                url="https://zenodo.org/record/7661399",
            )
        ]
    publications_map = {orcid_iri: pubs} if (with_orcid and include_publication) else {}

    return build_graph(
        repos=[repo],
        contributors_map=contributors_map,
        orcid_map=orcid_map,
        publications_map=publications_map,
    )


def test_schema_namespace_is_https():
    g = _minimal_graph()
    for s, p, o in g:
        for term in (str(s), str(p), str(o)):
            assert "http://schema.org/" not in term, (
                f"Found deprecated http://schema.org/ in graph term: {term}\n"
                "All schema.org terms must use https://schema.org/"
            )


def test_person_with_orcid_uses_orcid_iri():
    """A person with an ORCID must use the ORCID IRI as their RDF subject."""
    g = _minimal_graph(with_orcid=True)
    orcid_uri = URIRef("https://orcid.org/0000-0002-2307-1354")

    person_types = list(g.subjects(RDF.type, SDO.Person))
    assert orcid_uri in person_types, (
        f"Expected ORCID IRI as Person subject. Found: {person_types}"
    )


def test_person_without_orcid_uses_hash_iri():
    """A person without an ORCID must use a urn:hkg:person:... hash-based IRI."""
    g = _minimal_graph(with_orcid=False)

    person_uris = list(g.subjects(RDF.type, SDO.Person))
    assert len(person_uris) >= 1

    for person_uri in person_uris:
        uri_str = str(person_uri)
        assert uri_str.startswith("urn:hkg:person:"), (
            f"Expected hash-based local IRI for person without ORCID. Got: {uri_str}"
        )
        # Must NOT be an ORCID IRI
        assert "orcid.org" not in uri_str


def test_prov_wasDerivedFrom_present_on_repos():
    """Every SoftwareSourceCode node must have a prov:wasDerivedFrom triple."""
    g = _minimal_graph()
    repos = list(g.subjects(RDF.type, SDO.SoftwareSourceCode))
    assert len(repos) > 0, "No repository nodes in graph"

    for repo_uri in repos:
        prov_objects = list(g.objects(repo_uri, PROV.wasDerivedFrom))
        assert len(prov_objects) > 0, (
            f"Repository node {repo_uri} missing prov:wasDerivedFrom triple.\n"
            "All repository nodes must have provenance linking to the GitHub API."
        )
        # The provenance target must be a GitHub API URL
        assert any(
            "api.github.com" in str(prov_obj) for prov_obj in prov_objects
        )


def test_prov_wasDerivedFrom_present_on_publications():
    """Every publication node must have a prov:wasDerivedFrom triple."""
    g = _minimal_graph(with_orcid=True, include_publication=True)

    pub_types = [SDO.ScholarlyArticle, SDO.Dataset, SDO.CreativeWork]
    pub_uris = []
    for t in pub_types:
        pub_uris.extend(g.subjects(RDF.type, t))

    assert len(pub_uris) > 0, "No publication nodes in graph"

    for pub_uri in pub_uris:
        prov_objects = list(g.objects(pub_uri, PROV.wasDerivedFrom))
        assert len(prov_objects) > 0, (
            f"Publication node {pub_uri} missing prov:wasDerivedFrom triple.\n"
            "All publication nodes must have provenance linking to DataCite API."
        )
        assert any(
            "api.datacite.org" in str(prov_obj) for prov_obj in prov_objects
        )


def test_prov_wasDerivedFrom_present_on_orcid_persons():
    """ORCID-resolved persons must have a prov:wasDerivedFrom triple to pub.orcid.org."""
    g = _minimal_graph(with_orcid=True)
    orcid_uri = URIRef("https://orcid.org/0000-0002-2307-1354")

    prov_objects = list(g.objects(orcid_uri, PROV.wasDerivedFrom))
    assert len(prov_objects) > 0, (
        f"ORCID person node {orcid_uri} missing prov:wasDerivedFrom triple."
    )
    assert any("orcid.org" in str(p) for p in prov_objects)


def test_graph_serialises_to_valid_turtle(tmp_path):
    """The graph must serialise to valid Turtle and produce a non-empty file."""
    g = _minimal_graph()
    out_file = str(tmp_path / "test_graph.ttl")
    g.serialize(out_file, format="turtle")

    content = open(out_file).read()
    assert len(content) > 0
    # Valid Turtle must contain the schema namespace binding
    assert "schema" in content
    assert "prov" in content


def test_doi_url_used_as_publication_subject():
    """Publication node IRI must be the full DOI URL (https://doi.org/...)."""
    g = _minimal_graph(with_orcid=True, include_publication=True)
    doi_uri = URIRef("https://doi.org/10.5281/zenodo.7661399")

    # The DOI URI must appear as a subject in the graph
    triples = list(g.triples((doi_uri, None, None)))
    assert len(triples) > 0, f"DOI URI {doi_uri} not found as a subject in graph"


def test_repo_html_url_used_as_subject():
    """Repository node IRI must be the GitHub HTML URL."""
    g = _minimal_graph()
    repo_uri = URIRef(
        "https://github.com/Materials-Data-Science-and-Informatics/test-repo"
    )
    triples = list(g.triples((repo_uri, None, None)))
    assert len(triples) > 0, "GitHub HTML URL not found as repo subject"


def test_schema_name_on_all_nodes():
    """Every entity node must have a schema:name triple."""
    g = _minimal_graph(with_orcid=True, include_publication=True)

    entity_types = [SDO.Person, SDO.SoftwareSourceCode, SDO.ScholarlyArticle]
    for entity_type in entity_types:
        for subject in g.subjects(RDF.type, entity_type):
            names = list(g.objects(subject, SDO.name))
            assert len(names) > 0, (
                f"Node {subject} (type {entity_type}) missing schema:name triple"
            )
