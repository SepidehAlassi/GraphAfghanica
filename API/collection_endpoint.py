from flask_restful import Resource


class Collection(Resource):
    def get(self, collection_id):
        return {'collection': collection_id}, 200
