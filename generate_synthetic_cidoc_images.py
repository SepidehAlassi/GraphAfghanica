#!/usr/bin/env python3
"""Generate synthetic GraphAfghanica image resources in CIDOC CRM Turtle.

The generated data follows the patterns used in ontology_cidocCRM.ttl:
- image: E22 Human-Made Object
- production: E12 Production
- title: E35 Title
- place: E53 Place
- time-span: E52 Time-Span
- dimensions: E54 Dimension with numeric value and millimetre unit
- digital file: E73 Information Object with E42 Identifier
- description: E33 Linguistic Object created by E65 Creation
- classifications: E13 Attribute Assignment with confidence dimension

By default, the script creates exactly 1,000 image resources.
"""

from __future__ import annotations

import argparse
import random
from datetime import date, timedelta
import os

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
GA = Namespace("http://www.graphAfghanica.org/data/")

PLACES = [
    ("Herat", "Herat"),
    ("Kandahar", "Kandahar"),
    ("Ghazni", "Ghazni"),
    ("Kabul", "Kabul"),
    ("Nayak", "Nayak"),
    ("TalaOBarfak", "Tala o Barfak"),
    ("Dawlatabad", "Dawlatabad"),
    ("Qaysar", "Qaysar"),
    ("Almar", "Almar"),
    ("MazarSharif", "Mazar-e-Sharif"),
    ("Jalalabad", "Jalalabad"),
]

CLASSIFICATIONS = [
    ("Urban", "Urban"),
    ("Landscape", "Landscape"),
    ("People", "People"),
    ("Women", "Women")
]

QUALITY_VALUES = ["very good", "good", "fair", "poor"]

DESCRIPTION_TEMPLATES = [
    "A historical photograph made in {place}, showing {subject} during the EWA-76 expedition.",
    "The image documents {subject} in {place} in 1976.",
    "A black-and-white expedition photograph depicting {subject} near {place}.",
    "This photograph records a scene of {subject} observed in {place}.",
]

REFERENCE_TEMPLATES = [
    "EWA-76 field catalogue, image {number}.",
    "GraphAfghanica synthetic catalogue record {number}.",
    "Expedition documentation, 1976, record {number}.",
]


def add_name(graph: Graph, resource: URIRef, name_resource: URIRef, text: str) -> None:
    graph.add((resource, CRM.P1_is_identified_by, name_resource))
    graph.add((name_resource, RDF.type, CRM.E41_Appellation))
    graph.add((name_resource, CRM.P190_has_symbolic_content, Literal(text)))


def add_shared_resources(graph: Graph) -> None:
    """Add the common types, units, actors, and collection used by all images."""
    shared_types = {
        GA.Photograph_Type: "Photograph",
        GA.Image_Description_Type: "Image Description",
        GA.Bibliographic_Reference_Type: "Bibliographic Reference",
        GA.Artificial_Intelligence_Model: "Artificial Intelligence Model",
        GA.Confidence: "Confidence Score",
        GA.Image_Quality: "Image Quality",
        GA.Width: "Width",
        GA.Height: "Height",
    }
    for uri, label in shared_types.items():
        graph.add((uri, RDF.type, CRM.E55_Type))
        graph.add((uri, CRM.P190_has_symbolic_content, Literal(label)))

    for local, label in CLASSIFICATIONS:
        uri = GA[local]
        graph.add((uri, RDF.type, CRM.E55_Type))
        graph.add((uri, CRM.P190_has_symbolic_content, Literal(label)))

    graph.add((GA.Millimeters, RDF.type, CRM.E58_Measurement_Unit))
    graph.add((GA.Millimeters, CRM.P190_has_symbolic_content, Literal("millimeters")))
    graph.add((GA.Probability_Unit, RDF.type, CRM.E58_Measurement_Unit))
    graph.add(
        (
            GA.Probability_Unit,
            CRM.P190_has_symbolic_content,
            Literal("Probability value between 0 and 1"),
        )
    )

    graph.add((GA.EWA76_Collection, RDF.type, CRM.E78_Curated_Holding))
    add_name(
        graph,
        GA.EWA76_Collection,
        GA.EWA76_Collection_Name,
        "EWA76 Photo Collection",
    )

    graph.add((GA.MarekGawecki, RDF.type, CRM.E21_Person))
    add_name(graph, GA.MarekGawecki, GA.MarekGawecki_Name, "Marek Gawęcki")

    graph.add((GA.Pytorch_classifier_v2, RDF.type, CRM.E39_Actor))
    graph.add((GA.Pytorch_classifier_v2, CRM.P2_has_type, GA.Artificial_Intelligence_Model))
    add_name(
        graph,
        GA.Pytorch_classifier_v2,
        GA.Pytorch_classifier_v2_Name,
        "PyTorch ResNet-50 Classifier v2.0",
    )

    for local, label in PLACES:
        place = GA[local]
        place_name = GA[f"{local}_Name"]
        graph.add((place, RDF.type, CRM.E53_Place))
        graph.add((place, CRM.P1_is_identified_by, place_name))
        graph.add((place_name, RDF.type, CRM.E44_Place_Appellation))
        graph.add((place_name, CRM.P190_has_symbolic_content, Literal(label)))


