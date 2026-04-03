import json
import demistomock as demisto
from CommonServerPython import *


def normalize_to_list(data) -> list:
    """Accept a JSON list, a single-row dict, or a numeric-keyed container dict."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if data and all(k.isdigit() for k in data.keys()):
            return [data[k] for k in sorted(data.keys(), key=lambda x: int(x))]
        return [data]
    return []


def collect_headers(rows: list) -> list:
    """Return all keys found across every row, preserving first-seen order."""
    seen: dict = {}
    for row in rows:
        if isinstance(row, dict):
            for k in row.keys():
                seen[k] = None
    return list(seen.keys())


def get_nested(obj, path: str):
    """Navigate incident context by dot-separated key path.

    e.g. get_nested(ctx, "subplaybook-1.api_query_result.requestresult")
    """
    for key in path.split('.'):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
        if obj is None:
            return None
    return obj


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

        # ------------------------------------------------------------------
        # Two ways to supply data:
        #
        # 1. context_path (recommended)
        #    Pass the dot-separated path to the list inside incident context,
        #    e.g. "subplaybook-1.api_query_result.requestresult".
        #    The script reads the full list directly from demisto.context(),
        #    bypassing XSOAR's default behaviour of calling the script once
        #    per item when a list is passed as an argument.
        #
        # 2. json_data
        #    Pass the data as a JSON string (the entire array serialised).
        #    Works correctly only when the caller explicitly serialises the
        #    list to a string before passing it (e.g. via a JsonDumps
        #    transformer in the playbook task).
        # ------------------------------------------------------------------

        context_path = args.get("context_path", "").strip()
        raw_data = args.get("json_data", "")

        if context_path:
            ctx = demisto.context()
            data_raw = get_nested(ctx, context_path)
            if data_raw is None:
                return_error(f"context_path '{context_path}' not found in incident context")
        elif raw_data:
            # raw_data may be a list (when isArray:true) or a JSON string
            data_raw = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        else:
            return_error("Provide either context_path or json_data")

        rows = normalize_to_list(data_raw)
        if not rows:
            return_error("Input resolved to an empty list")

        headers_arg = args.get("headers", "").strip()
        headers = [h.strip() for h in headers_arg.split(",") if h.strip()] if headers_arg else collect_headers(rows)

        output_key = args.get("output_key", "JsonToHtmlTable").strip()

        html_table = build_html_table(rows, headers=headers)

        return_results(CommandResults(
            outputs_prefix=output_key,
            outputs_key_field=output_key,
            outputs=html_table,
            readable_output=tableToMarkdown(
                "JSON to HTML Table",
                rows,
                headers=headers,
                removeNull=False,
            ),
        ))

    except json.JSONDecodeError as e:
        return_error(f"Failed to parse json_data: {e}")
    except Exception as e:
        return_error(f"Unexpected error in JsonToHtmlTable: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
