import json
import demistomock as demisto
from CommonServerPython import *

# Keyfactor audit Operation codes for certificate requests
# https://software.keyfactor.com/Core-OnPrem/Current/Content/AuditLogs.htm
KEYFACTOR_OPERATION_MAP = {
    4: "Approved",
    5: "Denied",
}


def normalize_keyfactor_record(raw: dict) -> dict:
    """Normalize a raw Keyfactor audit record to the internal schema.

    Keyfactor audit fields:
      ImmutableIdentifier -> cert_id
      User                -> operator
      Timestamp           -> timestamp
      Operation (int)     -> result ("Approved" / "Denied" / raw int as string)
    """
    operation = raw.get("Operation")
    result = KEYFACTOR_OPERATION_MAP.get(operation, str(operation) if operation is not None else None)
    return {
        "cert_id": raw.get("ImmutableIdentifier"),
        "result": result,
        "operator": raw.get("User"),
        "timestamp": raw.get("Timestamp"),
        # Preserve extra audit fields for traceability
        "audit_id": raw.get("AuditIdentifier"),
        "entity_type": raw.get("EntityType"),
    }


def parse_keyfactor_response(raw_input) -> list:
    """Accept either:
    - a pre-normalised list (each item already has cert_id / result / operator)
    - the raw Keyfactor API envelope: { api_query_result: { result: [...] } }
    - a bare list of raw Keyfactor audit records
    """
    if isinstance(raw_input, str):
        raw_input = json.loads(raw_input)

    # Envelope format from the API: { "api_query_result": { "result": [...] } }
    if isinstance(raw_input, dict):
        records = raw_input.get("api_query_result", {}).get("result", [])
        return [normalize_keyfactor_record(r) for r in records]

    if isinstance(raw_input, list):
        if raw_input and "ImmutableIdentifier" in raw_input[0]:
            # Raw audit records list
            return [normalize_keyfactor_record(r) for r in raw_input]
        # Already normalised
        return raw_input

    return []


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

    # Index Keyfactor records by cert_id (last record wins for duplicate cert_ids)
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
            "audit_id": kf_record.get("audit_id"),
            "entity_type": kf_record.get("entity_type"),
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
                "audit_id": None,
                "entity_type": None,
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
        raw_keyfactor = args.get("keyfactor_records", "{}")

        # Accept both JSON strings and already-parsed structures
        xsoar_incidents = json.loads(raw_xsoar) if isinstance(raw_xsoar, str) else raw_xsoar
        if not isinstance(xsoar_incidents, list):
            return_error("xsoar_incidents must be a JSON list")

        # keyfactor_records accepts: API envelope dict, raw audit list, or normalised list
        keyfactor_records = parse_keyfactor_response(raw_keyfactor)

        merged_list = merge_cert_records(xsoar_incidents, keyfactor_records)

        demisto.setContext("MergedCertRecords", merged_list)

        demisto.results({
            "Type": entryTypes["note"],
            "ContentsFormat": formats["json"],
            "Contents": merged_list,
            "HumanReadable": tableToMarkdown(
                "Merged Cert Records",
                merged_list,
                headers=["cert_id", "source", "result", "operator", "requester", "timestamp",
                         "close_reason", "close_notes", "audit_id", "entity_type"],
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
