import os
import sys

os.environ["NEX_DRY_RUN"] = "1"  # never press real keys during tests
os.environ["NEX_DB"] = ":memory:"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
