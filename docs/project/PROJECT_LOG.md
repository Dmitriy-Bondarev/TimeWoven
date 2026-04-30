# PROJECT LOG — TimeWoven

## INCIDENT 2026-04-26 — потеря исходников family access слоя (post-mortem)

**Дата инцидента:** 2026-04-26
**Дата post-mortem:** 2026-04-27
**Статус:** Closed (см. секцию "Что мы изменили")
**Severity:** High — потеря исходных файлов; продолжение работы было возможно только через emergency hotfix.
**Ссылки:**
- Архив трёх stash дня инцидента: `/root/projects/TimeWoven_snapshots/protected/STASH-REFERENCE-2026-04-26/`
- Защищённый snapshot после восстановления: `protected/CLEAN-START-2026-04-27`
- Введённый протокол: `docs/PROJECT_OPS_PROTOCOL.md`
- Серия восстановительных коммитов: `35e01ec`, `6d4b668`, `d15d4aa`, `74e9d93`, `e54fad1`, `98696bc`

### Краткое резюме

26 апреля при работе по задаче P1.20 (admin login hardening) в репозитории накопилось большое количество не сохранённых в git изменений и новых файлов. Часть этих файлов существовала **только** на диске и не была отслежена git. При попытке использовать `git stash` для временной приостановки работы отслеживаемые файлы были сохранены, а неотслеживаемые — нет. После последующих операций неотслеживаемые файлы были физически утрачены. Прод был восстановлен в тот же день через emergency hotfix с временным отключением части функционала. На следующий день (27 апреля) был введён операционный протокол, ликвидирующий весь класс таких рисков; потерянные файлы были либо переписаны как минимальные shim-заглушки и закоммичены, либо отнесены в backlog как задачи на полное восстановление.

### Что произошло (нейтральная хронология)

1. **Утро 26 апреля** — началась рабочая сессия по продолжению семейного функционала (family access, i18n, theme system, admin polish). Постепенно объём не закоммиченных изменений нарастал: накопилось около 36 файлов в WIP, +3214/-761 строк, при этом значительная часть нового кода (i18n core, person_alias_service, theme module, новые admin-страницы, locales) существовала как untracked-файлы — не была добавлена в git.

2. **Около 9-10 утра** — для перехода к задаче P1.20 (admin login hardening) был выполнен `git stash push` без флага `-u`. Команда сохранила modified-файлы, но неотслеживаемые исходники остались только на диске. Это поведение `git stash` корректно по документации, но не было явно учтено в плане работы.

3. **В течение дня** — работа над P1.20 шла на чистом дереве; при последующих операциях с git (checkout, повторные stash, попытки восстановления) неотслеживаемые файлы были физически утрачены. Их следы остались только как `.pyc`-файлы в `__pycache__`.

4. **К концу дня 26 апреля** — приложение перестало запускаться из-за отсутствия импортируемых модулей. Был выполнен emergency hotfix: модели `EarlyAccessRequest` и `FamilyAccessSession` были временно отключены через try/except, импорт `app.core.theme` заменён на статическое значение, импорт admin_router обёрнут в try/except. Прод был поднят в урезанном виде. Этот hotfix зафиксирован в `stash@{1}: emergency-prod-breakage-2026-04-26`.

5. **Поздно вечером 26 апреля** — автор проекта остановил все работы и обратился к Перплексити-главному-исследователю в Space за разбором ситуации.

6. **27 апреля, утро** — был выполнен системный анализ инцидента, разработан и установлен на сервер операционный протокол (`PROJECT_OPS_PROTOCOL.md` v1.0) с тремя bash-скриптами (`clean_state_gate.sh`, `safety_snapshot.sh`, `rollback_to_snapshot.sh`).

7. **27 апреля, день** — был выполнен полный разбор оставшегося WIP по новому протоколу: 18 файлов разнесены по 6 атомарным коммитам с явными scope, проверками и ограничениями. Сервис перезапущен на новом коде; защищённый snapshot создан; три остаточных stash от 26 апреля архивированы и удалены.

### Что было потеряно

| Что | Текущий статус |
|---|---|
| `app/core/i18n.py` | Восстановлен и закоммичен 27.04 (коммит `6d4b668`) |
| `app/services/person_alias_service.py` | Восстановлен как минимальный shim (коммит `6d4b668`); полное восстановление — задача `T-FAMILY-ACCESS-REBUILD` в backlog |
| `app/services/timeline_event_view.py` | Восстановлен и закоммичен (коммит `d15d4aa`) |
| `locales/{ru,en}/{app,family,landing}.yml` | Восстановлены и закоммичены (коммит `6d4b668`) |
| `app/core/theme.py` | Утрачен; временно заменён на статическое значение `current_dark`. Восстановление — задача `T-CORE-THEME-RESTORE` в backlog |
| Полная версия admin pages, расширенная family/profile, расширенный landing | Утрачены в той версии, что была в WIP 26.04. Текущие версии в репо — рабочие, восстановленные через коммит `e54fad1`. Расширенный вариант остался только в архиве `STASH-REFERENCE-2026-04-26/stash_2_wip-before-p1-20.diff` как референс |

### Корневые причины

Три системные причины, которые сложились в инцидент:

**1. Неправильное распределение ролей.**
Браузерный консультативный AI (Перплексити в браузере) использовался как разработчик-проектировщик. Природа этого AI — давать быстрые консультации и работать с фрагментами, а не вести длинные проектные задачи с точностью к исходникам. Когда от него требовалось формулировать строгие технические задания и поддерживать когерентность процесса, он начинал заполнять пробелы догадками — что в условиях работы с git и долговременным состоянием репозитория критично.

**2. Implementation-агент (VSCode/Cursor) получал нечёткие технические задания.**
Без явных границ scope, явных запретов и явных критериев готовности он вынужденно принимал решения по своему усмотрению. В большинстве случаев это работало, но при действиях с git stash, выбором конкретных stash-индексов, операциями с веткой — каждое такое самостоятельное решение увеличивало риск отклонения от исходного плана.

**3. Отсутствие операционного контракта между ролями.**
Не было формального правила, обязывающего перед началом любого изменения зафиксировать текущее состояние в безопасный snapshot. Не было формального правила, что неотслеживаемые файлы — это технический долг, а не норма работы. Не было формального правила, что implementation-агент обязан остановиться при невозможности выполнить задание точно как описано. В отсутствие этих правил каждый отдельный шаг выглядел разумным, но их сумма привела к тому, что критичные исходники жили вне git.

### Что сработало хорошо

Эту часть важно отметить отдельно — она показывает, какие сильные стороны процесса нужно сохранить.

- **Автор проекта вовремя остановил работы.** Когда стало очевидно, что ситуация уходит из-под контроля, было принято решение прекратить попытки восстановления и обратиться к главному исследователю за системным разбором. Это решение спасло проект от ещё больших потерь.
- **Регулярные backup'ы продолжали работать.** Daily-cron сохранил `postgres_dump_20260426-030002.sql.gz`, `project_20260426-030002.tar.gz`, `uploads_20260426-030002.tar.gz`. БД и базовые конфиги в любом случае были защищены.
- **Git history до инцидента сохранилась.** Все коммиты до `bb66718` уцелели; восстановление шло от чистой точки в git.
- **Production data не пострадала.** Семейные истории, аудиозаписи, пользователи, аватары — всё осталось целым. Инцидент затронул только исходный код приложения.

### Learning Log

Главные уроки инцидента в формате "проблема → правило, которое это блокирует". Простой язык — чтобы можно было перечитать через полгода и сразу понять.

| Что произошло | Какое правило теперь это блокирует |
|---|---|
| Файлы существовали только как untracked и были потеряны при операции с git | **Правило 1.2** в `PROJECT_OPS_PROTOCOL.md`: untracked-файл — это технический долг. Любой untracked-файл, проживший дольше одного задания, считается дефектом и должен быть либо в коммите, либо в `.gitignore`. |
| `git stash` использовался как место для долговременного хранения WIP | **Правило 1.3**: `git stash` — не бэкап. Stash может быть только короткоживущим буфером внутри одного задания. |
| Перед началом изменений не делался snapshot текущего состояния | **Правило 4** + скрипт `safety_snapshot.sh`: перед каждым заданием создаётся полный архив рабочего дерева, включая untracked-файлы. Это и есть та защита, которой не было 26.04. |
| Браузерный AI использовался как проектировщик-разработчик | **Правило 10.1-10.3**: формально разделены роли. Главный исследователь пишет ТЗ. Implementation-агент исполняет. Браузерный AI используется только как быстрая консультативная функция, без права писать ТЗ или давать команды для git. |
| Implementation-агент принимал автономные решения при нечётких заданиях | **Правило 6.2 (DEVIATION-RULE)**: при невозможности выполнить задание точно как описано implementation-агент обязан остановиться и вернуть `BLOCKED:`-отчёт. Никаких автономных подмен scope. |
| WIP смешивал шлифовку, новый функционал, инфраструктуру и эксперименты | **Правило 1.5**: один блок работы — одна тема. Если по ходу появляется идея нового масштаба, она идёт в backlog отдельной задачей, а не реализуется в текущем коммите. |
| Отсутствовала возможность одной командой откатить состояние | **Скрипты 1-3** (`clean_state_gate.sh`, `safety_snapshot.sh`, `rollback_to_snapshot.sh`): проверка чистоты, snapshot, откат — три команды, покрывающие весь жизненный цикл. |
| Документация (TECH_PASSPORT) описывала функционал, которого не было в git | **Правило 1.4 + раздел 9.1**: документ описывает факт в коде, не намерение. Раз в неделю выполняется doc-reconciliation: каждый упомянутый файл проверяется через `git ls-files`. |

### Что мы изменили после инцидента

Установлено в репозитории и на сервере:

1. **`docs/PROJECT_OPS_PROTOCOL.md` v1.0** — операционный протокол: 4 уровня защиты, шаблон ТЗ, правила DEVIATION-RULE, разделение ролей.
2. **`scripts/ops/clean_state_gate.sh`** — проверка чистоты репо и сервиса перед началом задания.
3. **`scripts/ops/safety_snapshot.sh`** — полный архив рабочего дерева (включая untracked) с TTL и protected-режимом.
4. **`scripts/ops/rollback_to_snapshot.sh`** — откат к снапшоту с автоматическим pre-rollback snapshot для двойной страховки.
5. **`/root/projects/TimeWoven_snapshots/`** — каталог снапшотов с rolling-30-дней и `protected/` без авто-удаления.
6. **`/root/projects/TimeWoven_snapshots/protected/STASH-REFERENCE-2026-04-26/`** — архив трёх stash дня инцидента (sha-1 ниже).
7. **`/root/projects/TimeWoven_snapshots/protected/CLEAN-START-2026-04-27/`** — первая в истории проекта защищённая точка чистого старта (HEAD = `98696bc`, полный worktree + git bundle).

### Хеши дропнутых stash (для полноты учёта)

После архивирования содержимого в `STASH-REFERENCE-2026-04-26/` все три stash 27.04 были удалены через `git stash drop`. Их git-хеши:

- `stash@{2}` (wip before p1-20 admin login hardening) — `96e8aeac56082b451d9debe9639454533094724d`
- `stash@{1}` (emergency-prod-breakage-2026-04-26) — `7502f472dbd83a0043508281fb0a240c4634ed1c`
- `stash@{0}` (pre-restore-checkout-2026-04-26) — `42259dbd47e0979de7586cb0cfc9a04f1f576649`

Содержимое каждого сохранено как `.diff` в архивной папке выше.

### Доказательство, что новые правила работают

27 апреля (в тот же день, что post-mortem) по новому протоколу был выполнен полный разбор оставшегося WIP — 18 файлов разнесены по 6 атомарным коммитам без единого отклонения от scope. На каждом шаге WIP-counter совпадал с предсказанием до единицы. Implementation-агент дважды корректно остановился по DEVIATION-RULE (обрезанное commit-сообщение, конфликт с git-extension Cursor IDE) — именно то поведение, которого добивались.

Это и есть подтверждение, что класс рисков 26.04 закрыт.

---

## Запись 27 апреля — введение протокола и разбор WIP

Date: 2026-04-27

### Structural change

Yes — введён операционный протокол `docs/PROJECT_OPS_PROTOCOL.md` и три bash-скрипта в `scripts/ops/`. Изменён процесс работы над проектом: каждое новое задание проходит через PRE-CHECK (`clean_state_gate.sh`) и safety_snapshot.

### Schema change

No.

### Decision / Notes

