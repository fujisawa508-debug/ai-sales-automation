# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Japanese-language B2B sales outreach automation tool. It reads a prospect list (`prospects.csv`), generates industry-specific Japanese sales email copy, and saves the emails as **drafts** in Outlook — it never sends mail automatically. Comments, print output, CSV columns, and email copy are all in Japanese; keep new code and any user-facing strings consistent with that.

## Commands

Setup:
```
setup.bat
```
(equivalent to `pip install -r requirements.txt`)

Run (Windows only — depends on `pywin32`/Outlook COM automation):
```
python main.py                    # process only rank "A" prospects
python main.py --all              # process all ranks (A/B/C)
python main.py --scrape           # scrape prospect sources into prospects.csv first, then process
python main.py --research         # run the AI research agent to fill in "課題メモ" (pain-point notes) before processing
python main.py --research --save  # same as above, but overwrite prospects.csv with the researched notes
```
Flags combine, e.g. `python main.py --all --research --save`.

Unattended weekly run (used by Task Scheduler, see "Scheduling" below):
```
run_scheduled.bat
```
Runs `python main.py --scrape --research --save --all` with no prompts, redirecting stdout/stderr to `logs\<timestamp>.log` (log directory is created on first run and never pruned automatically).

There is no test suite, linter, or build step in this repo.

The `--research` flag requires `ANTHROPIC_API_KEY` to be set in the environment (used via the `anthropic` SDK, model `claude-haiku-4-5-20251001`).

## Architecture

Pipeline, driven by `main.py`, in order:

1. **`scraper.py`** (`--scrape`) — scrapes two fixed public sources (Tohoku DX Award winners, Fukui DX declaration companies), guesses prefecture from text, and appends new rows to `prospects.csv` (deduped by 会社名/company name).
2. **`company_researcher.py`** (`--research`) — for each prospect without an existing pain-point note, searches DuckDuckGo HTML for the company's official site, scrapes page text, and asks Claude to produce 3 bullet-point pain points, written into the in-memory `課題メモ` column. Rows with an existing substantive note (not a `【テスト】` test tag or `[...]` error marker, and >15 chars) are skipped. `--save` persists this back to `prospects.csv`.
3. **`main.py`** (`load_prospects` / `process_all`) — loads `prospects.csv`, filters by 優先度 (priority rank A/B/C), drops rows already flagged `下書き済み`=`済` (see schema below), and drops rows with no email address, then for each remaining row:
   - picks a template via `email_templates.get_template(industry)` (keyword match against 業種, e.g. "製造"→manufacturing, "建設"→construction, "物流"→logistics, "食品"→food, "農業"→agriculture, "エネルギー"→energy, else general)
   - fills it in via `email_templates.render(...)`, which also promotes a researched `課題メモ` into a dedicated "researched pain points" paragraph when present. The "is this a real researched note" check (>15 chars, not starting with `【テスト】` or `[`) is duplicated independently here and in `company_researcher.py`'s skip logic (line above) — if you change the threshold, update both.
   - calls `outlook_draft.create_draft(...)`
4. **`outlook_draft.py`** — creates the email via `win32com.client.Dispatch("Outlook.Application")` and calls **only `mail.Save()`**, never `mail.Send()`. This is a deliberate, load-bearing invariant of the tool — do not add or wire up a send path.
5. Back in **`main.py`**, after `process_all` returns the indices of rows that got a successful draft, `main()` re-reads `prospects.csv` from disk, sets `下書き済み`=`済` for those indices, and writes it back — **unconditionally, regardless of `--save`**. `--save` only controls whether `company_researcher`'s `課題メモ` results are persisted; the drafted-flag write is the anti-duplicate mechanism itself, so it always happens when any draft succeeds. Rows that failed (Outlook error) or were skipped (bad email format) are not flagged, so they're retried on the next run.

**Config**: `config.py` holds sender identity (name/company/phone/email/title) and `USE_HTML` (send HTML vs. plain-text body). Edit this file directly to change sender details — it's a plain settings module, not templated.

**`prospects.csv` schema** (UTF-8 with BOM, `utf-8-sig`): `会社名,都道府県,市区町村,業種,担当者名,役職,メールアドレス,電話番号,課題メモ,優先度,下書き済み`. Priority (優先度) is `A`/`B`/`C`. Rows missing an email address are logged and skipped rather than erroring. `下書き済み` is `済` once a draft was successfully created for that row, empty otherwise; `main.py`'s `_ensure_flag_column` adds the column automatically if an older CSV lacks it, so this is backward-compatible. Clear a cell manually to force that row to be re-drafted on the next run.

Adding a new industry template means adding both a keyword branch in `get_template()` and a corresponding `_xxx()` function returning `{"subject": ..., "body_text": ...}` in `email_templates.py`, following the existing template structure (placeholders: `{company}`, `{contact}`, `{prefecture}`, `{issue}`, `{issue_section}`, `{sender_name}`, `{sender_company}`, `{sender_phone}`, `{sender_email}`, `{sender_title}`).

## Scheduling

`run_scheduled.bat` is meant to be registered as a weekly Windows Task Scheduler job (registration is a one-time manual step, not something to automate — it makes a persistent system-level change):
```
schtasks /create /tn "AI営業自動化_週次" /tr "\"C:\Users\koya.fujisawa\ai_sales_automation\run_scheduled.bat\"" /sc weekly /d MON /st 09:00 /rl LIMITED /f
```
Two hard requirements for this to actually work unattended:
- **`ANTHROPIC_API_KEY` must be set persistently** (e.g. `setx ANTHROPIC_API_KEY "..."`, once, or via System Properties → Environment Variables) — Task Scheduler-launched processes don't inherit a `$env:...` set only in an interactive shell. Without this, `--research` silently fails per-row with `[エラー] 環境変数 ANTHROPIC_API_KEY が設定されていません` (visible only in the log file, not a crash).
- **The task must be configured "Run only when user is logged on"** (not "run whether user is logged on or not") — `outlook_draft.py`'s Outlook COM automation requires an interactive desktop session for the target Windows account; it does not work under SYSTEM or a logged-off session.

## Git Workflow

@docs/git-workflow.md
