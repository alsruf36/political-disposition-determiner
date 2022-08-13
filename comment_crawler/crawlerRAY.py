from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from datetime import datetime
from tqdm import tqdm
import requests
import sqlite3
import pandas
import time
import json
import ray

import os
import logging
import logging.handlers

def CreateLogger(loggerName):
    logger = logging.getLogger(loggerName)
    if len(logger.handlers) > 0:
        return logger

    logPath = os.path.join(os.path.realpath(""), "logs", loggerName + ".log")
    Mkdirs(logPath)

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(filename)s:%(lineno)s] %(asctime)s > %(levelname)s | %(message)s')

    streamHandler = logging.StreamHandler()
    streamHandler.setLevel(logging.INFO)
    streamHandler.setFormatter(formatter)
    rotatingHandler = logging.handlers.RotatingFileHandler(logPath, maxBytes=1024 * 1024 * 1024)
    rotatingHandler.setLevel(logging.DEBUG)
    rotatingHandler.setFormatter(formatter)

    logger.addHandler(streamHandler)
    logger.addHandler(rotatingHandler)
    return logger

def Mkdirs(filePath):
    dirPath = os.path.sep.join(filePath.split(os.path.sep)[:-1])
    if not os.path.exists(dirPath):
        os.makedirs(dirPath, exist_ok = True)

