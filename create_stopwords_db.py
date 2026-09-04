#!/usr/bin/env python3
"""
Create Static Stopwords Database with Geopolitical Terms and Security Lexicon
Run this once to initialize the database
"""

import json
import duckdb
from pathlib import Path

# ============================================
# STOPWORDS CATEGORIZED (DEDUPLICATED)
# ============================================

STOPWORDS_SETS = {
    'common': {
        'a', 'an', 'the', 'of', 'to', 'for', 'with', 'on', 'at', 'from',
        'by', 'in', 'as', 'into', 'through', 'during', 'including', 'without',
        'against', 'between', 'among', 'upon', 'about', 'after', 'before',
        'under', 'over', 'within', 'above', 'below', 'near', 'along', 'across'
    },
    'grammar': {
        'and', 'or', 'but', 'nor', 'so', 'yet', 'because', 'since',
        'although', 'though', 'while', 'whereas', 'unless', 'until', 'once',
        'where', 'when', 'why', 'how', 'whether', 'whenever', 'wherever'
    },
    'pronouns': {
        'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her',
        'us', 'them', 'my', 'your', 'his', 'our', 'their', 'mine',
        'yours', 'hers', 'ours', 'theirs', 'its', 'myself', 'yourself',
        'himself', 'herself', 'itself', 'ourselves', 'themselves'
    },
    'determiners': {
        'this', 'that', 'these', 'those', 'some', 'any', 'no', 'every',
        'each', 'either', 'neither', 'much', 'many', 'more', 'most', 'less',
        'least', 'few', 'several', 'enough', 'plenty', 'lots', 'all', 'both'
    },
    'adverbs': {
        'very', 'really', 'actually', 'quite', 'rather', 'somewhat',
        'extremely', 'highly', 'totally', 'completely', 'absolutely',
        'just', 'only', 'simply', 'merely', 'hardly', 'barely', 'scarcely',
        'almost', 'nearly', 'always', 'never', 'ever', 'often', 'usually',
        'sometimes', 'occasionally', 'frequently', 'rarely', 'seldom'
    },
    'modals': {
        'can', 'could', 'will', 'would', 'should', 'may', 'might', 'must',
        'shall', 'need', 'dare', 'ought', 'used', 'had', 'has', 'have',
        'do', 'does', 'did', 'done', 'was', 'were', 'am', 'is', 'are', 'be',
        'been', 'being'
    },
    'prepositions': {
        'over', 'under', 'above', 'below', 'across', 'along', 'around',
        'behind', 'beside', 'between', 'beyond', 'into', 'onto', 'out',
        'outside', 'through', 'throughout', 'toward', 'upon', 'within'
    },
    'conjunctions': {
        'whenever', 'wherever', 'whichever', 'however', 'therefore',
        'hence', 'consequently', 'accordingly', 'nevertheless',
        'nonetheless', 'likewise', 'meanwhile', 'otherwise'
    },
    'question': {
        'what', 'when', 'where', 'why', 'how', 'which', 'who', 'whom',
        'whose', 'whatever', 'whenever', 'wherever', 'whichever'
    },
    'ordinals': {
        'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh',
        'eighth', 'ninth', 'tenth', 'last', 'next', 'previous', 'former',
        'latter', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
        'eight', 'nine', 'ten', 'twenty', 'thirty', 'forty', 'fifty'
    },
    'adjectives': {
        'good', 'bad', 'new', 'old', 'big', 'small', 'large', 'great',
        'important', 'significant', 'major', 'minor', 'main', 'primary',
        'secondary', 'key', 'critical', 'essential', 'necessary', 'basic',
        'advanced', 'current', 'future', 'past', 'recent', 'latest'
    }
}

# ============================================
# SECURITY CONTEXT WORDS TO KEEP
# ============================================

