from flask_restful import Resource
import requests
import re
import os
from helpers import get_value

GRAPHDB_ENDPOINT = os.getenv(
    "GRAPHDB_ENDPOINT",
    "http://localhost:7200/repositories/GraphAfghanica"
)

DATA_NAMESPACE = "http://www.graphAfghanica.org/data/"
ONTOLOGY_NAMESPACE = "http://www.graphAfghanica.org/ontology/"


def get_collection_metadata(collection_id):

    if not re.fullmatch(r"[A-Za-z0-9_-]+", collection_id):
        return {"error": "Invalid collection ID"}, 400

    collection_iri = f"{DATA_NAMESPACE}{collection_id}"

    sparql_query = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>
        PREFIX ga: <http://www.graphAfghanica.org/data/>
        PREFIX schema: <http://schema.org/> 
        PREFIX : <http://www.graphAfghanica.org/ontology/>

        SELECT DISTINCT ?collection_name ?collection_description ?curation_begin ?curation_end ?group_label ?member_name
        WHERE {{
            BIND (<{collection_iri}> AS ?collection_iri )
            ?collection_iri crm:P1_is_identified_by ?collection_name_res .
            ?collection_name_res crm:P190_has_symbolic_content ?collection_name .
            ?collection_iri crm:P3_has_note ?collection_description .
            ?collection_iri crm:P147i_was_curated_by ?curation_activity .
            ?curation_activity crm:P14_carried_out_by ?group .
            ?curation_activity crm:P4_has_time-span ?time_span .
            ?time_span crm:P82a_begin_of_the_begin ?curation_begin .
            ?time_span crm:P82b_end_of_the_end ?curation_end .
            ?group rdfs:label ?group_label .
            ?group crm:P107_has_current_or_former_member ?group_member .
            ?group_member schema:name ?member_name .
    
        }} LIMIT 1
    """

    try:
        response = requests.post(
            GRAPHDB_ENDPOINT,
            data={"query": sparql_query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=30
        )

        response.raise_for_status()
        results = response.json()
        print("Collection IRI:", collection_iri)
        print("SPARQL results:", results)
    except requests.exceptions.Timeout:
        return {"error": "GraphDB request timed out"}, 504

    except requests.exceptions.RequestException as error:
        return {
            "error": "Failed to retrieve collection metadata",
            "details": str(error)
        }, 502

    except ValueError:
        return {"error": "Invalid response from GraphDB"}, 502

    bindings = results.get("results", {}).get("bindings", [])

    if not bindings:
        return {
            "collection_id": collection_id,
            "collection_name": None
        }, 200

    first = bindings[0]
    collection_metadata = {
        "id": collection_id,
        "iri": collection_iri,
        "collection_name": get_value(first, "collection_name"),
        "description": get_value(first, "collection_description"),
        "curation_begin": get_value(first, "curation_begin"),
        "curation_end": get_value(first, "curation_end"),
        "group_label": get_value(first, "group_label"),
        "members": []
    }
    seen_members = set()
    for binding in bindings:
        member = get_value(binding, "member_name")

        if member and member not in seen_members:
            collection_metadata["members"].append(member)
            seen_members.add(member)

    return collection_metadata, 200


def get_images_by_collection(collection_id):

    # Validate the collection ID
    if not re.fullmatch(r"[A-Za-z0-9_-]+", collection_id):
        return {"error": "Invalid collection ID"}, 400

    # Construct the full RDF IRI
    collection_iri = f"{DATA_NAMESPACE}{collection_id}"

    sparql_query = f"""
        PREFIX : <{ONTOLOGY_NAMESPACE}>
        PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>

        SELECT DISTINCT ?image ?image_url ?title
        WHERE {{
            ?image a :Image ;
                   :belongsTo <{collection_iri}> ;
                   :hasDigitalRepresentation ?image_url ;
                   :title ?title .
        }}
        ORDER BY ?image
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

    except requests.exceptions.RequestException as error:
        return {
            "error": "Failed to retrieve collection images",
            "details": str(error)
        }, 502

    except ValueError:
        return {"error": "Invalid response from GraphDB"}, 502

    images = []

    for binding in results.get("results", {}).get("bindings", []):
        image_iri = binding["image"]["value"]
        image_url = binding["image_url"]["value"]
        image_title = binding["title"]["value"]

        images.append({
            "iri": image_iri,
            "url": image_url,
            "title": image_title
        })
    return {
        "image_count": len(images),
        "images": images
    }, 200


class Collection(Resource):

    def get(self, collection_id):
        collection_info, status = get_collection_metadata(collection_id)
        if status == 200:
            images, status = get_images_by_collection(collection_id)
            if status != 200:
                return collection_info, 200
            else:
                return {**collection_info, **images}, 200
        else:
            return None