- Все 18 файлов остаточного WIP от инцидента 26.04 разнесены по 6 атомарным коммитам с явными scope и проверками:
  - `35e01ec` — T-OPS-PROTOCOL-INSTALL-2026-04-27 (5 файлов: protocol + 3 скрипта + README)
  - `6d4b668` — T-RECOVERY-FAMILY-ACCESS-SHIM-2026-04-26 (8 файлов: i18n, person_alias shim, locales)
  - `d15d4aa` — T-TIMELINE-EVENTS-VIEW-2026-04-26 (5 файлов: timeline_event_view + потребители)
  - `74e9d93` — T-FAMILY-PROFILE-COPY-2026-04-26 (2 файла: UX copy на семейном профиле)
  - `e54fad1` — T-ADMIN-RESTORE-AND-PAGES-2026-04-26 (14 файлов: атомарное восстановление admin)
  - `98696bc` — T-LANDING-EN-DEPLOY-2026-04-26 (1 файл: deploy_landing.sh, поддержка EN)
- Все 6 коммитов запушены в `origin/main` за один fast-forward push.
- Сервис `timewoven.service` перезапущен на новом коде (PID `387738`, `ActiveEnterTimestamp=2026-04-27 06:59:12 UTC`); `/health` отдаёт `ok` локально и публично; `py_compile` всех ключевых модулей зелёный.
- Защищённый snapshot `protected/CLEAN-START-2026-04-27` создан (HEAD=`98696bc`, размер 52M: worktree.tar.gz 28M, repo.bundle 24M).
- Три остаточных stash от 26.04 архивированы в `protected/STASH-REFERENCE-2026-04-26/` и удалены через `git stash drop` (хеши см. выше).
- Резолвлена техническая проблема: git-extension в Cursor IDE параллельно создаёт `.git/index.lock`, что приводило к интермиттирующим сбоям `git add`. Решение — оборачивать git-операции в `flock --timeout 30 .git/index.lock.flock`. Это решение зафиксировано в коммитах серии и будет добавлено в `PROJECT_OPS_PROTOCOL.md` отдельной задачей.

### Validation / Proof

- `clean_state_gate.sh` после серии: 6 PASS / 1 FAIL (FAIL — 3 modified документа, открытые в текущей сессии документации). Это ожидаемое и контролируемое состояние.
- `git stash list` пуст.
- `git rev-parse origin/main` = `git rev-parse HEAD` = `98696bc`.
- Прохождение по живым страницам админки и family-флоу автором проекта — без регрессий.

### References

- `docs/PROJECT_OPS_PROTOCOL.md` — правила процесса.
- `scripts/ops/{clean_state_gate,safety_snapshot,rollback_to_snapshot}.sh` — реализация защит.
- `INCIDENT 2026-04-26` — выше в этом файле.
- `PRODUCT_BACKLOG.md` — будут добавлены задачи `T-FAMILY-ACCESS-REBUILD`, `T-CORE-THEME-RESTORE`, `T-DUPLICATE-FAMILY-TREE-ROUTE-INVESTIGATE`, `T-OPS-INDEX-LOG-FORMAT`, `T-PROTOCOL-IDE-COEXISTENCE` (отдельный коммит документации, в той же сессии).

### T-ADMIN-HARDENING-2026-04-27 — admin hardening (C.1)

**Дата:** 27.04.2026
**Статус:** ✅ Завершено
**Коммиты:** `c927c3f`, `0bb0de4`, `b0ae7e8`, `0d608f2` (все на main, запушены)
**Snapshot:** `/root/projects/TimeWoven_snapshots/T-ADMIN-HARDENING-2026-04-27/`

**Цель:** усилить существующую (рабочую) авторизацию админки по трём направлениям + чистка мёртвого кода. Не редизайн, а минимальная инвазивная защита.

**Что сделано:**

1. **C1.A — Rate limit на POST /admin/login** (`c927c3f`)
   - In-memory bucket (deque per IP) в `app/security.py`: 5 попыток/мин и 20 попыток/час.
   - Без новых зависимостей (паттерн как у `family_access_service.check_rate_limit`).
   - Helper `get_client_ip` учитывает `X-Forwarded-For` (приложение за прокси).
   - При превышении — HTTP 429 с короткой страницей.
   - Curl-проверка: try 1-5 → 200, try 6-7 → 429.

2. **C1.C — Audit log попыток входа** (`0bb0de4`)
   - Новый модуль `app/core/admin_audit.py`, JSONL формат.
   - Файл лога: `logs/admin_audit.log` (TW_LOG_DIR override через env).
   - Каждая попытка: timestamp UTC ISO, IP, username (≤64 chars), result (`success` / `fail` / `rate_limited`).
   - Никогда не падает на ошибке записи (try/except OSError).
   - `/logs/` добавлено в `.gitignore`.

3. **C1.B — Idle timeout 30 минут** (`b0ae7e8`)
   - In-memory `{token: last_seen_ts}` в `app/security.py`, без изменения формата cookie.
   - Sliding window: каждый успешный проход через `require_admin` обновляет `last_seen`.
   - Превышение → редирект на `/admin/login?next=...` + `delete_cookie(tw_admin_session)`.
   - Регистрация при логине (`admin_register_login`) и явный logout (`admin_register_logout`).
   - **Env override:** `TW_ADMIN_IDLE_TIMEOUT_SECONDS` (по умолчанию `1800`).
   - Curl-проверка с override=10s: login=303, fresh=200, after_idle=303 + Set-Cookie Max-Age=0.

4. **C1.D — Удаление dead code app/core/security.py** (`0d608f2`)
   - Файл (33 строки, itsdangerous-based) использовал cookie `admin_token`, дублировал функционал `app/security.py`, никем не импортировался.
   - PRE-CHECK: 0 прямых импортов, 0 динамических, 0 строковых ссылок.
   - Smoke-тест после удаления: `systemctl is-active=active`, GET /admin/login=200, GET /health=200, нет ImportError.

**Что осознанно НЕ делалось (вынесено в backlog):**
- CSRF protection — P2
- 2FA / TOTP для админки — P2
- Перенос idle-store в Redis (для переживания рестартов) — P2
- Prometheus-метрики попыток входа — P3
- Структурированный logger вместо JSONL-файла — P3

**Известные ограничения:**
- In-memory state (`_LOGIN_ATTEMPTS`, `_ADMIN_LAST_SEEN`) теряется при рестарте `timewoven.service`. После рестарта rate limit обнуляется, idle-таймер начинается заново при первом запросе. Приемлемо для текущей нагрузки одного админа.
- Rate limit ключ — IP. За одним прокси/CGNAT все клиенты делят квоту. При появлении проблем — мигрировать на (IP+username) или Redis.

**Ссылки:**
- ТЗ: `TZ_C1_ADMIN_HARDENING_2026-04-27_v2` (Perplexity computer)
- PRE-CHECK снапшот: `/root/projects/TimeWoven_snapshots/T-ADMIN-HARDENING-2026-04-27/`

---

## OP-DIAG-BACKUP — daily verified + pre-timeline snapshot (2026-04-26)

**Daily (cron, UTC 03:00:02 2026-04-26):** `postgres_dump_20260426-030002.sql.gz` — `gzip -t` OK, начало файла — валидный `pg_dump` (PostgreSQL 14); `project_20260426-030002.tar.gz` — tar читается; `uploads_20260426-030002.tar.gz` — 157 B (только пустые/структурные `app/web/static/*/uploads/`, бэкап менеджером). В `backups/daily/backup_manager.log` есть строка `Backup completed at 2026-04-26T03:04:36Z` (и замечание `tar: .: file changed as we read it` в том прогоне). Воскресные копии `2026-04-26` дублируются в `backups/daily/archive/`. **Заметка:** в `backups/daily` нет `uploads_20260425-030001.tar.gz` (есть 24 и 26), при необходимости — отдельная проверка политики/логов за 25.04.

**Pre-timeline (ручной снимок, без правок `scripts/backup_manager.sh`):** `pg_dump "$DATABASE_URL" | gzip -9` → `postgres_dump_pre_timeline_20260426-1629.sql.gz` (`gzip -t` OK). Проект: те же `--exclude` что в скрипте (`.git`, `backups/daily`, venv) → `project_pre_timeline_20260426-1630.tar.gz` (~37M). **Git ref на момент:** `a5b7eb7` (см. также незакоммиченные правки в `git status`).

---

## Decision / Update: TW-2026-04-26-R4 — family reply screen local UX pass closed; next package in backlog

Date: 2026-04-26

### Structural change

No (только продуктовая фиксация в `PRODUCT_BACKLOG` / `PROJECT_LOG`).

### Schema change

No

### Decision / Notes

- **Локальный UX-проход** по `/family/reply/{id}` **завершён**; экран доведён до тёплого и рабочего состояния в рамках текущего hotfix/polish-контура.
- **Продуктовый язык:** экран смещён с акцента на «ответ / послание» к языку **«воспоминание / семейная история»** (copy и UX-линия в рамках уже выполненной сессии).
- **По итогам review** зафиксирован **следующий продуктовый пакет развития** (сильная идея, **не** внедрён в текущем блоке):
  - reply как **точка входа в коллективную память** семьи;
  - **event context** (понятная привязка к событию, reply ↔ event в UX);
  - **типы ответа** (воспоминание / мысль / факт);
  - **AI-assisted writing** на экране (сформулировать, короче, яснее) и дальнейшее сближение с **event-memory** моделью продукта.
- Пакет **вынесен в backlog** как отдельная задача **T43** в `PRODUCT_BACKLOG.md` — **без** изменения кода, шаблонов, CSS, backend и timeline в этой сессии.

### References

- `PRODUCT_BACKLOG.md` — T43

---

## Deploy: ADMIN-PEOPLE-FILTERS + gold theme (explorer / avatars) — 2026-04-26

**Commits (main):** `5f4185e` (restore filters, gold explorer/avatars), `05493eb` (filters moved into table header row).  
**Deploy:** `sudo ./deploy.sh` (app: `git pull origin main` + `systemctl restart timewoven.service`), `sudo ./deploy_landing.sh` (статика `landing.html` / `landing_en.html` → `/var/www/timewoven/`, nginx reload).  
**Проверки:** `systemctl status timewoven.service`, `curl https://app.timewoven.ru/health` → `{"status":"ok"}`; лендинг `https://timewoven.ru/`, `https://timewoven.ru/en/` → HTTP 200.

### Before / after (admin `/admin/people`)

- **Before:** отдельный блок поиска; риск несоответствия полей алиасов в шаблоне; explorer в «левом» акценте, аватары без выровненной шапки.
- **After:** поиск и фильтры **во второй строке thead** таблицы, счётчик «Показано n из m» над таблицей; колонка алиасов читает **`label` / `alias_type`**; ссылка **«Алиасы»** на `/admin/people/{id}/aliases`; `/explorer/` и `/admin/avatars` приведены к **gold**-теме (см. `TECH_PASSPORT` §5.5.1).

---

## Decision: T42 — meaning / events layer for the main family timeline

Date: 2026-04-26

### Structural change

Yes (planned): новый производный слой **`MemoryEvent` / `MemoryEventPerson`** поверх `Memories`; основной `/family/timeline` в перспективе переводится на чтение событий, а не только сырого текста.

### Schema change

Planned: миграции PostgreSQL для таблиц событий (детали — в `PRODUCT_BACKLOG` → T42).

### Decision / Notes

- **Контекст:** недавние локальные улучшения family (`/family/person` мини-timeline, дата в карточке, `/family/memory/.../edit` с оригинал / пересказ / суть + `essence_text`) **закрыты отдельно**; они дают фундамент (первоисточник vs пересказ vs краткое резюме), но **не** заменяют продуктовый эпик по структурированным событиям.
- **Принято:** следующим **большим** продуктовым блоком (после фиксации ТЗ в docs и отдельного коммита) считается **T42** — слой смысла и событий, извлекаемых из текста воспоминаний, для **основного** семейного timeline и согласованного отображения на персоне.
- **T42 не смешивается** в одной реализации с отложенным operational слоем **`admin / i18n / deploy`**: тот пласт остаётся следующим незакрытым **операционным** контуром; T42 — отдельный **продуктовый** track (schema + extraction + family UI + admin lite).
- **Первоисточник:** `Memories` (в т.ч. неизменяемый в family-редакторе оригинал) остаётся source of truth; события — derived, с фрагментом-источником и ручной/полуавтоматической верификацией.
- **Границы v1:** без `MemoryPeriod`, без тяжёлой дедупликации и карты мест — см. Non-goals в `PRODUCT_BACKLOG` (T42).

### Next task package

- Реализация T42 по фазам в `PRODUCT_BACKLOG` (schema → extraction → admin lite → timeline switch → fallback).
- Отдельно: operational backlog `admin / i18n / deploy` — не блокирует старт дизайна T42, но **не** сливается в один PR с T42.

### References

- `PRODUCT_BACKLOG.md` — T42
- `TECH_PASSPORT.md` — §4.2.1 roadmap note

## Decision: T37 — family graph split into Graph Lite / Time Machine / Legacy Graph

