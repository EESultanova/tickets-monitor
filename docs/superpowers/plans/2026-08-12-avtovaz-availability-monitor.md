# AvtoVAZ Excursion Availability Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dependency-free Python monitor that checks the 21.08.2026 excursion every 15 minutes in GitHub Actions and sends Telegram status-change and twice-daily heartbeat notifications.

**Architecture:** A focused HTML parser converts the target schedule card into a typed observation. A state module decides whether an observation or Moscow-time heartbeat requires notification, while a small application layer performs HTTP, Telegram, and JSON persistence through injectable functions. GitHub Actions runs tests before every check and commits state only when a notification-relevant state changes.

**Tech Stack:** Python 3.9+, standard library (`html.parser`, `urllib`, `json`, `zoneinfo`, `unittest`), GitHub Actions, Telegram Bot API.

## Global Constraints

- Check the exact target date `21.08.2026` every 15 minutes.
- Send heartbeat messages during the first scheduled run in the 09:00 and 21:00 hours in `Europe/Moscow`.
- Store `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` only in GitHub Secrets.
- Use no third-party Python packages.
- Never log the Telegram token.
- Notify once per distinct status/place-count transition, including error and recovery transitions.
- Do not implement automatic booking, additional dates, or a web interface.

## File Map

- `monitor/model.py` — immutable observation and persisted-state data contracts.
- `monitor/parser.py` — schedule-card HTML parsing and status normalization.
- `monitor/state.py` — JSON state persistence and notification decisions.
- `monitor/gateways.py` — page download and Telegram Bot API calls.
- `monitor/app.py` — one monitoring run and message formatting.
- `run_monitor.py` — environment-backed production entry point.
- `tests/fixtures/*.html` — minimal representative page fragments.
- `tests/test_parser.py` — parser behavior.
- `tests/test_state.py` — status transitions and heartbeat slots.
- `tests/test_app.py` — orchestration without network calls.
- `.github/workflows/monitor.yml` — 15-minute runner, tests, and state commit.
- `state/status.json` — initial state with no prior observation.
- `.gitignore` — Python and local-secret exclusions.
- `README.md` — safe GitHub and Telegram setup instructions.

---

### Task 1: Parse the Target Schedule Card

**Files:**
- Create: `monitor/__init__.py`
- Create: `monitor/model.py`
- Create: `monitor/parser.py`
- Create: `tests/fixtures/sold_out.html`
- Create: `tests/fixtures/available.html`
- Create: `tests/test_parser.py`

**Interfaces:**
- Produces: `Observation(status: str, raw_status: str, places: Optional[int])`.
- Produces: `parse_availability(html: str, target_date: str) -> Observation`.
- Status values are exactly `sold_out`, `available`, `unknown`, and `date_missing`.

- [ ] **Step 1: Write representative fixtures**

Use schedule items with the production marker `jatoms-schedule="item"`. The sold-out fixture must contain the exact date, a disabled booking button, and `Мест нет`. The available fixture must contain `Осталось 3 места` and an enabled booking button.

```html
<div jatoms-schedule="item" data-tags="nearest 08_26">
  <strong>21.08.2026</strong>
  <button disabled>Забронировать</button>
  <strong>Мест нет</strong>
</div>
```

- [ ] **Step 2: Write failing parser tests**

```python
class ParseAvailabilityTests(unittest.TestCase):
    def test_sold_out(self):
        result = parse_availability(load_fixture("sold_out.html"), "21.08.2026")
        self.assertEqual(result, Observation("sold_out", "Мест нет", None))

    def test_available_with_places(self):
        result = parse_availability(load_fixture("available.html"), "21.08.2026")
        self.assertEqual(result, Observation("available", "Осталось 3 места", 3))

    def test_missing_date(self):
        result = parse_availability(load_fixture("available.html"), "22.08.2026")
        self.assertEqual(result.status, "date_missing")

    def test_unknown_status(self):
        html = '<div jatoms-schedule="item"><strong>21.08.2026</strong></div>'
        self.assertEqual(parse_availability(html, "21.08.2026").status, "unknown")
```

