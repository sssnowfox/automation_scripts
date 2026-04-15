import json
import demistomock as demisto
from CommonServerPython import *

# Marker returned by XSOAR getList when the list does not exist yet
LIST_NOT_FOUND_MARKER = "Item not found"


def parse_list_contents(raw: str) -> list:
    """Parse the raw string returned by getList into a Python list.

    Handles three cases:
    - Empty string or None  -> empty list (list is blank)
    - XSOAR "Item not found" response -> empty list (list does not exist yet)
    - Valid JSON string -> parsed list; a lone dict is wrapped in a list
    """
    if not raw or LIST_NOT_FOUND_MARKER in raw:
        return []

    parsed = json.loads(raw)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    return []


def normalize_to_list(data) -> list:
    """Accept a JSON list, a single dict, or a JSON string and always return a list."""
    if isinstance(data, str):
        data = json.loads(data)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def merge_by_dedup_key(existing: list, incoming: list, dedup_key: str) -> list:
    """Merge incoming records into the existing list, deduplicating by dedup_key.

    Merge rules:
    - Items that carry the dedup_key are indexed; incoming items overwrite
      existing items that share the same key value (upsert semantics).
    - Items that lack the dedup_key field are appended without deduplication.
    """
    keyed: dict = {}
    no_key_items: list = []

    for item in existing:
        if isinstance(item, dict) and dedup_key in item:
            keyed[item[dedup_key]] = item
        else:
            no_key_items.append(item)

    for item in incoming:
        if isinstance(item, dict) and dedup_key in item:
            keyed[item[dedup_key]] = item
        else:
            no_key_items.append(item)

    return list(keyed.values()) + no_key_items


def extract_table_headers(records: list) -> list:
    """Collect all unique keys from a list of dicts, preserving first-seen order."""
    seen: dict = {}
    for record in records:
        if isinstance(record, dict):
            for key in record:
                seen[key] = None
    return list(seen.keys())


def main():
    try:
        args = demisto.args()

        list_name = args.get("list_name", "")
        raw_new_data = args.get("new_data", "[]")
        dedup_key = args.get("dedup_key", "")

        if not list_name:
            return_error("list_name is required")
        if not dedup_key:
            return_error("dedup_key is required")

        # Fetch existing list contents from XSOAR
        get_res = demisto.executeCommand("getList", {"listName": list_name})
        if is_error(get_res):
            return_error(f"Failed to retrieve list '{list_name}': {get_res[0]['Contents']}")

        raw_existing = get_res[0].get("Contents", "")
        existing_list = parse_list_contents(raw_existing)

        # Parse the incoming new_data (accept JSON string or already-parsed structure)
        incoming_list = normalize_to_list(raw_new_data)

        # Merge with deduplication
        final_list = merge_by_dedup_key(existing_list, incoming_list, dedup_key)

        # Write the merged list back to XSOAR
        final_json_str = json.dumps(final_list, ensure_ascii=False)
        set_res = demisto.executeCommand("setList", {"listName": list_name, "listData": final_json_str})
        if is_error(set_res):
            return_error(f"Failed to write list '{list_name}': {set_res[0]['Contents']}")

        headers = extract_table_headers(final_list)

        return_results(CommandResults(
            outputs_prefix="UpdatedJSONList",
            outputs_key_field=dedup_key,
            outputs=final_list,
            readable_output=tableToMarkdown(
                f"Updated XSOAR List: {list_name}",
                final_list,
                headers=headers or None,
                removeNull=False,
            ),
        ))

    except json.JSONDecodeError as e:
        return_error(f"Failed to parse input JSON: {e}")
    except Exception as e:
        return_error(f"Unexpected error in ISE-ADP-UpdateJSONList: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