Date: 2026-04-25

### Structural change

No

### Schema change

No

### Decision / Notes

- Продуктово: family graph больше не рассматривается как один общий перегруженный интерфейс.
- Принято разделение на три поверхности:
  - **Graph Lite** — основной семейный граф для структуры семьи и быстрой навигации.
  - **Time Machine** — отдельная семейная temporal‑поверхность для просмотра семьи по годам.
  - **Legacy Graph** — текущий граф сохраняется как admin-only / personal experimental tool.
- `personal timeline` уже выполняет роль story-board отдельного человека.
- Отдельный Story Mode в графе пока **не является текущим приоритетом**.
- Graph Lite и Time Machine планируются как **family-facing surfaces**.
- Privacy/visibility для graph/time views — отдельный будущий эпик.
- Важное уточнение для будущей visibility model: запрос на скрытие персоны, союза или части истории может исходить от **одного** участника семьи и **не обязан** автоматически становиться глобальным правилом для всех viewers.

### Next task package

- T37A — точки входа Graph Lite / Time Machine / Legacy Graph
- T37B — Graph Lite
- T37C — Time Machine
- T37D — privacy note / backlog item

## Update: T40 — bilingual landing (RU/EN) + waitlist polish

Date: 2026-04-25

### Structural change

Yes

### Schema change

No

### Changes

- Лендинг переведён на локали `landing` (RU/EN): `locales/ru/landing.yml`, `locales/en/landing.yml`.
- В шаблон `app/web/templates/site/landing.html` прокинут словарь `t` (секция `landing`) для выбранной локали.
- Весь контент лендинга переведён на использование ключей `landing.*` через `t.*` (без хардкода текста в шаблоне).
- Добавлена статическая сборка лендинга:
  - `python3 scripts/build_landing.py ru` → `index.html`
  - `python3 scripts/build_landing.py en` → `en/index.html`
- Production static scheme зафиксирована и проверена:
  - `/` → RU (`/var/www/timewoven/index.html`)
  - `/en/` → EN (`/var/www/timewoven/en/index.html`)
- EN copy polished (marketing-facing тексты переписаны на “native landing English” без SaaS-клише).
- Визуальный polish лендинга (без редизайна): header/hero/cards/footer; улучшены микро-интеракции, вертикальный ритм и типографика.
- Mobile header fix: на `<=420px` header разрешает перенос actions на вторую строку, CTA не сжимается; language switch выглядит аккуратнее.
- Waitlist form fix (CTA modal): добавлено отдельное email-поле `type="email"` + поле для Telegram, без ломания API payload (`contact_value` остаётся единым полем отправки).

## LANDING-TEXT-AUDIT-1 — landing texts comparison table (old vs new)

Date: 2026-04-25

### Structural change

No

### Schema change

No

### Result

- Blocks: 99
- only_new: 6
- only_old: 0
- anglicisms_after_whitelist: 2
- Report: `docs/legal/audits/landing_text_audit_2026-04-25.md`

## Update: TW-THEME-3-COVERAGE — reply/transcriptions/early-access moved to shared theme tokens

Date: 2026-04-25

### Structural change

No

### Schema change

No

### Changes

- Дотянут theme‑coverage для ключевых экранов, которые ранее жили на локальном `:root` и хардкодных палитрах.
- Шаблоны переведены на общий слой темы через `extends "base.html"` и CSS‑tokens из `app/web/static/site/theme.css`.
- Экранные цели coverage:
  - `family/reply` (ответы семьи на воспоминание)
  - `/admin/transcriptions`
  - `/admin/early-access`
- Результат: страницы уважают пресеты тем, включая `voice_premium`, без старого “золотого” оформления.

### Validation

- `python3 -m py_compile app/main.py app/core/theme.py app/api/routes/admin.py`
- Browser check: `/family/reply/{memory_id}?person_id=...`, `/admin/transcriptions`, `/admin/early-access` (в обоих presets: `current_dark`, `voice_premium`).

## Update: TW-THEME-2-VOICE — voice_premium tuned for long reading + voice context

Date: 2026-04-25

### Structural change

No

### Schema change

No

### Changes

- Обновлён preset `voice_premium` в `app/web/static/site/theme.css` как тема “вечернего радио” для длинного чтения семейных историй и будущего audio‑friendly сценария.
- Ключевые смысловые изменения токенов (без привязки к конкретным hex):
  - глубокий, но не чёрный фон;
  - более различимые `surface / surface-2` (слои карточек и вложенные блоки);
  - мягкий светлый основной текст для длинных абзацев;
  - читаемый muted‑текст для мета‑информации и подписей;
  - спокойный, “premium/voice” акцент без кислотности;
  - нейтральные границы и тени для читаемой глубины;
  - совместимость с admin UI (рабочий инструмент, без визуального разрыва с family).

### Validation

- `python3 -m py_compile app/main.py app/core/theme.py app/api/routes/admin.py`
- Browser check: `/family/welcome`, `/family/timeline`, `/family/profile`, `/family/tree` в `voice_premium`.

## Update: TW-THEME-1 — admin theme switch hardening (routing + base safety)

Date: 2026-04-25

### Structural change

No

### Schema change

No

### Changes

- Введена система theme‑presets (baseline + future‑preset) на базе CSS variables и data‑атрибута на `<html>`.
- Добавлен admin‑only UI выбора темы и persisted сохранение активного preset без schema change.
- Стабилизирован flow:
  - базовый layout не зависит от необязательных Jinja helpers (язык берётся из `request.state`);
  - сохранение темы из админки возвращает на `/admin/` без Not Found на окружениях, где redirect slashes не включён.
- Тема применяется глобально к основным HTML‑экранам приложения.

### Validation

- `python3 -m py_compile app/main.py app/core/theme.py app/api/routes/admin.py`
- Browser check: `/admin/login`, `/admin/`, переключение `current_dark` ↔ `voice_premium`, затем проверка ключевых family/admin экранов.

## Decision: Claude / Anthropic removed from active contour

Date: 2026-04-24

### Structural change

No

### Schema change

No

### Decision / Changes

- Принято решение: **Claude / Anthropic API выведен из активного контура проекта** (не рассматривается как текущий рабочий путь).
- Актуальный рабочий стек для AI:
  - **Текстовый анализ:** `local_llm` (localhost-only сервис на VPS).
  - **Транскрибация аудио:** `local Whisper small` (localhost-only сервис на VPS).
- Legacy-поддержка Anthropic/Claude в коде оставлена как опциональная, но **не является default** и **не рекомендуется** как текущий путь.

## Update: T25.4 — edit flow для memory (author-only)

Date: 2026-04-24

### Structural change

Yes

### Schema change

No

### Changes

- Добавлены маршруты редактирования воспоминаний: `GET/POST /family/memory/{memory_id}/edit`.
- Серверная проверка авторства: edit-route доступен только если `family_member_id` из cookie совпадает с `Memories.author_id` (иначе `403`).
- В UI добавлена ссылка «Редактировать» в `/family/person/{person_id}` и `/family/timeline` только для автора.
- После сохранения обновлённый текст сразу появляется в профиле/ленте (обновляются поля `content_text`, `transcript_readable`, `transcript_verbatim`).

### Validation

- `python3 -m py_compile app/api/routes/tree.py`

## Update: T32 — waitlist (ранний доступ) на публичном лендинге

Date: 2026-04-24

### Structural change

Yes

### Schema change

Yes (new table `EarlyAccessRequests`)

### Changes

- На лендинге добавлен видимый CTA-блок и кнопка «Записаться в ранний доступ» с формой (email/telegram) в модальном окне.
- Заявка отправляется из лендинга в приложение через публичный API: `POST /api/early-access-request` (CORS разрешён для `https://timewoven.ru`).
- Данные сохраняются в таблицу `EarlyAccessRequests` с метками: `contact_value`, `preferred_channel`, `created_at` и `source='landing_waitlist'`.
- Добавлен админский read-only список заявок: `GET /admin/early-access`.

### Validation

- `python3 -m py_compile app/api/routes/public_api.py app/main.py`

## Update M4 – Local LLM Provider for Memory Analysis

Date: 2026-04-24

### Structural change

Yes

### Schema change

No

### Architecture

- На VPS поднят отдельный localhost‑only HTTP‑сервис `ops/local_llm/`, который слушает `127.0.0.1:9000` и даёт:
  - `GET /health` → `{"status":"ok"}`
  - `POST /analyze` → AnalysisResult‑совместимый JSON (`summary/persons/dates/locations/raw_provider/status`)
- Основное приложение TimeWoven получает анализ через новый AI‑провайдер `local_llm` в `app/services/ai_analyzer.py`.

### Files changed / added

- `app/services/ai_analyzer.py` (новый провайдер `local_llm`, env alias `AIPROVIDER`)
- `app/api/routes/admin.py` (admin‑проверка `/admin/ai/local-llm-check`)
- `app/web/templates/admin/admin_ai_local_llm_check.html` (страница статуса)
- `app/web/templates/admin/admin_dashboard.html` (ссылка на проверку)
- `ops/local_llm/service.py`, `ops/local_llm/Dockerfile`, `ops/local_llm/docker-compose.yml`, `ops/local_llm/timewoven-llm.service`, `ops/local_llm/README.md`
- `scripts/test_local_llm.py` (smoke‑скрипт)
- `.env` (добавлены `AIPROVIDER` и `AI_LOCAL_LLM_URL`, без удаления существующих переменных)

### Validation / How to verify

- LLM service:
  - `curl -s http://127.0.0.1:9000/health`
  - `curl -s -X POST http://127.0.0.1:9000/analyze -H 'content-type: application/json' -d '{"text":"Это тестовая история о семье"}'`
- App-side client:
  - `AI_PROVIDER=local_llm` и `AI_LOCAL_LLM_URL=http://127.0.0.1:9000/analyze`
  - `python3 scripts/test_local_llm.py`
- Admin browser check:
  - открыть `/admin/ai/local-llm-check` → отображается “работает / не работает” + JSON результата.

## Fix: waitlist defects — landing mailto + admin 500

Date: 2026-04-24

### Structural change

No

### Schema change

No

### Changes

- Исправлен остаточный статический файл `timewoven-landing-clean.html`, где CTA «Запросить ранний доступ» всё ещё был `mailto:hello@timewoven.ru` и открывал почтовый клиент вместо формы.
- `/admin/early-access`: добавлен safe fallback на случай DB/схемных ошибок (страница рендерится без 500 и показывает empty state + текст ошибки).

### Validation

- `python3 -m py_compile app/api/routes/admin.py`

## Update: T31.2 — системный фикс семантики count/list в family profile

Date: 2026-04-24

### Structural change

Yes

### Schema change

No

### Changes

- Подтверждена фактическая семантика profile count на реальных данных для `person_id=3`, `person_id=1` (кейс с историческим `16`) и `person_id=4` (нулевой кейс).
- Введено единое правило профиля v1: основной показатель = related visible memories (`author + participant` через `MemoryPeople`, без дублей, только family-visible + audience-visible).
- Шапка и список профиля остаются на одном source-of-truth helper: `get_visible_memories_for_person_for_viewer(...)`.
- UI-подпись счётчика уточнена до «связанных воспоминаний», чтобы не путать метрику related с authored-only.
- Исправлена техническая нестабильность audience-фильтра (`InvalidRequestError` из-за correlated EXISTS): `filter_memories_for_person_audience(...)` переведён на `IN (select memory_id from MemoryPeople ...)`.

### Verified breakdown (viewer_person_id=1)

- `person_id=3` (Наталия):
  - `authored_visible_count=7` ids `[2,3,4,11,12,13,15]`
  - `participant_visible_count=0` ids `[]`
  - `related_visible_count=7` ids `[15,13,12,11,4,3,2]`
  - `raw_old_profile_count=9` ids `[2,3,4,10,11,12,13,14,15]`
  - Текущий профиль: `header=7`, `list=7`.
- `person_id=1` (кейс исторического `16`):
  - `authored_visible_count=0` ids `[]`
  - `participant_visible_count=2` ids `[3,4]`
  - `related_visible_count=2` ids `[4,3]`
  - `raw_old_profile_count=16` ids `[16,17,19,20,21,22,23,24,25,26,27,28,29,31,32,39]`
  - Текущий профиль: `header=2`, `list=2`.
- `person_id=4` (малый/нулевой кейс):
  - `authored_visible_count=0` ids `[]`
  - `participant_visible_count=0` ids `[]`
  - `related_visible_count=0` ids `[]`
  - `raw_old_profile_count=0` ids `[]`
  - Текущий профиль: `header=0`, `list=0`.

### Validation

- `python3 -m py_compile app/services/memory_audience.py app/services/memory_visibility.py app/api/routes/tree.py app/models/__init__.py`
- Runtime probe через `.env` + `PYTHONPATH=.`: breakdown и ID-списки по 3 персонам получены; `current_profile_header_count == current_profile_list_count` во всех проверенных кейсах.

