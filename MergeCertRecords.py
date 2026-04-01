import json
import demistomock as demisto
from CommonServerPython import *


def merge_cert_records(xsoar_incidents: list, keyfactor_records: list) -> list:
    """Merge cert records from XSOAR and Keyfactor, deduplicated by cert_id.

    Merge rules:
    - cert_id is the dedup key
    - Keyfactor data takes precedence (result, operator)
    - XSOAR supplements requester field
    - source = "keyfactor_only" | "both" | "xsoar_only"
    """
    # Index XSOAR records by cert_id
    xsoar_map: dict = {}
    for record in xsoar_incidents:
        cert_id = record.get("cert_id")
        if cert_id is not None:
            xsoar_map[cert_id] = record

    # Index Keyfactor records by cert_id
    keyfactor_map: dict = {}
    for record in keyfactor_records:
        cert_id = record.get("cert_id")
        if cert_id is not None:
            keyfactor_map[cert_id] = record

    merged: list = []

    # Process Keyfactor records first (source of truth for result/operator)
    for cert_id, kf_record in keyfactor_map.items():
        entry = {
            "cert_id": cert_id,
            "result": kf_record.get("result"),
            "operator": kf_record.get("operator"),
            "timestamp": kf_record.get("timestamp"),
        }

        xsoar_record = xsoar_map.get(cert_id)
        if xsoar_record:
            entry["requester"] = xsoar_record.get("requester")
            entry["close_notes"] = xsoar_record.get("close_notes")
            entry["close_reason"] = xsoar_record.get("close_reason")
            entry["source"] = "both"
        else:
            entry["requester"] = None
            entry["close_notes"] = None
            entry["close_reason"] = None
            entry["source"] = "keyfactor_only"

        merged.append(entry)

    # Process XSOAR-only records (not present in Keyfactor)
    for cert_id, xsoar_record in xsoar_map.items():
        if cert_id not in keyfactor_map:
            entry = {
                "cert_id": cert_id,
                "result": None,
                "operator": None,
                "timestamp": None,
                "requester": xsoar_record.get("requester"),
                "close_notes": xsoar_record.get("close_notes"),
                "close_reason": xsoar_record.get("close_reason"),
                "source": "xsoar_only",
            }
            merged.append(entry)

    return merged


def main():
    try:
        args = demisto.args()

        raw_xsoar = args.get("xsoar_incidents", "[]")
        raw_keyfactor = args.get("keyfactor_records", "[]")

        # Accept both JSON strings and already-parsed lists
        xsoar_incidents = json.loads(raw_xsoar) if isinstance(raw_xsoar, str) else raw_xsoar
        keyfactor_records = json.loads(raw_keyfactor) if isinstance(raw_keyfactor, str) else raw_keyfactor

        if not isinstance(xsoar_incidents, list):
            return_error("xsoar_incidents must be a JSON list")
        if not isinstance(keyfactor_records, list):
            return_error("keyfactor_records must be a JSON list")

        merged_list = merge_cert_records(xsoar_incidents, keyfactor_records)

        demisto.setContext("MergedCertRecords", merged_list)

        demisto.results({
            "Type": entryTypes["note"],
            "ContentsFormat": formats["json"],
            "Contents": merged_list,
            "HumanReadable": tableToMarkdown(
                "Merged Cert Records",
                merged_list,
                headers=["cert_id", "source", "result", "operator", "requester", "timestamp", "close_reason", "close_notes"],
                removeNull=False,
            ),
            "EntryContext": {
                "MergedCertRecords": merged_list,
            },
        })

    except json.JSONDecodeError as e:
        return_error(f"Failed to parse input JSON: {e}")
    except Exception as e:
        return_error(f"Unexpected error in MergeCertRecords: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
