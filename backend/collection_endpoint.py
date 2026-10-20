
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


def get_collection_metadata(collection_id):

    if not re.fullmatch(r"[A-Za-z0-9_-]+", collection_id):
        return {"error": "Invalid collection ID"}, 400

    collection_iri = f"{DATA_NAMESPACE}{collection_id}"

    sparql_query = f"""
        PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>

        SELECT DISTINCT ?collection_name
        WHERE {{
            <{collection_iri}>
                a crm:E78_Curated_Holding ;
                crm:P1_is_identified_by ?name_crm .

            ?name_crm
                crm:P190_has_symbolic_content ?collection_name .
        }}
        LIMIT 1
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

    return {
        "collection_id": collection_id,
        "collection_name": bindings[0]["collection_name"]["value"]
    }, 200


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
