import ray
from ray import serve
import json
import argparse
import kss
import starlette
from starlette.requests import Request

import requests
from bs4 import BeautifulSoup, Comment
from typing import List
from textrankr import TextRank
import random
import kss
from pprint import pprint
import re

class ShortContentError(Exception):
    pass

class ArticleListCrawler:
    def __init__(self, count):
        custom_header = {
          'referer' : 'https://www.naver.com/',
          'user-agent' : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'
        }

        list_href = []
        result = []

        section = "정치"
        req = self.get_request(section)
        soup = BeautifulSoup(req.text, "html.parser")

        list_href = self.get_href(soup)

        target = random.randrange(0, count)
        target_url = list_href[target]
        print(target_url)
        oid = target_url.split('/')[5]
        aid = target_url.split('/')[6].split('?')[0]
        print(oid)
        print(aid)

        self.ids = {
          "oid": oid,
          "aid": aid
        }

    def get_href(self, soup) :
        result = []

        div = soup.find("div", class_="list_body newsflash_body")

        for dt in div.find_all("dt", class_="photo"):
            result.append(dt.find("a")["href"])

        return result

    def get_request(self, section) :
        custom_header = {
          'referer' : 'https://www.naver.com/',
          'user-agent' : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.103 Safari/537.36'
        }

        url = "https://news.naver.com/main/list.nhn"

        sections = {
          "정치" : 100,
          "경제" : 101,
          "사회" : 102,
          "생활" : 103,
          "세계" : 104,
          "과학" : 105
        }

        req = requests.get(url, headers = custom_header,
              params = {"sid1" : sections[section]})

        return req

class MyTokenizer:
    def __call__(self, text: str) -> List[str]:
        tokens: List[str] = text.split()
        return tokens

def summarize(text, line):
    mytokenizer: MyTokenizer = MyTokenizer()
    textrank: TextRank = TextRank(mytokenizer)

    summaries: List[str] = textrank.summarize(text, line, verbose=False)
    return summaries

def getArticle(try_n, content_min_len):
    cnt = 0
    
    while cnt <= try_n:
        try:
            ids = ArticleListCrawler(20).ids
            
            url = 'https://news.naver.com/main/read.nhn?mode=LSD&mid=sec&sid1=100&oid={}&aid={}'.format(ids['oid'], ids['aid'])
            r = requests.get(url, headers={'User-Agent':'Mozilla/5.0'})
            soup = BeautifulSoup(r.text, 'html.parser')

            title = soup.select_one('.media_end_head_headline').text
            content = soup.select_one('#newsct_article').text
            print(len(content))
            if len(content) < content_min_len:
                raise ShortContentError(f"본문의 길이가 너무 짧습니다. (길이 : {len(content)}")
            
            try:
                subtitle = content.select_one('strong')
            except:
                subtitle = None
            if subtitle is not None: subtitle = subtitle.extract().text
            break

        except Exception as e:
            cnt += 1
            print(f"Error로 인하여 다시 시도합니다. (try : {cnt})")
            print(e)

    content = content.strip()                                                  # 앞뒤 공백 제거
    content= " ".join(re.split("\s+", content, flags=re.UNICODE))
    print(content)
    content = kss.split_sentences(content)                                     # 문장 단위로 분리
    summary = summarize("\n".join(content), 5)                                 # 문장 요약

    return {
      "title": title,
      "subtitle": subtitle,
      "content": content,
      "summary": summary
    }

@serve.deployment
class news:
    def __call__(self, api_request) -> str:
        # # Request came via an HTTP
        # if isinstance(api_request, starlette.requests.Request):
        #     body = api_request.query_params['body']
        # else:
        #     # Request came via a ServerHandle API method call.
        #     body = api_request

        return getArticle(5, 20)

if __name__=='__main__':
    parser = argparse.ArgumentParser(description='news')
    parser.add_argument('-r', '--ray_address', default='', type=str)
    parser.add_argument('-x', '--ray_port', default='10001', type=int)
    parser.add_argument('-d', '--api_name', default='news', type=str)
    parser.add_argument('-l', '--return_json', default=False, type=bool)
    parser.add_argument('-g', '--num_replicas', default=1, type=int)
    args = parser.parse_args()

    print("ray cluster에 연결합니다.")
    packages = ["textrankr", "bs4", "kss", "scipy"]
    ray.init(f"ray://{args.ray_address}:{args.ray_port}", runtime_env={"pip": packages})
    serve.start(detached=True, http_options={"host": "0.0.0.0"})

    news.options(name=args.api_name, num_replicas=args.num_replicas).deploy()

    serve_list = serve.list_deployments()

    if args.return_json == True:
        with open("/airflow/xcom/return.json", "w") as file:
            json.dump(serve_list, file)