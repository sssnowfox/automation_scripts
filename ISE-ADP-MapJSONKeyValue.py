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
        output_key = args.get("output_key") or "result"

        try:
            mapping = json.loads(mapping_str)
        except Exception as e:
            return_error(f"Failed to parse mapping_dict — ensure it is valid JSON: {e}")

        processed_data = map_table_values(raw_data, target_key, mapping)

        # Derive column headers dynamically from the first row
        headers = list(processed_data[0].keys()) if processed_data and isinstance(processed_data[0], dict) else []

        return_results(CommandResults(
            outputs_prefix="MapJSONKeyValue",
            outputs_key_field=output_key,
            outputs=processed_data,
            readable_output=tableToMarkdown(
                "Mapped JSON Key Values",
                processed_data,
                headers=headers,
                removeNull=False,
            ),
        ))

    except Exception as e:
        return_error(f"Unexpected error in ISE-ADP-MapJSONKeyValue: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
