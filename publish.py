"""Публикация TOPIKLAB в Instagram и Threads через официальные API Meta.
Запускается GitHub Actions каждые 10 минут: публикует пункты schedule.json, чьё время наступило
(не старше 3 часов), и записывает результат в state.json.

Аккаунты (ключ "account"): ig_ru, ig_en, th_ru, th_en. Для каждого в секретах репозитория:
  <ACCOUNT>_ID и <ACCOUNT>_TOKEN, например IG_RU_ID, IG_RU_TOKEN.
Переменная MEDIA_BASE: адрес GitHub Pages, где лежит папка media (например https://user.github.io/topiklab-publish).
Типы: reel (видео), carousel (2–10 картинок JPEG), text (Threads), image (одна картинка).
Локальная проверка без публикации: python3 publish.py --dry
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
KST = timezone(timedelta(hours=9))
IG = "https://graph.instagram.com/v23.0"
TH = "https://graph.threads.net/v1.0"
DRY = "--dry" in sys.argv
WINDOW = timedelta(hours=3)


def call(method, url, params):
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{e.code} {e.read().decode()[:400]}")


def creds(acc):
    a = acc.upper()
    return os.environ[f"{a}_ID"], os.environ[f"{a}_TOKEN"]


def media_url(path):
    base = os.environ["MEDIA_BASE"].rstrip("/")
    return base + "/" + urllib.parse.quote(path)


def ig_wait(cid, tok, limit=600):
    t0 = time.time()
    while time.time() - t0 < limit:
        s = call("GET", f"{IG}/{cid}", {"fields": "status_code,status", "access_token": tok})
        if s.get("status_code") == "FINISHED":
            return
        if s.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"контейнер {cid}: {s}")
        time.sleep(10)
    raise RuntimeError(f"контейнер {cid}: не дождались обработки")


def post_ig(item):
    uid, tok = creds(item["account"])
    cap = item.get("caption", "")
    if item["type"] == "reel":
        p = {"media_type": "REELS", "video_url": media_url(item["media"][0]), "caption": cap,
             "share_to_feed": "true", "access_token": tok}
        if item.get("cover"):
            p["cover_url"] = media_url(item["cover"])
        cid = call("POST", f"{IG}/{uid}/media", p)["id"]
        ig_wait(cid, tok)
    elif item["type"] == "carousel":
        kids = []
        for m in item["media"][:10]:
            k = call("POST", f"{IG}/{uid}/media", {"image_url": media_url(m), "is_carousel_item": "true", "access_token": tok})["id"]
            kids.append(k)
        for k in kids:
            ig_wait(k, tok, 180)
        cid = call("POST", f"{IG}/{uid}/media", {"media_type": "CAROUSEL", "children": ",".join(kids), "caption": cap, "access_token": tok})["id"]
        ig_wait(cid, tok, 180)
    elif item["type"] == "image":
        cid = call("POST", f"{IG}/{uid}/media", {"image_url": media_url(item["media"][0]), "caption": cap, "access_token": tok})["id"]
        ig_wait(cid, tok, 180)
    else:
        raise RuntimeError(f"тип {item['type']} не поддерживается в Instagram")
    return call("POST", f"{IG}/{uid}/media_publish", {"creation_id": cid, "access_token": tok})["id"]


def post_th(item):
    uid, tok = creds(item["account"])
    p = {"media_type": "TEXT", "text": item.get("caption", ""), "access_token": tok}
    if item["type"] == "reel":
        p.update(media_type="VIDEO", video_url=media_url(item["media"][0]))
    elif item["type"] == "image":
        p.update(media_type="IMAGE", image_url=media_url(item["media"][0]))
    if item.get("topic"):
        p["topic_tag"] = item["topic"]
    try:
        cid = call("POST", f"{TH}/{uid}/threads", p)["id"]
    except RuntimeError as e:
        if "topic_tag" not in p:
            raise
        print(f"  тема не принята ({e}), публикую без темы")
        p.pop("topic_tag")
        cid = call("POST", f"{TH}/{uid}/threads", p)["id"]
    if item["type"] != "text":
        time.sleep(30)  # Meta советует подождать обработку медиа
    return call("POST", f"{TH}/{uid}/threads_publish", {"creation_id": cid, "access_token": tok})["id"]


def main():
    sched = json.loads((ROOT / "schedule.json").read_text())
    sp = ROOT / "state.json"
    state = json.loads(sp.read_text()) if sp.exists() else {}
    now = datetime.now(timezone.utc)
    changed = False
    for it in sched:
        key = it["id"]
        if state.get(key, {}).get("ok"):
            continue
        at = datetime.fromisoformat(it["time"]).replace(tzinfo=KST)
        if DRY:
            print(f"{at:%d.%m %H:%M} {it['account']:5} {it['type']:8} {key}  media={len(it.get('media', []))}")
            continue
        if at > now or now - at > WINDOW:
            continue
        a = it["account"].upper()
        if not (os.environ.get(f"{a}_ID") and os.environ.get(f"{a}_TOKEN") and os.environ.get("MEDIA_BASE")):
            print(f"пропуск {key}: нет ключей для {a}, жду (попытка не считается)")
            continue
        tries = state.get(key, {}).get("tries", 0)
        if tries >= 3:
            continue
        print(f"→ {key} ({it['account']}, {it['type']}, {at:%d.%m %H:%M} KST)")
        try:
            pid = post_ig(it) if it["account"].startswith("ig") else post_th(it)
            state[key] = {"ok": True, "post_id": pid, "at": now.isoformat()}
            print(f"  опубликовано: {pid}")
        except Exception as e:  # пишем ошибку и пробуем ещё раз при следующем запуске (до 3 раз)
            state[key] = {"ok": False, "tries": tries + 1, "error": str(e)[:500], "at": now.isoformat()}
            print(f"  ОШИБКА: {e}")
        changed = True
    if changed:
        sp.write_text(json.dumps(state, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
