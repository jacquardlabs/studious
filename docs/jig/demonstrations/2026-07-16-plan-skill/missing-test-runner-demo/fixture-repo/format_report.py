"""Fixture only -- see CLAUDE.md. Formats a CSV file into a Markdown table."""

from __future__ import annotations

import csv
import sys


def format_csv_as_markdown(path: str) -> str:
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return ""
    header, *body = rows
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
        *("| " + " | ".join(row) + " |" for row in body),
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_csv_as_markdown(sys.argv[1]))
