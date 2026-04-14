import ast
import json
import demistomock as demisto
from CommonServerPython import *


def coerce_to_dict(item):
    """If item is a string that looks like a serialised dict, parse it.

    XSOAR sometimes passes context list items as Python repr strings
    e.g. "{'id': '123', ...}" instead of actual dicts.
    """
    if isinstance(item, dict):
        return item
    if isinstance(item, str):
        s = item.strip()
        if s.startswith("{"):
            try:
                return json.loads(s)
            except (ValueError, TypeError):
                pass
            try:
                return ast.literal_eval(s)
            except (ValueError, SyntaxError):
                pass
    return {}


def normalize_to_list(data) -> list:
    """Accept a JSON list, a single-row dict, or a numeric-keyed container dict."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if data and all(k.isdigit() for k in data.keys()):
            return [data[k] for k in sorted(data.keys(), key=lambda x: int(x))]
        return [data]
    return []


def merge_rows(left_row: dict, right_row, conflict_strategy: str) -> dict:
    """Merge a left row with a right row according to conflict_strategy.

    Strategies:
      prefix     - right-table fields that clash with left get an "r_" prefix (default)
      overwrite  - right-table fields overwrite left-table fields
      keep_left  - left-table fields take priority; clashing right-table fields are dropped
    """
    merged = dict(left_row)

    if right_row is None:
        return merged

    if conflict_strategy == "overwrite":
        merged.update(right_row)

    elif conflict_strategy == "keep_left":
        for k, v in right_row.items():
            if k not in merged:
                merged[k] = v

    else:  # prefix (default)
        for k, v in right_row.items():
            if k in merged:
                merged["r_" + k] = v
            else:
                merged[k] = v

    return merged


def parse_output_fields(raw: str) -> list:
    """Parse a comma-separated string of field names into a list.

    Returns an empty list when raw is blank, meaning "keep all fields".
    """
    if not raw or not raw.strip():
        return []
    return [f.strip() for f in raw.split(",") if f.strip()]


def parse_rename_fields(raw: str) -> list:
    """Parse a comma-separated string of 'source:target' pairs into an ordered list of tuples.

    Malformed entries (no colon) are silently skipped.
    """
    if not raw or not raw.strip():
        return []
    pairs = []
    for token in raw.split(","):
        token = token.strip()
        if ":" in token:
            src, tgt = token.split(":", 1)
            src, tgt = src.strip(), tgt.strip()
            if src and tgt:
                pairs.append((src, tgt))
    return pairs


def extract_field(row: dict, field_spec: str) -> tuple:
    """Extract a value from row, supporting one level of dot notation.

    'field'           -> (field_spec, row.get('field'))
    'parent.subfield' -> if row['parent'] is a list, pluck subfield from every item
                         if row['parent'] is a dict, return row['parent'].get('subfield')
    Output key is always the full field_spec (e.g. 'SubjectAltNameElements.Value').
    """
    if "." not in field_spec:
        return field_spec, row.get(field_spec)

    parent, subfield = field_spec.split(".", 1)
    parent_val = row.get(parent)

    if isinstance(parent_val, list):
        value = [
            item.get(subfield) if isinstance(item, dict) else None
            for item in parent_val
        ]
    elif isinstance(parent_val, dict):
        value = parent_val.get(subfield)
    else:
        value = None

    return field_spec, value


def apply_field_ops(row: dict, output_fields: list, rename_pairs: list) -> dict:
    """Apply field selection then rename/merge to a single row.

    Step 1 - output_fields filter:
      If output_fields is non-empty, only the listed fields are kept.
      Supports dot notation: 'Parent.SubField' plucks SubField from each item
      in the Parent list (or from the Parent dict) and stores it under the
      key 'Parent.SubField'. Use rename_pairs to give it a friendlier name.

    Step 2 - rename / merge:
      Each (src, tgt) pair in rename_pairs renames src to tgt.
      Multiple sources mapped to the same target name are merged:
      the first non-null value wins.
      Fields not referenced in rename_pairs keep their original name.
    """
    # Step 1: field selection with dot-notation support
    if output_fields:
        filtered = {}
        for spec in output_fields:
            out_key, value = extract_field(row, spec)
            filtered[out_key] = value
        row = filtered

    if not rename_pairs:
        return row

    # Step 2: build lookup structures for rename/merge
    target_sources: dict = {}
    for src, tgt in rename_pairs:
        target_sources.setdefault(tgt, []).append(src)

    src_to_tgt = {src: tgt for src, tgt in rename_pairs}
    renamed_sources = set(src_to_tgt.keys())

    # Walk row in its current order (respects output_fields ordering).
    # Renamed fields are placed at the position of their first source key.
    # A null result never overwrites a value that is already present.
    result = {}
    for k, v in row.items():
        if k not in renamed_sources:
            result[k] = v
        else:
            tgt = src_to_tgt[k]
            if tgt not in result:
                value = next(
                    (row[s] for s in target_sources[tgt] if s in row and row[s] is not None), None
                )
                if value is not None or tgt not in result:
                    result[tgt] = value

    return result


def json_table_join(
    left_table: list,
    left_key: str,
    right_table: list,
    right_key: str,
    join_type: str,
    conflict_strategy: str,
) -> list:
    """Join right_table into left_table on left_key == right_key.

    join_type "left"  - all left rows are kept; unmatched rows have None for right fields.
    join_type "inner" - only rows with a match in both tables are kept.

    Supports 1-to-many: if multiple right rows share the same key value,
    the left row is expanded into one output row per match.
    """
    # Build index: right key value -> list of matching right rows
    right_map: dict = {}
    for item in right_table:
        item = coerce_to_dict(item)
        key_val = str(item.get(right_key) or "").strip()
        if key_val:
            right_map.setdefault(key_val, []).append(item)

    result: list = []
    for left_row in left_table:
        left_row = coerce_to_dict(left_row)
        left_val = str(left_row.get(left_key) or "").strip()
        matches = right_map.get(left_val)

        if matches:
            for right_row in matches:
                result.append(merge_rows(left_row, right_row, conflict_strategy))
        elif join_type == "left":
            result.append(merge_rows(left_row, None, conflict_strategy))
        # inner join + no match: skip row

    return result


def main():
    try:
        args = demisto.args()

        raw_left = args.get("left_table") or "[]"
        raw_right = args.get("right_table") or "[]"
        left_key = (args.get("left_key") or "").strip()
        right_key = (args.get("right_key") or "").strip()
        join_type = (args.get("join_type") or "left").strip().lower()
        conflict_strategy = (args.get("conflict_strategy") or "prefix").strip().lower()
        output_key = (args.get("output_key") or "result").strip()
        output_fields = parse_output_fields(args.get("output_fields") or "")
        rename_pairs = parse_rename_fields(args.get("rename_pairs") or "")

        if not left_key:
            return_error("left_key is required")
        if not right_key:
            return_error("right_key is required")
        if join_type not in ("left", "inner"):
            return_error("join_type must be 'left' or 'inner'")
        if conflict_strategy not in ("prefix", "overwrite", "keep_left"):
            return_error("conflict_strategy must be 'prefix', 'overwrite', or 'keep_left'")

        left_raw = json.loads(raw_left) if isinstance(raw_left, str) else raw_left
        right_raw = json.loads(raw_right) if isinstance(raw_right, str) else raw_right

        left_table = normalize_to_list(left_raw)
        right_table = normalize_to_list(right_raw)

        joined = json_table_join(
            left_table, left_key, right_table, right_key, join_type, conflict_strategy
        )

        if output_fields or rename_pairs:
            joined = [apply_field_ops(row, output_fields, rename_pairs) for row in joined]

        return_results(CommandResults(
            outputs_prefix="JSONTableJoin",
            outputs_key_field=output_key,
            outputs={output_key: joined},
            readable_output=tableToMarkdown(
                "JSON Table Join Result",
                joined,
                removeNull=False,
            ),
        ))

    except json.JSONDecodeError as e:
        return_error("Failed to parse input JSON: {}".format(e))
    except Exception as e:
        return_error("Unexpected error in ISE-ADP-JSONTable-Join: {}".format(e))


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