## Update: T28 — audience rules v1 для family memories

Date: 2026-04-24

### Structural change

Yes

### Schema change

No

### Changes

- Добавлен backend-helper `app/services/memory_audience.py` с правилом audience v1 для family memories.
- Введена конфигурируемая глубина `FAMILY_MEMORY_AUDIENCE_DEPTH = 3`.
- Круг допустимых людей для текущего family-user считается BFS-обходом от `family_member_id` из family session/cookie.
- Для обхода используются `PersonRelationship` как parent/child edges (`bioparent`, `child`, `adoptparent`, `adoptchild`, `stepparent`, `stepchild`, `guardian`, `ward`) и `Unions` как partner edges.
- Audience-фильтр накладывается поверх уже существующего family visibility слоя T31, а не вместо него: сначала `visible_for_ui`, потом `visible_for_person_by_kinship_depth`.
- Правило видимости memory v1: запись видна, если `Memory.author_id` входит в разрешённый круг или если в `MemoryPeople` есть хотя бы один участник из этого круга.
- `app/api/routes/tree.py`: audience-фильтр подключён в `family timeline`, `family welcome`, `family reply` и в список memories на `family/profile`.
- `app/services/memory_visibility.py`: базовый family-visible query усилен исключением технических source types (`max_contact_test_marker`, `max_session`) до применения audience.
- `app/models/__init__.py`: добавлены ORM-модели `RelationshipType` и `PersonRelationship`; `MemoryPeople` используется для author/participant matching.

### Product rule v1

- Текущий family-user видит только опубликованные family-visible memories, связанные с людьми в радиусе `N=3` от его `person_id` по семейному графу.
- Связь memory с кругом определяется по `author_id` и по участникам в `MemoryPeople`.
- Админские экраны не менялись и не ограничиваются новым audience-фильтром.

### Validation

- `python3 -m py_compile app/api/routes/tree.py app/services/memory_visibility.py app/services/memory_audience.py app/models/__init__.py`
- Runtime-check на реальной БД после загрузки `.env`: подтверждены реальные `RelationshipType.code`, BFS для `root_person_id=2` возвращает круг из `9` человек на глубине `3`, audience-filtered query исполняется без ошибок.

### Open edge cases

- Если в данных есть семейные связи, не выраженные через `PersonRelationship` или `Unions`, они пока не попадут в audience circle.
- Исторические/временные интервалы `valid_from/valid_to` в `PersonRelationship` для audience v1 пока не учитываются.
- Family profile по-прежнему открывается как экран персоны; T28 ограничивает только memories внутри этого экрана, а не сам доступ к карточке.

## Update: T31 — аудит и выравнивание логики Memories

Date: 2026-04-24

### Structural change

Yes

### Schema change

No

### Changes

- Проведён аудит family-facing логики `Memories`: профиль считал raw authored count по `Memories.author_id`, а список воспоминаний в профиле отсутствовал; timeline уже фильтровал только `published + non-archived + active author + non-empty text` и скрывал технические blob-пейлоады.
- Подтверждено по данным, что `MemoryPeople` в БД заполнена, но ранее не использовалась в family UI.
- Добавлен общий helper `app/services/memory_visibility.py` с базовой пользовательской фильтрацией memories.
- `app/api/routes/tree.py`: profile count и profile list переведены на единый helper `get_visible_memories_for_person(...)`; timeline переведён на общий base query/text helper без изменения продуктового правила `published-only`.
- `app/web/templates/family/profile.html`: добавлен список видимых воспоминаний с ролью связи (`автор` / `участник`), датой, текстовым preview, ссылкой на existing reply screen и аккуратным empty state.
- Отдельная audit-note сохранена в `tech-docs/memories-visibility-audit-t31.md`.

### Audit notes

- Фактическое расхождение подтверждено на данных: например, у `person_id=1` raw authored count был `16`, но по live visibility в профиле остаются только `2` participant-memory через `MemoryPeople`; у `person_id=3` raw count `9` сужается до `7` live published memories.
- Из пользовательских экранов исключаются архивные, не опубликованные (`draft`/`archived`), тестовые marker rows (`max_contact_test_marker`) и технические raw blobs.
- Серые зоны оставлены без schema change: legacy rows со статусом `archived` при `is_archived=false`, а также отсутствие отдельного статуса для `AI-draft` vs `human-approved`.

### Validation

- `python3 -m py_compile app/services/memory_visibility.py app/models/__init__.py app/api/routes/tree.py`
- Runtime-check helper на реальных данных: profile visibility корректно возвращает authored/participant наборы и выравнивает count/list.

## Update: T30.3 — компактные фильтры в заголовках /admin/people

Date: 2026-04-24

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/admin/admin_people.html`: фильтры переработаны в компактный column-oriented формат через header dropdown/popover в колонках `Аватар`, `Роль`, `Статус`, `Канал`, `Жив`.
- Отдельное поле поиска по `имени/ID` сохранено и работает совместно с колонковыми фильтрами (пересечение условий).
- Добавлена единая кнопка `Сбросить все фильтры`, которая очищает и текстовый поиск, и все колонковые фильтры.
- Для активных фильтров добавлена визуальная индикация (подсветка filter-кнопки в заголовке).
- Sticky header и horizontal scroll сохранены без регрессий.

### Implementation

- Реализация фильтрации: client-side.
- Источники значений: существующие data-атрибуты строк (`data-avatar-state`, `data-role-key`, `data-status-key`, `data-channel-key`, `data-alive-key`) из backend контекста T30.2.
- Без изменений модели данных `People` и без миграций.

### Smoke-check

- `/admin/people` после логина: `200`.
- Проверено наличие header filter controls, reset-кнопки и объединённой логики фильтрации `search + filters`.

---

## Update: T30.2 — расширенные фильтры в /admin/people

Date: 2026-04-24

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/admin/admin_people.html`: добавлена панель бизнес-фильтров (avatar, role, status, channel, is_alive) и кнопка `Сбросить все фильтры`.
- Фильтры работают совместно с существующим поиском по имени/ID (client-side, единый `applyFilter`).
- Для строк таблицы добавлены data-атрибуты фильтрации: `data-avatar-state`, `data-role-key`, `data-status-key`, `data-channel-key`, `data-alive-key`.
- `app/api/routes/admin.py`: backend `/admin/people` расширен вычислением признаков `has_avatar`, `avatar_is_expired`, `avatar_state`, `avatar_state_label`, `avatar_last_updated_at` + нормализованные ключи фильтрации.

### Avatar logic (v1)

- Источник даты аватара: `AvatarHistory` (берётся последняя актуальная запись `is_current=1`, fallback — последняя любая запись по персоне).
- `no_avatar`: отсутствует текущий аватар (нет `People.avatar_url` и нет валидного пути в `AvatarHistory`).
- `expired_avatar`: только для живых (`is_alive=true`) при наличии аватара и возрасте последнего обновления `> 365` дней.
- `actual_avatar`: аватар есть и не просрочен; для умерших при наличии аватара применяется `actual_avatar`.

### Smoke-check

- `/admin/people` после логина: `200`, фильтры и data-атрибуты присутствуют в HTML.
- Sticky header + horizontal scroll контейнер сохранены.

---

## Update: T30 — admin UX hardening и smoke-check

Date: 2026-04-24

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/admin/admin_people.html`: добавлены sticky header для таблицы (`position: sticky`, непрозрачный фон, `z-index`) и client-side фильтр по имени/ID без backend-изменений.
- Для сохранения UX на узких экранах и при широких таблицах добавлен контейнер `table-wrap` с независимым horizontal/vertical scroll.
- `app/api/routes/admin.py`: добавлены `GET/POST /admin/logout` с очисткой `tw_admin_session` cookie.
- `app/web/templates/admin/admin_dashboard.html`: исправлен endpoint кнопки «Показать пароль дня» (`/admin/explorer/password`) и добавлена кнопка выхода из админки.

### Smoke-check

- Проверены маршруты: `/admin/people`, `/admin/people/new`, `/admin/people/{id}/edit`, `/admin/transcriptions`, `/admin/avatars`, login/logout flow.
- Все проверенные маршруты после логина возвращают `200`, logout корректно возвращает `303` на `/admin/login`, повторный доступ без cookie редиректит на login.

---

## Update: T24 — UX-пакет для админской работы с семейным архивом

Date: 2026-04-23

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/admin/admin_people.html`: ссылка `Редактировать` перенесена ближе к началу строки (сразу после статуса), чтобы не требовалась горизонтальная прокрутка таблицы.
- `app/api/routes/tree.py`: лимит параметра `depth` увеличен до `1..10` для `/family/tree` и `/family/tree/json`.
- `app/web/static/js/family_graph.js`: фронтенд-контрол глубины увеличен до `MAX_DEPTH=10` (и начальное ограничение `Math.min(..., 10)`).
- `app/web/templates/admin/admin_person_edit.html`: форма перегруппирована в рабочие блоки (основные данные, даты и статусы, контакты, союз/дети, зарезервированный блок под будущие воспоминания) без изменения маршрутов.

---

## Update: T23.4 — корректировка союза 9 под новую семью

Date: 2026-04-23

### Structural change

No

### Schema change

No (data-only)

### Changes

- Выполнена data-корректировка `Unions.id=9`: `partner1_id=57`, `partner2_id=58`.
- Набор детей союза 9 приведён к `{16,59,60}`: удалены лишние child-связи для `union_id=9`, вставлены недостающие.
- Проведён SQL-proof до/после: до — `(52,53)` + `{54}`, после — `(57,58)` + `{16,59,60}`.

---

## Update: T19 — live bot replies for Max session flow

Date: 2026-04-23

### Structural change

No

### Schema change

No

### Changes

- Добавлен новый модуль `app/services/bot_reply.py` для контролируемых ответов Max-бота.
- В `bot_reply` реализованы 3 функции для ключевых шагов:
  - `build_ack_for_new_session(...)`
  - `build_ack_for_audio(...)`
  - `build_ack_for_finalize(...)`
- Reply-слой использует `AI_PROVIDER`:
  - при `llama_local` может попытаться дать вариацию через AI;
  - при ошибке AI / disabled / пустом результате — всегда fallback шаблон.
- Добавлен лимит длины ответа (`<=240`) для финальных user-facing реплик.
- `app/api/routes/bot_webhooks.py` обновлён: ответы в text/audio/finalize ветках теперь формируются через `bot_reply`.
- Live smoke-test (HTTP, session flow) пройден:
  - Step1 reply: "Я записываю эту историю. Можете продолжать, а когда закончите — напишите 'Готово'."
  - Step2 reply: "Голос получил и сохранил. Можете добавить ещё или написать 'Готово'."
  - Step3 reply: "Спасибо. Я сохранил эту историю как черновик семейного архива."
  - SQL: session finalized, memory_id заполнен, `Memory(source_type='max_session', transcription_status='draft')` создана.

---

## Update: T18.D — finalize command normalization for Max sessions

Date: 2026-04-23

### Structural change

No

### Schema change

No

### Changes

- Исправлен `is_finalize_command(...)` в `app/services/max_session_service.py`.
- Добавлена нормализация команды завершения: trimming + lower + удаление хвостовой пунктуации (`!`, `.`, `?`).
- Команды вида `Готово!`, `готово!`, `это всё!`, `завершить`, `done`, `finish` теперь корректно триггерят финализацию.
- В text-ветке webhook команда завершения не пишется как обычный message item.
- Live validation (`Привет! Это тест сессии` → голосовое → `Готово!`) прошла:
  - `max_chat_sessions.status = finalized`
  - `memory_id` заполнен
  - создана ровно одна `Memory(source_type='max_session', transcription_status='draft')`
  - audio item + `local_path` присутствуют в metadata памяти.

---

## Update: T18.C — Max audio transcription inside session flow

Date: 2026-04-23

### Structural change

No

### Schema change

No

### Changes

- В `app/api/routes/bot_webhooks.py` в audio-ветке добавлен автоматический вызов `TranscriptionService` после успешного локального скачивания.
- Результат транскрипции добавляется в `draft_items` текущей open session через `max_session_service.add_audio_item(...)`.
- Для аудио теперь сохраняются поля: `audio_url`, `local_path`, `transcription_text`, `transcription_status`, `transcribed_at`, `transcription_error`.
- В `app/services/max_session_service.py` обновлён `_rebuild_draft_text`: включает успешные voice-фрагменты как `[voice] ...`.
- `finalize_session(...)` теперь всегда кладёт raw `draft_items` в metadata (`Memory.transcript_verbatim`), поэтому в финальной draft memory остаются все результаты транскрипции.
- Fallback реализован: при неуспехе транскрипции (`empty/error`) webhook не падает, аудио остаётся в черновике, финализация всё равно создаёт Memory.
- Удалён legacy-дубликат маршрута `/webhooks/maxbot/incoming`; оставлен один актуальный handler.
- Smoke-tests пройдены: service-level (успех+ошибка), webhook e2e (text+audio+Готово) через HTTP.

