#!/usr/bin/env python3
"""
RSS Intelligence Pipeline - v3.0 (Rewritten)
Fixes: empty cache trap, batch flush bug, missing diagnostics
"""

import sys
import json
import gzip
import re
import time
import hashlib
import logging
import gc
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import Counter, defaultdict

# ─── Third-party ───
import requests
import feedparser
import duckdb
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob

# ─── Config import with fallbacks ───
try:
    from config import *
except ImportError:
    print("⚠️  config.py not found — using defaults")
    pass

# ─── DEFAULTS (override these in config.py) ───
BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = getattr(sys.modules[__name__], 'LOGS_DIR', BASE_DIR / "logs")
CACHE_DIR = getattr(sys.modules[__name__], 'CACHE_DIR', BASE_DIR / "cache")
ARCHIVE_DIR = getattr(sys.modules[__name__], 'ARCHIVE_DIR', BASE_DIR / "archive")
DB_PATH = getattr(sys.modules[__name__], 'DB_PATH', BASE_DIR / "rss_intel.db")
FEEDS_FILE = getattr(sys.modules[__name__], 'FEEDS_FILE', BASE_DIR / "feeds.json")

USER_AGENT = getattr(sys.modules[__name__], 'USER_AGENT', 'RSS-Intel-Bot/3.0')
FEED_TIMEOUT = getattr(sys.modules[__name__], 'FEED_TIMEOUT', 30)
MAX_ARTICLES_PER_FEED = getattr(sys.modules[__name__], 'MAX_ARTICLES_PER_FEED', 50)

LOG_LEVEL = getattr(sys.modules[__name__], 'LOG_LEVEL', 'INFO')
LOG_ROTATE_AFTER = getattr(sys.modules[__name__], 'LOG_ROTATE_AFTER', 50)
ENABLE_CONSOLE_LOG = getattr(sys.modules[__name__], 'ENABLE_CONSOLE_LOG', True)
MEMORY_LIMIT_MB = getattr(sys.modules[__name__], 'MEMORY_LIMIT_MB', 2048)

MAX_KEYWORDS = getattr(sys.modules[__name__], 'MAX_KEYWORDS', 10)
TOPIC_RULES = getattr(sys.modules[__name__], 'TOPIC_RULES', {
    'ransomware': ['ransomware', 'cryptolocker', 'lockbit'],
    'vulnerability': ['vulnerability', 'cve-', 'zero-day', 'exploit'],
    'breach': ['breach', 'leaked', 'exposed data'],
    'phishing': ['phishing', 'spear-phishing', 'social engineering'],
    'malware': ['malware', 'trojan', 'backdoor', 'rootkit'],
    'geopolitics': ['sanctions', 'nation-state', 'apt', 'cyberwar'],
    'cloud': ['aws', 'azure', 'gcp', 'cloud misconfig'],
    'iot': ['iot', 'firmware', 'industrial control', 'scada']
})

CUSTOM_SENTIMENT_LEXICON = getattr(sys.modules[__name__], 'CUSTOM_SENTIMENT_LEXICON', {
    'critical': -0.8, 'breach': -0.7, 'ransomware': -0.8, 'attack': -0.6,
    'vulnerability': -0.5, 'exploit': -0.6, 'leak': -0.6, 'compromised': -0.7,
    'patched': 0.4, 'mitigated': 0.3, 'resolved': 0.5, 'secured': 0.4
})

RISK_MODE = getattr(sys.modules[__name__], 'RISK_MODE', 'feed_priority')
FEED_PRIORITY = getattr(sys.modules[__name__], 'FEED_PRIORITY', {
    'critical': 1.0, 'high': 0.8, 'medium': 0.5, 'low': 0.3, 'Unknown': 0.3
})

Z_SCORE_THRESHOLD = getattr(sys.modules[__name__], 'Z_SCORE_THRESHOLD', 2.0)
CRITICAL_THRESHOLD = getattr(sys.modules[__name__], 'CRITICAL_THRESHOLD', 0.8)
HIGH_THRESHOLD = getattr(sys.modules[__name__], 'HIGH_THRESHOLD', 0.6)
MEDIUM_THRESHOLD = getattr(sys.modules[__name__], 'MEDIUM_THRESHOLD', 0.4)

REPORT_LIMITS = getattr(sys.modules[__name__], 'REPORT_LIMITS', {
    'top_words': 20, 'top_spikes': 10, 'top_drops': 10,
    'new_words': 10, 'resurrected_words': 10, 'dropped_words': 10,
    'min_new_word_mentions': 3, 'resurrect_threshold_days': 7
})
REPORT_SECTIONS = getattr(sys.modules[__name__], 'REPORT_SECTIONS', {
    'overall_volume': True, 'top_words': True, 'spike_words': True,
    'drop_words': True, 'new_words': True, 'resurrected_words': True,
    'dropped_words': True, 'signal_noise': True
})