SECURITY_WORDS = {
    'threats': {
        'ransomware': 0.8, 'malware': 0.7, 'virus': 0.6, 'trojan': 0.7,
        'worm': 0.5, 'spyware': 0.6, 'adware': 0.4, 'rootkit': 0.7,
        'backdoor': 0.7, 'botnet': 0.6, 'phishing': 0.7, 'spearphishing': 0.8,
        'spam': 0.3, 'scam': 0.4, 'fraud': 0.5, 'exploit': 0.8,
        'zero-day': 0.9, 'vulnerability': 0.8, 'breach': 0.8, 'leak': 0.6,
        'compromise': 0.7, 'incident': 0.6, 'attack': 0.7, 'intrusion': 0.7,
        'infiltration': 0.6, 'exfiltration': 0.7, 'hijack': 0.6,
        'ddos': 0.7, 'dos': 0.6, 'brute-force': 0.6, 'credential-stuffing': 0.7
    },
    'controls': {
        'patch': 0.6, 'update': 0.4, 'fix': 0.5, 'mitigation': 0.6,
        'remediation': 0.6, 'response': 0.5, 'recovery': 0.4,
        'backup': 0.5, 'encryption': 0.6, 'authentication': 0.6,
        'authorization': 0.5, 'access': 0.4, 'permission': 0.4,
        'firewall': 0.5, 'ips': 0.6, 'ids': 0.6, 'siem': 0.7,
        'soar': 0.6, 'edr': 0.7, 'xdr': 0.7, 'mdr': 0.6,
        'vpn': 0.5, 'zero-trust': 0.7, 'mfa': 0.7, '2fa': 0.6
    },
    'compliance': {
        'compliance': 0.6, 'regulation': 0.6, 'standard': 0.5,
        'gdpr': 0.7, 'ccpa': 0.6, 'hipaa': 0.7, 'sox': 0.6,
        'pci': 0.7, 'dss': 0.6, 'iso': 0.5, 'nist': 0.7,
        'cmmc': 0.6, 'fedramp': 0.6, 'audit': 0.5, 'policy': 0.4,
        'bafin': 0.7, 'bsi': 0.7, 'bfdi': 0.7, 'eudp': 0.6
    },
    'infrastructure': {
        'cloud': 0.4, 'aws': 0.5, 'azure': 0.5, 'gcp': 0.5,
        'kubernetes': 0.5, 'docker': 0.4, 'container': 0.4,
        'server': 0.3, 'network': 0.3, 'firewall': 0.5,
        'router': 0.3, 'switch': 0.3, 'gateway': 0.4,
        'api': 0.4, 'microservice': 0.4, 'orchestration': 0.4
    },
    'actors': {
        'hacker': 0.6, 'cracker': 0.5, 'attacker': 0.7, 'adversary': 0.7,
        'apt': 0.8, 'nation-state': 0.8, 'cybercriminal': 0.7,
        'insider': 0.6, 'malicious': 0.6, 'threat': 0.7,
        'lockbit': 0.9, 'conti': 0.9, 'dark-side': 0.8, 'revil': 0.8,
        'apt28': 0.9, 'apt29': 0.9, 'sandworm': 0.8, 'fancy-bear': 0.8
    }
}

# ============================================
# GEOPOLITICAL TERMS
# ============================================

GEOPOLITICAL_TERMS = {
    'countries': {
        'united-states': 0.8, 'usa': 0.8, 'us': 0.7, 'america': 0.6,
        'china': 0.8, 'russia': 0.9, 'ukraine': 0.7, 'united-kingdom': 0.7,
        'uk': 0.7, 'germany': 0.7, 'france': 0.6, 'japan': 0.6,
        'south-korea': 0.6, 'north-korea': 0.8, 'iran': 0.8,
        'israel': 0.7, 'saudi-arabia': 0.6, 'india': 0.5,
        'brazil': 0.5, 'australia': 0.5, 'canada': 0.5,
        'turkey': 0.6, 'taiwan': 0.7, 'hong-kong': 0.6,
        'singapore': 0.5, 'netherlands': 0.5, 'switzerland': 0.5
    },
    'regions': {
        'european-union': 0.8, 'eu': 0.8, 'europe': 0.6,
        'asia-pacific': 0.7, 'apac': 0.7, 'middle-east': 0.7,
        'latin-america': 0.6, 'north-america': 0.6,
        'south-america': 0.5, 'africa': 0.5, 'southeast-asia': 0.6,
        'caspian': 0.6, 'baltic': 0.6, 'scandinavia': 0.5
    },
    'organizations': {
        'nato': 0.8, 'un': 0.7, 'united-nations': 0.7,
        'wto': 0.6, 'imf': 0.6, 'world-bank': 0.6,
        'oecd': 0.6, 'g7': 0.7, 'g20': 0.7, 'brics': 0.7,
        'apec': 0.6, 'asean': 0.6, 'csto': 0.7, 'shanghai-cooperation': 0.7
    },
    'sanctions': {
        'sanctions': 0.8, 'embargo': 0.7, 'export-control': 0.7,
        'trade-restriction': 0.7, 'tariff': 0.5, 'blockade': 0.6,
        'cyber-sanctions': 0.8, 'asset-freeze': 0.7, 'travel-ban': 0.6
    },
    'conflicts': {
        'war': 0.8, 'conflict': 0.7, 'tension': 0.6, 'dispute': 0.6,
        'invasion': 0.9, 'annexation': 0.8, 'occupation': 0.7,
        'cyber-war': 0.9, 'cyber-conflict': 0.8, 'hybrid-war': 0.8,
        'proxy-war': 0.7, 'cold-war': 0.6, 'escalation': 0.7
    },
    'energy': {
        'oil': 0.6, 'gas': 0.6, 'pipeline': 0.6, 'energy': 0.5,
        'nord-stream': 0.8, 'opec': 0.7, 'energy-security': 0.7,
        'rare-earth': 0.7, 'critical-minerals': 0.7, 'supply-chain': 0.7
    },
    'cyber_geopolitics': {
        'cyber-sovereignty': 0.8, 'data-sovereignty': 0.8,
        'digital-sovereignty': 0.7, 'internet-governance': 0.7,
        'cyber-diplomacy': 0.7, 'cyber-treaty': 0.7,
        'cyber-espionage': 0.8, 'state-sponsored': 0.8,
        'foreign-interference': 0.7, 'election-security': 0.7
    },
    'german_european': {
        'bundestag': 0.7, 'bundesrat': 0.7, 'bmi': 0.7,
        'auswaertiges-amt': 0.7, 'europaeische-union': 0.7,
        'berlin': 0.6, 'brussels': 0.6, 'frankfurt': 0.5,
        'eurozone': 0.6, 'europaeische-zentralbank': 0.7,
        'germany': 0.7, 'deutschland': 0.7, 'bundesregierung': 0.7
    }
}

