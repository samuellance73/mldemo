# Ligolo-ng (TUN pivoting)

[Ligolo-ng](https://github.com/nicocha30/ligolo-ng) provides Layer-3 tunneling via a TUN interface on the **proxy** host. Agents reverse-connect to the proxy; traffic to the TUN is translated to the agent's network (no SOCKS/proxychains for tooling).

Sanctuary integrates ligolo-ng v0.8.3:

- **Hub**: proxy runs on the HF Space (`neural-route-controller`), exposed at `/tensor-mesh` (agents) and `/routing-console` (Web UI).

See also [CONTEXT.md](CONTEXT.md) for the full stack.

## Hub workflow (recommended)

1. Enable `ligolo` (and `nginx`) on a node in `manifests/nodes.yaml`, then `make deploy`.
2. Print agent connect info:

   ```bash
   uv run python scripts/cc.py ligolo hub --node server-01 --info
   ```

3. On the pivoted host, run the printed command (`agent` must be on PATH or set via `LIGOLO_AGENT` / `--agent-bin`).

4. Manage sessions on the Space:
   - SSH: `uv run python scripts/cc.py chisel --node server-01 -s`
   - Or forward Web UI: `uv run python scripts/cc.py ligolo hub --node server-01 --via chisel -L 6801:127.0.0.1:6801` then open `http://127.0.0.1:6801`

5. After the proxy starts, TLS fingerprint is written to `/home/user/.torch_metrics/ligolo_fingerprint.txt`. Fetch into local cache:

   ```bash
   uv run python scripts/cc.py chisel --node server-01 -L 2222:127.0.0.1:2222
   uv run python scripts/cc.py ligolo hub --node server-01 --fetch
   ```

6. In the container (or via forwarded Web UI), create TUN and routes (ligolo >= 0.6):

   ```
   interface_create --name tensor-route
   session
   tunnel_start --tun tensor-route
   interface_add_route --name tensor-route --route 10.0.0.0/24
   ```

Use `nmap --unprivileged` or `-PE` when scanning through the tunnel ([ligolo docs](https://docs.ligolo.ng/Quickstart/)).



## Camouflage mapping

| Disguised name | Real binary |
|----------------|-------------|
| `neural-route-controller` | ligolo-ng proxy (container) |
| `inference-edge-worker` | ligolo-ng agent (name used in docs/CLI hints) |

## Nginx paths

| Path | Backend |
|------|---------|
| `/tensor-mesh` | `https://127.0.0.1:11601` (agent TLS/WebSocket) |
| `/routing-console` | `http://127.0.0.1:6801` (Web UI/API) |

## Troubleshooting

- **`sudo: a password is required`**: The service runs `sudo -n /usr/bin/neural-route-controller` (no `nice` wrapper). Sudoers must allow passwordless `/usr/bin/neural-route-controller` only. Rebuild the image after Dockerfile changes.
- **`cat: ligolo: Is a directory`**: Use `cat ~/.torch_metrics/ligolo_fingerprint.txt` for the TLS fingerprint, not `cat ligolo`.

## Constraints on Hugging Face Spaces

- The proxy needs **TUN** (`CAP_NET_ADMIN`). The container starts it with `sudo`; HF may block `/dev/net/tun` on some hosts.
- If TUN fails, use Chisel/GOST for access and treat ligolo as experimental on that node.
- Gradio: `SHOW_LOGS_LIGOLO` → `ligolo.log`.

## Web UI credentials

Default credentials in `/home/user/ligolo-ng.yaml` (copied from `config/ligolo-ng.yaml`): user `sanctuary` / password `sanctuary`. Ligolo hashes this with argon2 on first run and writes the hash back to the same file. Change before production deploy.
