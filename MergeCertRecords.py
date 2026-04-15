import json
import demistomock as demisto
from CommonServerPython import *

# Keyfactor audit Operation codes for certificate requests
# https://software.keyfactor.com/Core-OnPrem/Current/Content/AuditLogs.htm
KEYFACTOR_OPERATION_MAP = {
    4: "Approved",
    5: "Denied",
}


# ---------------------------------------------------------------------------
# Source 1: Keyfactor audit log  (api_query_result.result[])
# ---------------------------------------------------------------------------

def normalize_keyfactor_audit_record(raw: dict) -> dict:
    """Normalize a raw Keyfactor audit record.

      ImmutableIdentifier -> cert_id
      User                -> operator
      Timestamp           -> audit_timestamp
      Operation (int)     -> result ("Approved" / "Denied" / int-as-string)
      AuditIdentifier     -> audit_id
      EntityType          -> entity_type
    """
    operation = raw.get("Operation")
    result = KEYFACTOR_OPERATION_MAP.get(operation, str(operation) if operation is not None else None)
    return {
        "cert_id": raw.get("ImmutableIdentifier"),
        "result": result,
        "operator": raw.get("User"),
        "audit_timestamp": raw.get("Timestamp"),
        "audit_id": raw.get("AuditIdentifier"),
        "entity_type": raw.get("EntityType"),
    }


def parse_keyfactor_audit_response(raw_input) -> list:
    """Parse Keyfactor audit input into a normalised list.

    Accepts:
    - API envelope: { "api_query_result": { "result": [...] } }
    - Bare list of raw audit records (contain ImmutableIdentifier)
    - Already-normalised list
    """
    if isinstance(raw_input, str):
        raw_input = json.loads(raw_input)

    if isinstance(raw_input, dict):
        records = raw_input.get("api_query_result", {}).get("result", [])
        return [normalize_keyfactor_audit_record(r) for r in records]

    if isinstance(raw_input, list):
        if raw_input and "ImmutableIdentifier" in raw_input[0]:
            return [normalize_keyfactor_audit_record(r) for r in raw_input]
        return raw_input  # already normalised

    return []


# ---------------------------------------------------------------------------
# Source 2: Keyfactor request detail  (api_query_result.requestdetailresult)
# ---------------------------------------------------------------------------

def normalize_keyfactor_detail_record(raw: dict) -> dict:
    """Normalize a raw Keyfactor requestdetailresult record.

      Id               -> cert_id
      StateString      -> result  ("Approved" / "Denied")
      Requester        -> kf_requester
      SubmissionDate   -> submission_date
      CARequestId      -> ca_request_id
      CommonName       -> common_name
      DenialComment    -> denial_comment
      Template         -> template
      CertificateAuthority -> certificate_authority
    """
    return {
        "cert_id": str(raw.get("Id")) if raw.get("Id") is not None else None,
        "result": raw.get("StateString"),
        "kf_requester": raw.get("Requester"),
        "submission_date": raw.get("SubmissionDate"),
        "ca_request_id": raw.get("CARequestId"),
        "common_name": raw.get("CommonName"),
        "denial_comment": raw.get("DenialComment"),
        "template": raw.get("Template"),
        "certificate_authority": raw.get("CertificateAuthority"),
    }


def parse_keyfactor_detail_response(raw_input) -> list:
    """Parse Keyfactor request-detail input into a normalised list.

    Accepts:
    - Single API envelope:  { "api_query_result": { "requestdetailresult": {...} } }
    - List of API envelopes (one per cert)
    - Already-normalised list
    """
    if isinstance(raw_input, str):
        raw_input = json.loads(raw_input)

    if isinstance(raw_input, dict):
        detail = raw_input.get("api_query_result", {}).get("requestdetailresult")
        if detail:
            return [normalize_keyfactor_detail_record(detail)]
        return []

    if isinstance(raw_input, list):
        result = []
        for item in raw_input:
            if isinstance(item, dict):
                # List of envelopes
                detail = item.get("api_query_result", {}).get("requestdetailresult")
                if detail:
                    result.append(normalize_keyfactor_detail_record(detail))
                elif "Id" in item:
                    # Raw detail record without envelope
                    result.append(normalize_keyfactor_detail_record(item))
                else:
                    # Already normalised
                    result.append(item)
        return result

    return []


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

