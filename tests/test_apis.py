#!/usr/bin/env python3
"""Quick test of all three search APIs."""

import sys
from pathlib import Path

# Ensure clean environment
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

print("Starting API tests...")

from src.tools.search import patent_keyword_search

print('='*60)
print('TESTING PATENT SEARCH (Innography)')
print('='*60)

result = patent_keyword_search.invoke({
    'query': '@(dwpi_title) (worm NEAR/5 gear)',
    'feature_id': 'F1',
    'max_results': 2
})
print(result[:600])

print()
print("✅ Patent search test completed!")
