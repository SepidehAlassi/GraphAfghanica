from flask_restful import Resource
import requests

GRAPHDB_ENDPOINT = "http://localhost:7200/repositories/GraphAfghanica"

DATA_NAMESPACE = "http://www.graphAfghanica.org/data/"


def get_images_by_collection(collection_id):


    collection_iri = f"{DATA_NAMESPACE}{collection_id}"

    sparql_query = """
      PREFIX : <http://www.graphAfghanica.org/ontology/>
      PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>

      SELECT ?image
      WHERE {
          <%s> a crm:E78_Curated_Holding .
          ?image :belongsTo <%s> .
      }
      """ % (collection_iri, collection_iri)

    try:
        response = requests.post(
            GRAPHDB_ENDPOINT,
            data={"query": sparql_query},
            headers={
                "Accept": "application/sparql-results+json"
            },
            timeout=30
        )
        print(response)
        response.raise_for_status()

    except requests.exceptions.Timeout:
        return {
            "error": "GraphDB request timed out"
        }, 504

    except requests.exceptions.ConnectionError:
        return {
            "error": "Could not connect to GraphDB"
        }, 503

    except requests.exceptions.HTTPError as error:
        return {
            "error": "GraphDB returned an error",
            "details": str(error)
        }, response.status_code

    except requests.exceptions.RequestException as error:
        return {
            "error": "GraphDB request failed",
            "details": str(error)
        }, 502

    try:
        bindings = response.json()["results"]["bindings"]
    except (ValueError, KeyError, TypeError):
        return {
            "error": "GraphDB returned an invalid response",
            "response": response.text[:500]
        }, 502

        # No rows means that the collection does not exist as an E78 holding.
    if not bindings:
        return {
            "error": "Collection not found",
            "collection_id": collection_id,
            "iri": collection_iri
        }, 404

    images = []

    for binding in bindings:
        image_binding = binding.get("image")

        # An existing collection with no images produces an unbound
        # optional ?image variable.
        if image_binding:
            image_iri = image_binding["value"]
            image_id = image_iri.rsplit("/", 1)[-1]

            images.append({
                "id": image_id,
                "iri": image_iri
            })

    collection_data = {
        "id": collection_id,
        "iri": collection_iri,
        "image_count": len(images),
        "images": images
    }

    return collection_data, 200


class Collection(Resource):
    def get(self, collection_id):
        return get_images_by_collection(collection_id), 200