def merge_cert_records(
    xsoar_incidents: list,
    keyfactor_audit: list,
    keyfactor_details: list,
) -> list:
    """Merge three sources by cert_id.

    Priority:
    - result:      keyfactor_detail.StateString > keyfactor_audit.Operation mapping
    - operator:    keyfactor_audit.User (only audit has this)
    - requester:   keyfactor_detail.Requester > xsoar.requester
    - denial info: keyfactor_detail.DenialComment + xsoar.close_notes / close_reason
    - source flag: "keyfactor_only" | "both" | "xsoar_only"
    """
    xsoar_map: dict = {r["cert_id"]: r for r in xsoar_incidents if r.get("cert_id") is not None}
    audit_map: dict = {r["cert_id"]: r for r in keyfactor_audit if r.get("cert_id") is not None}
    detail_map: dict = {r["cert_id"]: r for r in keyfactor_details if r.get("cert_id") is not None}

    all_kf_ids = set(audit_map) | set(detail_map)
    merged: list = []

    # --- Records that exist in at least one Keyfactor source ---
    for cert_id in all_kf_ids:
        audit = audit_map.get(cert_id, {})
        detail = detail_map.get(cert_id, {})
        xsoar = xsoar_map.get(cert_id, {})

        # result: detail wins (StateString) over audit (Operation mapping)
        result = detail.get("result") or audit.get("result")

        # requester: detail's Requester wins over XSOAR's requester
        requester = detail.get("kf_requester") or xsoar.get("requester")

        entry = {
            "cert_id": cert_id,
            "result": result,
            "operator": audit.get("operator"),
            "requester": requester,
            # timestamps
            "submission_date": detail.get("submission_date"),
            "audit_timestamp": audit.get("audit_timestamp"),
            # Keyfactor detail fields
            "common_name": detail.get("common_name"),
            "denial_comment": detail.get("denial_comment"),
            "template": detail.get("template"),
            "ca_request_id": detail.get("ca_request_id"),
            "certificate_authority": detail.get("certificate_authority"),
            # Keyfactor audit fields
            "audit_id": audit.get("audit_id"),
            "entity_type": audit.get("entity_type"),
            # XSOAR fields
            "close_notes": xsoar.get("close_notes"),
            "close_reason": xsoar.get("close_reason"),
            "source": "both" if xsoar else "keyfactor_only",
        }
        merged.append(entry)

    # --- Records only in XSOAR ---
    for cert_id, xsoar in xsoar_map.items():
        if cert_id not in all_kf_ids:
            merged.append({
                "cert_id": cert_id,
                "result": None,
                "operator": None,
                "requester": xsoar.get("requester"),
                "submission_date": None,
                "audit_timestamp": None,
                "common_name": None,
                "denial_comment": None,
                "template": None,
                "ca_request_id": None,
                "certificate_authority": None,
                "audit_id": None,
                "entity_type": None,
                "close_notes": xsoar.get("close_notes"),
                "close_reason": xsoar.get("close_reason"),
                "source": "xsoar_only",
            })

    return merged


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    try:
        args = demisto.args()

        raw_xsoar = args.get("xsoar_incidents", "[]")
        raw_audit = args.get("keyfactor_records", "{}")
        raw_detail = args.get("keyfactor_request_detail", "{}")

        xsoar_incidents = json.loads(raw_xsoar) if isinstance(raw_xsoar, str) else raw_xsoar
        if not isinstance(xsoar_incidents, list):
            return_error("xsoar_incidents must be a JSON list")

        keyfactor_audit = parse_keyfactor_audit_response(raw_audit)
        keyfactor_details = parse_keyfactor_detail_response(raw_detail)

        merged_list = merge_cert_records(xsoar_incidents, keyfactor_audit, keyfactor_details)

        demisto.setContext("MergedCertRecords", merged_list)

        demisto.results({
            "Type": entryTypes["note"],
            "ContentsFormat": formats["json"],
            "Contents": merged_list,
            "HumanReadable": tableToMarkdown(
                "Merged Cert Records",
                merged_list,
                headers=[
                    "cert_id", "source", "result", "operator", "requester",
                    "common_name", "template", "ca_request_id",
                    "submission_date", "audit_timestamp",
                    "denial_comment", "close_reason", "close_notes",
                    "certificate_authority", "audit_id", "entity_type",
                ],
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
