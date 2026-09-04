#!/usr/bin/env python3
"""
Security Intelligence Report - Quick daily security summary
Run: ~/ai_env/bin/python ~/.rss-intel-pipeline/security_query.py
"""

import duckdb
from pathlib import Path
from datetime import datetime

def main():
    rss_db = Path.home() / ".rss-intel-pipeline" / "rss_intel.duckdb"
    stop_db = Path.home() / ".rss-intel-pipeline" / "stopwords.duckdb"
    
    rss = duckdb.connect(str(rss_db))
    stop = duckdb.connect(str(stop_db))
    
    today = datetime.now().date().isoformat()
    
    # Get security and geopolitical terms
    security_terms = stop.execute("SELECT term, risk_weight FROM security_terms").fetchall()
    geo_terms = stop.execute("SELECT term, risk_weight FROM geopolitical_terms").fetchall()
    
    security_words = {t[0]: t[1] for t in security_terms}
    geo_words = {t[0]: t[1] for t in geo_terms}
    all_important = {**security_words, **geo_words}
    
    # Get today's word counts
    word_counts = rss.execute(f"""
        SELECT word, SUM(count) as total
        FROM word_history
        WHERE date = '{today}'
        GROUP BY word
    """).fetchall()
    
    # Filter and score
    results = []
    for word, count in word_counts:
        if word in all_important:
            results.append({
                'word': word,
                'count': count,
                'score': all_important[word],
                'type': 'security' if word in security_words else 'geopolitical'
            })
    
    results.sort(key=lambda x: x['count'], reverse=True)
    
    print("\n" + "="*60)
    print("🔒 SECURITY INTELLIGENCE REPORT - " + datetime.now().strftime('%Y-%m-%d'))
    print("="*60)
    
    print("\n📊 Top Security/Geopolitical Terms Today:")
    print("-"*50)
    for r in results[:20]:
        emoji = "🔒" if r['type'] == 'security' else "🌍"
        print(f"{emoji} {r['word']:<20} {r['count']:>6} mentions")
    
    total = sum(r['count'] for r in results)
    security_total = sum(r['count'] for r in results if r['type'] == 'security')
    geo_total = sum(r['count'] for r in results if r['type'] == 'geopolitical')
    
    print(f"\n📊 Summary:")
    print(f"   Total Important Terms: {total}")
    print(f"   🔒 Security: {security_total}")
    print(f"   🌍 Geopolitical: {geo_total}")
    
    high_risk = [r for r in results if r['type'] == 'security' and r['score'] >= 0.7]
    if high_risk:
        print("\n⚠️ CRITICAL SECURITY TERMS (Risk Weight >= 0.7):")
        high_risk.sort(key=lambda x: x['score'], reverse=True)
        for r in high_risk:
            print(f"   🚨 {r['word']:<20} (Weight: {r['score']:.1f}) - {r['count']} mentions")
    
    cve_matches = [r for r in results if 'cve' in r['word'].lower() or 'vulnerability' in r['word'].lower()]
    if cve_matches:
        print(f"\n🛡️ Vulnerability-related terms:")
        for r in cve_matches:
            print(f"   {r['word']}: {r['count']} mentions")
    
    rss.close()
    stop.close()

if __name__ == "__main__":
    main()