- [ ] **Step 3: Run tests and confirm the red phase**

Run: `python3 -m unittest tests.test_parser -v`

Expected: import failure because `monitor.parser` does not exist.

- [ ] **Step 4: Implement the observation model and parser**

Use a private `HTMLParser` subclass that starts collecting at a tag whose attributes contain `jatoms-schedule="item"`, tracks nested `div` depth, collects normalized text, and remembers whether a booking button lacks `disabled`. Match the exact target date as a standalone `DD.MM.YYYY` token. Normalize in this order:

```python
if re.search(r"\bМест\s+нет\b", text, re.IGNORECASE):
    return Observation("sold_out", "Мест нет", None)
match = re.search(r"Осталось\s+(\d+)\s+мест(?:о|а)?", text, re.IGNORECASE)
if match:
    places = int(match.group(1))
    return Observation("available", match.group(0), places)
if card.booking_enabled:
    return Observation("available", "Бронирование доступно", None)
return Observation("unknown", "Статус не распознан", None)
```

If no card has the exact date, return `Observation("date_missing", "Дата не найдена", None)`.

- [ ] **Step 5: Run parser tests and confirm the green phase**

Run: `python3 -m unittest tests.test_parser -v`

Expected: four tests pass.

- [ ] **Step 6: Commit the parser slice**

```bash
git add monitor tests/fixtures tests/test_parser.py
git commit -m "feat: parse excursion availability"
```

---

### Task 2: Persist State and Decide Notifications

**Files:**
- Modify: `monitor/model.py`
- Create: `monitor/state.py`
- Create: `tests/test_state.py`
- Create: `state/status.json`

**Interfaces:**
- Produces: `MonitorState(observation: Optional[Observation], observed_at: Optional[str], last_heartbeat_slot: Optional[str])`.
- Produces: `load_state(path: Path) -> MonitorState`.
- Produces: `save_state(path: Path, state: MonitorState) -> None`.
- Produces: `observation_changed(previous: Observation | None, current: Observation) -> bool`.
- Produces: `heartbeat_slot(now: datetime) -> Optional[str]`.
- Consumes: `Observation` from Task 1.

- [ ] **Step 1: Write failing transition and heartbeat tests**

```python
class StateTests(unittest.TestCase):
    def test_first_observation_is_a_change(self):
        self.assertTrue(observation_changed(None, Observation("sold_out", "Мест нет", None)))

    def test_identical_observation_is_not_a_change(self):
        item = Observation("sold_out", "Мест нет", None)
        self.assertFalse(observation_changed(item, item))

    def test_place_count_change_is_a_change(self):
        before = Observation("available", "Осталось 3 места", 3)
        after = Observation("available", "Осталось 2 места", 2)
        self.assertTrue(observation_changed(before, after))

    def test_moscow_heartbeat_slots(self):
        morning = datetime(2026, 8, 12, 9, 17, tzinfo=ZoneInfo("Europe/Moscow"))
        evening = datetime(2026, 8, 12, 21, 2, tzinfo=ZoneInfo("Europe/Moscow"))
        self.assertEqual(heartbeat_slot(morning), "2026-08-12T09")
        self.assertEqual(heartbeat_slot(evening), "2026-08-12T21")

    def test_no_heartbeat_outside_target_hours(self):
        now = datetime(2026, 8, 12, 10, 0, tzinfo=ZoneInfo("Europe/Moscow"))
        self.assertIsNone(heartbeat_slot(now))
```

- [ ] **Step 2: Run state tests and confirm the red phase**

Run: `python3 -m unittest tests.test_state -v`

Expected: import failure because `monitor.state` does not exist.

- [ ] **Step 3: Implement JSON-safe models and state functions**

