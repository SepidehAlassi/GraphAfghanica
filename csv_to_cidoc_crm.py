#!/usr/bin/env python3
"""Convert GraphAfghanica CSV metadata to CIDOC CRM Turtle using RDFLib.

The mapper follows the modeling patterns in ontology_cidocCRM.ttl:
- photograph: crm:E22_Human-Made_Object
- title: crm:E35_Title
- dimensions/quality: crm:E54_Dimension
- digital image file: crm:E73_Information_Object + crm:E42_Identifier
- descriptions/references: crm:E33_Linguistic_Object
- classifications: crm:E13_Attribute_Assignment

"""

from __future__ import annotations

import argparse
import csv
import os.path
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
GA = Namespace("http://www.graphAfghanica.org/data/")

LANGUAGE_COLUMNS = {
    ":description (pl)": "pl",
    ":description (de)": "de",
    ":description (en)": "en",
}


def clean(value: object) -> str:
    """Return a stripped string, treating empty/NaN-like values as empty."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    return text


def local_name(value: str) -> str:
    """Convert :EWA76_MG69 or a full URI to a safe local identifier."""
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


def parse_url_lexical(value: str) -> str:
    """Extract the URL lexical value from CSV forms such as:
    '"http://localhost:8080/MG76.png"^^xsd:anyURI'.
    """
    text = clean(value)
    if not text:
        return ""
    typed = re.fullmatch(r'"(.*)"\^\^xsd:anyURI', text)
    if typed:
        return typed.group(1)
    if text.startswith("<") and text.endswith(">"):
        return text[1:-1]
    return text.strip('"')


def unique_nonempty(rows: Iterable[Mapping[str, str]], column: str) -> list[str]:
    """Return nonempty values in first-seen order without duplicates."""
    result: list[str] = []
    seen: set[str] = set()
    for row in rows:
        value = clean(row.get(column, ""))
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def first_nonempty(rows: Iterable[Mapping[str, str]], column: str) -> str:
    for row in rows:
        value = clean(row.get(column, ""))
        if value:
            return value
    return ""


def add_named_type(graph: Graph, uri: URIRef, label: str) -> None:
    graph.add((uri, RDF.type, CRM.E55_Type))
    graph.add((uri, CRM.P190_has_symbolic_content, Literal(label)))


def add_dimension(
        graph: Graph,
        image: URIRef,
        dimension: URIRef,
        dimension_type: URIRef,
        value: str,
) -> None:
    if not value:
        return
    graph.add((image, CRM.P43_has_dimension, dimension))
    graph.add((dimension, RDF.type, CRM.E54_Dimension))
    graph.add((dimension, CRM.P2_has_type, dimension_type))
    # Match values such as "175 mm", "175mm", or "175.5 mm".
    match = re.fullmatch(
        r"\s*([+-]?\d+(?:\.\d+)?)\s*mm\s*",
        value,
        flags=re.IGNORECASE,
    )

    if match:
        numeric_value = match.group(1)

        if "." in numeric_value:
            literal = Literal(numeric_value, datatype=XSD.decimal)
        else:
            literal = Literal(numeric_value, datatype=XSD.integer)

        graph.add((dimension, CRM.P90_has_value, literal))
        graph.add((dimension, CRM.P91_has_unit, GA.Millimeters))
    else:
        # Preserve nonstandard or unknown values instead of crashing.
        graph.add(
            (
                dimension,
                CRM.P90_has_value,
                Literal(value, datatype=XSD.string),
            )
        )
def add_description(
        graph: Graph,
        image: URIRef,
        image_id: str,
        text: str,
        language: str,
        creator: URIRef,
) -> None:
    if not text:
        return

    description = GA[f"{image_id}_Description_{language}"]
    creation = GA[f"{image_id}_Description_{language}_Creation"]
    confidence = GA[f"{image_id}_Description_{language}_Confidence"]

    graph.add((description, RDF.type, CRM.E33_Linguistic_Object))
    graph.add((description, CRM.P129_is_about, image))
    graph.add((description, CRM.P190_has_symbolic_content, Literal(text, lang=language)))
    graph.add((description, CRM.P2_has_type, GA.Image_Description_Type))

    graph.add((creation, RDF.type, CRM.E65_Creation))
    graph.add((creation, CRM.P94_has_created, description))
    graph.add((creation, CRM.P14_carried_out_by, creator))
    graph.add((creation, CRM.P43_has_dimension, confidence))

    graph.add((confidence, RDF.type, CRM.E54_Dimension))
    graph.add((confidence, CRM.P2_has_type, GA.Confidence))
    graph.add((confidence, CRM.P90_has_value, Literal("1.0", datatype=XSD.decimal)))
    graph.add((confidence, CRM.P91_has_unit, GA.Probability_Unit))


def add_reference(
        graph: Graph,
        image: URIRef,
        image_id: str,
        text: str,
        index: int,
) -> None:
    reference = GA[f"{image_id}_Reference_{index:03d}"]
    graph.add((reference, RDF.type, CRM.E33_Linguistic_Object))
    graph.add((reference, CRM.P129_is_about, image))
    graph.add((reference, CRM.P190_has_symbolic_content, Literal(text)))
    graph.add((reference, CRM.P2_has_type, GA.Bibliographic_Reference_Type))


def add_classification(
        graph: Graph,
        image: URIRef,
        image_id: str,
        classification_value: str,
        index: int,
        classifier: URIRef,
        confidence_value: str,
) -> None:
    concept = ga_uri(classification_value)
    assignment = GA[f"{image_id}_Classification_{index:03d}"]
    confidence = GA[f"{image_id}_Classification_{index:03d}_Confidence"]

    # In strict CRM, vocabulary entries are E55 Types.
    graph.add((concept, RDF.type, CRM.E55_Type))
    graph.add(
        (
            concept,
            CRM.P190_has_symbolic_content,
            Literal(local_name(classification_value).replace("_", " ")),
        )
    )

    graph.add((assignment, RDF.type, CRM.E13_Attribute_Assignment))
    graph.add((assignment, CRM.P14_carried_out_by, classifier))
    graph.add((assignment, CRM.P140_assigned_attribute_to, image))
    graph.add((assignment, CRM.P141_assigned, concept))
    graph.add((assignment, CRM.P177_assigned_property_type, CRM.P2_has_type))
    graph.add((assignment, CRM.P43_has_dimension, confidence))

    graph.add((confidence, RDF.type, CRM.E54_Dimension))
    graph.add((confidence, CRM.P2_has_type, GA.Confidence))
    graph.add(
        (confidence, CRM.P90_has_value, Literal(confidence_value, datatype=XSD.decimal))
    )
    graph.add((confidence, CRM.P91_has_unit, GA.Probability_Unit))


def add_digital_file(graph: Graph, image: URIRef, image_id: str, url: str) -> None:
    if not url:
        return
    digital_file = GA[f"{image_id}_DigitalFile"]
    identifier = GA[f"{image_id}_DigitalFile_URI"]

    # This follows the supplied ontology's existing P128 pattern.
    graph.add((image, CRM.P128_carries, digital_file))
    graph.add((digital_file, RDF.type, CRM.E73_Information_Object))
    graph.add((digital_file, CRM.P1_is_identified_by, identifier))
    graph.add((identifier, RDF.type, CRM.E42_Identifier))
    graph.add((identifier, CRM.P190_has_symbolic_content, Literal(url, datatype=XSD.anyURI)))


def map_group(
        graph: Graph,
        collection_id: str,
        rows: list[Mapping[str, str]],
        description_creator: URIRef,
        classifier: URIRef,
        classification_confidence: str,
) -> None:
    image_id = local_name(collection_id)
    image = GA[image_id]

    graph.add((image, RDF.type, CRM.E22_Human_Made_Object))
    graph.add((image, CRM.P2_has_type, GA.Photograph_Type))

    name = first_nonempty(rows, "Name")
    if name:
        title = GA[f"{image_id}_Title"]
        graph.add((image, CRM.P102_has_title, title))
        graph.add((title, RDF.type, CRM.E35_Title))
        graph.add((title, CRM.P190_has_symbolic_content, Literal(name)))

    legend = first_nonempty(rows, ":legend")
    if legend:
        graph.add((image, CRM.P3_has_note, Literal(legend)))

    collection = first_nonempty(rows, ":belongsTo")
    if collection:
        collection_uri = ga_uri(collection)
        graph.add((image, CRM.P46i_forms_part_of, collection_uri))
        graph.add((collection_uri, RDF.type, CRM.E78_Curated_Holding))

    production = first_nonempty(rows, "crm:P108i_was_produced_by")
    if production:
        production_uri = ga_uri(production)
        graph.add((image, CRM.P108i_was_produced_by, production_uri))
        graph.add((production_uri, RDF.type, CRM.E12_Production))

    quality = first_nonempty(rows, ":quality")
    width = first_nonempty(rows, ":format_width")
    height = first_nonempty(rows, ":format_height")
    add_dimension(graph, image, GA[f"{image_id}_Quality"], GA.Image_Quality, quality)
    add_dimension(graph, image, GA[f"{image_id}_Width"], GA.Width, width)
    add_dimension(graph, image, GA[f"{image_id}_Height"], GA.Height, height)

    url = parse_url_lexical(first_nonempty(rows, ":hasDigitalRepresentation"))
    add_digital_file(graph, image, image_id, url)

    for column, language in LANGUAGE_COLUMNS.items():
        text = first_nonempty(rows, column)
        add_description(graph, image, image_id, text, language, description_creator)

    for index, reference in enumerate(unique_nonempty(rows, ":references"), start=1):
        add_reference(graph, image, image_id, reference, index)

    for index, classification in enumerate(
            unique_nonempty(rows, ":classification"), start=1
    ):
        add_classification(
            graph,
            image,
            image_id,
            classification,
            index,
            classifier,
            classification_confidence,
        )


def read_csv_grouped(csv_path: Path) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")
        if ":collectionID" not in reader.fieldnames:
            raise ValueError("Required CSV column ':collectionID' is missing")
        for row_number, row in enumerate(reader, start=2):
            collection_id = clean(row.get(":collectionID", ""))
            if not collection_id:
                print(
                    f"Warning: skipping CSV row {row_number} without :collectionID",
                    file=sys.stderr,
                )
                continue
            grouped[collection_id].append(row)
    return grouped


def build_graph(
        csv_path: Path,
        ontology_path: Path | None,
        classification_confidence: str,
) -> Graph:
    graph = Graph()
    graph.bind("crm", CRM)
    graph.bind("ga", GA)
    graph.bind("xsd", XSD)

    if ontology_path is not None:
        graph.parse(ontology_path, format="turtle")

    grouped = read_csv_grouped(csv_path)

    for collection_id, rows in grouped.items():
        map_group(
            graph,
            collection_id,
            rows,
            description_creator=GA.MarekGawecki,
            classifier=GA.Pytorch_classifier_v2,
            classification_confidence=classification_confidence,
        )

    return graph


def main() -> int:
    input_csv = Path('qaysar_expedition_data.csv')
    output_turtle = Path('qaysar_expedition_crm.ttl')
    ontology_turtle = Path('./ontology_cidocCRM.ttl')
    classification_confidence = '1.0'
    try:
        graph = build_graph(
            input_csv,
            ontology_turtle,
            classification_confidence,
        )
        output_turtle.parent.mkdir(parents=True, exist_ok=True)
        graph.serialize(destination=output_turtle, format="turtle")
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # rdflib parser/serializer errors
        print(f"RDF conversion failed: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {len(graph):,} triples to {output_turtle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
