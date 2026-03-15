#!/usr/bin/env python3
import json
import math
import random
from glob import glob

TIRE_IDX = {"SOFT": 0, "MEDIUM": 1, "HARD": 2}
DRIVER_IDS = [f"D{i:03d}" for i in range(1, 21)]
DRIVER_IDX = {d: i for i, d in enumerate(DRIVER_IDS)}

# Feature layout:
# 0: pits * pit_lane_time
# For each tire t (0..2):
#   laps, age_sum, age2_sum, temp_laps, temp_age, temp_age2
BLOCK = 6
BASE_DIM = 1 + 3 * BLOCK
DIM = BASE_DIM + len(DRIVER_IDS)


def build_driver_features(race_config, strategy):
    temp = float(race_config["track_temp"])
    pit_lane = float(race_config["pit_lane_time"])
    total_laps = int(race_config["total_laps"])

    x = [0.0] * BASE_DIM
    pit_stops = sorted(strategy["pit_stops"], key=lambda p: p["lap"])
    pit_ix = 0
    tire = strategy["starting_tire"]
    age = 0

    for lap in range(1, total_laps + 1):
        age += 1
        t = TIRE_IDX[tire]
        b = 1 + t * BLOCK
        x[b] += 1.0
        x[b + 1] += age
        x[b + 2] += age * age
        x[b + 3] += temp
        x[b + 4] += temp * age
        x[b + 5] += temp * age * age

        if pit_ix < len(pit_stops) and pit_stops[pit_ix]["lap"] == lap:
            tire = pit_stops[pit_ix]["to_tire"]
            age = 0
            pit_ix += 1

    x[0] = len(pit_stops) * pit_lane
    return x


def race_features(race):
    out = {}
    for _, strategy in race["strategies"].items():
        out[strategy["driver_id"]] = build_driver_features(race["race_config"], strategy)
    return out


def score(features, driver_id, w):
    return dot(features, w[:BASE_DIM]) + w[BASE_DIM + DRIVER_IDX[driver_id]]


def dot(a, b):
    s = 0.0
    for i, v in enumerate(a):
        s += v * b[i]
    return s


def exact_match_accuracy(dataset, w, limit=None):
    ok = 0
    total = 0
    for i, (features, order) in enumerate(dataset):
        if limit is not None and i >= limit:
            break
        pred = sorted(order, key=lambda d: score(features[d], d, w))
        ok += int(pred == order)
        total += 1
    return ok, total, ok / total if total else 0.0


def build_dataset(races):
    return [(race_features(r), r["finishing_positions"]) for r in races]


def train_pairwise_logistic(train_data, valid_data, epochs=20, samples_per_race=90, base_lr=0.03):
    w = [0.0] * DIM
    w[0] = 1.0

    for epoch in range(epochs):
        random.shuffle(train_data)
        lr = base_lr * (0.9 ** epoch)

        for features, order in train_data:
            n = len(order)
            for _ in range(samples_per_race):
                i = random.randrange(0, n - 1)
                j = random.randrange(i + 1, n)
                fast = order[i]
                slow = order[j]

                x_fast = features[fast]
                x_slow = features[slow]

                # Want score(fast) < score(slow), i.e. w · (x_slow - x_fast) > 0.
                z = 0.0
                diffs = [0.0] * DIM
                for k in range(BASE_DIM):
                    d = x_slow[k] - x_fast[k]
                    diffs[k] = d
                    z += w[k] * d

                fast_b = BASE_DIM + DRIVER_IDX[fast]
                slow_b = BASE_DIM + DRIVER_IDX[slow]
                diffs[slow_b] = 1.0
                diffs[fast_b] = -1.0
                z += w[slow_b] - w[fast_b]

                # sigmoid(-z) in numerically stable form
                if z >= 0:
                    ez = math.exp(-z)
                    sigma = ez / (1.0 + ez)
                else:
                    sigma = 1.0 / (1.0 + math.exp(z))

                # Gradient descent on log(1 + exp(-z))
                for k in range(DIM):
                    w[k] += lr * sigma * diffs[k]

        ok, total, acc = exact_match_accuracy(valid_data, w, limit=800)
        print(f"epoch {epoch:02d}: valid@800 {ok}/{total} = {acc:.4f}")

    return w


def evaluate_public_tests(w):
    inputs = sorted(glob("data/test_cases/inputs/test_*.json"))
    expected = sorted(glob("data/test_cases/expected_outputs/test_*.json"))
    expected_map = {}
    for fp in expected:
        with open(fp, "r", encoding="utf-8") as f:
            obj = json.load(f)
        expected_map[obj["race_id"]] = obj["finishing_positions"]

    passed = 0
    total = 0
    for fp in inputs:
        with open(fp, "r", encoding="utf-8") as f:
            race = json.load(f)
        features = race_features(race)
        drivers = [race["strategies"][f"pos{i}"]["driver_id"] for i in range(1, 21)]
        pred = sorted(drivers, key=lambda d: score(features[d], d, w))

        exp = expected_map.get(race["race_id"])
        if exp is not None:
            total += 1
            passed += int(pred == exp)

    print(f"public tests: {passed}/{total} = {passed/total if total else 0.0:.4f}")


def main():
    random.seed(7)

    files = sorted(glob("data/historical_races/races_*.json"))
    races = []
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            races.extend(json.load(f))

    random.shuffle(races)
    train = races[:14000]
    valid = races[14000:17000]

    train_data = build_dataset(train)
    valid_data = build_dataset(valid)

    w = train_pairwise_logistic(train_data, valid_data)

    ok, total, acc = exact_match_accuracy(valid_data, w)
    print(f"valid full: {ok}/{total} = {acc:.4f}")
    print("weights =")
    print(json.dumps(w))

    evaluate_public_tests(w)


if __name__ == "__main__":
    main()
