import json
import demistomock as demisto
from CommonServerPython import *


def normalize_to_list(data) -> list:
    """Accept a JSON list or a dict with numeric string keys (e.g. {"0": {...}, "1": {...}})."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data[k] for k in sorted(data.keys(), key=lambda x: int(x) if x.isdigit() else x)]
    return []


def join_cert_to_audit_logs(audit_logs: list, new_certs: list) -> list:
    """Left-join new_certs into audit_logs using AuditIdentifier == CARecordId as the key.

    Every audit log entry is kept. Cert fields are attached where a match exists.
    cert_matched = True | False indicates whether a cert was found for the entry.
    """
    # Index certs by CARecordId (string-normalised)
    cert_map: dict = {}
    for cert in new_certs:
        ca_record_id = str(cert.get("CARecordId", "")).strip()
        if ca_record_id:
            cert_map[ca_record_id] = cert

    result: list = []
    for entry in audit_logs:
        audit_id = str(entry.get("AuditIdentifier", "")).strip()
        matched_cert = cert_map.get(audit_id)

        joined = dict(entry)  # copy all audit log fields
        if matched_cert:
            joined["cert_matched"] = True
            joined["cert_data"] = matched_cert
        else:
            joined["cert_matched"] = False
            joined["cert_data"] = None

        result.append(joined)

    return result


def main():
    try:
        args = demisto.args()

        raw_audit = args.get("audit_logs", "[]")
        raw_certs = args.get("new_certs", "[]")

        audit_logs_raw = json.loads(raw_audit) if isinstance(raw_audit, str) else raw_audit
        new_certs_raw = json.loads(raw_certs) if isinstance(raw_certs, str) else raw_certs

        audit_logs = normalize_to_list(audit_logs_raw)
        new_certs = normalize_to_list(new_certs_raw)

        if not isinstance(audit_logs, list):
            return_error("audit_logs must be a JSON list or numeric-keyed object")
        if not isinstance(new_certs, list):
            return_error("new_certs must be a JSON list or numeric-keyed object")

        joined = join_cert_to_audit_logs(audit_logs, new_certs)

        demisto.setContext("JoinedCertAuditLogs", joined)

        demisto.results({
            "Type": entryTypes["note"],
            "ContentsFormat": formats["json"],
            "Contents": joined,
            "HumanReadable": tableToMarkdown(
                "Joined Cert Audit Logs",
                joined,
                headers=["AuditIdentifier", "User", "Operation", "Timestamp", "EntityType", "cert_matched", "cert_data"],
                removeNull=False,
            ),
            "EntryContext": {
                "JoinedCertAuditLogs": joined,
            },
        })

    except json.JSONDecodeError as e:
        return_error(f"Failed to parse input JSON: {e}")
    except Exception as e:
        return_error(f"Unexpected error in JoinCertAuditLogs: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
