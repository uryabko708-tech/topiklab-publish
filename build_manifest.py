"""Собирает schedule.json и папку media/ из недели в Выкладке (локально, перед git push).
python3 build_manifest.py "../Выкладка/Неделя 17-23.11" [--threads "../04 Threads/Неделя 17-23.11.md"] [--skip th_ru]
- Подписи.txt: блоки «Заголовок (дд.11, ЧЧ:ММ)» + строки подписи до следующего заголовка.
- Ролик к заголовку подбирается по словам из MATCH; карусель: папка Карусель (PNG → JPEG).
- Карусели сдвигаются на +30 минут, чтобы не выходить в одну минуту с роликом.
- mp4 перепаковываются с faststart (без перекодирования), обложки PNG → JPEG.
Выводит таблицу: что куда и когда; неподобранные заголовки печатает как ОШИБКА.
"""
import json, re, subprocess, sys
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
YEAR = 2026
HDR = re.compile(r"^(.*)\((\d{2})\.(\d{2}), (\d{2}):(\d{2})\)\s*$")
# слова заголовка → слово в имени файла
MATCH = [("Карусель", None), ("Carousel", None),
         ("День 4", "День 4"), ("Day 4", "Day 4"), ("День 5", "День 5"), ("Day 5", "Day 5"),
         ("День 6", "День 6"), ("Day 6", "Day 6"), ("День 7", "День 7"), ("Day 7", "Day 7"),
         ("до экзамена", "до экзамена"), ("plenty of time", "plenty of time"),
         ("Письмо", "Письмо"), ("Letter", "Letter"),
         ("Мем", "Мем"), ("Meme", "Мем"), ("밥", "Рис"),
         ("Это или то", "Это или то"), ("This or that", "Это или то"),
         ("Переписка", "Переписка"), ("Chat", "Переписка"),
         ("보고 싶어", "보고 싶어"), ("Тир-лист", "Тир-лист"), ("tier list", "Тир-лист"),
         ("오빠", "Оппа"), ("K-pop", "K-pop"),
         ("уровень TOPIK", "уровень"), ("TOPIK level", "level"),
         ("из дорам", "Таймер дорамы"), ("drama words", "Таймер дорамы"),
         ("кафе в Сеуле", "Таймер кафе"), ("cafe in Seoul", "Таймер кафе"),
         ("переехал", "Таймер переезд"), ("moved to Korea", "Таймер переезд")]


def blocks(txt):
    out, cur = [], None
    for line in txt.splitlines():
        m = HDR.match(line.strip())
        if m:
            cur = {"title": m.group(1).strip(), "dt": datetime(YEAR, int(m.group(3)), int(m.group(2)), int(m.group(4)), int(m.group(5))), "lines": []}
            out.append(cur)
        elif cur is not None:
            cur["lines"].append(line)
    for b in out:
        b["caption"] = "\n".join(b["lines"]).strip()
    return out


def find_media(folder, title):
    for k, f in MATCH:
        if k.lower() in title.lower():
            if f is None:
                return "carousel", sorted((folder / "Карусель").glob("[0-9][0-9].png"))
            vids = [p for p in folder.glob("*.mp4") if f.lower() in p.name.lower()]
            if len(vids) == 1:
                return "reel", vids
            return None, vids
    return None, []


def cover_for(folder, video):
    """Обложка к ролику: «Обложка <имя ролика без RU/EN>», для серий D<N>, письмо L1, экзамен E1."""
    stem = re.sub(r"\s+(RU|EN)$", "", video.stem)
    lang = video.stem.split()[-1]
    exact = folder / f"Обложка {stem} {lang}.png"
    if exact.exists():
        return [exact]
    m = re.search(r"(?:День|Day) (\d+)", stem)
    code = f"D{m.group(1)}" if m else "L1" if re.search("Письмо|Letter", stem) else "E1" if re.search("экзамен|exam", stem) else None
    if code and (folder / f"Обложка {code} {lang}.png").exists():
        return [folder / f"Обложка {code} {lang}.png"]
    if re.search("уровень|level", stem, re.I) and (folder / f"Обложка Таймер {lang}.png").exists():
        return [folder / f"Обложка Таймер {lang}.png"]
    return []


