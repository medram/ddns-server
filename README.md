# DDNS → Cloudflare DNS

A lightweight DDNS receiver that keeps **Cloudflare DNS records** in sync with your dynamic IP(s). Deploy it on any server, point your router's DDNS client at it, and Cloudflare will always have your current IP(s) up to date.

This server implements the **No-IP / DynDNS protocol** (`/nic/update`), making it a drop-in replacement for No-IP on any router that supports custom DDNS servers.

## How it works

1. Your router sends a standard DDNS update request to this server (`GET /nic/update`).
2. The server checks if the IP has changed — if not, it skips the update.
3. It creates or updates an **A record** in your Cloudflare DNS zone via the Cloudflare API.
4. The new IP is saved locally (`data/ips.json`).

## Requirements

- A [Cloudflare](https://cloudflare.com) account with a domain/zone.
- A Cloudflare API token with **Zone > DNS: Edit** permission.
- Docker & Docker Compose (or Python 3.12+ with `uv`).

## Quick start with Docker

1. Clone the repo:

   ```bash
   git clone https://github.com/medram/ddns-server.git
   cd ddns-server
   ```

2. Edit the environment variables in `docker-compose.yml`:

   | Variable     | Description                                           |
   | ------------ | ----------------------------------------------------- |
   | `CF_ZONE_ID` | Your Cloudflare Zone ID (from the zone Overview page) |
   | `CF_TOKEN`   | Cloudflare API token with DNS Edit permission         |
   | `DDNS_USER`  | Basic auth username for your router                   |
   | `DDNS_PASS`  | Basic auth password for your router                   |

3. Start the server:
   ```bash
   docker compose up -d
   ```

The server listens on port **8080**.

## Docker run

If you prefer not to use Docker Compose, you can run the container directly:

```bash
docker run -d \
  --name ddns-receiver \
  --restart unless-stopped \
  -p 8080:8000 \
  -v $(pwd)/data:/app/data \
  -e CF_ZONE_ID=your_zone_id \
  -e CF_TOKEN=your_token \
  -e DDNS_USER=office_admin \
  -e DDNS_PASS=secret_pass \
  mrmed/ddns-server:latest
```

The server listens on port **8080**.

## Router configuration

Configure your router's DDNS client with:

| Field    | Value                                           |
| -------- | ----------------------------------------------- |
| Server   | `your-server-ip-or-domain`                      |
| URL      | `/nic/update?hostname=__HOSTNAME__&myip=__IP__` |
| Username | value of `DDNS_USER`                            |
| Password | value of `DDNS_PASS`                            |

> This server is compatible with the **No-IP protocol** (`/nic/update`). Any router that supports No-IP or a custom DynDNS server (e.g. MikroTik, ASUS, GL.iNet, OpenWrt) can use it as a direct replacement — just point the DDNS server address to your own host.

## Running locally (without Docker)

```bash
uv sync
uv run uvicorn app:app --host 0.0.0.0 --port 8000
```

## API

### `GET /nic/update`

Standard DynDNS-compatible update endpoint. Protected by HTTP Basic Auth.

| Query param | Required | Description                                |
| ----------- | -------- | ------------------------------------------ |
| `hostname`  | Yes      | The DNS record name to update              |
| `myip`      | No       | IP to register (uses source IP if omitted) |

**Responses:**

| Response    | Meaning                        |
| ----------- | ------------------------------ |
| `good <ip>` | IP updated successfully        |
| `nochg`     | IP unchanged, no update needed |
| `911`       | Cloudflare API error           |

### `GET /ips`

Returns the locally stored hostname → IP mapping as JSON. Protected by HTTP Basic Auth.

**Example response:**

```json
{
  "office.example.com": "1.2.3.4"
}
```

## Environment variables

| Variable     | Default    | Description                     |
| ------------ | ---------- | ------------------------------- |
| `CF_ZONE_ID` | —          | Cloudflare Zone ID              |
| `CF_TOKEN`   | —          | Cloudflare API token (DNS Edit) |
| `DDNS_USER`  | `admin`    | Basic auth username             |
| `DDNS_PASS`  | `password` | Basic auth password             |
