import json
import os
import secrets
from pathlib import Path
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

app = FastAPI()
security = HTTPBasic()

# Configuration & Persistence
STATE_FILE = Path("/app/data/ips.json")
CF_TOKEN = os.getenv("CF_TOKEN")
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID")
CF_LIST_ID = os.getenv("CF_LIST_ID")
AUTH_USER = os.getenv("DDNS_USER", "admin")
AUTH_PASS = os.getenv("DDNS_PASS", "password")


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    # Standard security check for the router credentials
    is_user_ok = secrets.compare_digest(credentials.username, AUTH_USER)
    is_pass_ok = secrets.compare_digest(credentials.password, AUTH_PASS)
    if not (is_user_ok and is_pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/nic/update")
async def update_ip(
    hostname: str = Query(...),
    myip: Optional[str] = Query(None),
    user: str = Depends(get_current_user),
):
    # If router doesn't send IP, use the connection's source IP
    ip_to_register = myip if myip else "source_ip"

    state = load_state()

    # Avoid unnecessary API calls if the IP hasn't changed
    if state.get(hostname) == ip_to_register:
        return "nochg"

    # Update local state
    state[hostname] = ip_to_register
    save_state(state)

    # Push all known router IPs to Cloudflare WAF List
    payload = [{"ip": ip, "comment": f"Router: {host}"} for host, ip in state.items()]

    async with httpx.AsyncClient() as client:
        cf_url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/rules/lists/{CF_LIST_ID}/items"
        headers = {
            "Authorization": f"Bearer {CF_TOKEN}",
            "Content-Type": "application/json",
        }

        response = await client.put(cf_url, json=payload, headers=headers)

        if response.status_code == 200:
            print(f"Successfully updated Cloudflare for {hostname}: {ip_to_register}")
            return f"good {ip_to_register}"
        else:
            print(f"Cloudflare API Error: {response.text}")
            return "911"  # Standard DDNS error code for server failure
