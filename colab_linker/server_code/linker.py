import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server

@anvil.server.http_endpoint("/article", methods=["GET"], enable_cors=True)
def getArticles():
  if anvil.server.request.method == 'GET':
    try:
      result = anvil.server.call("getArticle")
      return {
        "status": "success",
        "result": result
      }

    except Exception as e:
      return {
        "status": "fail",
        "reason": str(e)
      }

@anvil.server.http_endpoint("/analyze", methods=["GET"], enable_cors=True)
def analyze(**data):
  if anvil.server.request.method == 'GET':
    try:
      result = anvil.server.call("predicter", data['text'])
      return {
        "status": "success",
        "result": result
      }

    except Exception as e:
      return {
        "status": "fail",
        "reason": str(e)
      }

@anvil.server.http_endpoint("/heartbeat", methods=["GET"], enable_cors=True)
def analyze():
  if anvil.server.request.method == 'GET':
    return {
      'live': "true"
    }