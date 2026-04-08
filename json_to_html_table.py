import ast
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


def coerce_value(value):
    """If value is a string that looks like a serialised dict/list, try to parse it.

    XSOAR sometimes hands nested context values as Python repr strings
    (e.g. "{'CrlSign': False, 'DigitalSignature': True}") instead of real dicts.
    Try JSON first, then ast.literal_eval as a fallback for Python repr.
    """
    if not isinstance(value, str):
        return value
    s = value.strip()
    if not (s.startswith("{") or s.startswith("[")):
        return value
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        pass
    try:
        return ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return value


def flatten_row(row, prefix=""):
    """Recursively flatten a nested dict into dot-notation keys.

    {"metadata": {"requester": {"firstname": "John"}}}
    -> {"metadata.requester.firstname": "John"}
    """
    flat = {}
    for key, value in row.items():
        full_key = "{}.{}".format(prefix, key) if prefix else key
        value = coerce_value(value)
        if isinstance(value, dict):
            flat.update(flatten_row(value, full_key))
        elif isinstance(value, list):
            # If every element is a dict, flatten with numeric index keys
            # e.g. ExtendedKeyUsages -> ExtendedKeyUsages.0.DisplayName, ExtendedKeyUsages.1.DisplayName
            coerced = [coerce_value(item) for item in value]
            if coerced and all(isinstance(item, dict) for item in coerced):
                for idx, item in enumerate(coerced):
                    flat.update(flatten_row(item, "{}.{}".format(full_key, idx)))
            else:
                flat[full_key] = json.dumps(value)
        else:
            flat[full_key] = value
    return flat


def safe_str(value):
    """Render a cell value as a string.
    Dicts and lists are serialised as JSON rather than Python repr.
    """
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if value is None:
        return ""
    return str(value)


def collect_headers(rows) -> list:
    """Return all keys found across every row, preserving first-seen order."""
    seen = {}
    for row in rows:
        if isinstance(row, dict):
            for k in row.keys():
                seen[k] = None
    return list(seen.keys())


def build_horizontal_table(rows, headers) -> str:
    """Horizontal table: headers as columns, each item as a row."""
    th = "padding:6px 12px;border:1px solid #ddd;background:#f2f2f2;text-align:left;white-space:nowrap;"
    td = "padding:6px 12px;border:1px solid #ddd;word-break:break-all;"

    header_cells = "".join("<th style='{}'>{}</th>".format(th, h) for h in headers)
    body_rows = ""
    for i, row in enumerate(rows):
        bg = "#ffffff" if i % 2 == 0 else "#f9f9f9"
        cells = "".join(
            "<td style='{}'>{}</td>".format(td, safe_str(row.get(h)))
            for h in headers
        )
        body_rows += "<tr style='background:{};'>{}</tr>".format(bg, cells)

    return (
        "<table style='border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px;'>"
        "<thead><tr>{}</tr></thead>"
        "<tbody>{}</tbody>"
        "</table>"
    ).format(header_cells, body_rows)


def build_vertical_table(rows, headers) -> str:
    """Vertical table: headers as rows on the left, each item as a column."""
    th = "padding:6px 12px;border:1px solid #ddd;background:#f2f2f2;text-align:left;white-space:nowrap;"
    td = "padding:6px 12px;border:1px solid #ddd;word-break:break-all;"

    col_headers = "<th style='{}'>Field</th>".format(th)
    for i in range(len(rows)):
        col_headers += "<th style='{}'>Item {}</th>".format(th, i)

    body_rows = ""
    for i, key in enumerate(headers):
        bg = "#ffffff" if i % 2 == 0 else "#f9f9f9"
        key_cell = "<td style='{}'><strong>{}</strong></td>".format(th, key)
        value_cells = "".join(
            "<td style='{}'>{}</td>".format(td, safe_str(row.get(key)))
            for row in rows
        )
        body_rows += "<tr style='background:{};'>{}{}</tr>".format(bg, key_cell, value_cells)

    return (
        "<table style='border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px;'>"
        "<thead><tr>{}</tr></thead>"
        "<tbody>{}</tbody>"
        "</table>"
    ).format(col_headers, body_rows)


def main():
    try:
        args = demisto.args()

        raw_array = args.get("json_data_array")  # isArray:true in XSOAR settings
        raw_item  = args.get("json_data_item")   # isArray:false in XSOAR settings

        if raw_array:
            data_raw = json.loads(raw_array) if isinstance(raw_array, str) else raw_array
        elif raw_item:
            data_raw = json.loads(raw_item) if isinstance(raw_item, str) else raw_item
        else:
            return_error("Provide either json_data_array or json_data_item")

        rows = normalize_to_list(data_raw)
        if not rows:
            return_error("Input resolved to an empty list")

        # flatten: handle both Python bool True and string "true"/"1"/"yes" from XSOAR
        flatten_arg = args.get("flatten") or ""
        do_flatten = flatten_arg is True or str(flatten_arg).strip().lower() in ("true", "1", "yes")

        print("JsonToHtmlTable: flatten_arg={!r} do_flatten={}".format(flatten_arg, do_flatten))

        if do_flatten:
            rows = [flatten_row(r) if isinstance(r, dict) else r for r in rows]
            print("JsonToHtmlTable: after flatten, sample keys={}".format(
                list(rows[0].keys())[:20] if rows and isinstance(rows[0], dict) else []))

        all_keys = collect_headers(rows)

        headers_arg = args.get("headers") or ""
        if headers_arg:
            requested = [h.strip() for h in headers_arg.split(",") if h.strip()]
            headers = []
            for k in all_keys:
                if k in requested:
                    headers.append(k)
                # When flatten is active, also include sub-keys of any requested parent key
                # e.g. "DetailedKeyUsage" in requested → include "DetailedKeyUsage.CrlSign"
                elif do_flatten and any(k.startswith(req + ".") for req in requested):
                    headers.append(k)
            if not headers:
                return_error("None of the specified headers match keys in the data")
        else:
            headers = all_keys

        layout = (args.get("layout") or "horizontal").strip().lower()
        output_key = args.get("output_key") or "result"

        if layout == "vertical":
            html_table = build_vertical_table(rows, headers)
        else:
            html_table = build_horizontal_table(rows, headers)

        return_results(CommandResults(
            outputs_prefix="JsonToHTMLTable",
            outputs_key_field=output_key,
            outputs=html_table,
            readable_output=tableToMarkdown(
                "JSON to HTML Table",
                rows,
                headers=headers,
                removeNull=False,
            ),
        ))

    except ValueError as e:
        return_error("Failed to parse json_data: {}".format(e))
    except Exception as e:
        return_error("Unexpected error in JsonToHtmlTable: {}".format(e))


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
