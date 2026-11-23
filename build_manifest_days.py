"""Добавляет в schedule.json записи из новой структуры «Выкладка/<гггг-мм-дд>» (старый build_manifest.py не затрагивается).
python3 build_manifest_days.py [--from 2026-11-24] [--to 2026-12-03] [--threads "../04 Threads/_посты_24.11-03.12 v3.json"] [--dry-build]
- Reels: Выкладка/<дата>/Instagram/«15.00 …mp4» и «19.00 …mp4»; подпись берётся из блока Подписи.txt (блоки по порядку,
  время блока = время файла), обложка «<ЧЧ.00> Обложка <имя ролика>.png» → JPEG.
- Карусели: Выкладка/<дата>/Карусель/NN.png (Обзор.png не берём) + Подписи.txt (заголовок «== …», дальше подпись), время 12:00.
- Threads RU: JSON как _посты_28.json, поле msk = время Сеула, day = число (01–03 → декабрь), тема из поля topic, если есть.
- Идемпотентно: id стабильные; записи с этими id заменяются, остальные (в т.ч. уже опубликованные) не трогаются. state.json не трогается.
"""
import hashlib, json, re, shutil, subprocess, sys
from datetime import datetime, date, timedelta
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
PROMO = ROOT.parent
YEAR = 2026
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
TAG = "24.11-03.12"
CAROUSEL_TIME = "12:00"
H_NEW = re.compile(r"^(?:==\s*\S.*|\d{2}\.\d{2}\s+\d{1,2}:\d{2}\s+·\s+.*)$")


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def split_blocks(txt):
    """Блоки: заголовок («== …» или «дд.мм ЧЧ:ММ · …») + строки подписи до следующего заголовка."""
    out, cur = [], None
    for line in txt.splitlines():
        if H_NEW.match(line.strip()):
            cur = {"title": line.strip().lstrip("= ").strip(), "lines": []}
            out.append(cur)
        elif cur is not None:
            cur["lines"].append(line)
    for b in out:
        b["caption"] = "\n".join(b["lines"]).strip()
    return out


def jpeg(src, dst):
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.open(src).convert("RGB").save(dst, "JPEG", quality=92)


def faststart(src, dst):
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(src), "-c", "copy", "-movflags", "+faststart", str(dst)], check=True)


def sid(*parts):
    return hashlib.md5("|".join(parts).encode()).hexdigest()[:6]


