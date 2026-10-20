"""Deterministic synthetic capacity fixture; run with backend/.venv/bin/python."""
import argparse
import csv
import random
from pathlib import Path


def generate(path: Path, count: int, seed: int) -> None:
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['id', *[f'attribute_{i:02}' for i in range(1, 30)]])
        for number in range(count):
            writer.writerow([f'{number:08}', *[
                f'{i:02}_{rng.randrange(1_000_000):06}' for i in range(1, 30)
            ]])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    parser.add_argument('--count', type=int, choices=[100, 1000, 10000, 100000], default=100)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    generate(args.path, args.count, args.seed)