def random_date(rng: random.Random) -> date:
    start = date(1976, 5, 8)
    end = date(1976, 10, 3)
    return start + timedelta(days=rng.randint(0, (end - start).days))


def add_dimension(
    graph: Graph,
    image: URIRef,
    dimension: URIRef,
    dimension_type: URIRef,
    value: int | float | str,
    unit: URIRef | None = None,
) -> None:
    graph.add((image, CRM.P43_has_dimension, dimension))
    graph.add((dimension, RDF.type, CRM.E54_Dimension))
    graph.add((dimension, CRM.P2_has_type, dimension_type))

    if isinstance(value, int):
        graph.add((dimension, CRM.P90_has_value, Literal(value, datatype=XSD.integer)))
    elif isinstance(value, float):
        graph.add((dimension, CRM.P90_has_value, Literal(value, datatype=XSD.decimal)))
    else:
        graph.add((dimension, CRM.P90_has_value, Literal(value)))

    if unit is not None:
        graph.add((dimension, CRM.P91_has_unit, unit))


def add_description(
    graph: Graph,
    image: URIRef,
    image_id: str,
    text: str,
    confidence_value: float,
) -> None:
    description = GA[f"{image_id}_Description_en"]
    creation = GA[f"{image_id}_Description_en_Creation"]
    confidence = GA[f"{image_id}_Description_en_Confidence"]

    graph.add((description, RDF.type, CRM.E33_Linguistic_Object))
    graph.add((description, CRM.P129_is_about, image))
    graph.add((description, CRM.P190_has_symbolic_content, Literal(text, lang="en")))
    graph.add((description, CRM.P2_has_type, GA.Image_Description_Type))

    graph.add((creation, RDF.type, CRM.E65_Creation))
    graph.add((creation, CRM.P94_has_created, description))
    graph.add((creation, CRM.P14_carried_out_by, GA.MarekGawecki))
    graph.add((creation, CRM.P43_has_dimension, confidence))

    add_dimension(
        graph,
        creation,
        confidence,
        GA.Confidence,
        1.0,
        GA.Probability_Unit,
    )


def add_reference(graph: Graph, image: URIRef, image_id: str, text: str) -> None:
    reference = GA[f"{image_id}_Reference"]
    graph.add((reference, RDF.type, CRM.E33_Linguistic_Object))
    graph.add((reference, CRM.P129_is_about, image))
    graph.add((reference, CRM.P190_has_symbolic_content, Literal(text)))
    graph.add((reference, CRM.P2_has_type, GA.Bibliographic_Reference_Type))


def add_classification(
    graph: Graph,
    image: URIRef,
    image_id: str,
    concept: URIRef,
    index: int,
    confidence_value: float,
) -> None:
    assignment = GA[f"{image_id}_Classification_{index:02d}"]
    confidence = GA[f"{image_id}_Classification_{index:02d}_Confidence"]

    graph.add((assignment, RDF.type, CRM.E13_Attribute_Assignment))
    graph.add((assignment, CRM.P14_carried_out_by, GA.Pytorch_classifier_v2))
    graph.add((assignment, CRM.P140_assigned_attribute_to, image))
    graph.add((assignment, CRM.P141_assigned, concept))
    graph.add((assignment, CRM.P177_assigned_property_type, CRM.P2_has_type))
    graph.add((assignment, CRM.P43_has_dimension, confidence))

    add_dimension(
        graph,
        assignment,
        confidence,
        GA.Confidence,
        0.89,
        GA.Probability_Unit,
    )


