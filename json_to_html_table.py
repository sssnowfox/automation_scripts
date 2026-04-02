#!/usr/bin/env python3
"""
json_to_html_table.py
---------------------
Convert a JSON array (or numeric-keyed object) to a styled HTML table.

Usage:
    # from a file
    python json_to_html_table.py input.json

    # from stdin
    cat input.json | python json_to_html_table.py

    # write output to a file
    python json_to_html_table.py input.json -o output.html

    # specify which columns to include (and their order)
    python json_to_html_table.py input.json --headers Timestamp User Operation
"""

import argparse
import json
import sys


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def normalize_to_list(data) -> list:
    """Accept a JSON list or a dict with numeric string keys."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data[k] for k in sorted(data.keys(), key=lambda x: int(x) if x.isdigit() else x)]
    return []


def collect_headers(rows: list) -> list:
    """Return all keys found across every row, preserving first-seen order."""
    seen: dict = {}
    for row in rows:
        if isinstance(row, dict):
            for k in row.keys():
                seen[k] = None
    return list(seen.keys())


# ---------------------------------------------------------------------------
# core renderer
# ---------------------------------------------------------------------------

def build_html_table(rows: list, headers: list | None = None) -> str:
    """Generate a styled HTML table from a list of dicts.

    Args:
        rows:    List of dicts (one per table row).
        headers: Column names to include, in order.  If None, all keys found
                 across all rows are used.

    Returns:
        A self-contained HTML string containing the <table>.
    """
    if headers is None:
        headers = collect_headers(rows)

    th_style = (
        "padding:6px 12px;border:1px solid #ddd;"
        "background:#f2f2f2;text-align:left;white-space:nowrap;"
    )
    td_style = "padding:6px 12px;border:1px solid #ddd;word-break:break-all;"

    header_cells = "".join(f"<th style='{th_style}'>{h}</th>" for h in headers)

    body_rows = ""
    for i, row in enumerate(rows):
        bg = "#ffffff" if i % 2 == 0 else "#f9f9f9"
        cells = "".join(
            f"<td style='{td_style}'>{row.get(h) if row.get(h) is not None else ''}</td>"
            for h in headers
        )
        body_rows += f"<tr style='background:{bg};'>{cells}</tr>"

    return (
        "<table style='border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px;'>"
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{body_rows}</tbody>"
        "</table>"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert a JSON array to a styled HTML table."
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to JSON file.  Reads from stdin if omitted.",
    )
    parser.add_argument(
        "-o", "--output",
        help="Write HTML to this file instead of stdout.",
    )
    parser.add_argument(
        "--headers",
        nargs="+",
        metavar="COLUMN",
        help="Columns to include (and their order).  Defaults to all keys.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    # --- read input ---
    try:
        if args.input:
            with open(args.input, encoding="utf-8") as fh:
                raw = fh.read()
        else:
            raw = sys.stdin.read()
    except OSError as exc:
        sys.exit(f"ERROR reading input: {exc}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"ERROR parsing JSON: {exc}")

    rows = normalize_to_list(data)
    if not rows:
        sys.exit("ERROR: JSON resolved to an empty list.")

    # validate every item is a dict
    if not all(isinstance(r, dict) for r in rows):
        sys.exit("ERROR: every element in the JSON array must be an object (dict).")

    html = build_html_table(rows, headers=args.headers)

    # --- write output ---
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(html)
            print(f"Wrote HTML table to {args.output}", file=sys.stderr)
        except OSError as exc:
            sys.exit(f"ERROR writing output: {exc}")
    else:
        print(html)


if __name__ == "__main__":
    main()
