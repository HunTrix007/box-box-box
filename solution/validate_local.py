#!/usr/bin/env python3
import json
import glob
import subprocess

PY = 'd:/sachi/Work/Personal/box-box-box/.venv/Scripts/python.exe'
CMD = [PY, 'solution/race_simulator.py']

inputs = sorted(glob.glob('data/test_cases/inputs/test_*.json'))
passed = 0
for fp in inputs:
    with open(fp, 'r', encoding='utf-8') as f:
        inp = f.read()
    proc = subprocess.run(CMD, input=inp, text=True, capture_output=True)
    if proc.returncode != 0:
        continue
    out = json.loads(proc.stdout)
    exp_fp = fp.replace('inputs', 'expected_outputs')
    with open(exp_fp, 'r', encoding='utf-8') as f:
        exp = json.load(f)
    if out.get('finishing_positions') == exp.get('finishing_positions'):
        passed += 1
print(f'{passed}/{len(inputs)}')
