from flask import Flask, jsonify
from flask_restful import Resource, Api
from collection_endpoint import Collection
from images_enpoint import Images

app = Flask(__name__)
api = Api(app)


class GraphAfghanica(Resource):

    def get(self):
        return {"name": "GraphAfghanica API",
                "version": "1.0"}, 200


api.add_resource(GraphAfghanica,
                 '/')
api.add_resource(Images, '/images/',
                 '/images/<string:image_id>')
api.add_resource(Collection, '/collections/<string:collection_id>')

if __name__ == '__main__':
    app.run(debug=True)
