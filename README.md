# Публикация TOPIKLAB в Instagram и Threads (API Meta + GitHub Actions)

Как работает: ролики, карусели и schedule.json лежат в публичном репозитории GitHub. GitHub Pages раздаёт файлы по ссылке (Meta берёт медиа только по ссылке). GitHub Actions каждые 10 минут запускает publish.py: публикует то, чему пришло время (по Сеулу), и пишет результат в state.json. TikTok сюда не входит (его API требует проверки TikTok): TikTok ставит агент через браузер.

## Каждая неделя (делает Claude)
1. `python3 build_manifest.py "../Выкладка/Неделя <даты>" --threads "../04 Threads/Неделя <даты>.md"` → schedule.json + media/.
2. Проверить таблицу (что, куда, когда), `python3 publish.py --dry`.
3. git commit + push. Через ~1 минуту файлы доступны на Pages, дальше всё само.
Статус: state.json в репозитории (ok, post_id или error). Ошибка повторяется до 3 раз.

## Один раз: GitHub (делает пользователь)
1. Аккаунт на github.com (если нет).
2. Установить GitHub CLI: https://cli.github.com (скачать .pkg для macOS, установить).
3. В Claude Code: `! gh auth login` → GitHub.com → HTTPS → Login with a web browser.
4. Дальше Claude сам создаёт репозиторий topiklab-publish, включает Pages и переменную MEDIA_BASE.

## Один раз: Meta (делает пользователь, Claude подсказывает по шагам)
Аккаунты Instagram RU и EN должны быть профессиональными (Автор или Бизнес).
1. developers.facebook.com → Мои приложения → Создать приложение. Сценарии: «Instagram API» (вход через Instagram) и «Threads API».
2. Instagram: в приложении Instagram → «Настройка API со входом через Instagram» → Добавить аккаунт (войти RU, потом EN) → «Сгенерировать маркер». Скопировать маркер и ID аккаунта.
3. Threads: Роли приложения → добавить тестировщиков Threads (RU и EN аккаунты) → принять приглашение в Threads (Настройки → Аккаунт → Разрешения сайтов → Приглашения) → в сценарии Threads «Генератор маркеров» → маркер для каждого аккаунта. ID: `python3 whoami.py th <маркер>`.
4. Секреты вводит пользователь сам (Claude их не видит), по одному:
   `! gh secret set IG_RU_ID -R <логин>/topiklab-publish` (вставить значение, Enter) и так же IG_RU_TOKEN, IG_EN_ID, IG_EN_TOKEN, TH_RU_ID, TH_RU_TOKEN, TH_EN_ID, TH_EN_TOKEN.
Приложение остаётся в режиме разработки: публикует только в аккаунты, добавленные в роли. Проверка Meta не нужна.

## Маркеры живут 60 дней
Записать дату выдачи. За неделю до конца: сгенерировать новые и обновить секреты той же командой.

## Ограничения API
- Instagram: до 100 публикаций в сутки на аккаунт; картинки только JPEG (build_manifest конвертирует); Reels 9:16, H.264/AAC.
- Threads: до 250 постов в сутки; тема поста (topic_tag), если API её не примет, пост выйдет без темы.
- GitHub Actions по расписанию может запускаться с задержкой 5–15 минут.