RETENTION_DAYS = getattr(sys.modules[__name__], 'RETENTION_DAYS', 90)
BATCH_SIZE = getattr(sys.modules[__name__], 'BATCH_SIZE', 500)

# ─── Ensure dirs ───
for d in [LOGS_DIR, CACHE_DIR, ARCHIVE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================
# DIAGNOSTIC HELPERS
# ============================================

def diag(label: str, ok: bool, detail: str = ""):
    icon = "✅" if ok else "❌"
    print(f"  {icon} {label}{f': {detail}' if detail else ''}")

def die(msg: str):
    print(f"\n💥 FATAL: {msg}")
    sys.exit(1)

# ============================================
# CACHE (FIXED)
# ============================================

def cache_path(date_str: str) -> Path:
    return CACHE_DIR / f"articles_{date_str}.json"

def save_cache(articles: List[Dict], date_str: str):
    if not articles:
        print("  ⚠️  Not saving empty cache")
        return
    cp = cache_path(date_str)
    with open(cp, 'w') as f:
        json.dump(articles, f, indent=2)
    print(f"  💾 Cached {len(articles)} articles → {cp}")

def load_cache(date_str: str) -> List[Dict]:
    """Returns articles list; empty list means no valid cache."""
    cp = cache_path(date_str)
    if not cp.exists():
        return []
    try:
        with open(cp, 'r') as f:
            data = json.load(f)
        if not isinstance(data, list):
            print(f"  ⚠️  Cache file corrupt (not a list): {cp}")
            return []
        if len(data) == 0:
            print(f"  ⚠️  Cache file exists but is EMPTY — ignoring: {cp}")
            return []
        print(f"  📂 Loaded {len(data)} articles from cache")
        return data
    except Exception as e:
        print(f"  ⚠️  Cache read failed: {e}")
        return []

# ============================================
# LOGGING
# ============================================

def setup_logging() -> logging.Logger:
    log_file = LOGS_DIR / "pipeline.log"
    err_file = LOGS_DIR / "errors.log"
    
    if log_file.exists():
        rc_file = LOGS_DIR / ".run_count"
        count = int(rc_file.read_text().strip()) if rc_file.exists() else 0
        count += 1
        rc_file.write_text(str(count))
        if count > LOG_ROTATE_AFTER:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            for f in [log_file, err_file]:
                if f.exists():
                    f.rename(f.with_suffix(f".{ts}{f.suffix}"))
            rc_file.write_text("0")
    
    logger = logging.getLogger('RSSIntel')
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.handlers = []  # clear old
    
    fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    for lvl, path in [(logging.DEBUG, log_file), (logging.ERROR, err_file)]:
        h = logging.FileHandler(path)
        h.setLevel(lvl)
        h.setFormatter(fmt)
        logger.addHandler(h)
    
    if ENABLE_CONSOLE_LOG:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logger.addHandler(ch)
    
    return logger

# ============================================
# DATABASE
# ============================================

class DatabaseManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = duckdb.connect(str(db_path))
        self._init_schema()
    
    def _init_schema(self):
        self.conn.execute("DROP SEQUENCE IF EXISTS sw_seq")
        self.conn.execute("CREATE SEQUENCE sw_seq START 1")
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id VARCHAR PRIMARY KEY,
                feed_name VARCHAR,
                feed_category VARCHAR,
                title VARCHAR,
                summary TEXT,
                content TEXT,
                link VARCHAR,
                published_at TIMESTAMP,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                word_count INTEGER,
                keywords JSON,
                topics JSON,
                sentiment_score FLOAT,
                sentiment_label VARCHAR,
                risk_score FLOAT,
                relevance_score FLOAT,
                priority BOOLEAN
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_summary (
                date DATE PRIMARY KEY,
                total_articles INTEGER,
                feeds_active INTEGER,
                total_topics INTEGER,
                top_keywords JSON,
                risk_topics JSON,
                top_articles JSON,
                signal_words JSON,
                new_words JSON,
                resurrected_words JSON,
                dropped_words JSON,
                sentiment_distribution JSON,
                overall_sentiment FLOAT,
                summary_text TEXT
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS feed_health (
                feed_name VARCHAR,
                check_date DATE,
                status VARCHAR,
                response_time FLOAT,
                article_count INTEGER,
                error_message TEXT,
                PRIMARY KEY (feed_name, check_date)
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS word_history (
                word VARCHAR,
                date DATE,
                count INTEGER,
                total_articles INTEGER,
                normalized_frequency FLOAT,
                is_stopword BOOLEAN DEFAULT FALSE,
                is_security BOOLEAN DEFAULT FALSE,
                is_geopolitical BOOLEAN DEFAULT FALSE
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS signal_words (
                id BIGINT DEFAULT nextval('sw_seq') PRIMARY KEY,
                word VARCHAR,
                date DATE,
                signal_strength FLOAT,
                detection_methods JSON,
                z_score FLOAT,
                classification VARCHAR,
                is_noise BOOLEAN DEFAULT FALSE
            )
        """)
        self.conn.commit()
    
    def insert_articles(self, articles: List[Dict]):
        if not articles:
            return
        rows = []
        for a in articles:
            rows.append((
                a.get('id'), a.get('feed_name'), a.get('feed_category'),
                a.get('title'), a.get('summary'), a.get('content', ''),
                a.get('link'), a.get('published_at'), a.get('word_count', 0),
                json.dumps(a.get('keywords', [])), json.dumps(a.get('topics', [])),
                a.get('sentiment_score'), a.get('sentiment_label'),
                a.get('risk_score', 0.0), a.get('relevance_score', 0.0),
                a.get('priority', False)
            ))
        self.conn.executemany("""
            INSERT OR REPLACE INTO articles 
            (id, feed_name, feed_category, title, summary, content, link,
             published_at, word_count, keywords, topics, sentiment_score,
             sentiment_label, risk_score, relevance_score, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        self.conn.commit()
    
    def insert_daily_summary(self, date: str, summary: Dict):
        self.conn.execute("""
            INSERT OR REPLACE INTO daily_summary
            (date, total_articles, feeds_active, total_topics, top_keywords,
             risk_topics, top_articles, signal_words, new_words, resurrected_words,
             dropped_words, sentiment_distribution, overall_sentiment, summary_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date, summary.get('total_articles', 0), summary.get('feeds_active', 0),
            summary.get('total_topics', 0), json.dumps(summary.get('top_keywords', {})),
            json.dumps(summary.get('risk_topics', {})), json.dumps(summary.get('top_articles', [])),
            json.dumps(summary.get('signal_words', {})), json.dumps(summary.get('new_words', {})),
            json.dumps(summary.get('resurrected_words', {})), json.dumps(summary.get('dropped_words', {})),
            json.dumps(summary.get('sentiment_distribution', {})), summary.get('overall_sentiment', 0.0),
            summary.get('summary_text', '')
        ))
        self.conn.commit()
    
    def insert_feed_health(self, feed_name: str, status: Dict):
        self.conn.execute("""
            INSERT OR REPLACE INTO feed_health
            (feed_name, check_date, status, response_time, article_count, error_message)
            VALUES (?, CURRENT_DATE, ?, ?, ?, ?)
        """, (
            feed_name, status.get('status', 'UNKNOWN'),
            status.get('response_time', 0.0), status.get('article_count', 0),
            status.get('error_message', '')
        ))
        self.conn.commit()
    
    def insert_word_history(self, word_stats: Dict[str, Dict]):
        today = datetime.now().date().isoformat()
        for word, stats in word_stats.items():
            self.conn.execute("""
                INSERT INTO word_history (word, date, count, total_articles, normalized_frequency)
                VALUES (?, ?, ?, ?, ?)
            """, (word, today, stats['count'], stats['total_articles'], stats['normalized']))
        self.conn.commit()
    
    def insert_signal_words(self, signals: List[Dict]):
        for s in signals:
            self.conn.execute("""
                INSERT INTO signal_words (word, date, signal_strength, detection_methods, z_score, classification)
                VALUES (CURRENT_DATE, ?, ?, ?, ?, ?)
            """, (s['word'], s.get('signal_strength', 0.0),
                  json.dumps(s.get('detection_methods', [])), s.get('z_score'),
                  s.get('classification', 'UNKNOWN')))
        self.conn.commit()
    
    def get_all_words_last_7_days(self) -> Dict[str, int]:
        try:
            res = self.conn.execute("""
                SELECT word, SUM(count) as total
                FROM word_history
                WHERE date >= (CURRENT_DATE - INTERVAL '7' DAY)
                GROUP BY word
            """).fetchall()
            return {r[0]: r[1] for r in res}
        except Exception:
            return {}
    
    def get_word_history(self, word: str, days: int = 30) -> List[Dict]:
        try:
            res = self.conn.execute("""
                SELECT date, count, normalized_frequency
                FROM word_history
                WHERE word = ? AND date >= (CURRENT_DATE - INTERVAL ? DAY)
                ORDER BY date
            """, (word, days)).fetchall()
            return [{'date': r[0], 'count': r[1], 'normalized': r[2]} for r in res]
        except Exception:
            return []
    
    def archive_old_data(self):
        cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).date().isoformat()
        rows = self.conn.execute("SELECT * FROM articles WHERE DATE(published_at) < ?", (cutoff,)).fetchall()
        if not rows:
            return
        cols = [d[0] for d in self.conn.description]
        articles = [dict(zip(cols, r)) for r in rows]
        af = ARCHIVE_DIR / f"{datetime.now().strftime('%Y-%m')}-archive.json.gz"
        with gzip.open(af, 'wt', encoding='utf-8') as f:
            json.dump(articles, f, indent=2)
        self.conn.execute("DELETE FROM articles WHERE DATE(published_at) < ?", (cutoff,))
        self.conn.commit()
        print(f"  📦 Archived {len(articles)} old articles → {af}")
    
    def close(self):
        self.conn.close()

# ============================================
# FEED FETCHER
# ============================================

class FeedFetcher:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
    
    def fetch(self, url: str, name: str) -> Dict[str, Any]:
        result = {
            'status': 'OK', 'articles': [], 'response_time': 0.0,
            'error_message': '', 'article_count': 0
        }
        try:
            t0 = time.time()
            r = self.session.get(url, timeout=FEED_TIMEOUT)
            result['response_time'] = round(time.time() - t0, 2)
            
            if r.status_code != 200:
                result['status'] = f'HTTP_{r.status_code}'
                result['error_message'] = f"HTTP {r.status_code}"
                return result
            
            parsed = feedparser.parse(r.content)
            if parsed.bozo:
                result['status'] = 'PARSE_ERROR'
                result['error_message'] = str(getattr(parsed, 'bozo_exception', 'unknown'))[:200]
                return result
            
            if not hasattr(parsed, 'entries') or not parsed.entries:
                result['status'] = 'NO_ENTRIES'
                result['error_message'] = 'Feed parsed but contains zero entries'
                return result
            
            for entry in parsed.entries[:MAX_ARTICLES_PER_FEED]:
                pub = datetime.now()
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        pub = datetime(*entry.published_parsed[:6])
                    except Exception:
                        pass
                
                result['articles'].append({
                    'title': entry.get('title', '').strip(),
                    'link': entry.get('link', '').strip(),
                    'summary': entry.get('summary', entry.get('description', '')).strip(),
                    'published_at': pub,
                    'feed_name': name
                })
            
            result['article_count'] = len(result['articles'])
            
        except requests.exceptions.Timeout:
            result['status'] = 'TIMEOUT'
            result['error_message'] = f'Timeout after {FEED_TIMEOUT}s'
        except requests.exceptions.ConnectionError as e:
            result['status'] = 'CONNECTION_ERROR'
            result['error_message'] = str(e)[:200]
        except Exception as e:
            result['status'] = 'UNKNOWN_ERROR'
            result['error_message'] = str(e)[:200]
        
        return result

# ============================================
# PROCESSORS
# ============================================

class KeywordExtractor:
    STOPWORDS = {
        'security', 'cyber', 'attack', 'data', 'system', 'network',
        'computer', 'software', 'hardware', 'information', 'technology',
        'access', 'control', 'management', 'service', 'application',
        'server', 'client', 'user', 'admin', 'administrator',
        'company', 'business', 'organization', 'enterprise', 'corporate',
        'government', 'agency', 'department', 'office', 'federal',
        'said', 'says', 'will', 'would', 'could', 'should', 'also',
        'this', 'that', 'with', 'from', 'they', 'have', 'been', 'were'
    }
    
    def extract(self, text: str) -> List[str]:
        if not text or len(text.strip()) < 20:
            return []
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        filtered = [w for w in words if w not in self.STOPWORDS and len(w) > 3]
        freq = Counter(filtered)
        top = [w for w, _ in freq.most_common(MAX_KEYWORDS * 2)]
        
        # Security phrases
        text_l = text.lower()
        phrases = [p for p in [
            'ransomware attack', 'data breach', 'zero day', 'supply chain',
            'critical vulnerability', 'phishing campaign', 'malware infection',
            'cloud security', 'identity theft', 'access control'
        ] if p in text_l]
        
        combined = []
        seen = set()
        for kw in top + phrases:
            if kw not in seen and len(kw) > 3:
                combined.append(kw)
                seen.add(kw)
                if len(combined) >= MAX_KEYWORDS:
                    break
        return combined


class TopicDetector:
    def detect(self, text: str, keywords: List[str]) -> List[str]:
        topics = set()
        text_l = text.lower()
        for topic, patterns in TOPIC_RULES.items():
            if any(p in text_l for p in patterns):
                topics.add(topic)
        for kw in keywords:
            kl = kw.lower()
            for topic, patterns in TOPIC_RULES.items():
                if any(p in kl or kl in p for p in patterns):
                    topics.add(topic)
        return list(topics)[:5]


class SentimentAnalyzer:
    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        self.lexicon = CUSTOM_SENTIMENT_LEXICON
    
    def analyze(self, text: str) -> Dict[str, Any]:
        if not text or len(text.strip()) < 20:
            return {'score': 0.0, 'label': 'neutral', 'components': {}}
        
        v = self.vader.polarity_scores(text)['compound']
        b = TextBlob(text).sentiment.polarity
        
        text_l = text.lower()
        custom_scores = [self.lexicon[w] for w in self.lexicon if w in text_l]
        custom = sum(custom_scores) / len(custom_scores) if custom_scores else 0.0
        
        words = re.findall(r'\b[a-z]+\b', text_l)
        word_scores = [self.lexicon[w] for w in words if w in self.lexicon]
        word_based = sum(word_scores) / len(word_scores) if word_scores else 0.0
        
        score = max(-1.0, min(1.0, v * 0.25 + b * 0.20 + custom * 0.30 + word_based * 0.25))
        
        if score >= 0.6: label = 'very_positive'
        elif score >= 0.2: label = 'positive'
        elif score >= -0.2: label = 'neutral'
        elif score >= -0.6: label = 'negative'
        else: label = 'very_negative'
        
        return {'score': score, 'label': label, 'components': {'vader': v, 'textblob': b, 'custom': custom}}


class RiskScorer:
    RISK_KEYWORDS = {
        'critical': 0.3, 'exploit': 0.2, 'breach': 0.3,
        'vulnerability': 0.2, 'ransomware': 0.3, 'zero-day': 0.3,
        'patch': 0.1, 'attack': 0.1, 'compromised': 0.2,
        'malware': 0.2, 'phishing': 0.15
    }
    
    def score(self, category: str, topics: List[str], text: str) -> float:
        if RISK_MODE == "none":
            return 0.0
        priority = FEED_PRIORITY.get(category, 0.3)
        if RISK_MODE == "feed_priority":
            text_l = text.lower()
            s = sum(w for kw, w in self.RISK_KEYWORDS.items() if kw in text_l)
            return min(1.0, priority * 0.4 + min(s, 1.0) * 0.6)
        return priority

# ============================================
# WORD STATISTICS
# ============================================

class WordStatsAnalyzer:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def analyze(self, articles: List[Dict]) -> Dict[str, Any]:
        if not articles:
            return self._empty_stats()
        
        word_counts = Counter()
        article_word_counts = []
        
        for a in articles:
            text = f"{a.get('title', '')} {a.get('summary', '')}".lower()
            words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
            word_counts.update(words)
            article_word_counts.append(len(words))
        
        total_words = sum(article_word_counts)
        total_articles = len(articles)
        unique_words = len(word_counts)
        avg_words = total_words / total_articles if total_articles else 0
        lexical_density = (unique_words / total_words * 100) if total_words else 0
        
        baseline = self.db.get_all_words_last_7_days()
        
        word_stats = {}
        for word, count in word_counts.items():
            base = baseline.get(word, 0)
            avg_base = base / 7 if base > 0 else 1
            std = max(1, avg_base * 0.5)
            z = (count - avg_base) / std if std > 0 else 0
            word_stats[word] = {
                'count': count,
                'normalized': count / total_words * 100 if total_words else 0,
                'baseline': avg_base,
                'z_score': z,
                'total_articles': total_articles
            }
        
        # New words
        new_words = {
            w: s['count'] for w, s in word_stats.items()
            if (w not in baseline or baseline[w] == 0) and s['count'] >= REPORT_LIMITS.get('min_new_word_mentions', 3)
        }
        
        # Resurrected
        resurrected = {}
        for w, bc in baseline.items():
            if w not in word_counts and bc >= 2:
                hist = self.db.get_word_history(w, 30)
                if hist and len(hist) >= 3:
                    last = hist[-1]['date']
                    days = (datetime.now().date() - datetime.strptime(str(last), '%Y-%m-%d').date()).days
                    if days >= REPORT_LIMITS.get('resurrect_threshold_days', 7):
                        resurrected[w] = bc
        
        # Dropped
        dropped = {w: c for w, c in baseline.items() if w not in word_counts and c >= 2}
        
        # Spikes / Drops
        spikes = {w: s for w, s in word_stats.items() if s['z_score'] > Z_SCORE_THRESHOLD}
        drops = {w: s for w, s in word_stats.items() if s['z_score'] < -Z_SCORE_THRESHOLD}
        
        # Signals
        signals = []
        for w, s in word_stats.items():
            z = abs(s['z_score'])
            if z > Z_SCORE_THRESHOLD:
                strength = min(z / 5, 1.0)
                if strength >= CRITICAL_THRESHOLD: cls = 'CRITICAL_SIGNAL'
                elif strength >= HIGH_THRESHOLD: cls = 'HIGH_SIGNAL'
                elif strength >= MEDIUM_THRESHOLD: cls = 'MEDIUM_SIGNAL'
                else: cls = 'LOW_SIGNAL'
                signals.append({
                    'word': w, 'signal_strength': strength,
                    'detection_methods': ['z_score'], 'z_score': s['z_score'],
                    'classification': cls, 'count': s['count'],
                    'baseline': s['baseline']
                })
        
        if word_stats:
            self.db.insert_word_history(word_stats)
        if signals:
            try:
                self.db.insert_signal_words(signals)
            except Exception as e:
                print(f"  ⚠️  Signal insert failed: {e}")
        
        return {
            'total_words': total_words, 'unique_words': unique_words,
            'avg_words': avg_words, 'lexical_density': lexical_density,
            'word_counts': dict(word_counts.most_common(50)),
            'spikes': dict(sorted(spikes.items(), key=lambda x: x[1]['z_score'], reverse=True)[:10]),
            'drops': dict(sorted(drops.items(), key=lambda x: x[1]['z_score'])[:10]),
            'new_words': dict(sorted(new_words.items(), key=lambda x: x[1], reverse=True)[:10]),
            'resurrected_words': dict(sorted(resurrected.items(), key=lambda x: x[1], reverse=True)[:10]),
            'dropped_words': dict(sorted(dropped.items(), key=lambda x: x[1], reverse=True)[:10]),
            'signals': signals,
            'signal_count': len(signals),
            'critical_signal_count': len([s for s in signals if s['classification'] == 'CRITICAL_SIGNAL'])
        }
    
    def _empty_stats(self):
        return {
            'total_words': 0, 'unique_words': 0, 'avg_words': 0.0,
            'lexical_density': 0.0, 'word_counts': {}, 'spikes': {},
            'drops': {}, 'new_words': {}, 'resurrected_words': {},
            'dropped_words': {}, 'signals': [], 'signal_count': 0,
            'critical_signal_count': 0
        }

# ============================================
# REPORT GENERATOR
# ============================================

class ReportGenerator:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def generate(self, articles: List[Dict], feed_stats: Dict, word_stats: Dict, from_cache: bool = False) -> str:
        today = datetime.now().strftime('%Y-%m-%d')
        lim = REPORT_LIMITS
        secs = REPORT_SECTIONS
        lines = [f"# 📊 Daily Word Statistics Report - {today}\n"]
        
        # ── Overall Volume ──
        if secs.get('overall_volume', True):
            tw = word_stats['total_words']
            lines.append("## 📈 Overall Word Volume\n| Metric | Value |\n|--------|-------|")
            lines.append(f"| **Total Words Processed** | {tw:,} |")
            lines.append(f"| **Total Unique Words** | {word_stats['unique_words']:,} |")
            lines.append(f"| **Average Words per Article** | {word_stats['avg_words']:.1f} |")
            lines.append(f"| **Lexical Density** | {word_stats['lexical_density']:.1f}% |")
            lines.append(f"| **Estimated Reading Time** | {tw/200:.1f} mins |")
            lines.append("")
        
        # ── Top Words ──
        if secs.get('top_words', True) and word_stats['word_counts']:
            lines.append(f"## 🔝 Top {lim['top_words']} Most Frequent Words\n| Rank | Word | Count | % |")
            lines.append("|------|------|-------|---|")
            for i, (w, c) in enumerate(list(word_stats['word_counts'].items())[:lim['top_words']], 1):
                pct = c / tw * 100 if tw else 0
                lines.append(f"| {i} | {w} | {c:,} | {pct:.2f}% |")
            lines.append("")
        
        # ── Spikes ──
        if secs.get('spike_words', True) and word_stats['spikes']:
            lines.append(f"## 📈 Top {lim['top_spikes']} Word Spikes\n| Word | Today | 7-Day Avg | Ratio | Z-Score |")
            lines.append("|------|-------|-----------|-------|---------|")
            for w, s in list(word_stats['spikes'].items())[:lim['top_spikes']]:
                ratio = s['count'] / s['baseline'] if s['baseline'] > 0 else s['count']
                lines.append(f"| {w} | {s['count']} | {s['baseline']:.1f} | {ratio:.1f}x | {s['z_score']:.1f} |")
            lines.append("")
        
        # ── Drops ──
        if secs.get('drop_words', True) and word_stats['drops']:
            lines.append(f"## 📉 Top {lim['top_drops']} Word Drops\n| Word | Today | 7-Day Avg | Drop | Z-Score |")
            lines.append("|------|-------|-----------|------|---------|")
            for w, s in list(word_stats['drops'].items())[:lim['top_drops']]:
                ratio = s['count'] / s['baseline'] if s['baseline'] > 0 else 0
                drop = (1 - ratio) * 100 if ratio > 0 else 100
                lines.append(f"| {w} | {s['count']} | {s['baseline']:.1f} | -{drop:.1f}% | {s['z_score']:.1f} |")
            lines.append("")
        
        # ── New Words ──
        if secs.get('new_words', True) and word_stats['new_words']:
            lines.append(f"## 🆕 New Words (First Appearance)\n| Word | Count |")
            lines.append("|------|-------|")
            for w, c in list(word_stats['new_words'].items())[:lim['new_words']]:
                lines.append(f"| {w} | {c} |")
            lines.append("")
        
        # ── Resurrected ──
        if secs.get('resurrected_words', True) and word_stats['resurrected_words']:
            lines.append(f"## 🔄 Resurrected Words\n| Word | 7-Day Count |")
            lines.append("|------|-------------|")
            for w, c in list(word_stats['resurrected_words'].items())[:lim['resurrected_words']]:
                lines.append(f"| {w} | {c} |")
            lines.append("")
        
        # ── Dropped ──
        if secs.get('dropped_words', True) and word_stats['dropped_words']:
            lines.append(f"## 📉 Dropped Words\n| Word | 7-Day Count |")
            lines.append("|------|-------------|")
            for w, c in list(word_stats['dropped_words'].items())[:lim['dropped_words']]:
                lines.append(f"| {w} | {c} |")
            lines.append("")
        
        # ── Signal vs Noise ──
        if secs.get('signal_noise', True):
            ts = word_stats['signal_count']
            sp = (ts / tw * 100) if tw else 0
            lines.append("## 📝 Signal vs Noise\n| Category | Words | % |")
            lines.append("|----------|-------|---|")
            lines.append(f"| **Signal Words** | {ts:,} | {sp:.1f}% |")
            lines.append(f"| **Noise Words** | {tw - ts:,} | {100 - sp:.1f}% |")
            lines.append("")
        
        # ── System Health ──
        ok_feeds = sum(1 for s in feed_stats.values() if s.get('status') == 'OK')
        total_feeds = len(feeds) if 'feeds' in dir() else len(feed_stats)
        cache_note = " *(from cache)*" if from_cache else ""
        lines.append("## 📝 System Health\n| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| **Run Status** | ✅ {ok_feeds}/{total_feeds} feeds OK{cache_note} |")
        lines.append(f"| **Articles Processed** | {len(articles)} |")
        lines.append(f"| **Signal Words Detected** | {word_stats['signal_count']} |")
        lines.append(f"| **New Words Discovered** | {len(word_stats['new_words'])} |")
        lines.append("")
        lines.append(f"---\n*Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        
        return "\n".join(lines)

# ============================================
# MAIN
# ============================================

def main():
    parser = argparse.ArgumentParser(description='RSS Intelligence Pipeline')
    parser.add_argument('--no-cache', action='store_true', help='Force fresh fetch, ignore cache')
    parser.add_argument('--clear-cache', action='store_true', help='Delete cache before running')
    args = parser.parse_args()
    
    print("\n" + "=" * 50)
    print("  RSS Intelligence Pipeline v3.0")
    print("=" * 50 + "\n")
    
    # ── Diagnostics: Environment ──
    print("🔍 Environment Checks:")
    diag("Base directory", BASE_DIR.exists(), str(BASE_DIR))
    diag("Logs directory", LOGS_DIR.exists(), str(LOGS_DIR))
    diag("Cache directory", CACHE_DIR.exists(), str(CACHE_DIR))
    diag("Archive directory", ARCHIVE_DIR.exists(), str(ARCHIVE_DIR))
    
    if not FEEDS_FILE.exists():
        die(f"Feeds file not found: {FEEDS_FILE}\n   Create it with your RSS feed list.")
    diag("Feeds file", True, str(FEEDS_FILE))
    
    try:
        feeds = json.loads(FEEDS_FILE.read_text())
    except json.JSONDecodeError as e:
        die(f"Feeds file is invalid JSON: {e}")
    
    if not isinstance(feeds, list) or len(feeds) == 0:
        die("Feeds file must contain a non-empty list of feed objects.")
    
    diag("Feeds loaded", True, f"{len(feeds)} feeds")
    print()
    
    # ── Clear cache if requested ──
    today_str = datetime.now().strftime('%Y-%m-%d')
    cp = cache_path(today_str)
    if args.clear_cache and cp.exists():
        cp.unlink()
        print("🗑️  Cache cleared.\n")
    
    # ── Logger ──
    logger = setup_logging()
    logger.info("🚀 Pipeline started")
    
    # ── Try cache ──
    all_articles = []
    feed_stats = {}
    from_cache = False
    
    if not args.no_cache:
        cached = load_cache(today_str)
        if cached:
            all_articles = cached
            from_cache = True
            print(f"📂 Using cached data ({len(all_articles)} articles)\n")
            for f in feeds:
                feed_stats[f.get('name', 'unknown')] = {'status': 'CACHED', 'articles': 0}
    
    # ── Fetch fresh if needed ──
    if not all_articles:
        print("🔄 Fetching fresh data...\n")
        
        db = DatabaseManager(DB_PATH)
        fetcher = FeedFetcher(logger)
        kex = KeywordExtractor()
        tdet = TopicDetector()
        sent = SentimentAnalyzer()
        risk = RiskScorer()
        
        # Master list for cache + analysis (FIX: separate from DB batch buffer)
        all_articles = []
        db_batch = []
        
        for idx, feed in enumerate(feeds, 1):
            name = feed.get('name', 'unnamed')
            url = feed.get('url', '')
            category = feed.get('category', 'Unknown')
            
            print(f"  [{idx}/{len(feeds)}] {name} ... ", end="", flush=True)
            
            if not url:
                print("❌ NO_URL")
                feed_stats[name] = {'status': 'NO_URL', 'articles': 0}
                continue
            
            result = fetcher.fetch(url, name)
            
            if result['status'] != 'OK':
                print(f"❌ {result['status']} ({result.get('error_message', '')[:40]})")
                feed_stats[name] = {
                    'status': result['status'], 'articles': 0,
                    'error': result.get('error_message', '')
                }
                try:
                    db.insert_feed_health(name, result)
                except Exception:
                    pass
                continue
            
            processed = []
            for entry in result['articles']:
                text = entry.get('summary', '')
                if not text or len(text.strip()) < 20:
                    continue
                
                keywords = kex.extract(text)
                topics = tdet.detect(text, keywords)
                sentiment = sent.analyze(text)
                rscore = risk.score(category, topics, text)
                
                processed.append({
                    'id': hashlib.md5(entry['link'].encode()).hexdigest()[:16],
                    'feed_name': name,
                    'feed_category': category,
                    'title': entry['title'],
                    'summary': entry['summary'],
                    'content': '',
                    'link': entry['link'],
                    'published_at': entry['published_at'].isoformat() if isinstance(entry['published_at'], datetime) else str(entry['published_at']),
                    'word_count': len(text.split()),
                    'keywords': keywords,
                    'topics': topics,
                    'sentiment_score': sentiment['score'],
                    'sentiment_label': sentiment['label'],
                    'risk_score': rscore,
                    'relevance_score': rscore * (0.8 + 0.2 * (len(topics) / 5)),
                    'priority': False
                })
            
            print(f"✅ {len(processed)} articles")
            feed_stats[name] = {'status': 'OK', 'articles': len(processed)}
            
            # Add to master list (for cache & analysis)
            all_articles.extend(processed)
            # Add to DB batch buffer
            db_batch.extend(processed)
            
            # Flush DB batch when large (FIX: don't touch all_articles)
            if len(db_batch) >= BATCH_SIZE:
                try:
                    db.insert_articles(db_batch)
                    logger.info(f"Flushed {len(db_batch)} articles to DB")
                except Exception as e:
                    logger.error(f"DB flush failed: {e}")
                db_batch = []
                gc.collect()
            
            # Log feed health
            try:
                db.insert_feed_health(name, result)
            except Exception:
                pass
        
        # Final DB flush
        if db_batch:
            try:
                db.insert_articles(db_batch)
                logger.info(f"Stored final {len(db_batch)} articles to DB")
            except Exception as e:
                logger.error(f"Final DB flush failed: {e}")
        
        # Save cache (FIX: save all_articles, not the empty db_batch)
        save_cache(all_articles, today_str)
        db.archive_old_data()
        db.close()
        
        print(f"\n📊 Total articles collected: {len(all_articles)}")
    
    # ── Validate we have data ──
    if not all_articles:
        die("No articles were collected. Check your feeds and network connection.")
    
    # ── Word Statistics ──
    print("\n📊 Analyzing word statistics...")
    db = DatabaseManager(DB_PATH)
    wsa = WordStatsAnalyzer(db)
    word_stats = wsa.analyze(all_articles)
    
    # ── Generate Report ──
    print("📄 Generating report...")
    rg = ReportGenerator(db)
    report = rg.generate(all_articles, feed_stats, word_stats, from_cache=from_cache)
    
    report_file = LOGS_DIR / f"daily-summary-{today_str}.md"
    report_file.write_text(report, encoding='utf-8')
    
    # ── Summary to DB ──
    summary = {
        'total_articles': len(all_articles),
        'feeds_active': sum(1 for s in feed_stats.values() if s.get('status') == 'OK'),
        'total_topics': len(set(t for a in all_articles for t in a.get('topics', []))),
        'top_keywords': {},  # populated from word_stats if needed
        'risk_topics': {},
        'top_articles': [],
        'signal_words': {},
        'new_words': word_stats['new_words'],
        'resurrected_words': word_stats['resurrected_words'],
        'dropped_words': word_stats['dropped_words'],
        'sentiment_distribution': {},
        'overall_sentiment': 0.0,
        'summary_text': report[:2000]
    }
    try:
        db.insert_daily_summary(today_str, summary)
    except Exception as e:
        logger.warning(f"Daily summary insert failed: {e}")
    
    db.close()
    
    print(f"\n{'=' * 50}")
    print(f"  ✅ Report saved: {report_file}")
    print(f"  📰 Articles: {len(all_articles)}")
    print(f"  📈 Words: {word_stats['total_words']:,} | Signals: {word_stats['signal_count']}")
    print(f"{'=' * 50}\n")
    
    logger.info("Pipeline completed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())
