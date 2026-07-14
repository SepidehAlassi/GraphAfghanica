#!/usr/bin/env python3
"""Convert GraphAfghanica CSV metadata to Turtle with RDFLib.

Mapping rules:
- one image resource per distinct :collectionID
- description columns become :description literals with language tags
- width and height values such as "175 mm" become xsd:int literals such as 175
- repeated rows are merged; repeated references/classifications are preserved once

Example:
    python csv_to_graphafghanica.py data.csv output.ttl \
        --ontology ontology_star_noannotation.ttl
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
GA = Namespace("http://www.graphAfghanica.org/data/")
GAO = Namespace("http://www.graphAfghanica.org/ontology/")

# Accept both the actual CSV headers and the colon-prefixed variants.
DESCRIPTION_COLUMNS = {
    "pl": (":description (pl)",),
    "de": (":description (de)",),
    "en": (":description (en)",)
}


def clean(value: object) -> str:
    """Return a stripped string; treat empty/NaN-like values as empty."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def local_name(value: str) -> str:
    """Turn a CURIE-like value or URI into a safe GraphAfghanica local name."""
    value = clean(value)
    if value.startswith(":"):
        value = value[1:]
    elif value.startswith("http://") or value.startswith("https://"):
        value = value.rstrip("/").rsplit("/", 1)[-1]

    value = re.sub(r"[^A-Za-z0-9._~-]+", "_", value).strip("_")
    if not value:
        raise ValueError("Cannot create a URI from an empty identifier")
    return value


def ga_uri(value: str) -> URIRef:
    return GA[local_name(value)]


def first_nonempty(rows: Iterable[Mapping[str, str]], *columns: str) -> str:
    """Return the first nonempty value found in any of the supplied columns."""
    for row in rows:
        for column in columns:
            value = clean(row.get(column, ""))
            if value:
                return value
    return ""


def unique_nonempty(rows: Iterable[Mapping[str, str]], column: str) -> list[str]:
    """Return distinct nonempty values in first-seen order."""
    result: list[str] = []
    seen: set[str] = set()
    for row in rows:
        value = clean(row.get(column, ""))
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def parse_integer_dimension(value: str) -> int | None:
    """Extract an integer from values such as '175 mm', '175mm', or '175'."""
    text = clean(value)
    if not text:
        return None

    match = re.fullmatch(r"([+-]?\d+)\s*(?:mm)?", text, flags=re.IGNORECASE)
    if not match:
        raise ValueError(
            f"Dimension value {value!r} is not an integer optionally followed by 'mm'"
        )
    return int(match.group(1))


def parse_url(value: str) -> str:
    """Extract the URL from plain, IRI, or typed-literal CSV representations."""
    text = clean(value)
    if not text:
        return ""

    typed = re.fullmatch(r'"(.*)"\^\^xsd:anyURI', text)
    if typed:
        return typed.group(1)
    if text.startswith("<") and text.endswith(">"):
        return text[1:-1]
    return text.strip('"')


