"""python -m frontend [--url http://127.0.0.1:8765 --token SECRET]  (omit both to embed the backend)"""
import argparse
import sys

from .app import run

ap = argparse.ArgumentParser(description="HideIt frontend")
ap.add_argument("--url")
ap.add_argument("--token", default="")
a = ap.parse_args()
sys.exit(run(a.url, a.token))
