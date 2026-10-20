
from flask_restful import Resource
import requests
import re
import os

GRAPHDB_ENDPOINT = os.getenv(
    "GRAPHDB_ENDPOINT",
    "http://localhost:7200/repositories/GraphAfghanica"
)

DATA_NAMESPACE = "http://www.graphAfghanica.org/data/"
ONTOLOGY_NAMESPACE = "http://www.graphAfghanica.org/ontology/"


def get_value(binding, variable):
    return binding.get(variable, {}).get("value")


def get_language(binding, variable):
    return binding.get(variable, {}).get("xml:lang")


def get_image(image_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", image_id):
        return {"error": "Invalid image ID"}, 400

    image_iri = f"{DATA_NAMESPACE}{image_id}"
    sparql_query = f"""
        PREFIX : <{ONTOLOGY_NAMESPACE}>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX schema: <http://schema.org/>
        PREFIX ga: <http://www.graphAfghanica.org/data/>
        select DISTINCT ?collection ?image_url ?title ?legend ?class_name  ?model_name ?classification_confidence ?width ?height ?quality ?description ?description_creator_name ?description_confidence ?references ?photographer_name ?location_name ?location_wiki_iri ?time_span_begin ?time_span_end
        where {{
            <{image_iri}>  a :Image ;
            :belongsTo ?collection ;
            :hasDigitalRepresentation ?image_url ;
            :title ?title .
            optional {{
                <{image_iri}> :legend ?legend .
            }}
            Optional {{
                <{image_iri}> :classification ?classification .
                ?classification skos:prefLabel ?class_name .
            }}
            Optional {{
                <{image_iri}> :format_width ?width .
            }}
            Optional {{
                <{image_iri}> :format_height ?height .
            }}
            optional {{
                <{image_iri}> :legend ?legend .
            }}
	        optional {{
                <{image_iri}> :quality ?quality  .
	        }}
            optional {{
                <{image_iri}> :description ?description 
            }}
            optional {{
                <{image_iri}> :references ?references .
	        }}
    
            <{image_iri}> crm:P108i_was_produced_by ?photography_event .
            ?photography_event crm:P14_carried_out_by ?photographer ;
                                crm:P9i_forms_part_of ?expedition ;
                                crm:P7_took_place_at ?location ;
                                crm:P4_has_time-span ?time_span .
            ?time_span crm:P82a_begin_of_the_begin ?time_span_begin ;
                        crm:P82b_end_of_the_end ?time_span_end .
            ?photographer schema:name ?photographer_name .    
            ?location crm:P1_is_identified_by ?location_name_resource.
            ?location owl:sameAs ?location_wiki_iri .
            ?location_name_resource crm:P190_has_symbolic_content ?location_name . 
            OPTIONAL {{
                << <{image_iri}> :description ?description >>
                    :creator ?description_creator ;
                    :confidence ?description_confidence_float .
                BIND(
                    CONCAT(STR(?description_confidence_float * 100), "%")
                    AS ?description_confidence
                )
                ?description_creator schema:name ?description_creator_name .  
            }}
            OPTIONAL {{
                << <{image_iri}> :classification ?classification >> :model
                                ?classification_model ;
                                :confidence ?classification_confidence_float .
                ?classification_model crm:P1_is_identified_by ?model_name .
                BIND(
                    CONCAT(STR(?classification_confidence_float * 100), "%")
                    AS ?classification_confidence
                )
            }}
    
        }}
    """
    try:
        response = requests.post(
            GRAPHDB_ENDPOINT,
            data={"query": sparql_query},
            headers={
                "Accept": "application/sparql-results+json"
            },
            timeout=30
        )

        response.raise_for_status()
        results = response.json()

    except requests.exceptions.Timeout:
        return {"error": "GraphDB request timed out"}, 504


    except requests.exceptions.HTTPError as error:

        return {

            "error": "GraphDB rejected the SPARQL query",

            "status_code": error.response.status_code,

            "details": error.response.text

        }, 502


    except requests.exceptions.RequestException as error:

        return {

            "error": "Failed to retrieve the image metadata",

            "details": str(error)

        }, 502

    except ValueError:
        return {"error": "Invalid response from GraphDB"}, 502


    bindings = results.get("results", {}).get("bindings", [])

    if not bindings:
        return {"error": "Image not found"}, 404

    first = bindings[0]

    # General image metadata
    image_metadata = {
        "id": image_id,
        "iri": image_iri,
        "collection": get_value(first, "collection"),
        "image_url": get_value(first, "image_url"),
        "title": get_value(first, "title"),
        "legend": get_value(first, "legend"),
        "width": get_value(first, "width"),
        "height": get_value(first, "height"),
        "quality": get_value(first, "quality"),
        "photographer_name": get_value(first, "photographer_name"),
        "location_name": get_value(first, "location_name"),
        "location_wiki_iri": get_value(first, "location_wiki_iri"),
        "time_span_begin": get_value(first, "time_span_begin"),
        "time_span_end": get_value(first, "time_span_end"),
        "classifications": [],
        "descriptions": [],
        "references": []
    }

    # Track already processed values
    classifications_by_name = {}
    seen_descriptions = set()
    seen_references = set()

    for binding in bindings:

        # Classifications and RDF-star annotations
        # Classifications and RDF-star annotations
        class_name = get_value(binding, "class_name")

        if class_name:
            model_name = get_value(binding, "model_name")
            confidence = get_value(
                binding, "classification_confidence"
            )

            if class_name not in classifications_by_name:
                classifications_by_name[class_name] = {
                    "name": class_name,
                    "model": None,
                    "confidence": None
                }

            classification_info = classifications_by_name[class_name]

            # Prefer a readable model name over an IRI.
            if model_name:
                is_iri = model_name.startswith(
                    ("http://", "https://")
                )

                current_model = classification_info["model"]

                if current_model is None or (
                        current_model.startswith(("http://", "https://"))
                        and not is_iri
                ):
                    classification_info["model"] = model_name

            # Preserve an available confidence score.
            if confidence is not None:
                classification_info["confidence"] = confidence

        # -----------------------------------
        # Descriptions and RDF-star metadata
        # -----------------------------------


        # Descriptions and RDF-star metadata
        description = get_value(binding, "description")

        if description:
            description_info = {
                "text": description,
                "language": get_language(binding, "description"),
                "creator": get_value(
                    binding, "description_creator_name"
                ),
                "confidence": get_value(
                    binding, "description_confidence"
                )
            }

            key = (
                description_info["text"],
                description_info["language"],
                description_info["creator"],
                description_info["confidence"]
            )

            if key not in seen_descriptions:
                image_metadata["descriptions"].append(
                    description_info
                )
                seen_descriptions.add(key)

        # -----------------------------------
        # References
        # -----------------------------------

        reference = get_value(binding, "references")

        if reference and reference not in seen_references:
            image_metadata["references"].append(reference)
            seen_references.add(reference)
    image_metadata["classifications"] = list(
        classifications_by_name.values()
    )
    return image_metadata, 200



class Image(Resource):

    def get(self, image_id):
        return get_image(image_id)
