"""Ссылки с метками через API marketing.topiklab.com (ключ: ~/.config/topiklab/marketing.env, в репозиторий не кладётся).
  python3 make_link.py --presets                       список размещений (preset)
  python3 make_link.py --preset "TikTok · профиль" --site info --url https://info.topiklab.com/ --name "TikTok EN · профиль"
      [--campaign "Соцсети → сайт"] [--preview]       --preview: показать метки, ничего не создавая
--site: info (лендинг), web (платформа), telegram, external. По умолчанию кампания «Соцсети → сайт · 17.11–28.12».
Печатает короткую ссылку go.topiklab.com/… и куда она ведёт."""
import argparse, json, uuid, urllib.request
from pathlib import Path

ENV = dict(l.strip().split("=", 1) for l in (Path.home() / ".config/topiklab/marketing.env").read_text().splitlines() if "=" in l)
BASE = ENV["MARKETING_API_BASE_URL"].strip().strip('"').rstrip("/")
TOKEN = ENV["MARKETING_API_TOKEN"].strip().strip('"')


def api(method, path, body=None, extra=None):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", **(extra or {})}
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=h)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Ошибка API {e.code}: {e.read().decode()[:300]}")


def items(x):
    return x if isinstance(x, list) else x.get("data", x)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--presets", action="store_true")
    a.add_argument("--preset")
    a.add_argument("--site", default="info", choices=["info", "web", "telegram", "external"])
    a.add_argument("--url")
    a.add_argument("--name")
    a.add_argument("--campaign", default="Соцсети → сайт")
    a.add_argument("--preview", action="store_true")
    o = a.parse_args()
    presets = items(api("GET", "/api/placement-templates"))
    if o.presets:
        for p in presets:
            print(f"{p['label']}  [{p['source']}/{p['medium']}/{p['placement']}]")
        return
    p = [x for x in presets if o.preset.lower() in x["label"].lower()]
    if len(p) != 1:
        raise SystemExit(f"preset «{o.preset}»: найдено {len(p)}; уточните (--presets)")
    c = [x for x in items(api("GET", "/api/campaigns")) if o.campaign.lower() in x["name"].lower() and x.get("status") != "archived"]
    if len(c) != 1:
        raise SystemExit(f"кампания «{o.campaign}»: найдено {len(c)}")
    body = {"campaignId": c[0]["id"], "name": o.name or p[0]["label"], "targetSite": o.site, "preset": p[0]["id"],
            "placementUrl": None, "note": None, "destinationUrl": o.url}
    if o.preview:
        r = api("POST", "/api/links/preview", body)
        print(f"ПРЕДПРОСМОТР (не создано): {r['destinationUrl']}")
        return
    r = api("POST", "/api/links", body, {"idempotency-key": uuid.uuid4().hex})
    print(f"{r['shortUrl']}  →  {r['destinationUrl']}")


if __name__ == "__main__":
    main()
