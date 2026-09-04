#!/bin/bash
# One command: Run pipeline + show security report

echo "🚀 Running RSS Intelligence Pipeline..."
~/ai_env/bin/python ~/.rss-intel-pipeline/main.py

echo ""
echo "🔒 Security Intelligence Report:"
~/ai_env/bin/python ~/.rss-intel-pipeline/report.py
