import ast
import json
import demistomock as demisto
from CommonServerPython import *

OPERATION_MAP = {
    4: "Approved",
    5: "Denied",
}


def coerce_to_dict(item):
    """If item is a string that looks like a serialised dict, parse it.

    XSOAR sometimes passes context list items as Python repr strings
    e.g. "{'CARecordId': '415462', ...}" instead of actual dicts.
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


def join_cert_to_audit_logs(audit_logs: list, new_certs: list, request_details: list) -> list:
    """Left-join new_certs and request_details into audit_logs.

    Join keys:
      audit_logs.AuditIdentifier == new_certs.CARecordId
      audit_logs.AuditIdentifier == request_details.CARequestId

    Output fields per row:
      Timestamp, User, CARecordId, Operation,
      RequesterName, IssuedCN, TemplateName, Thumbprint,
      StateString, CommonName, DenialComment, Requester, SubmissionDate
    """
    cert_map: dict = {}
    for cert in new_certs:
        cert = coerce_to_dict(cert)
        ca_record_id = str(cert.get("CARecordId") or "").strip()
        if ca_record_id:
            cert_map[ca_record_id] = cert

    detail_map: dict = {}
    for detail in request_details:
        detail = coerce_to_dict(detail)
        ca_request_id = str(detail.get("CARequestId") or "").strip()
        if ca_request_id:
            detail_map[ca_request_id] = detail

    result: list = []
    for entry in audit_logs:
        entry = coerce_to_dict(entry)
        audit_id = str(entry.get("AuditIdentifier") or "").strip()
        cert = cert_map.get(audit_id)
        detail = detail_map.get(audit_id)

        operation_raw = entry.get("Operation")
        try:
            operation_raw = int(operation_raw)
        except (TypeError, ValueError):
            pass
        operation = OPERATION_MAP.get(operation_raw, operation_raw)

        row = {
            "Timestamp": entry.get("Timestamp"),
            "User": entry.get("User"),
            "CARecordId": audit_id,
            "Operation": operation,
            "RequesterName": cert.get("RequesterName") if cert else None,
            "IssuedCN": cert.get("IssuedCN") if cert else None,
            "TemplateName": cert.get("TemplateName") if cert else None,
            "Thumbprint": cert.get("Thumbprint") if cert else None,
            "StateString": detail.get("StateString") if detail else None,
            "CommonName": detail.get("CommonName") if detail else None,
            "DenialComment": detail.get("DenialComment") if detail else None,
            "Requester": detail.get("Requester") if detail else None,
            "SubmissionDate": detail.get("SubmissionDate") if detail else None,
        }
        result.append(row)

    return result


def main():
    try:
        args = demisto.args()

        raw_audit = args.get("audit_logs") or "[]"
        raw_certs = args.get("new_certs") or "[]"
        raw_details = args.get("request_details") or "[]"
        output_key = args.get("output_key") or "result"

        audit_logs_raw = json.loads(raw_audit) if isinstance(raw_audit, str) else raw_audit
        new_certs_raw = json.loads(raw_certs) if isinstance(raw_certs, str) else raw_certs
        request_details_raw = json.loads(raw_details) if isinstance(raw_details, str) else raw_details

        audit_logs = normalize_to_list(audit_logs_raw)
        new_certs = normalize_to_list(new_certs_raw)
        request_details = normalize_to_list(request_details_raw)

        if not isinstance(audit_logs, list):
            return_error("audit_logs must be a JSON list or numeric-keyed object")
        if not isinstance(new_certs, list):
            return_error("new_certs must be a JSON list or numeric-keyed object")
        if not isinstance(request_details, list):
            return_error("request_details must be a JSON list or numeric-keyed object")

        joined = join_cert_to_audit_logs(audit_logs, new_certs, request_details)

        return_results(CommandResults(
            outputs_prefix="joined_data",
            outputs_key_field=output_key,
            outputs={output_key: joined},
            readable_output=tableToMarkdown(
                "Joined Cert Audit Logs",
                joined,
                headers=["Timestamp", "User", "CARecordId", "Operation",
                         "RequesterName", "IssuedCN", "TemplateName", "Thumbprint",
                         "StateString", "CommonName", "DenialComment", "Requester", "SubmissionDate"],
                removeNull=False,
            ),
        ))

    except json.JSONDecodeError as e:
        return_error("Failed to parse input JSON: {}".format(e))
    except Exception as e:
        return_error("Unexpected error in JoinCertAuditLogs: {}".format(e))


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
