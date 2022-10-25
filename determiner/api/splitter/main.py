import ray
from ray import serve
import json
import argparse
import kss
import starlette
from starlette.requests import Request

@serve.deployment
class splitter:
    def __call__(self, api_request) -> str:
        # Request came via an HTTP
        if isinstance(api_request, starlette.requests.Request):
            body = api_request.query_params['body']
        else:
            # Request came via a ServerHandle API method call.
            body = api_request

        return kss.split_sentences(body)
        

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='splitter')
    parser.add_argument('-r', '--ray_address', default='', type=str)
    parser.add_argument('-x', '--ray_port', default='10001', type=int)
    parser.add_argument('-d', '--api_name', default='splitter', type=str)
    parser.add_argument('-l', '--return_json', default=False, type=bool)
    parser.add_argument('-g', '--num_replicas', default=1, type=int)
    args = parser.parse_args()

    print("ray cluster에 연결합니다.")
    packages = ["kss"]
    ray.init(f"ray://{args.ray_address}:{args.ray_port}", runtime_env={"pip": packages})
    serve.start(detached=True, http_options={"host": "0.0.0.0"})

    splitter.options(name=args.api_name, num_replicas=args.num_replicas).deploy()

    serve_list = serve.list_deployments()

    if args.return_json == True:
        with open("/airflow/xcom/return.json", "w") as file:
            json.dump(serve_list, file)