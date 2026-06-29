from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, XSD, PROV

from harvester import Repository, Contributor
from publications import Publication, RESOURCE_TYPE_MAP, DEFAULT_TYPE

logger = logging.getLogger(__name__)

_ALL_SCHEMA_TYPES: list[tuple[str, str]] = [
    ("Person",             "https://schema.org/Person"),
    ("SoftwareSourceCode", "https://schema.org/SoftwareSourceCode"),
    ("ScholarlyArticle",   "https://schema.org/ScholarlyArticle"),
    ("Article",            "https://schema.org/Article"),
    ("Dataset",            "https://schema.org/Dataset"),
    ("Book",               "https://schema.org/Book"),
    ("Report",             "https://schema.org/Report"),
    ("MediaObject",        "https://schema.org/MediaObject"),
    ("Collection",         "https://schema.org/Collection"),
    ("CreativeWork",       "https://schema.org/CreativeWork"),
]

SDO = Namespace("https://schema.org/")


def build_graph(
    repos: list[Repository],
    contributors_map: dict[str, list[Contributor]],
    orcid_map: dict[str, Optional[str]],
    publications_map: dict[str, list[Publication]],
) -> Graph:
    """
    Args:
        repos:             List of harvested GitHub Repository objects.
        contributors_map:  Mapping from repo.full_name to list of Contributor.
        orcid_map:         Mapping from contributor.login to ORCID IRI (or None).
        publications_map:  Mapping from ORCID IRI to list of Publication.

    Returns:
        A populated rdflib Graph with schema.org types and PROV-O provenance.
    """
    g = Graph()
    g.bind("schema", SDO)
    g.bind("prov", PROV)
    g.bind("xsd", XSD)

    person_uri_cache: dict[str, URIRef] = {}

    for repo in repos:
        repo_uri = _add_repo(g, repo)
        contributors = contributors_map.get(repo.full_name, [])

        for contributor in contributors:
            person_uri = _get_or_add_person(
                g, contributor, orcid_map, person_uri_cache
            )

            g.add((repo_uri, SDO.author, person_uri))

    pubs_added: set[str] = set()
    for login, orcid_iri in orcid_map.items():
        if orcid_iri is None:
            continue
        for pub in publications_map.get(orcid_iri, []):
            doi_url = f"https://doi.org/{pub.doi}"
            if doi_url in pubs_added:
                pub_uri = URIRef(doi_url)
                person_uri = person_uri_cache.get(login)
                if person_uri:
                    g.add((pub_uri, SDO.author, person_uri))
                continue
            _add_publication(g, pub, orcid_iri, person_uri_cache.get(login))
            pubs_added.add(doi_url)

    type_counts = {
        name: len(list(g.subjects(RDF.type, URIRef(iri))))
        for name, iri in _ALL_SCHEMA_TYPES
    }
    populated = {k: v for k, v in type_counts.items() if v > 0}
    type_summary = " | ".join(f"{k}: {v}" for k, v in populated.items())
    logger.info("Graph built — %d triples | %s", len(g), type_summary)
    return g


def _person_uri_from_orcid(orcid_iri: str) -> URIRef:
    return URIRef(orcid_iri)


def _person_uri_from_name(name: str) -> URIRef:
    md5 = hashlib.md5(name.encode("utf-8")).hexdigest()
    return URIRef(f"urn:hkg:person:{md5}")


def _get_or_add_person(
    g: Graph,
    contributor: Contributor,
    orcid_map: dict[str, Optional[str]],
    cache: dict[str, URIRef],
) -> URIRef:

    if contributor.login in cache:
        return cache[contributor.login]

    orcid_iri: Optional[str] = orcid_map.get(contributor.login)
    display_name = contributor.name or contributor.login

    if orcid_iri:
        person_uri = _person_uri_from_orcid(orcid_iri)
        orcid_path = orcid_iri.replace("https://orcid.org/", "")
        g.add((person_uri, RDF.type, SDO.Person))
        g.add((person_uri, SDO.name, Literal(display_name)))
        g.add((person_uri, SDO.identifier,
               Literal(orcid_iri, datatype=XSD.anyURI)))

        g.add((person_uri, PROV.wasDerivedFrom,
               URIRef(f"https://pub.orcid.org/v3.0/{orcid_path}")))
        logger.debug("Added Person (ORCID): %s → %s", display_name, orcid_iri)
    else:
        # Hash-based local IRI — no provenance triple, source is GitHub only
        person_uri = _person_uri_from_name(display_name)
        g.add((person_uri, RDF.type, SDO.Person))
        g.add((person_uri, SDO.name, Literal(display_name)))
        logger.debug("Added Person (hash): %s", display_name)

    cache[contributor.login] = person_uri
    return person_uri


def _add_repo(g: Graph, repo: Repository) -> URIRef:
    repo_uri = URIRef(repo.html_url)
    g.add((repo_uri, RDF.type, SDO.SoftwareSourceCode))
    g.add((repo_uri, SDO.name, Literal(repo.name)))
    if repo.description:
        g.add((repo_uri, SDO.description, Literal(repo.description)))
    g.add((repo_uri, SDO.codeRepository, URIRef(repo.html_url)))
    if repo.language:
        g.add((repo_uri, SDO.programmingLanguage, Literal(repo.language)))
    for topic in repo.topics:
        g.add((repo_uri, SDO.keywords, Literal(topic)))

    g.add((repo_uri, PROV.wasDerivedFrom,
           URIRef(f"https://api.github.com/repos/{repo.full_name}")))
    logger.debug("Added Repository: %s", repo.full_name)
    return repo_uri


def _add_publication(
    g: Graph,
    pub: Publication,
    orcid_iri: str,
    person_uri: Optional[URIRef],
) -> URIRef:
    doi_url = f"https://doi.org/{pub.doi}"
    pub_uri = URIRef(doi_url)

    schema_type_str = RESOURCE_TYPE_MAP.get(pub.resource_type, DEFAULT_TYPE)
    schema_type = URIRef(schema_type_str)

    g.add((pub_uri, RDF.type, schema_type))
    display_title = f"{pub.title} ({pub.version})" if pub.version else pub.title
    g.add((pub_uri, SDO.name, Literal(display_title)))
    g.add((pub_uri, SDO.identifier, URIRef(doi_url)))

    if pub.publication_year:
        g.add((pub_uri, SDO.datePublished,
               Literal(str(pub.publication_year), datatype=XSD.gYear)))
    if pub.publisher:
        g.add((pub_uri, SDO.publisher, Literal(pub.publisher)))
    if pub.url:
        g.add((pub_uri, SDO.url, URIRef(pub.url)))

    if person_uri:
        g.add((pub_uri, SDO.author, person_uri))

    doi_encoded = pub.doi.replace("/", "%2F")
    g.add((pub_uri, PROV.wasDerivedFrom,
           URIRef(f"https://api.datacite.org/dois/{doi_encoded}")))

    logger.debug("Added Publication: %s (%s)", pub.title[:60], pub.doi)
    return pub_uri


def serialize_graph(g: Graph, output_dir: str) -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    ttl_path = out / "graph.ttl"
    jsonld_path = out / "graph.jsonld"

    g.serialize(str(ttl_path), format="turtle")
    g.serialize(str(jsonld_path), format="json-ld", indent=2)

    logger.info("Graph serialised → %s, %s", ttl_path, jsonld_path)

