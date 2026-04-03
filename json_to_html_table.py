import json
import demistomock as demisto
from CommonServerPython import *


def normalize_to_list(data) -> list:
    """Accept a JSON list or a dict with numeric string keys (e.g. {"0": {...}, "1": {...}})."""
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


def build_html_table(rows: list, headers: list = None) -> str:
    """Generate a styled HTML table from a list of dicts for use as email htmlBody."""
    if headers is None:
        headers = collect_headers(rows)

    th = "padding:6px 12px;border:1px solid #ddd;background:#f2f2f2;text-align:left;white-space:nowrap;"
    td = "padding:6px 12px;border:1px solid #ddd;word-break:break-all;"

    header_cells = "".join(f"<th style='{th}'>{h}</th>" for h in headers)
    body_rows = ""
    for i, row in enumerate(rows):
        bg = "#ffffff" if i % 2 == 0 else "#f9f9f9"
        cells = "".join(
            f"<td style='{td}'>{row.get(h) if row.get(h) is not None else ''}</td>"
            for h in headers
        )
        body_rows += f"<tr style='background:{bg};'>{cells}</tr>"

    return (
        "<table style='border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px;'>"
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{body_rows}</tbody>"
        "</table>"
    )


def main():
    try:
        args = demisto.args()

        # --- required: the JSON data to render ---
        raw_data = args.get("json_data", "[]")
        data_raw = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        rows = normalize_to_list(data_raw)

        if not isinstance(rows, list):
            return_error("json_data must be a JSON array or a numeric-keyed object")

        if not rows:
            return_error("json_data resolved to an empty list")

        # --- optional: comma-separated list of columns to include ---
        headers_arg = args.get("headers", "").strip()
        headers = [h.strip() for h in headers_arg.split(",") if h.strip()] if headers_arg else collect_headers(rows)

        html_table = build_html_table(rows, headers=headers)

        demisto.setContext("JsonToHtmlTable", html_table)

        demisto.results({
            "Type": entryTypes["note"],
            "ContentsFormat": formats["json"],
            "Contents": rows,
            "HumanReadable": tableToMarkdown(
                "JSON to HTML Table",
                rows,
                headers=headers,
                removeNull=False,
            ),
            "EntryContext": {
                "JsonToHtmlTable": html_table,
            },
        })

    except json.JSONDecodeError as e:
        return_error(f"Failed to parse json_data: {e}")
    except Exception as e:
        return_error(f"Unexpected error in JsonToHtmlTable: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
