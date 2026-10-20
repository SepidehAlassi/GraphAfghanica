from flask_restful import Resource
import requests
import re
import os
from helpers import get_value, get_language

GRAPHDB_ENDPOINT = os.getenv(
    "GRAPHDB_ENDPOINT",
    "http://localhost:7200/repositories/GraphAfghanica"
)

DATA_NAMESPACE = "http://www.graphAfghanica.org/data/"
ONTOLOGY_NAMESPACE = "http://www.graphAfghanica.org/ontology/"


def get_expedition(expedition_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", expedition_id):
        return {"error": "Invalid expedition ID"}, 400
    expdition_iri = f"{DATA_NAMESPACE}{expedition_id}"

    sparql_query = f"""
        PREFIX : <{ONTOLOGY_NAMESPACE}>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX ga: <{DATA_NAMESPACE}>
        PREFIX schema: <http://schema.org/> 
        select DISTINCT ?label ?group_label ?location_name ?location_wiki_iri ?expedition_begin ?expedition_end ?member_name ?collection_iri
        where {{
            BIND(<{expdition_iri}> AS ?expedition_iri)
    
            ?expedition_iri rdfs:label ?label ;
                            crm:P14_carried_out_by ?group ;
                            crm:P7_took_place_at  ?location ;
                            crm:P4_has_time-span ?timespan .
            ?timespan crm:P82a_begin_of_the_begin ?expedition_begin .
            ?timespan crm:P82b_end_of_the_end ?expedition_end .
            ?group rdfs:label ?group_label .
            ?location crm:P1_is_identified_by ?location_name_resource.
            ?location owl:sameAs ?location_wiki_iri .
            ?location_name_resource crm:P190_has_symbolic_content ?location_name .
            ?group crm:P107_has_current_or_former_member ?group_member .
            ?group_member schema:name ?member_name .
            ?curation crm:P9_consists_of ?expedition_iri .
            ?collection_iri crm:P147i_was_curated_by ?curation .
    
        }} limit 100
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

            "error": "Failed to retrieve the expedition metadata",

            "details": str(error)

        }, 502

    except ValueError:
        return {"error": "Invalid response from GraphDB"}, 502


    bindings = results.get("results", {}).get("bindings", [])
    expedition_metadata = {'location': [], "members": []}
    seen_locations = set()
    seen_members = set()
    for binding in bindings:
        expedition_metadata['label'] = get_value(binding, "label")
        expedition_metadata['group_label'] = get_value(binding, "group_label")
        location_name = get_value(binding, "location_name")
        if location_name and location_name not in seen_locations:
            expedition_metadata['location'].append({'name':location_name, 'wiki_iri':get_value(binding, "location_wiki_iri")})
            seen_locations.add(location_name)
        member_name = get_value(binding, "member_name")
        if member_name and member_name not in seen_members:
            expedition_metadata['members'].append(member_name)
            seen_members.add(member_name)
        expedition_metadata['expedition_begin'] = get_value(binding, "expedition_begin")
        expedition_metadata['expedition_end'] = get_value(binding, "expedition_end")
        expedition_metadata['collection_iri'] = get_value(binding, "collection_iri")
    return expedition_metadata, 200


def get_images_by_expedition(expedition_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", expedition_id):
        return {"error": "Invalid expedition ID"}, 400
    expedition_iri = f"{DATA_NAMESPACE}{expedition_id}"
    sparql_query = f"""
    PREFIX ga: <{DATA_NAMESPACE}>
    PREFIX : <{ONTOLOGY_NAMESPACE}>
    PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>
    SELECT DISTINCT ?image ?image_url ?title
    WHERE {{
    
        ?production crm:P9i_forms_part_of <{expedition_iri}> .
        ?image crm:P108i_was_produced_by ?production ;
                :hasDigitalRepresentation ?image_url ;
                :title ?title .
    
    }} ORDER BY ?image
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

class Expedition(Resource):

    def get(self, expedition_id):
        expedition_info, status = get_expedition(expedition_id)
        if status == 200:
            images_info, status = get_images_by_expedition(expedition_id)
            if status != 200:
                return expedition_info, 200
            else:
                return {**expedition_info, **images_info}
        else:
            return None