Use dataclasses with explicit `to_dict()` and `from_dict()` methods. `observation_changed` compares `(status, places, raw_status)` so a changed place count is announced. `heartbeat_slot` first converts `now` with `ZoneInfo("Europe/Moscow")` and returns only an hour-level key for hours 9 and 21. `save_state` creates the parent directory and writes UTF-8 JSON with `ensure_ascii=False`, two-space indentation, and a trailing newline.

Initialize `state/status.json` as:

```json
{
  "observation": null,
  "observed_at": null,
  "last_heartbeat_slot": null
}
```

- [ ] **Step 4: Add a round-trip persistence test**

Create a temporary directory, save a state containing an available observation and heartbeat slot, reload it, and assert dataclass equality.

- [ ] **Step 5: Run state tests and confirm the green phase**

Run: `python3 -m unittest tests.test_state -v`

Expected: all transition, heartbeat, and persistence tests pass.

- [ ] **Step 6: Commit the state slice**

```bash
git add monitor/model.py monitor/state.py tests/test_state.py state/status.json
git commit -m "feat: track monitor notification state"
```

---

### Task 3: Orchestrate Checks and Telegram Notifications

**Files:**
- Create: `monitor/gateways.py`
- Create: `monitor/app.py`
- Create: `run_monitor.py`
- Create: `tests/test_app.py`

**Interfaces:**
- Produces: `fetch_page(url: str, timeout: float = 20.0) -> str`.
- Produces: `send_telegram(token: str, chat_id: str, text: str, timeout: float = 20.0) -> None`.
- Produces: `run_check(config: Config, fetch: Callable, send: Callable, now: datetime) -> RunResult`.
- `RunResult` contains `observation`, `messages_sent`, and `state_changed`.
- Consumes parser and state interfaces from Tasks 1–2.

- [ ] **Step 1: Write failing orchestration tests with injected fakes**

Cover four exact scenarios:

```python
def test_first_run_sends_current_status(self):
    # fake fetch returns sold_out fixture; fake send appends messages
    # assert one message contains "21.08.2026" and "мест нет"

def test_unchanged_non_heartbeat_run_sends_nothing(self):
    # pre-save sold_out state; run at 10:15 Moscow; assert []

def test_available_transition_sends_alert(self):
    # pre-save sold_out; fetch available fixture; assert message contains "ПОЯВИЛИСЬ МЕСТА" and "3"

def test_heartbeat_sends_once_per_slot(self):
    # pre-save sold_out; run twice in the 09 hour; assert only first run sends heartbeat
```

Also assert that a raised fetch exception produces a `fetch_error` observation and one warning, and that a repeated identical fetch error sends nothing.

- [ ] **Step 2: Run app tests and confirm the red phase**

Run: `python3 -m unittest tests.test_app -v`

Expected: import failure because `monitor.app` does not exist.

- [ ] **Step 3: Implement HTTP gateways**

`fetch_page` must send `User-Agent: AvtoVAZ-Availability-Monitor/1.0 (+personal notification monitor)` and decode using the response charset with UTF-8 fallback. `send_telegram` must POST form-encoded `chat_id`, `text`, and `disable_web_page_preview=true` to `https://api.telegram.org/bot{token}/sendMessage`, then require both HTTP success and JSON `{"ok": true}`. Error messages must omit the token and request URL.

- [ ] **Step 4: Implement application decisions and Russian message formatting**

`Config` contains URL, target date, state path, Telegram token, and chat ID. Build messages with these rules:

- `available`: start with `🚨 ПОЯВИЛИСЬ МЕСТА` and include place count when known.
- `sold_out`: start with `ℹ️ Статус изменился: мест нет`.
- `unknown`, `date_missing`, `fetch_error`: start with `⚠️ Монитор требует внимания`.
- recovery from an error to a normal status: include `✅ Монитор снова работает нормально`.
- heartbeat: start with `💚 Монитор включён и ожидает смены статуса`.

All messages include `21.08.2026`, Moscow time, current raw status, and the excursion URL. Send all required messages first; save the new state only after successful sends, so a Telegram failure is retried on the next run. When a status-change message and heartbeat are due in the same run, send one combined message and persist both pieces of state.