---

## Update: T18.B — Max chat sessions + draft aggregation + audio hardening

Date: 2026-04-23

### Structural change

Yes (new table `max_chat_sessions`)

### Schema change

Yes — миграция `006_add_max_chat_sessions.sql`

### Changes

- Добавлена таблица `max_chat_sessions` (id, max_user_id, person_id FK, status, created/updated/finalized_at, draft_text, draft_items JSON, message_count, audio_count, memory_id FK, analysis_status).
- Добавлен ORM-модель `MaxChatSession` в `app/models/__init__.py`.
- Создан `app/services/max_session_service.py`: `get_open_session`, `create_session`, `get_or_create_open_session`, `add_text_item`, `add_audio_item`, `finalize_session`, `is_finalize_command`.
- Рефакторинг `app/api/routes/bot_webhooks.py`: входящий текст/аудио → `add_text_item`/`add_audio_item`; команда «Готово/Завершить/…» → `finalize_session`; контакты без изменений.
- Audio hardening: `_download_audio_to_raw` вызывается всегда; при ошибке скачивания сессия не падает, CDN URL сохраняется в `draft_items`.
- Финализация создаёт `Memory(source_type='max_session', transcription_status='draft')` с AI-metadata.
- Finalize commands: `готово`, `завершить`, `это всё`, `это все`, `закончить`, `стоп`, `end`, `done`, `finish`.
- Smoke-test пройден: 9 шагов против реальной БД (lifecycle + fallback при AI error).

---

## Update: T18.A — AI-провайдер llama_local (LLaMA local HTTP server)

Date: 2026-04-23

### Structural change

No

### Schema change

No

### Changes

- В `app/services/ai_analyzer.py` добавлен класс `LlamaLocalAnalyzerProvider` (`provider_name="llama_local"`).
- Читает `AI_LLAMA_LOCAL_URL` из `.env`; POST `{"text": str}`; парсит `{"summary", "people", "events", "dates"}`.
- Таймаут 30 с (`LLAMA_LOCAL_TIMEOUT_SECONDS`); все ошибки → `status="error"`, сервис не падает.
- Добавлено поле `events` в возвращаемый словарь (для LLaMA-ответа; другие провайдеры возвращают пустой список).
- `_build_provider` в `ProviderAgnosticAnalyzer` дополнен веткой `"llama_local"`.
- Обновлены `TECH_PASSPORT.md` (раздел M2 AI abstraction) и `TimeWoven_Anchor_2026-04-23.md` (AI-анализ + Max-бот).

---

## Update: T17 — Soft-archive duplicate People 40/43 after Max contacts manual review

Date: 2026-04-23

### Structural change

No

### Schema change

No (data-only)

### Changes

- Диагностика FK для `person_id IN (40, 43)`: нулевые ссылки во всех таблицах — ребайнд не потребовался.
- `People.person_id=40` переведён в `record_status='test_archived'` (дубль `person_id=2`; `messenger_max_id` уже был перенесён вручную).
- `People.person_id=43` переведён в `record_status='test_archived'` (дубль `person_id=8`; `messenger_max_id` уже был перенесён вручную).
- `person_id IN (41, 42)` подтверждены как `active` + `relative` + ru/en в `People_I18n` — изменений не вносилось.
- Записи физически не удалены (soft cleanup через `record_status`, как в T14/T16).

---

## Update: T16 — Max contacts ingestion hardening and duplicate cleanup

Date: 2026-04-23

### Structural change

Yes

### Schema change

Yes

### Changes

- Контактные attachment-события из Max больше не создают `People` автоматически: вместо этого сохраняются в `MaxContactEvents` (raw payload + sender/contact ids + names + status).
- В `bot_webhooks` удалён path авто-создания contact-person (`role='member'`, `is_user=1`, `messenger_max_id`) при `type='contact'`.
- Выполнен cleanup тестовых дублей: `People.person_id IN (35,36,37,38,39)` помечены `record_status='test_archived'`.
- Выполнен cleanup test marker memories: `Memories.id IN (20..24)` и future `TEST CONTACT` markers переводятся в archived (`is_archived=true`, `transcription_status='archived'`, `source_type='max_contact_test_marker'`).
- Live family surfaces ужесточены до `People.record_status='active'` (who-am-i, family tree/json, timeline, welcome random memory).
- Админка продолжает видеть архивные/тестовые записи для ручной ревизии.

## Update: T14 — person record_status and live family hiding for test_archived

Date: 2026-04-23

### Structural change

No

### Schema change

Yes

### Changes

- В `People` добавлено поле `record_status` (`active|archived|test_archived`, default `active`).
- Live family surfaces скрывают только `test_archived`: `who-am-i` + PIN flow, `/family/person/{id}`, `/family/tree/json`, `/family/timeline`.
- Админский список `/admin/people` сохраняет видимость всех записей и показывает `record_status` отдельной колонкой.
- Добавлена миграция `migrations/004_add_record_status_to_people.sql`, включая data update: `person_id IN (20,21,22,23) -> test_archived`.

## Update: T13 — finalize T11 timeline filtering and T12 maiden name UI polish

Date: 2026-04-23

### Structural change

No

### Schema change

No

### Changes

- family timeline now shows only published items.
- raw/json-like payloads are hidden from family timeline.
- maiden name moved from `h1` to a secondary muted line under the person name.

## Update: T9 — Role select in admin person form

Date: 2026-04-23

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/admin/admin_person_new.html` — текстовое поле роли заменено на `select` с фиксированными значениями: `placeholder`, `relative`, `family_admin`, `bot_only`.
- `app/api/routes/admin.py` — добавлен whitelist ролей и нормализация input: невалидные значения приводятся к `placeholder`.
- `app/services/people_service.py` — добавлена сервисная защита по тому же whitelist для устойчивости при альтернативных вызовах.
- Ручная проверка: форма отдаёт `select`, роли `relative` и `family_admin` корректно сохраняются и отображаются в `/admin/people`.

## Update: T8 — P1.11 Maiden Name Support

Date: 2026-04-23

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/admin/admin_person_new.html` — добавлено поле `Девичья фамилия (при рождении)` (`maiden_name_ru`) в форму создания персоны.
- `app/api/routes/admin.py` — чтение `maiden_name_ru` из формы, нормализация (`strip`, пустое значение -> `None`) и маппинг в `person_data["maiden_name"]`.
- `app/services/people_service.py` — запись `maiden_name` в `People.maiden_name` при создании персоны.
- `app/api/routes/tree.py` — в context профиля добавлен `person_i18n` для корректного сравнения текущей и девичьей фамилии.
- `app/web/templates/family/profile.html` и `app/web/templates/family/person_card.html` — отображение формата `Имя Фамилия (урождённая X)` только если `maiden_name` заполнено и отличается от текущей фамилии.
- E2E проверка выполнена через приложение: сценарий с `maiden_name != last_name` показывает скобки, сценарий с пустым `maiden_name` — без скобок.

## Update: T10 — Repository hygiene (docs/tech-docs/temp reorganization)

Date: 2026-04-23

### Structural change

Yes

### Schema change

No

### Changes

