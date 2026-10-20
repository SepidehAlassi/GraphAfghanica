from flask import Flask
from flask_restful import Api, Resource
from image_endpoint import Image
from images_endpoint import Images
from collection_endpoint import Collection
from expedition_endpoint import Expedition

app = Flask(__name__)
api = Api(app)


class GraphAfghanica(Resource):
    def get(self):
        return {
            "name": "GraphAfghanica API",
            "version": "1.0"
        }, 200


api.add_resource(GraphAfghanica, "/")
api.add_resource(Images, "/images/")
api.add_resource(
    Collection,
    "/collections/<string:collection_id>"
)
api.add_resource(Image,  "/images/<string:image_id>")
api.add_resource(Expedition, "/expeditions/<string:expedition_id>/")
