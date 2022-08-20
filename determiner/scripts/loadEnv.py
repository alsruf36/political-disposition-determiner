import argparse
import json

parser = argparse.ArgumentParser(description='loadEnv')
parser.add_argument('-f', '--file', default='.env', type=str)
args = parser.parse_args()

with open("/tmp/" + args.file, 'r') as f:
    result = dict(tuple(line.replace('\n', '').split('=')) for line in f.readlines() if not line.startswith('#'))

with open("/airflow/xcom/return.json", "w") as file:
    json.dump(result, file)