#!/usr/bin/env python3
"""
RSS Intelligence Pipeline - Configuration File (Memory Optimized)
"""

import os
from pathlib import Path

# ============================================
# PATH CONFIGURATION
# ============================================
BASE_DIR = Path.home() / ".rss-intel-pipeline"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
ARCHIVE_DIR = BASE_DIR / "archive"
DB_PATH = BASE_DIR / "rss_intel.duckdb"
STOPWORDS_DB_PATH = BASE_DIR / "stopwords.duckdb"
ACTORS_DB_PATH = BASE_DIR / "threat_actors.duckdb"
FEEDS_FILE = DATA_DIR / "feeds.json"

for d in [BASE_DIR, DATA_DIR, LOGS_DIR, ARCHIVE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================
# FETCH CONFIGURATION (REDUCED)
# ============================================
FEED_TIMEOUT = 15
ARTICLE_TIMEOUT = 10
MAX_RETRIES = 3
USER_AGENT = "RSS-Intel-Pipeline/1.0"
MAX_ARTICLES_PER_FEED = 20  # Reduced from 50

# ============================================
# CONTENT EXTRACTION
# ============================================
FULL_TEXT_MODE = "snippet"
PRIORITY_FEEDS = [
    "CISA Alerts", "Europol EC3 News", "NIST News",
    "Palo Alto Unit 42", "CrowdStrike Blog", "SecureList (Kaspersky)",
    "ESET Research", "Google Security Blog", "Schneier on Security",
    "Krebs on Security", "The Hacker News", "BleepingComputer"
]

# ============================================
# KEYWORD EXTRACTION
# ============================================
KEYWORD_MODE = "hybrid"
MAX_KEYWORDS = 8  # Reduced from 10

# ============================================
# TOPIC DETECTION
# ============================================
TOPIC_MODE = "rule"
TOPIC_RULES = {
    "ransomware": ["ransomware", "encrypt", "decrypt", "bitcoin", "locker"],
    "vulnerability": ["vulnerability", "patch", "exploit", "0-day", "zero-day"],
    "breach": ["breach", "exposed", "leak", "compromised", "stolen"],
    "malware": ["malware", "trojan", "worm", "virus", "rootkit"],
    "phishing": ["phishing", "spearphishing", "social engineering"],
    "supply_chain": ["supply chain", "third-party", "vendor", "dependency"],
    "cloud_security": ["cloud", "aws", "azure", "gcp", "container"],
    "iot_security": ["iot", "embedded", "device", "firmware"],
    "identity": ["identity", "authentication", "mfa", "password", "access"],
    "compliance": ["compliance", "gdpr", "ccpa", "regulation", "audit"]
}

# ============================================
# RISK SCORING
# ============================================
RISK_MODE = "feed_priority"
FEED_PRIORITY = {
    "Government": 1.0,
    "Security (Vendors)": 0.9,
    "Security (Community)": 0.7,
    "Tech News": 0.4,
    "Cloud & Infra": 0.4,
    "Science & AI": 0.3,
    "Programming": 0.2,
    "News": 0.3
}

# ============================================
# ENTITY RESOLUTION
# ============================================
SIMILARITY_THRESHOLD = 0.7
SIMILARITY_METHODS = ['levenshtein', 'jaccard', 'tfidf_cosine']

# ============================================
# THREAT ACTOR SCORING
# ============================================
RISK_SCORE_WEIGHTS = {
    'context_weight': 0.4,
    'frequency_weight': 0.3,
    'source_weight': 0.3,
}
FEED_CREDIBILITY = {
    "Government": 1.0,
    "Security (Vendors)": 0.9,
    "Security (Community)": 0.7,
    "Tech News": 0.4,
    "Cloud & Infra": 0.4,
    "News": 0.3,
    "Programming": 0.2,
    "Science & AI": 0.3
}

# ============================================
# SENTIMENT ANALYSIS
# ============================================
ENABLE_SENTIMENT = True
SENTIMENT_METHODS = ['vader', 'textblob', 'custom']
CUSTOM_SENTIMENT_LEXICON = {
    'critical': 0.1, 'emergency': 0.1, 'catastrophic': 0.0,
    'exploited': 0.15, 'ransomware': 0.1, 'breach': 0.2,
    'compromised': 0.2, 'exposed': 0.25, 'leaked': 0.3,
    'malware': 0.3, 'virus': 0.3, 'trojan': 0.3,
    'phishing': 0.3, 'scam': 0.3, 'fraud': 0.25,
    'vulnerability': 0.35, 'patch': 0.35, 'fix': 0.4,
    'attack': 0.35, 'intrusion': 0.35, 'hack': 0.4,
    'risk': 0.4, 'threat': 0.4, 'warning': 0.35,
    'alert': 0.35, 'urgent': 0.3,
    'update': 0.5, 'release': 0.5, 'announcement': 0.5,
    'report': 0.5, 'analysis': 0.5, 'review': 0.5,
    'protected': 0.65, 'secure': 0.6, 'defense': 0.6,
    'detected': 0.55, 'prevented': 0.65, 'blocked': 0.6,
    'contained': 0.6, 'mitigated': 0.55, 'resolved': 0.65,
    'solved': 0.8, 'fixed': 0.8, 'patched': 0.8,
    'remediated': 0.75, 'recovered': 0.7, 'restored': 0.7,
    'improved': 0.7, 'enhanced': 0.7, 'strengthened': 0.75,
    'arrested': 0.9, 'captured': 0.9, 'dismantled': 0.85
}

# ============================================
# STATISTICAL ANALYSIS (DISABLED FOR MEMORY)
# ============================================
ENABLE_WORD_STATS = True
ENABLE_NGRAM_STATS = False
ENABLE_CO_OCCURRENCE = False
ENABLE_TOPIC_EVOLUTION = False
ENABLE_ANOMALY_DETECTION = True
ENABLE_CHANGE_POINT = False
ENABLE_PREDICTIVE = False
ENABLE_NETWORK_ANALYSIS = False

WORD_STATS_WINDOW = 30
ANOMALY_THRESHOLD = 2.0
BURST_THRESHOLD = 3.0
MIN_CO_OCCURRENCE = 5

# ============================================
# SIGNAL VS NOISE
# ============================================
Z_SCORE_THRESHOLD = 2.0
BURST_THRESHOLD = 3.0
CO_OCCURRENCE_THRESHOLD = 3.0

CRITICAL_THRESHOLD = 0.8
HIGH_THRESHOLD = 0.6
MEDIUM_THRESHOLD = 0.4
LOW_THRESHOLD = 0.2

MIN_WORD_LENGTH = 4
MIN_MENTIONS = 3
BASELINE_DAYS = 30

# ============================================
# STORAGE CONFIGURATION
# ============================================
DB_SIZE_LIMIT_MB = 500
RETENTION_DAYS = 30
ARCHIVE_COMPRESSION = True

# ============================================
# LOGGING CONFIGURATION
# ============================================
LOG_ROTATE_AFTER = 7
LOG_LEVEL = "INFO"
ENABLE_CONSOLE_LOG = True

# ============================================
# REPORT CONFIGURATION
# ============================================
REPORT_LIMITS = {
    'top_words': 10,
    'top_spikes': 10,
    'top_drops': 10,
    'new_words': 10,
    'resurrected_words': 10,
    'dropped_words': 10,
    'noise_words': 10,
    'trend_days': 7,
    'min_signal_strength': 0.2,
    'min_new_word_mentions': 2,
    'min_resurrected_mentions': 2,
    'resurrect_threshold_days': 7,
}

REPORT_SECTIONS = {
    'overall_volume': True,
    'top_words': True,
    'spike_words': True,
    'drop_words': True,
    'new_words': True,
    'resurrected_words': True,
    'dropped_words': True,
    'signal_noise': True,
    'feed_categories': True,
    'seven_day_trend': True,
    'change_summary': True,
    'system_health': True,
}

SHOW_COMPARISON = True
SHOW_PERCENTAGE_CHANGE = True
SHOW_DIRECTION_ARROWS = True

# ============================================
# PERFORMANCE CONFIGURATION (MEMORY OPTIMIZED)
# ============================================
MEMORY_LIMIT_MB = 1536  # Increased to 1.5GB
BATCH_SIZE = 30  # Reduced batch size
MAX_ARTICLES_PER_FEED = 20

# ============================================
# ERROR HANDLING
# ============================================
FAIL_GRACEFULLY = True
MAX_CONSECUTIVE_FAILURES = 5
SEND_ALERT_ON_CRITICAL = False
