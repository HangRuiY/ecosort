"""临时：查看 /text 接口返回的完整结构"""
import json
import requests

r = requests.post("http://localhost:8000/api/v1/text", json={"text": "沾了油的外卖塑料餐盒"}, timeout=15)
print(json.dumps(r.json(), ensure_ascii=False, indent=2))
