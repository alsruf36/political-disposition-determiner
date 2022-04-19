from flask import Flask, request
from flask_restx import Resource, Api, reqparse

app = Flask(__name__)
api = Api(app)

parser = reqparse.RequestParser()
parser.add_argument('count', required=True, type=int, help="요청할 댓글 개수입니다.")

@api.route('/comment')
class Comments(Resource):

    @api.expect(parser)
    def get(self):
        args = parser.parse_args()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port="5001", debug=True)