def build_days(d0, d1, bad):
    items = []
    days = sorted(p for p in (PROMO / "Выкладка").iterdir() if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name) and d0 <= p.name <= d1)
    for day in days:
        dd = date.fromisoformat(day.name)
        short = f"{dd:%d.%m}"
        ig = day / "Instagram"
        if ig.exists():
            videos = sorted(ig.glob("[0-9][0-9].[0-9][0-9] *.mp4"))
            videos = [v for v in videos if "Обложка" not in v.name]
            blocks = split_blocks((ig / "Подписи.txt").read_text(encoding="utf-8")) if (ig / "Подписи.txt").exists() else []
            by_time = {}
            for b in blocks:
                m = re.match(r"^(?:==\s*)?(?:\d{2}\.\d{2}\s+)?(\d{1,2})[.:](\d{2})\b", b["title"])
                if m:
                    by_time[f"{int(m.group(1)):02d}.{m.group(2)}"] = b
            for v in videos:
                hh, mm = v.name[:5].split(".")
                b = by_time.get(v.name[:5])
                if not b or not b["caption"]:
                    print(f"ОШИБКА {day.name}: нет подписи для «{v.name}» (блоки: {[x['title'] for x in blocks]}); запись не добавлена")
                    bad.append(f"{day.name} {v.name}")
                    continue
                name = v.stem[6:]
                iid = f"d{day.name}-ig_ru-{hh}{mm}-{sid(name)}"
                rel = f"media/{TAG}/{iid}"
                faststart(v, ROOT / rel / "video.mp4")
                item = {"id": iid, "account": "ig_ru", "type": "reel", "time": f"{day.name}T{hh}:{mm}",
                        "title": name, "caption": b["caption"], "media": [f"{rel}/video.mp4"]}
                cov = ig / f"{hh}.{mm} Обложка {name}.png"
                if cov.exists():
                    jpeg(cov, ROOT / rel / "cover.jpg")
                    item["cover"] = f"{rel}/cover.jpg"
                else:
                    print(f"ПРЕДУПРЕЖДЕНИЕ {day.name}: нет обложки для «{name}»")
                items.append(item)
        car = day / "Карусель"
        if (car / "Подписи.txt").exists():
            pngs = sorted(car.glob("[0-9][0-9].png"))
            blocks = split_blocks((car / "Подписи.txt").read_text(encoding="utf-8"))
            if not pngs or len(blocks) != 1:
                print(f"ОШИБКА {day.name}: карусель: слайдов {len(pngs)}, блоков {len(blocks)}"); bad.append(day.name); continue
            b = blocks[0]
            iid = f"d{day.name}-ig_ru-car-{sid(b['title'])}"
            rel = f"media/{TAG}/{iid}"
            media = []
            for i, f in enumerate(pngs, 1):
                jpeg(f, ROOT / rel / f"{i:02d}.jpg")
                media.append(f"{rel}/{i:02d}.jpg")
            items.append({"id": iid, "account": "ig_ru", "type": "carousel", "time": f"{day.name}T{CAROUSEL_TIME}",
                          "title": "Карусель · " + b["title"], "caption": b["caption"], "media": media})
    return items


def build_threads(path, d0, d1):
    out = []
    for p in json.loads(path.read_text(encoding="utf-8")):
        month = 12 if int(p["day"]) <= 5 else 11
        dt = datetime(YEAR, month, int(p["day"]), *map(int, p["msk"].split(":")))
        if not (d0 <= f"{dt:%Y-%m-%d}" <= d1):
            continue
        it = {"id": f"d{dt:%Y-%m-%d}-th_ru-{dt:%H%M}-n{p['n']}", "account": "th_ru", "type": "text",
              "time": dt.isoformat(timespec="minutes"), "caption": p["text"]}
        if p.get("topic"):
            it["topic"] = p["topic"]
        out.append(it)
    return out


def main():
    d0, d1 = arg("--from", "2026-11-24"), arg("--to", "2026-12-03")
    th = Path(arg("--threads", str(PROMO / "04 Threads" / "_посты_24.11-03.12 v3.json")))
    bad = []
    new = build_days(d0, d1, bad) + build_threads(th, d0, d1)
    sh = int(arg("--shift", "0"))  # сдвиг дат публикации в днях (пауза), id не меняются
    for n in new:
        n["time"] = (datetime.fromisoformat(n["time"]) + timedelta(days=sh)).isoformat(timespec="minutes")
    sp = ROOT / "schedule.json"
    old = json.loads(sp.read_text(encoding="utf-8"))
    ids = {n["id"] for n in new}
    kept = [o for o in old if o["id"] not in ids]
    sched = sorted(kept + new, key=lambda x: x["time"])  # sorted() стабилен: старые записи сохраняют порядок
    sp.write_text(json.dumps(sched, ensure_ascii=False, indent=1), encoding="utf-8")
    for n in sorted(new, key=lambda x: x["time"]):
        print(f"{n['time'][8:10]}.{n['time'][5:7]} {n['time'][11:]} {n['account']:5} {n['type']:8} {(n.get('title') or n['caption'])[:50]!r}")
    print(f"\nДобавлено/обновлено {len(new)} (ig reel {sum(n['type']=='reel' for n in new)}, carousel {sum(n['type']=='carousel' for n in new)}, "
          f"threads {sum(n['account']=='th_ru' for n in new)}), в файле всего {len(sched)}, ошибок {len(bad)}.")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
