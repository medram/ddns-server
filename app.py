import json
import os
import secrets
from pathlib import Path
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

app = FastAPI()
security = HTTPBasic()

# Configuration & Persistence
STATE_FILE = Path("/app/data/ips.json")
CF_TOKEN = os.getenv("CF_TOKEN")
CF_ZONE_ID = os.getenv("CF_ZONE_ID")
AUTH_USER = os.getenv("DDNS_USER", "admin")
AUTH_PASS = os.getenv("DDNS_PASS", "password")


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


async def update_cloudflare_dns(
    name: str,
    content: str,
    record_type: str = "A",
    ttl: int = 1,
    proxied: bool = False,
    comment: Optional[str] = None,
) -> bool:
    """Update or create a DNS record in Cloudflare. Returns True on success."""
    cf_url = f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}/dns_records"
    headers = {
        "Authorization": f"Bearer {CF_TOKEN}",
        "Content-Type": "application/json",
    }
    record_payload = {
        "type": record_type,
        "name": name,
        "content": content,
        "ttl": ttl,
        "proxied": proxied,
    }
    if comment is not None:
        record_payload["comment"] = comment

    async with httpx.AsyncClient() as client:
        list_resp = await client.get(
            cf_url, params={"type": record_type, "name": name}, headers=headers
        )
        list_data = list_resp.json()

        if not list_data.get("success"):
            print(f"Cloudflare API Error (list): {list_resp.text}")
            return False

        records = list_data.get("result", [])
        if records:
            record_id = records[0]["id"]
            resp = await client.put(
                f"{cf_url}/{record_id}", json=record_payload, headers=headers
            )
        else:
            resp = await client.post(cf_url, json=record_payload, headers=headers)

        if resp.json().get("success"):
            print(f"Successfully updated Cloudflare DNS for {name}: {content}")
            return True

        print(f"Cloudflare API Error: {resp.text}")
        return False


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
    request: Request,  # Add request to get the real client IP
    hostname: str = Query(...),
    myip: Optional[str] = Query(None),
    user: str = Depends(get_current_user),
):
    # If the router didn't send 'myip', grab its actual public IP from the request
    # This replaces your "source_ip" string with the real IP address
    ip_to_register = myip if myip else request.client.host  # type: ignore

    state = load_state()

    # Avoid unnecessary API calls if the IP hasn't changed
    if state.get(hostname) == ip_to_register:
        # Returns raw: nochg 1.2.3.4
        return PlainTextResponse(f"nochg {ip_to_register}")

    if await update_cloudflare_dns(
        hostname, ip_to_register, comment=f"Updated by DDNS server for {hostname}"
    ):
        state[hostname] = ip_to_register
        save_state(state)
        # Returns raw: good 1.2.3.4
        return PlainTextResponse(f"good {ip_to_register}")

    return PlainTextResponse("911")  # Server error


@app.get("/ips")
async def get_ips(user: str = Depends(get_current_user)):
    if not STATE_FILE.exists():
        raise HTTPException(status_code=404, detail="No IP records found")
    return load_state()
