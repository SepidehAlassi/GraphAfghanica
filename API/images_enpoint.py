from flask_restful import Resource, Api
import requests


GRAPHDB_ENDPOINT = "http://localhost:7200/repositories/GraphAfghanica"

IMAGE_NAMESPACE = "http://www.graphAfghanica.org/data/"


def get_image_id(image_id):
    image_iri = f"{IMAGE_NAMESPACE}{image_id}"

    sparql_query = """
      PREFIX : <http://www.graphAfghanica.org/ontology/>

      SELECT ?property ?value
      WHERE {
          <%s> a :Image ;
            ?property ?value .
      }
      """ % image_iri

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

    results = response.json()["results"]["bindings"]

    if not results:
        return {
            "error": "Image not found",
            "image_id": image_id
        }, 404

    image_data = {
        "id": image_id,
        "iri": image_iri
    }

    for binding in results:
        property_iri = binding["property"]["value"]
        value = binding["value"]["value"]

        property_name = property_iri.rsplit("/", 1)[-1]
        property_name = property_name.rsplit("#", 1)[-1]
        if property_name == 'P3_has_note':
            continue
        if property_name in image_data:
            if not isinstance(image_data[property_name], list):
                image_data[property_name] = [
                    image_data[property_name]
                ]

            image_data[property_name].append(value)
        else:
            image_data[property_name] = value

    return image_data, 200


class Images(Resource):
    def get(self, image_id=None):
        if image_id is not None:

            return {'image_id': get_image_id(image_id)}, 200
        else:
            return {'GraphAfghanica': 'All images of GraphAfghnica'}, 200
