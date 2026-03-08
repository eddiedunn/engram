"""Container health check script for Engram service."""
import sys
import urllib.request

try:
    urllib.request.urlopen("http://localhost:8800/health")
    sys.exit(0)
except Exception:
    sys.exit(1)
