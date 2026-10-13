
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


def get_images_by_collection(collection_id):

    # Validate the collection ID
    if not re.fullmatch(r"[A-Za-z0-9_-]+", collection_id):
        return {"error": "Invalid collection ID"}, 400

    # Construct the full RDF IRI
    collection_iri = f"{DATA_NAMESPACE}{collection_id}"

    sparql_query = f"""
        PREFIX : <{ONTOLOGY_NAMESPACE}>

        SELECT DISTINCT ?image
        WHERE {{
            ?image a :Image ;
                   :belongsTo <{collection_iri}> .
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

        images.append({
            "id": image_iri.rsplit("/", 1)[-1],
            "uri": image_iri
        })

    return {
        "collection_id": collection_id,
        "collection_iri": collection_iri,
        "image_count": len(images),
        "images": images
    }, 200


class Collection(Resource):

    def get(self, collection_id):
        return get_images_by_collection(collection_id)
