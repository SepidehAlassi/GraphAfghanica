
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

def get_image(image_id):
    image_iri = f"{DATA_NAMESPACE}{image_id}"
    sparql_query = f"""
        PREFIX : <{ONTOLOGY_NAMESPACE}>
        PREFIX crm: <http://www.cidoc-crm.org/cidoc-crm/>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX schema: <http://schema.org/>
        PREFIX ga: <http://www.graphAfghanica.org/data/>
        PREFIX : <http://www.graphAfghanica.org/ontology/>
        select DISTINCT ?collection ?image_url ?title ?legend ?classification  ?classification_model ?classification_confidence ?width ?height ?quality ?description_creator_name ?description_confidence ?references ?photographer_name ?location_name ?location_wiki_iri ?time_span_begin ?time_span_end
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

    except requests.exceptions.RequestException as error:
        return {
            "error": "Failed to retrieve the image metadata:",
            "details": str(error)
        }, 502

    except ValueError:
        return {"error": "Invalid response from GraphDB"}, 502

    image_metadata = {'references': [], 'description': [], 'classification': []}
    for binding in results.get("results", {}).get("bindings", []):
        image_metadata['iri'] = image_iri
        image_metadata['collection'] = binding["collection"]["value"]
        image_metadata['image_url'] = binding["image_url"]["value"]
        image_metadata['title'] = binding["title"]["value"]
        image_metadata['legend'] = binding["legend"]["value"]
        if binding["classification"]["value"] is not None:
            classification_info = set()
            classification_info.add(binding["classification"]["value"])
            if binding["classification_model"]["value"] is not None:
                classification_info.add(binding["classification_model"]["value"])
            if binding["classification_confidence"]["value"] is not None:
                classification_info.add(binding["classification_confidence"]["value"])
            image_metadata['classification'].append(classification_info)

        image_metadata['width'] = binding["width"]["value"]
        image_metadata['height'] = binding["height"]["value"]
        image_metadata['quality'] = binding["quality"]["value"]
        if binding["description"]["value"] is not None:
            description_info = set()
            description_info.add(binding["description"]["value"])
            if binding["description_creator_name"]["value"] is not None:
                description_info.add(binding["description_creator_name"]["value"])
            if binding["description_confidence"]["value"] is not None:
                description_info.add(binding["description_confidence"]["value"])
            image_metadata['description'].append(description_info)
        if binding["references"]["value"] is not None:
            image_metadata['references'].append(binding["references"]["value"])
        image_metadata['photographer_name'] = binding["photographer_name"]["value"]
        image_metadata['location_name'] = binding["location_name"]["value"]
        image_metadata['location_wiki_iri'] = binding["location_wiki_iri"]["value"]
        image_metadata['time_span_begin'] = binding["time_span_begin"]["value"]
        image_metadata['time_span_end'] = binding["time_span_end"]["value"]
    return image_metadata, 200


class Image(Resource):

    def get(self, image_id):
        image_info, status = get_image(image_id)
        if status == 200:
            return image_info, 200
        else:
            return None
