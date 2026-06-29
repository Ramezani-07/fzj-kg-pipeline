from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path

from harvester import harvest_all, RateLimitError
from resolver import resolve_contributors, get_resolution_stats
from publications import fetch_all_publications
from graph_builder import build_graph, serialize_graph
from visualise import build_visualisation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "FZJ Knowledge Graph Pipeline: GitHub → ORCID → DataCite → RDF → visualisation"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python pipeline.py --max-repos 10\n"
            "  python pipeline.py --max-repos 37 --output-dir ./output\n"
            "  python pipeline.py --max-repos 5 --log-level DEBUG\n"
        ),
    )
    parser.add_argument(
        "--max-repos",
        type=int,
        default=10,
        metavar="N",
        help="Maximum number of GitHub repositories to process (default: 10). "
             "Use 37 for the full IAS-9 organisation.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        metavar="PATH",
        help="Directory for output files: graph.ttl, graph.jsonld, graph.html "
             "(default: ./output).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level (default: INFO).",
    )
    return parser.parse_args()


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> int:
    args = parse_args()
    configure_logging(args.log_level)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("FZJ Knowledge Graph Pipeline")
    logger.info("Target org : github.com/Materials-Data-Science-and-Informatics")
    logger.info("Max repos  : %d", args.max_repos)
    logger.info("Output dir : %s", args.output_dir)
    logger.info("=" * 60)

    # Stage 1

    logger.info("[1/5] Harvesting GitHub repositories and contributors …")
    try:
        repos, contributors_map = harvest_all(max_repos=args.max_repos)
    except RateLimitError as exc:
        logger.error("GitHub rate limit hit — %s", exc)
        logger.error(
            "Verify GITHUB_TOKEN is set and has public_repo scope, "
            "or reduce --max-repos."
        )
        return 1
    except RuntimeError as exc:
        logger.error("Configuration error: %s", exc)
        return 1

    unique_contributors = {
        c.login
        for contributors_list in contributors_map.values()
        for c in contributors_list
    }
    logger.info(
        "  → %d repos, %d unique contributors",
        len(repos), len(unique_contributors)
    )

    # Stage 2

    logger.info("[2/5] Resolving contributor ORCIDs via ORCID Public API …")
    orcid_map = resolve_contributors(contributors_map)
    stats = get_resolution_stats()
    pct = (
        round(stats["resolved"] / stats["attempted"] * 100)
        if stats["attempted"] > 0 else 0
    )
    logger.info(
        "  → %d/%d ORCIDs resolved (%d%%) — unresolved contributors "
        "will use hash-based local IRIs in the graph",
        stats["resolved"], stats["attempted"], pct
    )

    # Stage 3

    logger.info("[3/5] Fetching publications from DataCite …")
    publications_map = fetch_all_publications(orcid_map)
    total_pubs = sum(len(v) for v in publications_map.values())
    logger.info("  → %d publications retrieved", total_pubs)

    # Stage 4

    logger.info("[4/5] Building RDF graph (schema.org + PROV-O) …")
    graph = build_graph(repos, contributors_map, orcid_map, publications_map)
    serialize_graph(graph, args.output_dir)

    # Stage 5

    logger.info("[5/5] Generating interactive visualisation (pyvis) …")
    html_path = build_visualisation(graph, args.output_dir)

    # Summary

    output_dir = Path(args.output_dir)
    logger.info("")
    logger.info("=" * 60)
    logger.info("Pipeline complete.")
    logger.info("  Repos harvested:        %d", len(repos))
    logger.info("  Unique contributors:    %d", len(unique_contributors))
    logger.info(
        "  ORCIDs resolved:        %d / %d (%d%%)",
        stats["resolved"], stats["attempted"], pct
    )
    logger.info("  Publications retrieved: %d", total_pubs)
    logger.info("  Total RDF triples:      %d", len(graph))
    logger.info("  Output written to:      %s", output_dir.resolve())
    logger.info("    graph.ttl     — Turtle RDF serialisation")
    logger.info("    graph.jsonld  — JSON-LD RDF serialisation")
    logger.info("    graph.html    — Interactive pyvis visualisation")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
