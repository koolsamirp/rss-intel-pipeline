#!/usr/bin/env python3
"""
One File - Everything
Run: ~/ai_env/bin/python ~/.rss-intel-pipeline/pipeline.py
"""

import duckdb, json, re, hashlib, requests, feedparser, os, sys, time, gzip
from pathlib import Path
from datetime import datetime
from collections import Counter
from config import *

HOME = Path.home()
BASE = HOME / ".rss-intel-pipeline"
DB = BASE / "rss_intel.duckdb"
STOP = BASE / "stopwords.duckdb"
CACHE = BASE / "cache" / f"articles_{datetime.now().strftime('%Y-%m-%d')}.json"

# ============ 1. FETCH RSS ============
def fetch_feeds():
    if CACHE.exists():
        print(f"📂 Cache exists: {CACHE}")
        return json.load(open(CACHE))
    
    print("🔄 Fetching feeds...")
    feeds = json.load(open(BASE / "data" / "feeds.json"))
    all_articles = []
    
    for f in feeds:
        try:
            r = requests.get(f['url'], timeout=15)
            p = feedparser.parse(r.content)
            for e in p.entries[:20]:
                all_articles.append({
                    'title': e.get('title', ''),
                    'summary': e.get('summary', ''),
                    'link': e.get('link', ''),
                    'feed': f['name'],
                    'category': f.get('category', 'Unknown'),
                    'date': datetime(*e.published_parsed[:6]) if hasattr(e, 'published_parsed') else datetime.now()
                })
        except:
            pass
    
    CACHE.parent.mkdir(exist_ok=True)
    json.dump(all_articles, open(CACHE, 'w'))
    print(f"💾 Cached {len(all_articles)} articles")
    return all_articles

# ============ 2. PROCESS ARTICLES ============
def process_articles(articles):
    print("📊 Processing...")
    conn = duckdb.connect(str(DB))
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS words (word VARCHAR, date DATE, count INTEGER)
    """)
    
    today = datetime.now().date().isoformat()
    word_counts = Counter()
    
    for a in articles:
        text = (a['title'] + ' ' + a['summary']).lower()
        words = re.findall(r'\b[a-z]{3,}\b', text)
        word_counts.update(words)
    
    for word, count in word_counts.most_common(10000):
        conn.execute("INSERT INTO words VALUES (?, ?, ?)", (word, today, count))
    
    conn.close()
    return word_counts

# ============ 3. GENERATE REPORT ============
def show_report():
    print("\n" + "="*60)
    print(f"🔒 SECURITY REPORT - {datetime.now().strftime('%Y-%m-%d')}")
    print("="*60)
    
    conn = duckdb.connect(str(DB))
    stop = duckdb.connect(str(STOP))
    
    # Get security terms
    terms = {}
    for t in stop.execute("SELECT term, risk_weight FROM security_terms").fetchall():
        terms[t[0]] = ('security', t[1])
    for t in stop.execute("SELECT term, risk_weight FROM geopolitical_terms").fetchall():
        terms[t[0]] = ('geopolitical', t[1])
    
    # Get today's words
    today = datetime.now().date().isoformat()
    words = conn.execute(f"SELECT word, count FROM words WHERE date = '{today}'").fetchall()
    
    # Filter
    results = []
    for word, count in words:
        if word in terms:
            results.append((word, count, terms[word][0], terms[word][1]))
    
    results.sort(key=lambda x: x[1], reverse=True)
    
    print("\n📊 TOP SECURITY TERMS")
    for w,c,t,s in results[:15]:
        emoji = "🔒" if t == "security" else "🌍"
        print(f"  {emoji} {w:<18} {c:>6}")
    
    high = [x for x in results if x[3] >= 0.7]
    if high:
        print("\n🚨 CRITICAL (Risk >= 0.7)")
        for w,c,t,s in high[:10]:
            print(f"  ⚠️ {w:<18} {c:>6} (weight: {s:.1f})")
    
    total = sum(x[1] for x in results)
    sec = sum(x[1] for x in results if x[2] == "security")
    geo = sum(x[1] for x in results if x[2] == "geopolitical")
    print(f"\n📊 Total: {total} (🔒 {sec} | 🌍 {geo})")
    
    conn.close()
    stop.close()

# ============ MAIN ============
if __name__ == "__main__":
    articles = fetch_feeds()
    process_articles(articles)
    show_report()
