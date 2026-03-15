#!/usr/bin/env python3
import collections
import glob
import json

pos = collections.defaultdict(list)

for fp in sorted(glob.glob('data/historical_races/*.json')):
    with open(fp, 'r', encoding='utf-8') as f:
        races = json.load(f)
    for race in races:
        for place, driver in enumerate(race['finishing_positions'], 1):
            pos[driver].append(place)

for driver in sorted(pos):
    avg = sum(pos[driver]) / len(pos[driver])
    print(driver, round(avg, 4))
