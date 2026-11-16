"""Сохранить маркеры Meta в секреты GitHub, не показывая их.
Запуск: python3 set_secret.py --wait   → ждёт до 15 минут, пока в буфере обмена появится маркер (Threads: THAA…, Instagram: IGAA…).
Каждый новый маркер: узнаёт аккаунт по имени, кладёт <ACC>_TOKEN и <ACC>_ID в секреты, очищает буфер.
Выводит только имя аккаунта и ID. Аккаунты: Threads topiklab → th_ru, topik.lab → th_en; Instagram topiklab.ru → ig_ru, topik.lab → ig_en."""
import json, subprocess, sys, time, urllib.request

REPO = "uryabko708-tech/topiklab-publish"
MAP = {("th", "topiklab"): "th_ru", ("th", "topik.lab"): "th_en", ("ig", "topiklab.ru"): "ig_ru", ("ig", "topik.lab"): "ig_en"}


def clip():
    return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout.strip()


IG_IDS = {"17841449517123164": "ig_ru", "17841441289573232": "ig_en"}  # topiklab.ru, topik.lab


def save_fb(tok):
    """Маркер системного пользователя (EAA…): проверяем доступ к каждому аккаунту Instagram через graph.facebook.com."""
    got = []
    for iid, acc in IG_IDS.items():
        try:
            me = json.loads(urllib.request.urlopen(f"https://graph.facebook.com/v23.0/{iid}?fields=username&access_token={tok}", timeout=30).read())
        except Exception:
            continue
        for name, val in ((f"{acc.upper()}_TOKEN", tok), (f"{acc.upper()}_ID", iid)):
            subprocess.run(["gh", "secret", "set", name, "-R", REPO], input=val, text=True, check=True, capture_output=True)
        print(f"OK: {acc} = @{me.get('username')} (id {iid}), секреты сохранены.", flush=True)
        got.append(acc)
    subprocess.run(["pbcopy"], input="", text=True)
    if not got:
        print("Маркер EAA не дал доступа ни к одному аккаунту Instagram.", flush=True)
    return got


def save(tok):
    if tok.startswith("EAA"):
        return save_fb(tok)
    kind = "th" if tok.startswith("TH") else "ig"
    if kind == "th":
        me = json.loads(urllib.request.urlopen(f"https://graph.threads.net/v1.0/me?fields=id,username&access_token={tok}", timeout=30).read())
        uid = me["id"]
    else:
        me = json.loads(urllib.request.urlopen(f"https://graph.instagram.com/v23.0/me?fields=user_id,username&access_token={tok}", timeout=30).read())
        uid = me["user_id"]
    acc = MAP.get((kind, me.get("username")))
    if not acc:
        print(f"Неизвестный аккаунт @{me.get('username')} ({kind}), не сохранён.", flush=True)
        return None
    for name, val in ((f"{acc.upper()}_TOKEN", tok), (f"{acc.upper()}_ID", str(uid))):
        subprocess.run(["gh", "secret", "set", name, "-R", REPO], input=val, text=True, check=True, capture_output=True)
    subprocess.run(["pbcopy"], input="", text=True)
    print(f"OK: {acc} = @{me.get('username')} (id {uid}), секреты сохранены, буфер очищен.", flush=True)
    return acc


if __name__ == "__main__":
    want = set(sys.argv[2:]) or {"th_ru", "th_en"}
    done, seen, t0 = set(), set(), time.time()
    print(f"Жду маркеры для: {', '.join(sorted(want))}", flush=True)
    while time.time() - t0 < 900 and not want <= done:
        c = clip()
        if c not in seen and len(c) > 40 and " " not in c and (c[:2] in ("TH", "IG") or c.startswith("EAA")):
            seen.add(c)
            try:
                a = save(c)
                if isinstance(a, list):
                    done.update(a)
                elif a:
                    done.add(a)
            except Exception as e:
                print(f"Маркер не подошёл: {str(e)[:150]}", flush=True)
        time.sleep(2)
    print(f"Готово: {', '.join(sorted(done)) or 'ничего'}", flush=True)