def add_image(graph: Graph, number: int, rng: random.Random, base_url: str) -> None:
    image_id = f"EWA76_SYN_{number:04d}"
    image = GA[image_id]
    title = GA[f"{image_id}_Title"]
    production = GA[f"{image_id}_Production"]
    timespan = GA[f"{image_id}_TimeSpan"]
    digital_file = GA[f"{image_id}_DigitalFile"]
    digital_file_uri = GA[f"{image_id}_DigitalFile_URI"]

    place_local, place_label = rng.choice(PLACES)
    place = GA[place_local]
    taken_on = random_date(rng)
    width = rng.randint(90, 240)
    height = rng.randint(70, 180)
    quality = rng.choice(QUALITY_VALUES)
    # Assign 1–2 random classes excluding Women.
    base_classes = [item for item in CLASSIFICATIONS if item[0] != "Women"]
    selected_classes = rng.sample(base_classes, k=rng.randint(1, 2))

    # Deterministically assign Women to exactly one quarter of the images
    # when count is divisible by four: images 4, 8, 12, ...
    if number % 4 == 0:
        selected_classes.append(("Women", "Women"))
    subject = ", ".join(label.lower() for _, label in selected_classes)

    graph.add((image, RDF.type, CRM["E22_Human-Made_Object"]))
    graph.add((image, CRM.P2_has_type, GA.Photograph_Type))
    graph.add((image, CRM.P102_has_title, title))
    graph.add((image, CRM.P46i_forms_part_of, GA.EWA76_Collection))
    graph.add((image, CRM.P108i_was_produced_by, production))
    # This reproduces the link pattern used in the supplied ontology.
    graph.add((image, CRM.P128_carries, digital_file))

    graph.add((title, RDF.type, CRM.E35_Title))
    graph.add(
        (
            title,
            CRM.P190_has_symbolic_content,
            Literal(f"Synthetic photograph {number} from {place_label}"),
        )
    )
    graph.add((image, CRM.P3_has_note, Literal(f"Synthetic test image {number}")))

    graph.add((production, RDF.type, CRM.E12_Production))
    graph.add((production, CRM.P14_carried_out_by, GA.MarekGawecki))
    graph.add((production, CRM.P7_took_place_at, place))
    graph.add((production, CRM["P4_has_time-span"], timespan))

    graph.add((timespan, RDF.type, CRM["E52_Time-Span"]))
    graph.add((timespan, CRM.P82a_begin_of_the_begin, Literal(taken_on, datatype=XSD.date)))
    graph.add((timespan, CRM.P82b_end_of_the_end, Literal(taken_on, datatype=XSD.date)))

    add_dimension(graph, image, GA[f"{image_id}_Width"], GA.Width, width, GA.Millimeters)
    add_dimension(graph, image, GA[f"{image_id}_Height"], GA.Height, height, GA.Millimeters)
    add_dimension(graph, image, GA[f"{image_id}_Quality"], GA.Image_Quality, quality)

    image_url = f"{base_url.rstrip('/')}/{image_id}.jpg"
    graph.add((digital_file, RDF.type, CRM.E73_Information_Object))
    graph.add((digital_file, CRM.P1_is_identified_by, digital_file_uri))
    graph.add(
        (
            digital_file,
            CRM.P3_has_note,
            Literal(f"Digital image file representing photograph {image_id}."),
        )
    )
    graph.add((digital_file_uri, RDF.type, CRM.E42_Identifier))
    graph.add(
        (
            digital_file_uri,
            CRM.P190_has_symbolic_content,
            Literal(image_url, datatype=XSD.anyURI),
        )
    )

    description_text = rng.choice(DESCRIPTION_TEMPLATES).format(
        place=place_label,
        subject=subject,
    )
    add_description(
        graph,
        image,
        image_id,
        description_text,
        confidence_value=rng.uniform(0.85, 1.0),
    )

    reference_text = rng.choice(REFERENCE_TEMPLATES).format(number=number)
    add_reference(graph, image, image_id, reference_text)

    for index, (classification_local, _) in enumerate(selected_classes, start=1):
        add_classification(
            graph,
            image,
            image_id,
            GA[classification_local],
            index,
            confidence_value=rng.uniform(0.55, 0.99),
        )


def build_graph(count: int, seed: int, base_url: str) -> Graph:
    if count < 1:
        raise ValueError("count must be at least 1")

    rng = random.Random(seed)
    graph = Graph()
    graph.bind("crm", CRM)
    graph.bind("ga", GA)
    graph.bind("xsd", XSD)

    add_shared_resources(graph)
    for number in range(1, count + 1):
        add_image(graph, number, rng, base_url)

    return graph


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate random CIDOC CRM image resources as Turtle."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1000,
        help="Number of image resources to generate (default: 1000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=76,
        help="Random seed for reproducible output (default: 76)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8080/EWA76",
        help="Base URL used for generated digital image identifiers",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        graph = build_graph(args.count, args.seed, args.base_url)
        outputfilename = "generated_synthetic_crm_"+str(args.count)+'.ttl'
        output = os.path.join('.', outputfilename)
        graph.serialize(destination=output, format="turtle")

        # Parse the result again to catch serialization problems.
        # validation_graph = Graph()
        # validation_graph.parse(output, format="turtle")
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1
    except Exception as exc:
        print(f"RDF generation failed: {exc}")
        return 2

    print(
        f"Created {args.count:,} image resources and "
        f"{len(graph):,} triples in {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
