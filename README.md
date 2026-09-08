# RSS Intelligence Pipeline

A daily open-source-intelligence pipeline for cyber-security and geopolitics. It
fetches a curated set of RSS feeds, cleans and analyzes each article, stores the
results in DuckDB, and emits a daily Markdown "intelligence" report with
word-frequency statistics, trend/spike detection, topic tagging, and sentiment.

## What it does

1. **Fetch** — pulls each configured RSS feed (`data/feeds.json`), with per-feed
   health tracking (status, response time, error message).
2. **Process** — strips HTML, extracts keywords (stopword-filtered), tags topics
   with rule-based patterns, scores sentiment (VADER + TextBlob + a custom
   security lexicon), and assigns a feed-priority risk score.
3. **Analyze** — computes per-word statistics against a rolling 7-day baseline and
   flags spikes, new words, resurrected words, and dropped words via z-scores.
4. **Report** — writes `logs/daily-summary-<date>.md` and persists a structured
   daily summary to DuckDB. `security_query.py` prints a focused security /
   geopolitical terms report.

## Requirements

- Python 3.10+
- The dependencies in `requirements.txt`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# One-time: build the curated stopwords / security / geopolitical lexicon DB
python3 create_stopwords_db.py

# Provide your feed list (see the sample for the required shape)
mkdir -p data
cp data/feeds.example.json data/feeds.json   # then edit to taste
```

### Feed file shape

`data/feeds.json` is a non-empty JSON array of objects:

```json
[
  { "name": "CISA Alerts", "url": "https://…/all.xml", "category": "Government" }
]
```

`category` should match a key in `FEED_PRIORITY` (see `config.py`) so risk scoring
is meaningful; unknown categories fall back to the lowest priority.

## Running

```bash
python3 main.py                # normal run (uses today's cache if present)
python3 main.py --no-cache     # force a fresh fetch
python3 main.py --clear-cache  # delete today's cache first
python3 security_query.py      # focused security/geopolitical terms report

# or the convenience wrapper
./run.sh
```

Paths (DB, logs, cache, archive) are configured in `config.py`; by default they
live under `~/.rss-intel-pipeline/`.

## Development

```bash
pip install -r requirements-dev.txt
ruff check .        # lint
ruff format .       # format
pytest              # run the offline unit tests
```

See [CODING_GUIDELINES.md](CODING_GUIDELINES.md) for the conventions this project
follows.
