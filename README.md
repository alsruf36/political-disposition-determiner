# political-disposition-determiner

## Folders
- frontend : for frontend
- news_crawler : news crawler to suggest articles
- comment_crawler : comments crawler to make comment database
- colab_linker : A linker to offer API connected with google colab
- notebooks : colab notebooks

## Press
| **Level** | **Conservative** | **Progressive** |
|---------:|:----------------:|:---------------:|
| 0         | 조선일보             | 한겨례             |
| 1         | 중앙일보             | 프레시안            |
| 2         | 동아일보             | 오마이뉴스           |
| 3         | 문화일보             | 경향신문            |

## Crawl comments
For convenience, the code connecting to the server was separated into the following file : `mongodbAuth.py`.
```python
from pymongo import MongoClient

AuthMongoClient = MongoClient("mongodb://<ID>:<PASSWORD>@localhost:<PORT>", authSource="admin")
```

To crawl comments, the server starting to query the data to the database must be preceded.
```python
cd comment_crawler
python3 app.py
```

Then, modify the date range and level in the last line of `crawlerMONGODB.py`.
```python
python3 crawlerMONGODB.py
```

If you crawled using the depreciated code `crawlerSQLITE.py`, you have to combine the db into mongo db by using `dbupdate.py`.

## Deploy frontend to Heroku
```python
heroku login #Heroku에 로그인
heroku create <APP_NAME> #Heroku에 저장소가 없다면 생성
heroku git:remote <APP_NAME> #Heroku에 이미 저장소가 있다면 사용
heroku stack:set container #스택 유형 변경

git add .
git commit -m "heroku"
git push heroku master #Deploy 끝
```

## Run colab linker
```python
nano anvil_startup #origin과 uplin-key를 수정해준다. [https://github.com/anvil-works/anvil-runtime 참고]
su - <NON_ROOT_USER> #anvil runtime은 non root user이 실행해야 오류가 없다.
chmod +x anvil_startup

./anvil_startup
```
