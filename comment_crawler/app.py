from flask import Flask, request
from flask_restx import Resource, Api, reqparse
from pymongo import MongoClient
from pprint import pprint
from mongodbAuth import AuthMongoClient

dbclient = AuthMongoClient
db = dbclient['comments']
cur = db['comments']

app = Flask(__name__)
api = Api(app)

parser = reqparse.RequestParser()
parser.add_argument('minlength', type=int, help="문장의 최소 길이 입니다.")
parser.add_argument('minlike', type=int, help="댓글의 최소 공감 개수 입니다.")
parser.add_argument('mintimestamp', type=int, help="댓글의 최소 날짜입니다.")
parser.add_argument('count', required=True, type=int, help="요청할 댓글 개수입니다.")
parser.add_argument('level', type=int, help="언론사의 최대 레벨입니다.")
parser.add_argument('tend', type=str, help="진보/보수를 결정합니다.")

@api.route('/comment')
class Comments(Resource):

    @api.expect(parser)
    def get(self):
        query = {}
        args = parser.parse_args()
        #query['normalized'] = { "$exists": "true" }

        if not args['minlength'] == None:
            query['$expr'] = {"$gte": [{"$strLenCP": "$text"}, args['minlength']]}

        if not args['minlike'] == None:
            query['like'] = {"$gte": args['minlike']}

        if not args['mintimestamp'] == None:
            query['timestamp'] = {"$gte": args['mintimestamp']}

        if not args['level'] == None:
            query['level'] = {"$lte": args['level']}

        if args['count'] < 0:
            return {
                "status": False,
                "reason": "COUNT_SHOULD_BE_POSITIVE"
            }

        res = []
        if args['tend'] == None:
            for i in range(0, 2):
                Q = query
                Q['tend'] = {"$eq": i}

                pprint(Q)
                res.extend(list(cur.find(Q).limit(int(args['count']/2))))
        
        else:
            if args['tend'] == "CON" or args['tend'] == "con":
                query['tend'] = {"$eq": 0}

            elif args['tend'] == "PRO" or args['tend'] == "pro":
                query['tend'] = {"$eq": 1}

            else:
                return {
                    "status": False,
                    "reason": "UNKNOWN_TEND"
                }

            res = list(cur.find(query).limit(args['count']))

        #pprint(res[0])
        print("{}개의 데이터를 쿼리하였습니다.".format(len(res)))
        return res

    def put(self):
        date = request.json.get('date')
        data = request.json.get('data')

        '''
        id : 댓글 고유 ID
        tend : 정치 성향 (보수/진보)
        date : 날짜 텍스트
        timestamp : date를 timestamp로 변환한 값
        text : 댓글 내용
        like : 공감 수
        dislike : 반대 수
        calculate : 추정 정치 성향 (보수/진보)
        press : 언론사 이름
        level : CON/PRO 언론사 index
        '''

        for row in data:
            rowdict = {
                "_id": row[0],
                "tend": row[1],
                "date": row[2],
                "timestamp": row[3],
                "text": row[4],
                "like": row[5],
                "dislike": row[6],
                "calculate": row[7],
                "press": row[8],
                "level": row[9]
            }

            cur.update_one(
                {"_id": rowdict['_id']},
                {"$set": rowdict},
                upsert = True
            )

        print("{}일 데이터 | {}개의 데이터를 데이터베이스에 쿼리하였습니다.".format(date, len(data)))

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)