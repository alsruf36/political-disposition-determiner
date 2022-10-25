import ray
from ray import serve
import json
import argparse
import requests
from pymongo import MongoClient
import starlette
from starlette.requests import Request

@serve.deployment
class community:
    def __init__(self, mongodb_address):
        AuthMongoClient = MongoClient(mongodb_address, authSource="admin")
        dbclient = AuthMongoClient
        db = dbclient['community']
        self.cur = db['dcinside']

    def __call__(self, api_request) -> str:
        def get_article_list(limit, gallId):
            queue = {"galleryID": {"$eq": gallId}}
            res = list(self.cur.find(queue).limit(limit))
            return res

        def analyze_tend_with_limit(limit, gallId):
            res = get_article_list(limit, gallId)
            
            cons = 0
            pros = 0
            nones = 0
            for r in res:
                if r['tend'] == 0:
                    cons +=  1
                    
                elif r['tend'] == 1:
                    pros += 1
                    
                else:
                    nones += 1
                    
            cons_percent = float(cons)/float(cons + pros)
            cons_percent = round(cons_percent,3)
            pros_percent = float(1) - cons_percent
            
            ret = {
                "cons": cons,
                "pros": pros,
                "nones": nones,
                "cons_percent": cons_percent * 100,
                "pros_percent": pros_percent * 100
            }

            print(ret)
            return ret

        # Request came via an HTTP
        if isinstance(api_request, starlette.requests.Request):
            query = api_request.query_params['query']
            gallId = api_request.query_params['gallid']
            limit = int(api_request.query_params['limit'])
        else:
            # Request came via a ServerHandle API method call.
            body = api_request

        if query == "list":
            return get_article_list(limit, gallId)

        if query == "tend":
            return analyze_tend_with_limit(limit, gallId)

        else:
            return "NO_OPTION_ERROR"
        

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='community')
    parser.add_argument('-r', '--ray_address', default='', type=str)
    parser.add_argument('-x', '--ray_port', default='10001', type=int)
    parser.add_argument('-d', '--api_name', default='community', type=str)
    parser.add_argument('-l', '--return_json', default=False, type=bool)
    parser.add_argument('-g', '--num_replicas', default=1, type=int)
    parser.add_argument('-m', '--mongodb_id', default='id', type=str)
    parser.add_argument('-n', '--mongodb_pass', default='pass', type=str)
    parser.add_argument('-o', '--mongodb_ip', default='10.26.0.189', type=str)
    parser.add_argument('-p', '--mongodb_port', default=27010, type=int)
    args = parser.parse_args()

    print("ray cluster에 연결합니다.")
    packages = ["pymongo"]
    ray.init(f"ray://{args.ray_address}:{args.ray_port}", runtime_env={"pip": packages})
    serve.start(detached=True, http_options={"host": "0.0.0.0"})

    mongodb_address = f"mongodb://{args.mongodb_id}:{args.mongodb_pass}@{args.mongodb_ip}:{args.mongodb_port}"
    community.options(name=args.api_name, num_replicas=args.num_replicas).deploy(mongodb_address)

    serve_list = serve.list_deployments()

    if args.return_json == True:
        with open("/airflow/xcom/return.json", "w") as file:
            json.dump(serve_list, file)