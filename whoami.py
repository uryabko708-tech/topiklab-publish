"""Узнать ID аккаунта по маркеру: python3 whoami.py ig <маркер>  |  python3 whoami.py th <маркер>
Маркер никуда не сохраняется."""
import json, sys, urllib.request

kind, tok = sys.argv[1], sys.argv[2]
url = {"ig": "https://graph.instagram.com/v23.0/me?fields=user_id,username",
       "th": "https://graph.threads.net/v1.0/me?fields=id,username"}[kind]
print(json.loads(urllib.request.urlopen(f"{url}&access_token={tok}", timeout=30).read()))