@ray.remote
class Crawler:
    def __init__(self):
        self.ARTICLE_URL = "https://news.naver.com/main/list.nhn?mode=LS2D&mid=shm&sid2=269&sid1=100&date={}&page={}"
        self.COMMENT_URL = "https://apis.naver.com/commentBox/cbox/web_neo_list_jsonp.json?ticket=news&templateId=view_politics&pool=cbox5&_callback=_callback&lang=ko&country&objectId=news{}%2C{}&includeAllStatus=true&pageSize=100&pageType=more&page={}"
        self.HEADER = {
            'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36',
            'accept' : "*/*",
            'accept-encoding' : 'gzip, deflate, br',
            'accept-language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'referer' : 'https://news.naver.com/main/read.nhn?m_view=1&includeAllCount=true&mode=LSD&mid=shm&sid1=102&oid=119&aid=0002479801'  #이거 안넣으면 거부당함!
        }

        #인덱스가 작은 언론사일수록 한 쪽에 치우친 정도가 큰 언론사이다.
        self.CON = ['조선일보', '중앙일보', '동아일보', '문화일보']   #보수
        self.PRO = ['한겨레', '프레시안', '오마이뉴스', '경향신문']   #진보
        self.PORTAL = ['네이버', '다음']

        self.DBURL = "http://localhost:5000/comment"
        self.logger = CreateLogger("crawler")

    def getArticles(self, date, level):
        page = 1
        total_list = []
        prev_list = []

        if level > len(self.CON) or level > len(self.PRO):
            self.logger.error("성향 레벨이 언론사 수보다 큽니다.")
            raise Exception("성향 레벨이 언론사 수보다 큽니다.")

        while(True):
            URL = self.ARTICLE_URL.format(date, page)
            html = requests.get(URL, headers = self.HEADER)  #여기서 예외처리
            soup = BeautifulSoup(html.content, 'html.parser')
            temp_list = [[x.find('a').get('href'), x.find('span', {"class": "writing"}).text] for x in soup.select_one('#main_content > div.list_body.newsflash_body').find_all('li')]
            
            if(temp_list == prev_list):
                break

            else:
                prev_list = temp_list
                total_list.extend(temp_list)
                page += 1

            self.logger.debug("다음 페이지를 파싱중입니다 : {} / {}개의 Articles를 찾았습니다.".format(page, len(total_list)))

        ArticleURLs = total_list
        ArticlePARAMs = []

        for url in ArticleURLs:
            url_split = url[0].split("/")
            ArticlePARAMs.append([url_split[5], url_split[6].split("?")[0], url[1]])

        CONPARAMs = [x for x in ArticlePARAMs if x[2] in self.CON[:level]]
        PROPARAMs = [x for x in ArticlePARAMs if x[2] in self.PRO[:level]]

        return CONPARAMs, PROPARAMs

    def getComments(self, oid, aid):
        page = 1
        comment_raw_list = []

        while(True):
            URL = self.COMMENT_URL.format(oid, aid, page)
            response = requests.get(URL, headers=self.HEADER)
            code = response.status_code

            if code == 200:
                html = response.text
                html = html.replace("_callback(","")[:-2]
                response_dict = json.loads(html)
                comments_dict = response_dict['result']['commentList']
                comment_raw_list.extend(comments_dict)

                self.logger.debug("다음 페이지의 API를 호출중입니다 : {} / {}개의 Comments를 찾았습니다.".format(page, len(comment_raw_list)))
                page += 1

                if(len(comments_dict) < 100):
                    break
            
            else:
                self.logger.debug(html)
                self.logger.debug("반환 오류!")
                raise Exception("반환 오류!")

        self.logger.debug("{}개의 댓글들을 찾았습니다.".format(len(comment_raw_list)))
        comment_list = [[x['contents'], x['sympathyCount'], x['antipathyCount'], x['commentNo'], x['regTime']] for x in comment_raw_list]
        return comment_list

    def getCommentsByDate(self, date, level):
        CONcomments = []
        PROcomments = []
        CONindex = lambda x: self.CON.index(x)
        PROindex = lambda x: self.PRO.index(x)
        CONPARAMs, PROPARAMs = self.getArticles(date, level)
        self.logger.info("{}개의 Article들을 찾았습니다.".format(len(CONPARAMs) + len(PROPARAMs)))

        for article in CONPARAMs:
            comments = self.getComments(article[0], article[1])
            for comment in comments:
                comment.append(article[2])
                comment.append(CONindex(article[2]))

            if len(comments) > 50:
                CONcomments.extend(comments)

            else:
                self.logger.debug("댓글 개수가 너무 적습니다.")

        for article in PROPARAMs:
            comments = self.getComments(article[0], article[1])
            for comment in comments:
                comment.append(article[2])
                comment.append(PROindex(article[2]))

            if len(comments) > 50:
                PROcomments.extend(comments)

            else:
                self.logger.debug("댓글 개수가 너무 적습니다.")
            
        self.logger.info("{}개의 댓글들을 찾았습니다.".format((len(PROcomments) + len(CONcomments))))
        return CONcomments, PROcomments

    def crawlDate(self, date, level):
        tries = 5
        tried = 0

        self.logger.info("{}일의 정보를 받아옵니다.".format(date))
        while tried <= tries:
            try:
                CONcomments, PROcomments = self.getCommentsByDate(date, level)
                break
            except Exception as e:
                print(e)
                self.logger.error("네트워크 에러가 났습니다. 다시 시도합니다.")
                tried += 1

        comments = []
        for x in CONcomments:
            x.extend([0, date])

        for x in PROcomments:
            x.extend([1, date])

        comments.extend(CONcomments)
        comments.extend(PROcomments)

        return comments

def dateDevide(start, end):
    start = datetime.strptime(start, "%Y%m%d")
    end = datetime.strptime(end, "%Y%m%d")
    dates = [date.strftime("%Y%m%d") for date in pandas.date_range(start, periods=(end-start).days+1)]
    return dates

def crawlMulti(start, end, level):
    dates = dateDevide(start, end)
    dates = reversed(dates)

    resultFuture = [ Crawler.remote().crawlDate.remote(date, level) for date in dates ]
    result = ray.get(resultFuture)
    result = result[0]

    print(result)
    print(str(len(result)))

if __name__=='__main__':
    ray.init("ray://:10001")
    crawlMulti("20200101", "20220501", 4)