def create_stopwords_db():
    db_path = Path.home() / ".rss-intel-pipeline" / "stopwords.duckdb"
    if db_path.exists():
        db_path.unlink()
    
    conn = duckdb.connect(str(db_path))
    print("🌍 Creating stopwords database with Geopolitical Terms...")
    
    # Create tables
    conn.execute("""
        CREATE TABLE stopwords (
            id INTEGER PRIMARY KEY,
            word VARCHAR UNIQUE,
            category VARCHAR,
            priority INTEGER,
            notes TEXT
        )
    """)
    
    conn.execute("""
        CREATE TABLE security_terms (
            id INTEGER PRIMARY KEY,
            term VARCHAR UNIQUE,
            category VARCHAR,
            risk_weight FLOAT,
            notes TEXT
        )
    """)
    
    conn.execute("""
        CREATE TABLE geopolitical_terms (
            id INTEGER PRIMARY KEY,
            term VARCHAR UNIQUE,
            category VARCHAR,
            risk_weight FLOAT,
            region VARCHAR,
            notes TEXT
        )
    """)
    
    # Insert stopwords
    print("📝 Inserting stopwords...")
    id_counter = 0
    for category, words in STOPWORDS_SETS.items():
        for word in words:
            id_counter += 1
            priority = 1 if category in ['common', 'grammar'] else 2
            conn.execute("""
                INSERT OR IGNORE INTO stopwords (id, word, category, priority, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (id_counter, word, category, priority, f'Category: {category}'))
    
    # Insert security terms
    print("🔒 Inserting security terms...")
    id_counter = 0
    for category, terms in SECURITY_WORDS.items():
        for term, weight in terms.items():
            id_counter += 1
            conn.execute("""
                INSERT OR IGNORE INTO security_terms (id, term, category, risk_weight, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (id_counter, term, category, weight, f'Category: {category}'))
    
    # Insert geopolitical terms
    print("🌍 Inserting geopolitical terms...")
    id_counter = 0
    for category, terms in GEOPOLITICAL_TERMS.items():
        for term, weight in terms.items():
            id_counter += 1
            region = 'global'
            if category in ['countries', 'regions']:
                region = term
            elif category == 'german_european':
                region = 'europe'
            elif category == 'organizations':
                region = 'international'
            
            conn.execute("""
                INSERT OR IGNORE INTO geopolitical_terms (id, term, category, risk_weight, region, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (id_counter, term, category, weight, region, f'Category: {category}'))
    
    # Create indices
    conn.execute("CREATE INDEX idx_stopwords_word ON stopwords(word)")
    conn.execute("CREATE INDEX idx_security_term ON security_terms(term)")
    conn.execute("CREATE INDEX idx_geo_term ON geopolitical_terms(term)")
    conn.execute("CREATE INDEX idx_geo_region ON geopolitical_terms(region)")
    
    # Verify counts
    stopword_count = conn.execute("SELECT COUNT(*) FROM stopwords").fetchone()[0]
    security_count = conn.execute("SELECT COUNT(*) FROM security_terms").fetchone()[0]
    geo_count = conn.execute("SELECT COUNT(*) FROM geopolitical_terms").fetchone()[0]
    
    print(f"\n✅ Database Created Successfully!")
    print(f"   📊 Stopwords: {stopword_count}")
    print(f"   🔒 Security Terms: {security_count}")
    print(f"   🌍 Geopolitical Terms: {geo_count}")
    print(f"   📁 Database: {db_path}")
    
    # Save as JSON
    json_path = Path.home() / ".rss-intel-pipeline" / "data" / "stopwords.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, 'w') as f:
        json.dump({
            'stopwords': {k: list(v) for k, v in STOPWORDS_SETS.items()},
            'security_terms': SECURITY_WORDS,
            'geopolitical_terms': GEOPOLITICAL_TERMS
        }, f, indent=2)
    print(f"\n📄 Stopwords also saved to: {json_path}")
    conn.close()

if __name__ == "__main__":
    create_stopwords_db()
