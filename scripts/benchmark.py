#!/usr/bin/env python3
"""Mesure la latence médiane des endpoints (API lancée sur BASE_URL).

Usage : python scripts/benchmark.py [http://localhost:8000] [N]
Le 1er appel de chaque endpoint (cache froid, requête réelle vers Wikidata)
est mesuré séparément des appels suivants (cache chaud).
"""
import statistics
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 20

ENDPOINTS = [
    "/health",
    "/compounds/search?q=caffeine",
    "/compounds/27732",
    "/compounds/27732/classes",
    "/compounds/27732/xrefs",
]


def timed(client, path):
    t0 = time.perf_counter()
    r = client.get(BASE + path)
    r.raise_for_status()
    return (time.perf_counter() - t0) * 1000


with httpx.Client(timeout=30) as c:
    cold, warm = [], []
    print(f"{'endpoint':35} {'froid (ms)':>11} {'médiane chaud (ms)':>20}")
    for path in ENDPOINTS:
        first = timed(c, path)
        runs = [timed(c, path) for _ in range(N)]
        cold.append(first)
        warm.extend(runs)
        print(f"{path:35} {first:11.0f} {statistics.median(runs):20.1f}")
    print(f"\nMédiane globale (cache chaud) : {statistics.median(warm):.1f} ms")
    print(f"Médiane globale (1er appel)   : {statistics.median(cold):.1f} ms")