- Инвентаризировано содержимое документационных папок.
- **docs/** теперь содержит только публичные артефакты для GitHub Pages: `CNAME`, `logo.png`.
  - Удалены: `DATABASE_SCHEMA.md` (перемещён в `tech-docs/`), `snapshots/` (перемещён в `tech-docs/snapshots/`), `PROJECT_LOG.md` (перемещён в корень репозитория).
- **tech-docs/** стал центральным хранилищем архитектурной документации:
  - `DATABASE_SCHEMA.md` — техническое описание схемы PostgreSQL.
  - `adr/` — Architecture Decision Records (ADR-001 до ADR-006).
  - `snapshots/` — снимки состояния структуры и графов для истории.
  - `family-graph-snapshot-timeline-notes.md` — исследовательские заметки.
  - `README.md` — индекс документации.
- **temp/** остаётся рабочей песочницей, но полностью игнорируется git (кроме `.gitkeep` и `README.md`).
  - `project_docs/` с шаблонами документации сохранена для справки.
- **Корень репозитория:** `PROJECT_LOG.md` перемещён сюда для удобного доступа к операционному журналу.
- `.gitignore` подтверждён и усилен правилами для `temp/`.

**Результат:** репозиторий упорядочен, документация централизована в `tech-docs/`, граница между публичной документацией (`docs/`) и архитектурной (`tech-docs/`) ясна.

## Update: P1.14 — Exclude deceased relatives from who-am-I selector

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- Список персон для login/who-am-I теперь фильтруется по `is_alive = 1`.
- Защищены смежные шаги flow (`POST /who-am-i`, `GET/POST /who-am-i/pin`): умершие персоны исключены и при прямом доступе по `person_id`.
- Умершие сохраняются в базе, графе, карточках и истории, но больше не участвуют в selector-flow входа.

## Update: Docs artifact — PRODUCT_BACKLOG registry introduced

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- Добавлен постоянный продуктовый артефакт `PRODUCT_BACKLOG.md` в корне проекта.
- `PRODUCT_BACKLOG.md` используется как живой реестр продуктовых задач, статусов и принятых решений.
- Документ синхронизируется с `CHANGELOG.md`, `DB_CHANGELOG.md` и `docs/PROJECT_LOG.md` по мере реализации задач.

## Update: P1.12 — Support person creation without contact channel

Date: 2026-04-22

### Structural change

No

### Schema change

Yes

### Changes

- `app/api/routes/admin.py` — добавлена канонизация `preferred_ch` из UI (`NONE/MAX/TG/EMAIL/PUSH`) в БД-совместимые значения; отсутствие канала сохраняется как `NULL`.
- `app/api/routes/admin.py` — контакты (`max_user_id`, `phone`, `contact_email`) нормализуются: пустые строки больше не пишутся в БД, сохраняются как `NULL`.
- `app/api/routes/admin.py` — для `IntegrityError` добавлены точные сообщения: дубликат Max ID, недопустимый канал связи, общий fallback по контактам.
- `app/services/people_service.py` — нормализация опциональных текстовых полей на уровне сервиса, сохранение `preferred_ch` и контактов без принудительного значения `"None"`.
- `app/web/templates/admin/admin_person_new.html` — добавлен явный вариант `Нет канала связи` (по умолчанию), поддержка `MAX` в UI и поле `Email` как необязательный контакт.
- `migrations/003_expand_preferred_channel_for_max.sql` — применена миграция в рабочей БД: CHECK `People.preferred_ch` расширен до `('Max', 'TG', 'Email', 'Push', 'None')`.
- Ручные тест-кейсы создания (умерший без контактов, живой без контактов, живой с Max) проходят успешно.

## Update: P1.10 — Admin-only Person Creation Form activation

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/api/routes/admin.py` — добавлены два защищённых эндпоинта `/admin/people` (GET, список), `/admin/people/new` (GET, форма) и `/admin/people/new` (POST, обработка). Все роуты защищены `require_admin`.
- `app/services/people_service.py` — добавлена функция `create_person_with_i18n()` для одного-шагового создания Person + RU-i18n + опциональной EN-i18n записей в одной транзакции.
- `app/services/__init__.py` — подключена функция `create_person_with_i18n` в пакет services.
- `app/web/templates/admin/admin_people.html` — добавлена кнопка «+ Новая персона» для перехода на форму `/admin/people/new`.
- `app/web/templates/admin/admin_person_new.html` — создан новый шаблон админ-формы с полями: пол, жив ли, роль, язык, даты рождения/смерти, телефон, Max ID, предпочтительный канал, аватар, RU (обязательно имя) и EN (опционально) локализация.
- Валидация на уровне POST-обработчика: required first_name_ru, gender, допустимые values для lang, preferred_ch, date_prec.
- Редирект на `/admin/people` (статус 302) после успешного создания, рендер формы с ошибкой (400) при проблемах.
- Max Messenger contact mapsится на существующее поле `messenger_max_id` в таблице People.

## Update: M3-local — Local stub AI provider (HTTP client only)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/services/ai_analyzer.py` — `AI_PROVIDER=local_stub` теперь делает POST на `AI_LOCAL_STUB_URL` с телом `{ "text": ... }`, безопасно маппит `summary/people/dates` в общий результат анализа и не роняет pipeline при transport/JSON ошибках.
- `.env` — дефолт `AI_LOCAL_STUB_URL` приведён к `http://localhost:9000/analyze`, при этом `AI_PROVIDER=disabled` сохранён как безопасное поведение по умолчанию.
- `scripts/test_ai_local_stub.py` — добавлен локальный smoke-сценарий для режимов `disabled`, `local_stub` без URL, `local_stub` с недоступным URL и `local_stub` с успешным HTTP-моком.

## Update: M2 — Provider-agnostic AI analyzer for Max -> Memory

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/services/ai_analyzer.py` — добавлен единый интерфейс `analyze_memory_text(text)` и provider-agnostic слой с режимами `disabled | mock | anthropic | local_stub` через `AI_PROVIDER`.
- `app/services/ai_analyzer.py` — сохранена обратная совместимость через `MemoryAnalyzer.extract_entities(...)` (адаптер поверх нового интерфейса), чтобы не ломать текущие вызовы MaxBot.
- `app/api/routes/bot_webhooks.py` — после успешного `create_memory_from_max(...)` добавлен не-блокирующий вызов анализа; ошибки AI не роняют webhook и не мешают persistence/ACK.
- `app/services/memory_store.py` — добавлена `attach_analysis_to_memory(memory_id, analysis_result)` для безопасного сохранения анализа в metadata (`transcript_verbatim`) без изменения схемы БД.
- `.env` — добавлены `AI_PROVIDER` (безопасный default: `disabled`) и `AI_LOCAL_STUB_URL` как задел под будущий локальный провайдер.
- Контур M1 сохранён: входящее сообщение в любом случае сохраняется в Memory; ACK-ответ в Max остаётся простым.

## Update: M1 — Min loop Max -> Memory complete

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/api/routes/bot_webhooks.py` — входящий webhook `/webhooks/maxbot/incoming` стабилизирован для M1: невалидный JSON и payload без текста корректно возвращают `400`, добавлен минимальный контур сохранения текстовых сообщений в Memory + автоответ в Max после успешного сохранения.
- `app/services/memory_store.py` — добавлена функция `create_memory_from_max(user_id, text, raw_payload)`: сохраняет текст в `Memories.content_text`, source в `Memories.source_type='max_messenger'`, пытается связать сообщение с Person по `messenger_max_id`/`messenger_tg_id`, и пишет `external_id`/raw payload в metadata (`transcript_verbatim`).
- `app/bot/max_messenger.py` — `send_message(user_id, text)` больше не использует хардкод `chat_id`; отправка идёт через `httpx` на `MAX_API_SEND_URL` с `chat_id=user_id`.
- person mapping оставлен минимальным и безопасным: если соответствия нет, запись сохраняется в общий inbox (`author_id=NULL`) без падений.
- temporal/family graph слои не затрагивались.

## Update: Task 6C.3.1 — Keyframe Mode Toggle and Stale Fetch Guard

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/family_tree.html` — добавлен явный toggle `Слои времени: ON/OFF` в блоке keyframe-навигации, а также визуальная индикация активного режима и лёгкая подсветка текущего keyframe year.
- `app/web/static/js/family_graph.js` — wheel keyframe-navigation переведена в управляемый режим: при `OFF` wheel остаётся zoom/pan, при `ON` wheel листает keyframes и блокирует D3 wheel zoom через zoom filter.
- `app/web/static/js/family_graph.js` — добавлена защита от stale fetch на уровне request sequence в `loadAndRender`; устаревшие ответы игнорируются, чтобы не откатывать `activeYear` и текущий snapshot.
- Существующий fallback workflow по обычному year-input сохранён; backend/API не менялись.
- `tech-docs/family-graph-snapshot-timeline-notes.md` и `CHANGELOG.md` синхронизированы для трассируемости задачи 6C.3.1.

## Update: Task 6C.3 — Keyframe Navigation Prototype for Family Graph

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/static/js/family_graph.js` — добавлена прототипная keyframe-навигация поверх stable year update: сбор keyframe years из текущих graph-данных, состояние `currentKeyframeIndex`, переходы prev/next и wheel-navigation в режиме `По году`.
- `app/web/templates/family_tree.html` — добавлены минимальные кнопки `‹ предыдущий слой` / `следующий слой ›` и индикатор текущего keyframe year рядом с temporal-контролами.
- `tech-docs/family-graph-snapshot-timeline-notes.md` — добавлен раздел `Prototype 6C.3 — Keyframe Navigation Notes` (подход, ограничения, рекомендации для Phase 2).
- Backend/API не менялись; numeric year input и fallback к обычному year workflow сохранены.

## Update: Task 6C.2 — Stable Year Update Prototype for Family Graph

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/static/js/family_graph.js` — реализован прототип стабильного обновления снапшота при смене года (feature flag `USE_STABLE_UPDATE`): в режиме «По году» обновление идёт in-place через keyed joins и reuse существующей D3 simulation.
- Для существующих узлов сохраняются текущие координаты (`x/y/vx/vy`), что уменьшает layout jumping при переходах между соседними годами.
- Для появляющихся/исчезающих узлов и рёбер добавлены базовые fade-in/fade-out transition.
- Поведение режима «Сейчас» не изменено; backend/API не менялись.
- `tech-docs/family-graph-snapshot-timeline-notes.md` — добавлен раздел "Prototype 6C.2 — Stable Update Notes" с ограничениями и next steps.

## Update: Task 6C.1 — Snapshot Timeline Preparation (ADR-006 Follow-up)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `tech-docs/family-graph-snapshot-timeline-notes.md` — добавлен краткий техдок по подготовке Snapshot Timeline: текущая точка входа year-mode, где происходит reload/fetch, почему сейчас есть layout jumping, и минимальный Phase 1 путь без backend-рефакторинга.
- Зафиксировано, что на текущем этапе wheel/swipe не внедрялись и runtime-логика семейного графа не менялась.
- Этап выполнен как engineering discovery после ADR-006: подготовка к будущей реализации temporal layers / snapshot navigation.

## Update: ADR-006 Proposal — Temporal Layers and Snapshot Navigation

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `tech-docs/adr/ADR-006.md` — добавлен новый ADR со статусом `Proposed`: концепция temporal layers/snapshots для семейного графа, keyframe-навигация (wheel/swipe), continuity между соседними снапшотами и staged implementation path.
- `tech-docs/README.md` — обновлён индекс ADR (добавлена запись ADR-006).
- Зафиксировано, что ADR-006 не требует немедленных изменений БД или backend-логики; это roadmap для UX/visualization эволюции поверх текущего режима `Сейчас/По году`.

## Update: Task 6A — Year Timeline Slider in Family Graph

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/family_tree.html` — добавлен UI-элемент шкалы времени (`#year-slider`) и подпись «Год для режима «По году»» в панели управления графом.
- `app/web/static/js/family_graph.js` — рефакторинг работы с годом: выделены `getCurrentYearFromUI()`, `setYearInUI(year)`, `applyYearAndReloadGraph(year)`.
- `app/web/static/js/family_graph.js` — добавлена двусторонняя синхронизация input ↔ slider, диапазон лет `1900..(current+5)` и шаг `1`.
- `app/web/static/js/family_graph.js` — добавлен debounced reload (250мс) для запросов `/family/tree/json?year=...` при движении бегунка, чтобы не перегружать API.
- Поведение режимов: в «Сейчас» поле года и слайдер отключены (видимы, но не активны); в «По году» активны и управляют temporal-визуализацией.

## Update: ADR-005 Proposal — Union v2 and Temporal Strict Mode

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `tech-docs/adr/ADR-005.md` — добавлен новый ADR со статусом `Proposed`: целевая модель Union v2 (`union_type`, `single_parent`, adoption/guardianship через union), а также концепция двух temporal-режимов (soft/strict) для семейного графа.
- `tech-docs/README.md` — обновлён индекс ADR (добавлены ADR-003, ADR-004, ADR-005).
- Подчёркнуто, что изменение на текущем этапе документальное: без миграций и без изменения поведения v1.

## Update: Family Graph 5F — Temporal Filtering End-to-End Fix

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/services/family_graph.py` — `extract_year()` теперь корректно парсит даты в формате "DD.MM.YYYY" (хранится в БД), не только "YYYY-MM-DD". Год извлекается из последней части при разделении по ".". Также перезапущен сервис, т.к. `family_graph.py` был изменён уже после запуска (`union_to_node` получал корректные даты, но старый бинарный процесс не подхватывал изменения).
- Причина проблемы: `union.start_date` и `union.end_date` хранятся как строки "DD.MM.YYYY" (например, "06.11.1976"). Предыдущий `extract_year` разбивал по "-" и получал `int("06.11.1976")` → ValueError → None, что делало все union permanently active.
- Проверка: `year=1980` → union 1 (1976–1983) `is_active=True`, union 2 (2007+) `is_active=False`; `year=2010` → union 1 `is_active=False`, union 2 `is_active=True`. ✓

## Update: Family Graph 5C — Filter & Temporal Bug Fixes

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/services/family_graph.py` — `union_to_node` принимает `year`, вычисляет `is_active` относительно него; при переданном `year` персоны с `birth_year > year` не попадают в граф (backend-фильтрация).
- `app/web/static/js/family_graph.js` — `updateVisuals` переработан: строится `hiddenNodeIds` из фильтра "Умершие", затем `visibleEdgeIds` с учётом скрытых узлов, затем `visibleDegree` — union-узлы и изолированные person-узлы без видимых рёбер скрываются; `getRequestedYear()` в режиме "Сейчас" возвращает `null`; `forceCollide`/`linkDistance` увеличены для root-узла.
- Проверки: Python `ast.parse` OK, JS `esprima.parseScript` OK; `curl year=1977` вернул на 1 узел и 1 ребро меньше — фильтрация подтверждена.

---

## Update: Temporal Family Graph 5B — Visual Polish

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/family_tree.html` — визуально улучшены temporal-контролы (`Сейчас/По году` как toggle), состояния кнопок истории, disabled-стили поля года и типографика нижней панели.
- `app/web/static/js/family_graph.js` — обновлены стили и поведение графа без изменения backend-логики: более явные состояния рёбер (`active`/`inactive`/`neutral`), hover/focus polish, подпись фокусного узла с годами жизни, дружелюбный temporal summary и refined CTA в нижней панели.
- Проверка: JS parse (`esprima.parseScript`) успешно; `timewoven.service` перезапущен.

## Update: Temporal Family Graph v2 (v1.22)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/schemas/family_graph.py` — расширен контракт узлов/рёбер для temporal-данных (`death_year`, `start_date`, `end_date`, `is_active`, `is_active_for_year`).
- `app/services/family_graph.py` — добавлена year-aware логика для графа: вычисление активности связи на выбранный год и заполнение `valid_from`/`valid_to`.
- `app/api/routes/tree.py` — `/family/tree/json` поддерживает `year`; `/family/tree` прокидывает `year` в шаблон; `/family/timeline` поддерживает фильтры `person_id`/`union_id` для кнопок из нижней панели.
- `app/web/templates/family_tree.html` — добавлены temporal-контролы (режим `Сейчас/По году` + input года), прокинут `window.GRAPH_YEAR`.
- `app/web/static/js/family_graph.js` — добавлен temporal-режим загрузки с `year`, визуальное разделение active/inactive/neutral рёбер, расширение нижней панели (person/union) и переходы в timeline.
- Проверка: Python compile и JS parse пройдены; `timewoven.service` перезапущен; `/health` и оба варианта `/family/tree/json` (с и без `year`) возвращают `200`.

## Update: Family Graph Syntax Hotfix (v1.21.1)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/static/js/family_graph.js` — исправлен синтаксический дефект в районе `line ~460`: восстановлена функция `updateDepthButtons()` и корректная структура скобок, из-за которой браузер ранее падал с `missing ) in parenthetical`.
- Выполнена синтаксическая проверка JS через `esprima.parseScript` (валидно).
- Перезапущен `timewoven.service`, подтверждён статус `active (running)`.
- Проверены endpoint'ы после рестарта: `/static/js/family_graph.js` -> 200, `/family/tree/json?root_person_id=1&depth=2` -> 200, JSON содержит `nodes` и `edges`.

## Update: Family Graph 4B — Bottom Panel UX (v1.21)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/static/js/family_graph.js` — убран action-card showTooltip (кнопки Профиль/Корень/Закрыть поверх графа). Добавлен: showHoverTooltip (name-only, no actions), updateBottomPanel(), getUnionPartners(). Обновлён click handler: person → setFocus + updateBottomPanel; union → updateBottomPanel + visual ring. History nav обновляет нижнюю панель. State расширен: selectedUnionId.
- `app/web/templates/family_tree.html` — удалены CSS-стили action-card (.tt-actions, .tt-btn). #graph-tooltip упрощён до hover-label. Добавлены: CSS .gip-* (нижняя панель в палитре TimeWoven), HTML #graph-info-panel с .gip-placeholder / .gip-content / .gip-name / .gip-meta / .gip-actions.
- Подробности: CHANGELOG v1.21-family-graph-4b-ux.

## Update: Family Graph v2 Acceptance Hotfix (v1.20.1)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/family_tree.html` — удалены дублирующиеся Jinja-блоки (`extends`/`block`) после первичного деплоя Graph v2.
- `app/web/static/js/family_graph.js` — файл переписан в валидный единый v2 скрипт (устранён parse error `Unexpected end of input`).
- Выполнена приёмка через Playwright (реальный браузер): граф рендерится; click/focus, tooltip, filters, depth и history работают; JS page errors отсутствуют.

## Update: Family Graph v2 MVP (v1.20)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/static/js/family_graph.js` — полная замена (Graph v2): focus mode, semantic edges, dim, filters, history, dark tooltip, depth controls.
- `app/web/templates/family_tree.html` — полная замена: controls panel, filter buttons, depth ±, history nav, #graph-tooltip.
- Подробности: CHANGELOG v1.20-family-graph-v2-mvp.

## Update: Navigation & Admin Security Fixes (v1.19)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

* Applied navigation & admin security fixes per audit (Задание №1) — see CHANGELOG v1.19-nav-auth-security-fixes.
* `app/security.py` — полностью переписан: добавлена реальная auth-логика через cookie `tw_admin_session`, `make_admin_token()`, защита `require_admin` с редиректом на `/admin/login`.
* `app/api/routes/admin.py` — добавлены `import os`, guard `require_admin` в `GET /admin/avatars`, реальная проверка credentials в `POST /admin/login`, защита `next` от open redirect, установка сессионной cookie.
* `app/api/routes/tree.py` — исправлен redirect в `POST /family/reply/{id}`: `person_id=None` больше не попадает в URL.
* `timewoven.service` перезапущен — production-сервер теперь работает на актуальном коде.

### Result

* `/health` → 200 на production.
* `next=` в `_require_family_session` передаёт реальный URL запроса.
* Все admin-маршруты требуют auth (cookie `tw_admin_session`), иначе редирект на `/admin/login`.
* `POST /admin/login` не допускает open redirect.
* `POST /family/reply` не генерирует `422` при отсутствии `person_id`.

---

## Baseline: Stabilization & Control Phase Complete

Date: 2026-04-21

### Folders

docs/snapshots/tree_2026-04-21.txt

### Files (Critical)

* app/models.py
* .env
* nginx.conf
* docker-compose.yml (если есть)
* requirements.txt или package.json

### Logic

* Структура зафиксирована как исходная точка стабилизации
* Все изменения структуры отслеживаются через snapshots
* Любые изменения должны сопровождаться логированием (Handshake protocol)
* Закрытие любой сессии изменений допускается только после проверки заполнения обязательных журналов

---

## Update: Total Traceability Protocol (Mandatory)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

* Зафиксирован обязательный процесс логирования для всех изменений в фазе «Стабилизация и Контроль».
* Введено обязательство по каждой задаче обновлять `CHANGELOG.md` с датой, типом изменения и кратким обоснованием.
* Подтверждено правило: любые структурные изменения каталогов/файлов фиксируются в `docs/PROJECT_LOG.md` с причиной.
* Подтверждено правило: изменения SQLAlchemy/PostgreSQL требуют синхронизации `docs/DATABASE_SCHEMA.md` и записи в `DB_CHANGELOG.md`.
* Введен инфраструктурный контроль: изменения `scripts/backup_manager.sh` и Nginx-конфигураций должны логироваться в журналах.

### Result

* Total Traceability включен как обязательный operational gate.
* Сессия изменений не считается завершенной без подтверждения, что все релевантные журналы обновлены.

---

## Update: FastAPI Max Bot Webhook Router

Date: 2026-04-21

### Structural change

Yes

### Schema change

No

### Changes

* Added MAX_BOT_ID=235301348589_bot to .env.
* Added new router app/api/routes/bot_webhooks.py with prefix /webhooks/maxbot.
* Added POST endpoint /incoming with JSON payload parsing.
* Added payload validation for text field with HTTP 400 on missing value.
* Connected router in app/main.py via app.include_router(bot_webhooks.router).

### Result

* FastAPI webhook endpoint for Max Messenger is integrated and ready for incoming events.
* Implemented outgoing message logic for MAX Messenger API using httpx.
* Integrated Max Bot with Persistence Layer: incoming stories are saved to `Memories` via `app/services/memory_store.py`.

## Update: Max Messenger Bot Architecture Start

Date: 2026-04-21

### Structural change

Yes

### Schema change

No

### Changes

* Started Phase 2.2 architecture for Max Messenger Bot.
* Added new bot module folder app/bot with app/bot/__init__.py.
* Added async integration scaffold in app/bot/max_messenger.py.
* Wired MemoryAnalyzer call path for incoming text processing.

### Result

* Repository scan completed for Max Bot metadata in TECH_PASSPORT.md, .env, and app/web/templates/admin/admin_login.html.
* No fixed Max Bot ID or status was found in current project files.

## Fix: ENV Override for Anthropic Models

Date: 2026-04-21

### Structural change

No

### Schema change

No

### Changes

* Enabled dotenv override=True to force reload of updated .env variables

### Result

```text
Primary model (claude-3-5-sonnet-20241022) failed: NotFoundError: Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-5-sonnet-20241022'}, 'request_id': 'req_011CaGoQ1gzwrGy7Qw2FGWNj'}
Fallback model (claude-3-haiku-20240307) also failed: NotFoundError: Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-haiku-20240307'}, 'request_id': 'req_011CaGoQ3LTvyAz1PJMDK9Ru'}; returning empty extraction
Extracted entities:
{'dates': [], 'persons': [], 'locations': []}
Person lookup result: person_id=2
```

[2026-04-21] — Automation Update
* Action: Enabled daily crontab backup at 03:00
* Status: Stabilization block officially closed.

[2026-04-21] — Structural Change
* Action: Added `app/services` service module baseline for Phase 2.1 AI-Enrichment.
* Status: Services folder registered in project structure.

[2026-04-21] — AI Integration Update
* Action: Migrated `app/services/ai_analyzer.py` from mock extraction to Anthropic Claude API.
* Details: Added `ANTHROPIC_API_KEY` env-based config, JSON parsing with error handling, and model fallback (Sonnet -> Haiku).
* Status: AI extraction pipeline connected to external LLM provider.

## Update: Anthropic Model Fix

Date: 2026-04-21

### Structural change

No

### Schema change

No

### Changes

* Updated ANTHROPIC_PRIMARY_MODEL to claude-3-5-sonnet-20241022
* Updated ANTHROPIC_FALLBACK_MODEL to claude-3-haiku-20240307

### Result

```text
Primary model (claude-3-5-sonnet-latest) failed: NotFoundError: Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-5-sonnet-latest'}, 'request_id': 'req_011CaGoBpaRp6tVC1KhfLuUz'}
Fallback model (claude-3-haiku-latest) also failed: NotFoundError: Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-haiku-latest'}, 'request_id': 'req_011CaGoBqevKfXwJ2vL4L8vB'}; returning empty extraction
Extracted entities:
{'dates': [], 'persons': [], 'locations': []}
Person lookup result: person_id=2
```

---

## TimeWoven – Update M4.2 Local LLM Provider on VPS

Date: 2026-04-24

### Structural change

No (инфраструктура и конфиг, без изменения доменной модели).

### Schema change

No.

### Changes

Завершена интеграция локального LLM‑провайдера local_llm на VPS для анализа семейных воспоминаний.

В app/services/ai_analyzer.py активирован провайдер local_llm через AI_PROVIDER, используется HTTP‑endpoint AI_LOCAL_LLM_URL с JSON‑протоколом summary/persons/dates/locations/raw_provider/status.

Добавлен admin‑маршрут GET /admin/ai/local-llm-check и шаблон admin_ai_local_llm_check.html, который показывает статус локального провайдера и сырое JSON‑тело ответа.

В ops/local_llm/ поднят отдельный FastAPI‑сервис (service.py) на базе GGUF‑модели Saiga Mistral 7B (q4_K, ~4.1 GB) с эндпоинтами /health и /analyze, Dockerfile и docker-compose.yml биндуют сервис только на 127.0.0.1:9000.

Настроен systemd‑юнит timewoven-llm.service, обеспечивающий автозапуск docker compose up и стабильный runtime после перезагрузки VPS.

### Validation / Proof

curl http://127.0.0.1:9000/health → {"status":"ok"}.

curl http://127.0.0.1:9000/analyze с текстом "Это тестовая история о семье" возвращает JSON со status:"ok", непустым summary:"Тестовая история о семье" и raw_provider.mode:"llama_cpp".

AI_LOCAL_LLM_URL=http://127.0.0.1:9000/analyze python3 scripts/test_local_llm.py завершился успешно с OK и тем же summary.

docker ps показывает timewoven-local-llm в статусе Up с портом 127.0.0.1:9000->9000/tcp; systemctl status timewoven-llm.service в состоянии active (running).

Admin‑страница /admin/ai/local-llm-check под админ‑логином отображает “Локальный AI‑провайдер работает” и JSON‑ответ со status:"ok" и непустым summary.

### Result

Задача M4.2 “Local LLM на VPS доведён до рабочего состояния” переведена в статус ГОТОВО.

Для всех сценариев анализа текстов теперь доступен локальный LLM‑провайдер, не требующий внешних API‑ключей; Anthropic и другие внешние провайдеры могут использоваться как fallback по отдельной конфигурации.

Date 2026-04-24
TITLE PROJECT LOG TimeWoven – Update W1 Whisper Small Transcription Service on VPS
Structural change: Yes (новый ops-сервис для транскрипции).
Schema change: No.

Changes:
- В ops/whisper_small/ добавлен FastAPI-сервис service.py с эндпоинтами GET /health и POST /transcribe, использующий модель WhisperModel("small", device="cpu", compute_type="int8") с параметрами beam_size=2 и temperature=0.0.
- Подготовлен Dockerfile на базе python:3.10.12-slim с установкой faster-whisper и ffmpeg, а также docker-compose.yml для сервиса timewoven-whisper-small, слушающего только 127.0.0.1:9100.
- Добавлен systemd-юнит timewoven-whisper.service, запускающий docker compose up -d --build и обеспечивающий автозапуск Whisper-сервиса после перезагрузки VPS.
- В .env настроены переменные WHISPER_PROVIDER=local_small и WHISPER_LOCAL_URL=http://127.0.0.1:9100/transcribe для дальнейшей интеграции в TranscriptionService.

Validation / Proof:
- curl http://127.0.0.1:9100/health возвращает {"status":"ok"}.
- curl -X POST http://127.0.0.1:9100/transcribe -F "file=@/root/projects/TimeWoven/app/web/static/audio/raw/max_14557742588039_20260423131047.ogg" возвращает status="ok", language="ru" и осмысленный русский текст, начинающийся с “Это тестовая сессия. Ее задача посмотреть как отработает аудио…”, с duration_seconds ≈ 23.9 и временем обработки ≈ 8.4s на CPU.
- docker ps --filter name=timewoven-whisper-small показывает контейнер timewoven-whisper-small в статусе Up с портом 127.0.0.1:9100->9100/tcp.
- systemctl status timewoven-whisper.service в состоянии loaded+enabled, последний ExecStart=/usr/bin/docker compose up -d --build завершился status=0/SUCCESS.

Result:
- Задача W1 (“Whisper small на VPS (CPU) поднят”) переведена в статус ГОТОВО.
- На VPS появился локальный сервис транскрипции, готовый к интеграции в основной TranscriptionService; сервис доступен только по 127.0.0.1, не открыт во внешнюю сеть.

Date 2026-04-24
TITLE PROJECT LOG TimeWoven – Update M4.3/W1.1 Local Providers Integrated into Live Memory Pipeline
Structural change: No (интеграция существующих локальных сервисов в рабочий pipeline).
Schema change: No.

Changes:
- В app/services/ai_analyzer.py функция analyze_memory_text() теперь создаёт ProviderAgnosticAnalyzer с явным provider_name, выбранным из AI_PROVIDER / AIPROVIDER, чтобы рабочий pipeline явно использовал нужный провайдер и это было видно в proof/логах.
- В app/services/transcription.py добавлен выбор локального Whisper-сервиса по WHISPER_PROVIDER + WHISPER_LOCAL_URL; при local_small/local_* транскрибация идёт через локальный HTTP endpoint, а не через внешний API.
- Проверен живой путь через POST /webhooks/maxbot/incoming для текста и аудио.

Validation / Proof:
- Текстовый сценарий: создан Memory id=41 (source_type=max_session, status=draft), в analysis содержатся summary/persons/dates/locations, а analysis.raw_provider.provider="local_llm" и endpoint="http://127.0.0.1:9000/analyze".
- Голосовой сценарий: POST /webhooks/maxbot/incoming с audio attachment дал transcription_status="ok", затем POST /webhooks/maxbot/incoming с текстом "Готово" создал Memory id=42.
- Для Memory id=42 в analysis.raw_provider.provider="local_llm", что подтверждает полный end-to-end поток: voice -> local Whisper -> text -> local_llm analysis.
- Транскрибация прошла при пустом WHISPER_API_TOKEN, что подтверждает использование локального WHISPER_LOCAL_URL вместо внешнего OpenAI endpoint.

Result:
- Локальные провайдеры LLM и Whisper не только подняты как сервисы на VPS, но и реально интегрированы в живой pipeline создания и анализа Memories.
- End-to-end сценарий “голосовое воспоминание -> транскрипция -> анализ -> запись в БД” подтверждён на прод-подобной среде.

---

## Update: T-DATA-MIGRATION-CORE-BOOTSTRAP-2026-04-28-04 — bootstrap core DB and register bondarev family

Date: 2026-04-28

### Structural change

Yes — добавлен core-слой данных: отдельная БД `timewoven_core` с реестром семей `families`.

### Schema change

Yes (в новой БД `timewoven_core`): создана таблица `families`, включено расширение `pgcrypto`.

### Changes

- Создана БД `timewoven_core`.
- Включено расширение `pgcrypto`.
- Создана таблица `families`:
  - `id UUID PRIMARY KEY`
  - `slug TEXT UNIQUE NOT NULL`
  - `db_name TEXT NOT NULL`
  - `data_path TEXT NOT NULL`
  - `created_at TIMESTAMP DEFAULT NOW()`
- Добавлена запись семьи:
  - `slug=bondarev`
  - `db_name=timewoven_bondarev`
  - `data_path=/root/data/timewoven/bondarev`

### Validation / Proof

- `SELECT slug, db_name, data_path FROM families;` в `timewoven_core` вернул:
  - `bondarev | timewoven_bondarev | /root/data/timewoven/bondarev`

---

## Update: T-DATA-MIGRATION-RENAME-DB-TO-BONDAREV-2026-04-28-05 — rename DB to timewoven_bondarev

Date: 2026-04-28

### Structural change

Yes — нормализация naming: `timewoven` переименована в `timewoven_bondarev`.

### Schema change

No (переименование БД без изменения таблиц/данных).

### Changes

- Завершены активные подключения к БД `timewoven` (если были).
- Выполнено: `ALTER DATABASE timewoven RENAME TO timewoven_bondarev;`
- Проверен registry в `timewoven_core.families`: `bondarev` указывает на `timewoven_bondarev`.

### Validation / Proof

- `\l` показывает: `timewoven_bondarev`, `timewoven_core` (и прочие базы), при этом `timewoven` отсутствует.
- `SELECT slug, db_name FROM families;` в `timewoven_core` вернул: `bondarev | timewoven_bondarev`.

---

## Update: T-FAMILY-RESOLVER-V1-2026-04-28-06 — resolve DB via core registry

Date: 2026-04-28

### Structural change

Yes — добавлен runtime-резолв семьи: `slug` → `timewoven_core.families` → `db_name` → подключение.

### Schema change

No.

### Changes

- Добавлен модуль `app/core/family_resolver.py`:
  - читает `db_name`/`data_path` по `slug` из `timewoven_core.families`.
- `app/db/session.py` теперь:
  - читает `DEFAULT_FAMILY_SLUG` из `.env` (fallback `bondarev`);
  - резолвит `db_name` через core registry;
  - собирает `DATABASE_URL` для engine на основе существующих кредов/host/port, но с `db_name` из registry.
- В `.env` добавлено: `DEFAULT_FAMILY_SLUG=bondarev`.

### Validation / Proof

- Приложение стартует и подключается к `timewoven_bondarev` через резолв из core registry.

---

## Update: T-DATA-MIGRATION-FILESYSTEM-2026-04-28-07 — migrate filesystem to /root/data/timewoven/bondarev

Date: 2026-04-28

### Structural change

Yes — введена отдельная директория данных семьи вне репозитория: `/root/data/timewoven/bondarev/`.

### Schema change

No.

### Changes

- Создана директория `/root/data/timewoven/bondarev/` и поддиректории:
  - `raw/`
  - `processed/`
  - `storage/`
- Выполнено копирование данных **без удаления источников** (`cp`, не `mv`):
  - `/root/projects/TimeWoven/raw/*` → `/root/data/timewoven/bondarev/raw/`
  - `/root/projects/TimeWoven/processed/*` → `/root/data/timewoven/bondarev/processed/`
  - `/root/projects/TimeWoven/storage/*` → `/root/data/timewoven/bondarev/storage/`
- Выставлены права: `chown -R root:root /root/data/timewoven` и `chmod -R 755 /root/data/timewoven`.

### Validation / Proof

- `du -sh` совпадает для каждой пары source/target директорий (`raw`, `processed`, `storage`).

---

## Update: T-FILESYSTEM-SWITCH-PROCESSOR-2026-04-28-10 — switch processor to DATA_PATH

Date: 2026-04-28

### Structural change

No (только смена путей записи/чтения для processor).

### Schema change

No.

### Changes

- `scripts/processor.py` переведён на использование `DATA_PATH`:
  - `RAW_DIR = f"{DATA_PATH}/raw"`
  - `PROCESSED_DIR = f"{DATA_PATH}/processed"`
  - `STORAGE_DIR = f"{DATA_PATH}/storage"`
  - `DATA_PATH` читается из env с fallback `/root/data/timewoven/bondarev`.

### Validation / Proof

- Запуск: `DB_NAME=timewoven_bondarev python3 scripts/processor.py` → подключение к БД OK, директории создаются в `/root/data/timewoven/bondarev/...`.

---

## Update: T-CLEANUP-OLD-DATA-SOFT-2026-04-28-12 — archive old filesystem directories

Date: 2026-04-28

### Structural change

Yes — старые проектные директории данных вынесены из репозитория в архив.

### Schema change

No.

### Changes

- Создан архив: `/root/data/timewoven/_legacy_backup/`
- Перемещены директории (без удаления данных):
  - `/root/projects/TimeWoven/raw` → `/root/data/timewoven/_legacy_backup/raw_legacy`
  - `/root/projects/TimeWoven/processed` → `/root/data/timewoven/_legacy_backup/processed_legacy`
  - `/root/projects/TimeWoven/storage` → `/root/data/timewoven/_legacy_backup/storage_legacy`

### Validation / Proof

- В корне проекта `raw/processed/storage` отсутствуют.
- `systemctl is-active timewoven.service` = `active`, `/health` = `200`.

---

## Update: T-FAMILY-CONTEXT-V1-2026-04-28-13 — introduce slug-based routing

Date: 2026-04-28

### Structural change

Yes — добавлен routing-контур для выбора семьи по URL: `/f/{slug}/...`.

### Schema change

No.

### Changes

- `app/db/session.py`: `get_db` теперь резолвит family DB по `slug` (fallback `bondarev`) через `timewoven_core.families`; если slug неизвестен → HTTP 404.
- `app/api/routes/tree.py`: добавлены зеркальные маршруты с префиксом `/f/{slug}` для family-flow (`/family/*`, `/who-am-i*`, `/profile/avatar`).
- `app/main.py`: добавлена точка входа `/f/{slug}/` с редиректом на `/f/{slug}/family/welcome` или `/f/{slug}/family/need-access`.

### Validation / Proof

- `/f/bondarev/` работает (редирект в family flow).
- Неверный slug возвращает 404 (Family not found).

---

## Update: T-ROOT-STRUCTURE-CLEANUP-2026-04-28-14 — normalize root structure and scripts layout

Date: 2026-04-28

### Structural change

Yes — скрипты вынесены из `/root` в `/root/scripts` с явной структурой подпапок.

### Schema change

No.

### Changes

- Создана структура:
  - `/root/scripts/ops/`
  - `/root/scripts/deploy/`
  - `/root/scripts/maintenance/`
- Перенесены ops-скрипты:
  - `/root/backup_timewoven.sh` → `/root/scripts/ops/backup_timewoven.sh`
  - `/root/check_timewoven.sh` → `/root/scripts/ops/check_timewoven.sh`
- Deploy-скрипты вынесены из проекта:
  - `deploy.sh` и `deploy_landing.sh` перемещены из `/root/projects/TimeWoven/` в `/root/scripts/deploy/`
- В `/root` больше нет task-скриптов (root очищен от `*.sh`).

### Validation / Proof

- `systemctl is-active timewoven.service` → `active`
- `curl http://127.0.0.1:8000/health` → `200`

---

## Update: T-ROOT-DOCS-README-2026-04-28-15 — add root-level documentation (README)

Date: 2026-04-28

### Structural change

No (добавлена только текстовая документация-ориентир).

### Schema change

No.

### Changes

- Созданы README-файлы для навигации по серверной структуре:
  - `/root/README.md`
  - `/root/projects/README.md`
  - `/root/data/README.md`
  - `/root/logs/README.md`
  - `/root/scripts/README.md`
  - `/root/backups/README.md`

### Validation / Proof

- `systemctl is-active timewoven.service` → `active`
- `curl http://127.0.0.1:8000/health` → `200`

---

## Update: T-PROJECTS-CLEANUP-V1-2026-04-28-16 — cleanup projects directory

Date: 2026-04-28

### Structural change

Yes — нормализована структура `/root/projects` до единственного проекта `TimeWoven`.

### Schema change

No.

### Changes

- Snapshots перенесены:
  - `/root/projects/TimeWoven_snapshots` → `/root/backups/timewoven_snapshots/TimeWoven_snapshots`
- Recovery-артефакты архивированы:
  - `/root/projects/_recovery_check_*` → `/root/backups/recovery_archive/`
- Временные worktrees удалены:
  - `/root/projects/TimeWoven.worktrees` (copilot worktrees)
- `/root/projects` очищен от служебных артефактов, оставлен только:
  - `/root/projects/TimeWoven`

### Validation / Proof

- `systemctl is-active timewoven.service` → `active`
- `curl http://localhost:8000/health` → `{"status":"ok"}`

---

## Update: T-MEDIA-SEPARATION-V1-2026-04-28-21 — separate runtime media from repo via symlinks

Date: 2026-04-28

### Structural change

Yes — runtime media вынесена в data-layer и подключена обратно через symlink, без изменения ссылок в БД.

### Schema change

No.

### Changes

- Создана media-структура:
  - `/root/data/timewoven/bondarev/media/audio/processed/`
  - `/root/data/timewoven/bondarev/media/avatars/current/`
  - `/root/data/timewoven/bondarev/media/avatars/history/`
- Перенесены runtime файлы из `app/web/static` в `/root/data/.../media/...`.
- Созданы symlink'и обратно:
  - `app/web/static/audio/processed` → `/root/data/timewoven/bondarev/media/audio/processed`
  - `app/web/static/images/avatars` → `/root/data/timewoven/bondarev/media/avatars/current`
  - `app/web/static/avatars` → `/root/data/timewoven/bondarev/media/avatars/history`
- `StaticFiles` настроен на отдачу symlink-таргетов: `follow_symlink=True`.

### Validation / Proof

- `/static/audio/processed/13517383557209.mp3` → `200`
- `/static/images/avatars/person_1.jpg` → `200`
- `/static/avatars/person_1.png` → `200`

---

## Update: T-MEDIA-CLEANUP-V2-2026-04-28-23 — finalize media routing and remove static dependency

Date: 2026-04-28

### Structural change

Yes — media полностью обслуживается через `/media/{slug}/...`; static остаётся только для core assets.

### Schema change

No.

### Changes

- Удалены media-symlink'и из `app/web/static`:
  - `app/web/static/audio/processed`
  - `app/web/static/images/avatars`
  - `app/web/static/avatars`
- Убран `follow_symlink` из static-mount (`StaticFiles(...)` без symlink support).
- Добавлен/включён routing для media:
  - `GET /media/{slug}/{file_path:path}` → `FileResponse` из `{data_path}/media/...`
- Убраны backend-зависимости от static media paths (перевод на `/media/...` для новых записей и runtime-нормализация legacy URL).

### Validation / Proof

- `/static/audio/...` → `404`
- `/static/images/avatars/...` → `404`
- `/media/bondarev/audio/processed/...` → `200`
- `/media/bondarev/avatars/current/...` → `200`

---

## Запись 28 апреля — введение Git workflow

Date: 2026-04-28

### Structural change

Yes — введена модель веток разработки.

### Decision / Notes

- Зафиксирована модель:
  - main — production
  - develop — integration
  - feature/* — task branches
- Запрещены прямые коммиты в main
- Вся разработка теперь проходит через feature → develop → main

### Reason

- Снижение риска повторения инцидента 26.04
- Контроль изменений и rollback
- Синхронизация с PROJECT_OPS_PROTOCOL

### Impact

- Все будущие задачи выполняются только в feature-ветках
