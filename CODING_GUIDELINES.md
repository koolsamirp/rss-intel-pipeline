# Coding Guidelines — RSS Intelligence Pipeline

Context and conventions for anyone (human or AI agent) working in this repository.
The goal is a single, coherent, testable pipeline — not several half-merged copies.

## 1. One source of truth

- **`main.py` is the pipeline.** There is exactly one entry point and one report
  path (`security_query.py`). Do not add parallel "v2 / backup / one-file"
  implementations — that is how this project accumulated divergent DB filenames and
  two different word tables. Backups belong in git history, not the working tree.
- If you must experiment, use a branch, not a `*back.py` file.

## 2. Configuration

- All tunables live in `config.py`. Read them; do not hard-code paths, thresholds,
  or lexicons at call sites.
- `main.py` keeps *fallback defaults* only so it runs without `config.py`. **Fallbacks
  must agree with `config.py`** (e.g. the DB filename is `rss_intel.duckdb` in both).
  A mismatch is a bug.
- Prefer explicit, typed config. When touching config plumbing, move toward a single
  typed settings object rather than expanding the `getattr(sys.modules...)` pattern.
- **Never define the same constant twice** (`TOPIC_RULES`, `FEED_PRIORITY`,
  `CUSTOM_SENTIMENT_LEXICON`). One definition, one place.

## 3. Sentiment lexicon scale

- Sentiment is on the **[-1, 1] polarity scale** (−1 = most negative, +1 = most
  positive), matching VADER and TextBlob. Threat terms (`breach`, `ransomware`)
  are **negative**; remediation terms (`patched`, `resolved`) are **positive**.
- A `[0, 1]` "positivity" lexicon is auto-normalized to `[-1, 1]` via `2v − 1`
  (see `SentimentAnalyzer._normalize_lexicon`). If you add lexicon entries, keep the
  whole lexicon on one consistent scale.

## 4. Database access

- **Always use parameterized queries** (`execute(sql, params)`). Never f-string user
  or date values into SQL, even when the value looks safe.
- **Schema creation is idempotent and side-effect free.** `_init_schema` must only
  `CREATE ... IF NOT EXISTS`. It must never `DROP` a sequence/table or reset an ID
  counter — that method runs on every startup and must not mutate existing data.
- Keep schema DDL and data mutation in separate methods.

## 5. Error handling & logging

- **No bare `except:` and no `except Exception: pass`.** Catch the narrowest
  exception you can, and log it. A silently swallowed feed error is invisible and
  undebuggable. (`contextlib.suppress` is acceptable only for a deliberate,
  documented best-effort side call.)
- The pipeline configures a real `logging` logger — use it for diagnostics. Reserve
  `print()` for the deliberate, user-facing console UX (the run banner / progress).

## 6. Data quality

- Word statistics must be **stopword-filtered**. Use the curated stopwords DB built
  by `create_stopwords_db.py` when present, falling back to the built-in set. Raw
  unfiltered token counts produce junk "top words".
- The 7-day baseline needs history to be meaningful; spike/new/dropped signals are
  empty on the first runs by design. Do not "fix" this by fabricating a baseline.

## 7. Dependencies & reproducibility

- All third-party imports must be declared in `requirements.txt` with a pinned
  compatible-release range (`~=`). Dev-only tools go in `requirements-dev.txt`.
- Do not assume a hard-coded interpreter path. Scripts honor the active interpreter
  (`$PYTHON`, else `python3`).

## 8. Testing

- Pure functions (`KeywordExtractor.extract`, `SentimentAnalyzer.analyze`,
  `RiskScorer.score`, `TopicDetector.detect`, the z-score math) must have unit tests
  that run **offline** — no network, no external DB.
- Run `pytest` and `ruff check .` before committing.

## 9. Style

- Format with `ruff format`; lint with `ruff check` (config in `pyproject.toml`).
- Type-hint public function signatures; keep hints specific (`list[str]`, not bare
  `List`).
- Explain non-obvious constants (e.g. the sentiment blend weights) with a comment
  stating *why*, not *what*.

## 10. Commits

- Conventional Commits (`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`).
- Imperative subject ≤ 50 chars; body explains *what* and *why*.
