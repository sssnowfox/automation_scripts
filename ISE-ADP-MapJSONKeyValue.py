import json
import demistomock as demisto
from CommonServerPython import *


def map_table_values(data, target_key: str, mapping: dict) -> list:
    """Map values of a specific key in a list of dicts according to a mapping table.

    Values not present in the mapping are left unchanged.
    If data is a single dict it is automatically wrapped in a list.
    """
    if not isinstance(data, list):
        data = [data]

    for item in data:
        # Only process dicts that contain the target key
        if isinstance(item, dict) and target_key in item:
            # Coerce to string to match JSON object keys in the mapping
            current_val = str(item[target_key])
            if current_val in mapping:
                item[target_key] = mapping[current_val]

    return data


def main():
    try:
        args = demisto.args()

        raw_data = args.get("value")
        target_key = args.get("target_key")
        mapping_str = args.get("mapping_dict", "{}")

        try:
            mapping = json.loads(mapping_str)
        except Exception as e:
            return_error(f"Failed to parse mapping_dict — ensure it is valid JSON: {e}")

        processed_data = map_table_values(raw_data, target_key, mapping)

        return_results(processed_data)

    except Exception as e:
        return_error(f"Unexpected error in ISE-ADP-MapJSONKeyValue: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
