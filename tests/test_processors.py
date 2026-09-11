"""Offline unit tests for the pure processing functions.

No network, no external DB — these import main.py and exercise the stateless
analyzers. They also lock in the sentiment-lexicon scale fix.
"""
import main


class TestSentimentLexiconScale:
    def test_zero_one_positivity_lexicon_is_remapped(self):
        # A [0, 1] "positivity" lexicon: threat low, remediation high.
        lex = {"breach": 0.2, "update": 0.5, "patched": 0.8}
        out = main.SentimentAnalyzer._normalize_lexicon(lex)
        assert out["breach"] < 0.0        # threat -> negative polarity
        assert abs(out["update"]) < 1e-9  # midpoint -> neutral
        assert out["patched"] > 0.0       # remediation -> positive polarity

    def test_signed_lexicon_passes_through(self):
        lex = {"breach": -0.7, "patched": 0.4}
        out = main.SentimentAnalyzer._normalize_lexicon(lex)
        assert out == lex

    def test_empty_lexicon(self):
        assert main.SentimentAnalyzer._normalize_lexicon({}) == {}

    def test_threat_text_scores_negative(self):
        sa = main.SentimentAnalyzer()
        res = sa.analyze("A critical data breach exposed millions of records "
                         "in a ransomware attack on the network.")
        assert res["score"] < 0.0
        assert res["label"] in ("negative", "very_negative")


class TestKeywordExtractor:
    def test_strips_html(self):
        clean = main.KeywordExtractor._strip_html("<p>hello <b>world</b></p>")
        assert "<" not in clean and "world" in clean

    def test_extract_filters_stopwords_and_short_words(self):
        kx = main.KeywordExtractor()
        kws = kx.extract("The ransomware campaign targeted the healthcare "
                         "network with a sophisticated phishing attack.")
        assert isinstance(kws, list)
        assert all(len(w) > 3 for w in kws)
        # 'the' / 'with' are stopwords and must not appear
        assert "the" not in kws and "with" not in kws

    def test_extract_short_text_returns_empty(self):
        assert main.KeywordExtractor().extract("too short") == []


class TestTopicDetector:
    def test_detects_known_topic(self):
        td = main.TopicDetector()
        topics = td.detect("a new ransomware variant was found", [])
        assert "ransomware" in topics

    def test_no_topic_for_unrelated_text(self):
        td = main.TopicDetector()
        assert td.detect("the weather is sunny today", []) == []


class TestRiskScorer:
    def test_score_is_bounded(self):
        rs = main.RiskScorer()
        s = rs.score("Government", ["breach"],
                     "critical zero-day exploit and ransomware breach")
        assert 0.0 <= s <= 1.0

    def test_higher_priority_category_scores_higher(self):
        rs = main.RiskScorer()
        text = "a routine software update"
        assert rs.score("Government", [], text) >= rs.score("Programming", [], text)