def jpeg(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.open(src).convert("RGB").save(dst, "JPEG", quality=92)


def main():
    week = Path(sys.argv[1]).resolve()
    skip = sys.argv[sys.argv.index("--skip") + 1].split(",") if "--skip" in sys.argv else []
    tag = week.name.split()[-1]  # 17-23.11
    sched, bad, n = [], 0, 0
    for day in sorted((p for p in week.iterdir() if p.is_dir() and re.fullmatch(r"\d{2}\.\d{2}", p.name)), key=lambda p: p.name[::-1]):
        for lang in ("RU", "EN"):
            folder = day / lang
            cap = folder / "Подписи.txt"
            if not cap.exists():
                continue
            for b in blocks(cap.read_text(encoding="utf-8")):
                kind, files = find_media(folder, b["title"])
                if not kind or not files:
                    print(f"ОШИБКА {day.name} {lang}: не нашёл файл для «{b['title']}» (кандидаты: {[f.name for f in files]})")
                    bad += 1
                    continue
                n += 1
                iid = f"w{tag}-{day.name}-{lang.lower()}-{n:02d}"
                dt = b["dt"] + (timedelta(minutes=30) if kind == "carousel" else timedelta())
                rel = f"media/{tag}/{iid}"
                media, cover = [], None
                if kind == "carousel":
                    for i, f in enumerate(files, 1):
                        jpeg(f, ROOT / rel / f"{i:02d}.jpg")
                        media.append(f"{rel}/{i:02d}.jpg")
                else:
                    out = ROOT / rel / "video.mp4"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(files[0]), "-c", "copy", "-movflags", "+faststart", str(out)], check=True)
                    media.append(f"{rel}/video.mp4")
                    covers = cover_for(folder, files[0])
                    if covers:
                        jpeg(covers[0], ROOT / rel / "cover.jpg")
                        cover = f"{rel}/cover.jpg"
                acc = "ig_" + lang.lower()
                if acc in skip:
                    continue
                item = {"id": iid, "account": acc, "type": kind, "time": dt.isoformat(timespec="minutes"),
                        "title": b["title"], "caption": b["caption"], "media": media}
                if cover:
                    item["cover"] = cover
                sched.append(item)
                print(f"{dt:%d.%m %H:%M} {acc} {kind:8} {b['title'][:40]:40} ← {files[0].parent.name}/{files[0].name}")
    if "--threads" in sys.argv:
        sched += threads(Path(sys.argv[sys.argv.index("--threads") + 1]), tag, skip)
    sched.sort(key=lambda x: x["time"])
    (ROOT / "schedule.json").write_text(json.dumps(sched, ensure_ascii=False, indent=1))
    print(f"\nВсего {len(sched)} публикаций, ошибок {bad}. schedule.json записан.")


def threads(md, tag, skip):
    """Threads из файла недели: RU «### дд.11» + «ЧЧ:ММ · тема» + текст; EN строки «дд.11 ЧЧ:ММ · текст»."""
    out, sec, day, cur = [], None, None, None
    topics = {"Корейский язык": "Корейский язык", "Корея": "Корея", "дорамы": "дорамы"}
    for line in md.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            sec = "ru" if line.startswith("## RU") else "en" if line.startswith("## EN") else None
            cur = None
            continue
        if sec == "ru":
            m = re.match(r"^### (\d{2})\.(\d{2})", line)
            if m:
                day, cur = (int(m.group(1)), int(m.group(2))), None
                continue
            m = re.match(r"^(\d{2}):(\d{2}) · (.+)$", line.strip())
            if m and day:
                cur = {"account": "th_ru", "type": "text", "time": datetime(YEAR, day[1], day[0], int(m.group(1)), int(m.group(2))),
                       "topic": topics.get(m.group(3).strip(), m.group(3).strip()), "lines": []}
                out.append(cur)
            elif cur is not None:
                cur["lines"].append(line)
        elif sec == "en":
            m = re.match(r"^(\d{2})\.(\d{2}) (\d{2}):(\d{2}) · (.+)$", line.strip())
            if m:
                out.append({"account": "th_en", "type": "text", "time": datetime(YEAR, int(m.group(2)), int(m.group(1)), int(m.group(3)), int(m.group(4))),
                            "topic": "Korean Language", "lines": [m.group(5)]})
    res = []
    for i, c in enumerate(out, 1):
        if c["account"] in skip:
            continue
        text = "\n".join(c["lines"]).strip()
        res.append({"id": f"w{tag}-{c['account']}-{i:02d}", "account": c["account"], "type": "text",
                    "time": c["time"].isoformat(timespec="minutes"), "topic": c["topic"], "caption": text})
        print(f"{c['time']:%d.%m %H:%M} {c['account']} text     {text[:50]}")
    return res


if __name__ == "__main__":
    main()
