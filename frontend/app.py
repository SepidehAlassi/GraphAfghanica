
from flask import Flask, render_template, abort
import requests
import os

app = Flask(__name__)

API_URL = os.getenv("API_URL", "http://localhost:4000")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/collections/<string:collection_id>")
def collection(collection_id):

    try:
        response = requests.get(
            f"{API_URL}/collections/{collection_id}",
            timeout=30
        )
        response.raise_for_status()

        collection_data = response.json()

    except requests.exceptions.HTTPError as error:
        if error.response is not None and error.response.status_code == 404:
            abort(404, description="Collection not found")
        abort(502, description="API returned an error")

    except (requests.exceptions.RequestException, ValueError):
        abort(502, description="Could not retrieve collection data")

    return render_template(
        "collection.html",
        collection=collection_data
    )

@app.route("/events")
def events():
    symposium = {
        "title": "Digital Futures for Afghan Photographic Heritage",
        "date": "23 October 2026",
        "time": "14:00–18:00 CEST",
        "format": "Online via Zoom",
        "organizers": "Dr. Sepideh Alassi and Joël László, Digital Humanities Lab and University Library, University of Basel.",
        "description": (
            "This symposium explores digital approaches to the "
            "preservation, curation, interconnection, and scholarly "
            "exploration of historical Afghan photographic collections. "
            "It introduces the GraphAfghanica project and brings together "
            "researchers working on Afghan photographic heritage, "
            "digital archives, and computational approaches to cultural heritage."
        ),
        "flyers": [
            "images/GraphAfghanica_flyer1.png",
            "images/GraphAfghanica_flyer2.png"
        ],
        "register": 'https://forms.gle/g3hFg4RyczUfcA6d8'
    }

    return render_template("events.html", symposium=symposium)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3030, debug=True)
