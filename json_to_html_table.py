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

        raw_data = args.get("json_data", "")
        # raw_data may be a Python list (isArray:true) or a JSON string
        data_raw = json.loads(raw_data) if isinstance(raw_data, str) else raw_data

        rows = normalize_to_list(data_raw)
        if not rows:
            return_error("Input resolved to an empty list")

        all_keys = collect_headers(rows)

        headers_arg = args.get("headers", "").strip()
        if headers_arg:
            # Keep only headers that actually exist in the data, in the order specified
            requested = [h.strip() for h in headers_arg.split(",") if h.strip()]
            headers = [h for h in requested if h in all_keys]
            if not headers:
                return_error("None of the specified headers match keys in the data")
        else:
            headers = all_keys

        output_key = args.get("output_key", "JsonToHtmlTable").strip()

        html_table = build_html_table(rows, headers=headers)

        return_results(CommandResults(
            outputs_prefix=output_key,
            outputs_key_field="",
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


    except json.JSONDecodeError as e:
        return_error(f"Failed to parse json_data: {e}")
    except Exception as e:
        return_error(f"Unexpected error in JsonToHtmlTable: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