def group_rows(csv_path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")
        if ":collectionID" not in reader.fieldnames:
            raise ValueError("Required column ':collectionID' is missing")

        for row_number, row in enumerate(reader, start=2):
            collection_id = clean(row.get(":collectionID", ""))
            if not collection_id:
                print(
                    f"Warning: skipping row {row_number} without :collectionID",
                    file=sys.stderr,
                )
                continue
            grouped[collection_id].append(row)

    return grouped


def add_image(graph: Graph, collection_id: str, rows: list[Mapping[str, str]]) -> None:
    image = ga_uri(collection_id)
    graph.add((image, RDF.type, GAO.Image))

    title = first_nonempty(rows, "Name", ":title")
    if title:
        graph.add((image, GAO.title, Literal(title)))

    legend = first_nonempty(rows, ":legend", "legend")
    if legend:
        graph.add((image, GAO.legend, Literal(legend)))

    width = parse_integer_dimension(first_nonempty(rows, ":format_width"))
    if width is not None:
        graph.add((image, GAO.format_width, Literal(width, datatype=XSD.int)))

    height = parse_integer_dimension(first_nonempty(rows, ":format_height"))
    if height is not None:
        graph.add((image, GAO.format_height, Literal(height, datatype=XSD.int)))

    quality = first_nonempty(rows, ":quality")
    if quality:
        # The source values are German in the supplied CSV.
        graph.add((image, GAO.quality, Literal(quality, lang="de")))

    for language, columns in DESCRIPTION_COLUMNS.items():
        description = first_nonempty(rows, *columns)
        if description:
            graph.add((image, GAO.description, Literal(description, lang=language)))

    for reference in unique_nonempty(rows, ":references"):
        graph.add((image, GAO.references, Literal(reference)))

    for classification in unique_nonempty(rows, ":classification"):
        concept = ga_uri(classification)
        graph.add((image, GAO.classification, concept))
        graph.add((concept, RDF.type, Namespace("http://www.w3.org/2004/02/skos/core#").Concept))

    collection = first_nonempty(rows, ":belongsTo")
    if collection:
        collection_uri = ga_uri(collection)
        graph.add((image, GAO.belongsTo, collection_uri))
        graph.add((collection_uri, RDF.type, CRM.E78_Curated_Holding))

    production = first_nonempty(rows, "crm:P108i_was_produced_by")
    if production:
        production_uri = ga_uri(production)
        graph.add((image, CRM.P108i_was_produced_by, production_uri))
        graph.add((production_uri, RDF.type, CRM.E12_Production))

    url = parse_url(first_nonempty(rows, ":hasDigitalRepresentation"))
    if url:
        graph.add(
            (
                image,
                GAO.hasDigitalRepresentation,
                Literal(url, datatype=XSD.anyURI),
            )
        )


def build_graph(csv_path: Path, ontology_path: Path | None = None) -> Graph:
    graph = Graph()
    graph.bind("crm", CRM)
    graph.bind("ga", GA)
    graph.bind("", GAO)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)
    graph.bind("xsd", XSD)
    graph.bind("skos", Namespace("http://www.w3.org/2004/02/skos/core#"))

    # Optionally include the ontology triples in the resulting graph.
    if ontology_path is not None:
        graph.parse(ontology_path, format="turtle")

    for collection_id, rows in group_rows(csv_path).items():
        add_image(graph, collection_id, rows)

    return graph

def add_rdfstar_annotations(csv_path: Path):
    star_triples = ""
    for collection_id, rows in group_rows(csv_path).items():
        image = collection_id
        for language, columns in DESCRIPTION_COLUMNS.items():
            description = first_nonempty(rows, *columns).replace('"', r'\"')

            if description:
                star_triples += ('<< ga' + image + ' :description "' + description + '"@' +language+ ' >> \n' +
                                 "\t :creator ga:MarekGawecki ; \n" +
                                 '\t :confidence "1.0"^^xsd:decimal .\n\n')
        for classification in unique_nonempty(rows, ":classification"):

            star_triples += ("<< ga" + image + " :classification ga" + classification + " >>\n" +
                             "\t :model ga:Pytorch_classifier_v2 ; \n" +
                             '\t :confidence "0.89"^^xsd:decimal .\n\n')
    return star_triples

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert GraphAfghanica CSV metadata to Turtle."
    )
    parser.add_argument("input_csv", type=Path, help="Input CSV file")
    parser.add_argument("output_turtle", type=Path, help="Output Turtle file")
    parser.add_argument(
        "--ontology",
        type=Path,
        default=None,
        help="Optional ontology Turtle file to include in the output graph",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        graph = build_graph(args.input_csv, args.ontology)
        args.output_turtle.parent.mkdir(parents=True, exist_ok=True)
        graph.serialize(destination=args.output_turtle, format="turtle")

        # Parse the generated output once to catch serialization problems.
        validation_graph = Graph()
        validation_graph.parse(args.output_turtle, format="turtle")
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"RDF conversion failed: {exc}", file=sys.stderr)
        return 2

    print(
        f"Wrote {len(graph):,} triples for "
        f"{len(group_rows(args.input_csv)):,} images to {args.output_turtle}"
    )

    star_triples = add_rdfstar_annotations(args.input_csv)
    with open(args.output_turtle, "a") as f:
        f.write(star_triples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