- [ ] **Step 5: Implement the production entry point**

Read `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from the environment and exit with a concise configuration error when either is absent. Set constants for the target URL, `21.08.2026`, and `state/status.json`. Use `datetime.now(ZoneInfo("Europe/Moscow"))`. Print only status, message count, and whether state changed; never print environment values.

- [ ] **Step 6: Run app tests and the complete suite**

Run: `python3 -m unittest discover -s tests -v`

Expected: all parser, state, and app tests pass with no network access.

- [ ] **Step 7: Commit the application slice**

```bash
git add monitor run_monitor.py tests/test_app.py
git commit -m "feat: notify Telegram about availability"
```

---

### Task 4: Automate, Document, and Verify Production Behavior

**Files:**
- Create: `.github/workflows/monitor.yml`
- Create: `.gitignore`
- Create: `README.md`
- Modify: `state/status.json` only through verified manual execution.

**Interfaces:**
- Consumes: `python3 run_monitor.py` from Task 3.
- Consumes secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- Produces: GitHub schedule `*/15 * * * *` and manual `workflow_dispatch`.

- [ ] **Step 1: Create the GitHub Actions workflow**

Use `ubuntu-latest`, `actions/checkout@v4`, and `actions/setup-python@v5` with Python `3.12`. Set:

```yaml
permissions:
  contents: write
concurrency:
  group: avtovaz-availability-monitor
  cancel-in-progress: false
on:
  schedule:
    - cron: "*/15 * * * *"
  workflow_dispatch:
```

Run `python -m unittest discover -s tests -v` before `python run_monitor.py`. Pass secrets only in the monitor step. If `state/status.json` differs, configure the Git author as `github-actions[bot]`, commit only that file with message `chore: update monitor state`, pull with rebase, and push.

- [ ] **Step 2: Add secret-safe repository defaults**

Ignore `.env`, `.venv/`, `__pycache__/`, `*.pyc`, and local coverage files. Do not ignore `state/status.json`, because transition deduplication depends on its committed value.

- [ ] **Step 3: Write setup and operations documentation**

Document these exact user actions:

1. Revoke the token posted in chat through `@BotFather` and create a replacement.
2. Create a private GitHub repository and push this project.
3. Add repository secrets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` under Settings → Secrets and variables → Actions.
4. Open Actions → `Monitor excursion availability` → Run workflow.
5. Verify a Telegram start message and a green workflow run.

Document that scheduled workflows normally detect changes within 15 minutes but GitHub may delay a run, and explain how to disable monitoring by disabling the workflow.

- [ ] **Step 4: Validate workflow syntax and repository safety**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile monitor/*.py run_monitor.py
git diff --check
grep -R "8601971459:" --exclude-dir=.git .
```

Expected: tests and compilation pass; `git diff --check` is silent; the compromised token scan returns no matches.

- [ ] **Step 5: Perform a live dry fetch without Telegram**

Use a short one-off Python command that calls `fetch_page` and `parse_availability` for the production URL without importing or reading Telegram secrets. Assert that the exact date is found and print only the normalized observation. Expected current result at implementation time is `sold_out`; if the site has changed legitimately, record the live result instead of forcing the fixture expectation.

- [ ] **Step 6: Review the generated files for secret leakage**

Inspect tracked files with `git grep -nE '(TELEGRAM_BOT_TOKEN=|api.telegram.org/bot[0-9]+:)'`. Expected: no literal token assignment or token-bearing URL; references to the environment variable name are allowed.

- [ ] **Step 7: Commit automation and documentation**

```bash
git add .github/workflows/monitor.yml .gitignore README.md
git commit -m "ci: run excursion monitor every 15 minutes"
```

- [ ] **Step 8: Final verification**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile monitor/*.py run_monitor.py
git status --short
```

Expected: all tests pass, compilation succeeds, and the working tree is clean.
