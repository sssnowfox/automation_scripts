import requests

# ── Config ──────────────────────────────────────────────
SN_BASE_URL   = "https://<instance>.service-now.com"
CLIENT_ID     = "your_client_id"
CLIENT_SECRET = "your_client_secret"   # 如果有的话
USERNAME      = "your_username"
PASSWORD      = "your_password"


# ── 1. 获取 OAuth token (Resource Owner Password Grant) ──
def get_token():
    resp = requests.post(
        f"{SN_BASE_URL}/oauth_token.do",
        data={
            "grant_type":    "password",
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "username":      USERNAME,
            "password":      PASSWORD,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# ── 2. Query table ───────────────────────────────────────
def query_table(token, table, sysparm_query, fields=None, limit=100):
    params = {
        "sysparm_query":         sysparm_query,
        "sysparm_limit":         limit,
        "sysparm_display_value": "true",   # 返回 display value 而不是 sys_id
    }
    if fields:
        params["sysparm_fields"] = ",".join(fields)

    resp = requests.get(
        f"{SN_BASE_URL}/api/now/table/{table}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept":        "application/json",
        },
        params=params,
    )
    resp.raise_for_status()
    return resp.json().get("result", [])


# ── 3. 拉取 incident 的 assigned groups ──────────────────
if __name__ == "__main__":
    INCIDENT_SYS_ID = "abc123..."

    token = get_token()
    records = query_table(
        token,
        table="metric_instance",
        sysparm_query=f"id={INCIDENT_SYS_ID}^metric.nameSTARTSWITHassignment",
        fields=["value", "date", "sys_created_on", "metric.name"],
    )

    for r in records:
        print(r.get("sys_created_on"), "→", r.get("value"))
