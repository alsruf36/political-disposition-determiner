from pymongo import MongoClient
from mongodbAuth import AuthMongoClient
import dill
from tqdm import tqdm

dbclient = AuthMongoClient
db = dbclient['comments']
cur = db['comments']

with open("../data/pickle/normalize.pickle", 'rb') as f:
    res = dill.load(f)

    for i in tqdm(res):
        cur.update_one(
            {"_id": i['_id']},
            {"$set": i},
            upsert = True
        )