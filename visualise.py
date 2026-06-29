from __future__ import annotations

import logging
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, PROV
from pyvis.network import Network

logger = logging.getLogger(__name__)

NODE_STYLES: dict[str, dict] = {
    "https://schema.org/Person": {
        "color": "#4e79a7", "shape": "dot", "size": 16,
    },
    "https://schema.org/SoftwareSourceCode": {
        "color": "#59a14f", "shape": "box", "size": 20,
    },
    "https://schema.org/ScholarlyArticle": {
        "color": "#f28e2b", "shape": "diamond", "size": 15,
    },
    "https://schema.org/Article": {
        "color": "#edc948", "shape": "triangle", "size": 15,
    },
    "https://schema.org/Dataset": {
        "color": "#e15759", "shape": "square", "size": 15,
    },
    "https://schema.org/Book": {
        "color": "#ff69b4", "shape": "star", "size": 16,
    },
    "https://schema.org/Report": {
        "color": "#76b7b2", "shape": "ellipse", "size": 15,
    },
    "https://schema.org/MediaObject": {
        "color": "#b07aa1", "shape": "triangleDown", "size": 15,
    },
    "https://schema.org/Collection": {
        "color": "#9c755f", "shape": "database", "size": 18,
    },
    "https://schema.org/CreativeWork": {
        "color": "#bab0ac", "shape": "hexagon", "size": 13,
    },
}
DEFAULT_STYLE: dict = {"color": "#cccccc", "shape": "ellipse", "size": 10}

SDO_NAME = URIRef("https://schema.org/name")
PROV_DERIVED_FROM = PROV.wasDerivedFrom
LABEL_MAX_LEN = 40


def build_visualisation(g: Graph, output_dir: str) -> str:
    if len(g) == 0:
        logger.warning("Graph is empty — writing a placeholder HTML file.")

    net = Network(
        height="800px",
        width="100%",
        bgcolor="#ffffff",
        font_color="#333333",
        directed=True,
    )
    net.barnes_hut(
        gravity=-8000,
        central_gravity=0.3,
        spring_length=120,
        spring_strength=0.05,
        damping=0.09,
    )

    added_nodes: set[str] = set()
    added_edges: set[tuple] = set()

    # Step 1: Add nodes

    for subject, _, rdf_type in g.triples((None, RDF.type, None)):
        node_id = str(subject)
        if node_id in added_nodes:
            continue

        label = _get_label(g, subject)
        tooltip = _build_tooltip(g, subject, rdf_type)
        style = NODE_STYLES.get(str(rdf_type), DEFAULT_STYLE)

        net.add_node(
            node_id,
            label=label,
            title=tooltip,
            color=style["color"],
            shape=style["shape"],
            size=style["size"],
        )
        added_nodes.add(node_id)

    # Step 2: Add edges

    for subject, predicate, obj in g:
        if predicate == PROV_DERIVED_FROM:
            continue
        # Skip type triples (handled in node creation)
        if predicate == RDF.type:
            continue
        src = str(subject)
        dst = str(obj)
        # Skip self-loops
        if src == dst:
            continue
        # Only draw edges between typed nodes in the graph
        if src not in added_nodes or dst not in added_nodes:
            continue

        edge_label = _predicate_label(predicate)
        edge_key = (src, dst, edge_label)
        if edge_key in added_edges:
            continue

        net.add_edge(src, dst, label=edge_label, title=edge_label)
        added_edges.add(edge_key)

    # Step 3

    out_path = Path(output_dir) / "graph.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    net.write_html(str(out_path))

    logger.info(
        "Visualisation saved → %s (%d nodes, %d edges)",
        out_path, len(added_nodes), len(added_edges)
    )
    return str(out_path)


def _get_label(g: Graph, subject: URIRef) -> str:
    name = g.value(subject, SDO_NAME)
    if name:
        text = str(name)
        return text[:LABEL_MAX_LEN] + "…" if len(text) > LABEL_MAX_LEN else text

    uri_str = str(subject)
    return uri_str.rstrip("/").split("/")[-1][:LABEL_MAX_LEN]


def _build_tooltip(g: Graph, subject: URIRef, rdf_type: URIRef) -> str:
    type_label = str(rdf_type).replace("https://schema.org/", "schema:")
    return f"{type_label}\n{str(subject)}"


def _predicate_label(predicate: URIRef) -> str:
    pred_str = str(predicate)
    for sep in ("#", "/"):
        if sep in pred_str:
            return pred_str.split(sep)[-1]
    return pred_str
