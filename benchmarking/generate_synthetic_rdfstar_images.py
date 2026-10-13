#!/usr/bin/env python3
"""Generate X synthetic GraphAfghanica image resources as Turtle.

The generated data follows the ontology pattern used by GraphAfghanica:
- one :Image resource per synthetic image
- multilingual :description literals with @pl, @de, and @en
- integer width and height values
- quality, title, legend, references, classifications, collection membership
- CIDOC CRM production events
- typed image URLs
- RDF-star provenance annotations for descriptions and classifications

Example:
    python generate_synthetic_rdfstar_images.py 1000 output.ttl \
        --ontology ontology_star_noannotation.ttl \
        --seed 76
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

from rdflib import Graph, Literal, Namespace
from rdflib.namespace import RDF, RDFS, XSD

CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
GA = Namespace("http://www.graphAfghanica.org/data/")
GAO = Namespace("http://www.graphAfghanica.org/ontology/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

CLASSIFICATIONS = ["People", "Women", "Landscape", "Urban"]
PLACES = ["Qaysar", "Almar", "Herat", "Kabul", "Kandahar", "Ghazni", "MazarSharif", "Jalalabad"]
QUALITIES = ["sehr gut", "gut", "befriedigend", "beschädigt"]
LEGENDS = [
    "Street scene",
    "Bazaar scene",
    "Village landscape",
    "Portrait of local residents",
    "Agricultural activity",
    "Market activity",
]
REFERENCES = [
    "Tapper, R. and N. Lindisfarne-Tapper (2020): Afghan Village Voices.",
    "EWA-76 expedition field notes.",
    "GraphAfghanica photographic archive catalogue.",
    "Poznań Ethnology Department expedition documentation.",
]
DESCRIPTIONS = {
    "en": [
        "A historical photograph showing everyday life during the EWA-76 expedition.",
        "The image depicts a market scene with people, shops, and local goods.",
        "A rural landscape with traditional buildings and agricultural activity.",
        "Several residents are visible in a street scene near the local bazaar.",
    ],
    "de": [
        "Eine historische Fotografie aus der EWA-76-Expedition.",
        "Das Bild zeigt eine Marktszene mit Menschen, Geschäften und lokalen Waren.",
        "Eine ländliche Landschaft mit traditionellen Gebäuden und Landwirtschaft.",
        "Mehrere Bewohner sind in einer Straßenszene nahe dem Basar zu sehen.",
    ],
    "pl": [
        "Fotografia historyczna wykonana podczas wyprawy EWA-76.",
        "Zdjęcie przedstawia scenę targową z ludźmi, sklepami i lokalnymi towarami.",
        "Wiejski krajobraz z tradycyjną zabudową i działalnością rolniczą.",
        "Kilku mieszkańców jest widocznych na ulicy w pobliżu bazaru.",
    ],
}


def bind_namespaces(graph: Graph) -> None:
    graph.bind("crm", CRM)
    graph.bind("ga", GA)
    graph.bind("", GAO)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)
    graph.bind("xsd", XSD)
    graph.bind("skos", SKOS)


def add_shared_resources(graph: Graph) -> None:
    graph.add((GA.EWA76_Collection, RDF.type, CRM.E78_Curated_Holding))
    graph.add((GA.MarekGawecki, RDF.type, GAO.Person))
    graph.add((GA.Pytorch_classifier_v2, RDF.type, GAO.AI_Model))
    graph.add((GA.ImageTaxonomy, RDF.type, SKOS.ConceptScheme))

    for classification in CLASSIFICATIONS:
        concept = GA[classification]
        graph.add((concept, RDF.type, SKOS.Concept))
        graph.add((concept, SKOS.inScheme, GA.ImageTaxonomy))
        graph.add((concept, SKOS.prefLabel, Literal(classification, lang="en")))

    for place_name in PLACES:
        place = GA[place_name]
        place_name_resource = GA[f"{place_name}_name"]
        graph.add((place, RDF.type, CRM.E53_Place))
        graph.add((place, CRM.P1_is_identified_by, place_name_resource))
        graph.add((place_name_resource, RDF.type, CRM.E44_Place_Appellation))
        graph.add((place_name_resource, CRM.P190_has_symbolic_content, Literal(place_name)))


def make_image_id(index: int) -> str:
    return f"SYNTH_IMG_{index:05d}"


def make_production_id(index: int) -> str:
    return f"SYNTH_PRODUCTION_{index:05d}"


def add_synthetic_image(graph: Graph, index: int, rng: random.Random, base_url: str) -> dict[str, object]:
    image_id = make_image_id(index)
    image = GA[image_id]
    place_name = rng.choice(PLACES)
    place = GA[place_name]
    production = GA[make_production_id(index)]

    width = rng.randint(90, 240)
    height = rng.randint(90, 240)
    quality = rng.choice(QUALITIES)
    legend = rng.choice(LEGENDS)
    # Assign 1–2 random classes excluding Women.
    base_classifications = [
        classification
        for classification in CLASSIFICATIONS
        if classification != "Women"
    ]
    selected_classifications = rng.sample(
        base_classifications,
        k=rng.randint(1, 2),
    )

    # Assign Women deterministically to exactly one quarter of the images
    # when image_count is divisible by four: images 4, 8, 12, ...
    if index % 4 == 0:
        selected_classifications.append("Women")
    descriptions = {language: rng.choice(values) for language, values in DESCRIPTIONS.items()}
    title = f"Synthetic historical image {index:05d}"
    image_url = f"{base_url.rstrip('/')}/{image_id}.jpg"

    graph.add((image, RDF.type, GAO.Image))
    graph.add((image, GAO.title, Literal(title)))
    graph.add((image, GAO.legend, Literal(legend)))
    graph.add((image, GAO.format_width, Literal(width, datatype=XSD.int)))
    graph.add((image, GAO.format_height, Literal(height, datatype=XSD.int)))
    graph.add((image, GAO.quality, Literal(quality, lang="de")))
    graph.add((image, GAO.belongsTo, GA.EWA76_Collection))
    graph.add((image, CRM.P108i_was_produced_by, production))
    graph.add((image, GAO.hasDigitalRepresentation, Literal(image_url, datatype=XSD.anyURI)))

    for language, description in descriptions.items():
        graph.add((image, GAO.description, Literal(description, lang=language)))

    graph.add((image, GAO.references, Literal(rng.choice(REFERENCES))))

    for classification in selected_classifications:
        graph.add((image, GAO.classification, GA[classification]))

    graph.add((production, RDF.type, CRM.E12_Production))
    graph.add((production, CRM.P14_carried_out_by, GA.MarekGawecki))
    graph.add((production, CRM.P7_took_place_at, place))

    return {"image_id": image_id, "descriptions": descriptions, "classifications": selected_classifications}


def create_rdfstar_annotations(generated_images: list[dict[str, object]]) -> str:
    statements: list[str] = []

    for record in generated_images:
        image_term = f"ga:{record['image_id']}"
        descriptions = record["descriptions"]
        classifications = record["classifications"]

        assert isinstance(descriptions, dict)
        assert isinstance(classifications, list)

        for language, description in descriptions.items():
            literal = Literal(str(description), lang=str(language)).n3()
            statements.append(
                f"<< {image_term} :description {literal} >>\n"
                f"    :creator ga:MarekGawecki ;\n"
                f"    :confidence \"1.0\"^^xsd:decimal ."
            )

        for classification in classifications:
            statements.append(
                f"<< {image_term} :classification ga:{classification} >>\n"
                f"    :model ga:Pytorch_classifier_v2 ;\n"
                f"    :confidence \"0.89\"^^xsd:decimal ."
            )

    return "\n\n" + "\n\n".join(statements) + "\n" if statements else ""


def build_graph(image_count: int, ontology_path: Path | None, seed: int, base_url: str) -> tuple[Graph, list[dict[str, object]]]:
    if image_count < 1:
        raise ValueError("image_count must be at least 1")

    graph = Graph()
    bind_namespaces(graph)

    if ontology_path is not None:
        graph.parse(ontology_path, format="turtle")

    add_shared_resources(graph)
    rng = random.Random(seed)
    records = [add_synthetic_image(graph, i, rng, base_url) for i in range(1, image_count + 1)]
    return graph, records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic GraphAfghanica image data as Turtle.")
    parser.add_argument("image_count", type=int, help="Number of synthetic image resources to generate")
    parser.add_argument("--ontology", type=Path, default=None, help="Optional ontology Turtle file to include")
    parser.add_argument("--seed", type=int, default=76, help="Random seed for reproducible output")
    parser.add_argument("--base-url", default="http://localhost:8080/images", help="Base URL for image files")
    parser.add_argument("--without-rdfstar", action="store_true", help="Do not append RDF-star annotations")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        graph, generated_images = build_graph(args.image_count, args.ontology, args.seed, args.base_url)
        outputfilename = "generated_synthetic_star_" + str(args.image_count) + '.ttl'
        graph.serialize(destination=outputfilename, format="turtle", encoding="utf-8")

        if not args.without_rdfstar:
            with open(outputfilename, "a", encoding="utf-8") as handle:
                handle.write(create_rdfstar_annotations(generated_images))

        # Validate the standard Turtle graph. RDFLib versions without Turtle-star
        # support cannot validate the appended << ... >> statements.
        validation_graph = Graph()
        validation_graph.parse(data=graph.serialize(format="turtle"), format="turtle")

    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"RDF generation failed: {exc}", file=sys.stderr)
        return 2

    print(f"Wrote {len(graph):,} standard RDF triples for {args.image_count:,} synthetic images to {outputfilename}")
    if not args.without_rdfstar:
        print("RDF-star annotations were appended as Turtle-star text.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
