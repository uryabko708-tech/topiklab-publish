"""Сохранить маркер Meta в секреты GitHub, не показывая его.
1) Скопируйте маркер (Cmd+C) на странице Meta.  2) Запустите: python3 set_secret.py th_ru   (th_ru | th_en | ig_ru | ig_en)
Скрипт берёт маркер из буфера обмена, узнаёт ID и имя аккаунта, кладёт <ACC>_TOKEN и <ACC>_ID в секреты репозитория,
очищает буфер. На экран выводится только имя аккаунта и ID."""
import json, subprocess, sys, urllib.request

REPO = "uryabko708-tech/topiklab-publish"
acc = sys.argv[1].lower()
assert acc in ("th_ru", "th_en", "ig_ru", "ig_en"), "аккаунт: th_ru, th_en, ig_ru или ig_en"
tok = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout.strip()
assert len(tok) > 40 and " " not in tok, "в буфере нет маркера: скопируйте его на странице Meta"
if acc.startswith("th"):
    me = json.loads(urllib.request.urlopen(f"https://graph.threads.net/v1.0/me?fields=id,username&access_token={tok}", timeout=30).read())
    uid = me["id"]
else:
    me = json.loads(urllib.request.urlopen(f"https://graph.instagram.com/v23.0/me?fields=user_id,username&access_token={tok}", timeout=30).read())
    uid = me["user_id"]
for name, val in ((f"{acc.upper()}_TOKEN", tok), (f"{acc.upper()}_ID", str(uid))):
    subprocess.run(["gh", "secret", "set", name, "-R", REPO], input=val, text=True, check=True, capture_output=True)
subprocess.run(["pbcopy"], input="", text=True)
print(f"OK: {acc} = @{me.get('username')} (id {uid}). Секреты {acc.upper()}_TOKEN и {acc.upper()}_ID сохранены, буфер очищен.")
