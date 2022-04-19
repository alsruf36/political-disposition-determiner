import demoji
from soynlp.normalizer import *
from hanspell import spell_checker
from pprint import pprint
import parmap

def remove_emoji(text):
    dem = demoji.findall(text)
    for item in dem.keys():
        text = text.replace(item, '')
    return text

def normalize(x):
    if not x["text"] == "":
        try:
            remove_emoji_text = remove_emoji(x["text"])
        except:
            remove_emoji_text = ""

    else:
        remove_emoji_text = ""

    if not remove_emoji_text == "":
        try:
            remove_repeat_text = emoticon_normalize(remove_emoji_text, num_repeats=2)
        except:
            remove_repeat_text = ""

    else:
        remove_repeat_text = ""

    return {
        "_id": x["_id"],
        "normalize": [
            {
                "level": 1,
                "text": remove_emoji_text
            },
            {
                "level": 2,
                "text": remove_repeat_text
            }
        ]
    }

if __name__=='__main__':
    from pymongo import MongoClient
    from mongodbAuth import AuthMongoClient
    import dill
    from tqdm.contrib.concurrent import process_map

    dbclient = AuthMongoClient
    db = dbclient['comments']
    cur = db['comments']

    x = cur.find({}, {"_id": 1, "text": 1})
    x = list(x)
    print("fetch가 완료되었습니다.")
    
    result = process_map(normalize, x, chunksize=1000, max_workers=200)

    with open("../data/pickle/normalize.pickle", 'wb') as f:
        dill.dump(result, f)

    print("저장이 완료되었습니다.")