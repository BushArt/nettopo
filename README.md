# NetTopo — Live Network Topology Visualizer

**Current status: Phase 2 — Streaming** (Live real-time network topology)

---

## ⚠️ Legal Warning

**Only scan networks you own or have explicit written permission to scan.**

Scanning without authorization violates Taiwan Criminal Code Articles 358–359. The scanner enforces RFC1918 subnet restrictions and requires a `permission_statement` in `config.yaml` before any scan will run. See [Section 12 of the project plan](docs/architecture.md) for full legal context.

Authorized environments: your own lab, TryHackMe rooms (while connected to their VPN), HackTheBox machines, self-hosted Docker lab.

---

## Quickstart (Phase 2)

### 1. Clone and set up

```bash
git clone https://github.com/YOUR_USERNAME/nettopo.git
cd nettopo
git checkout phase/2-streaming

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

Edit `config.yaml`:
```yaml
legal:
  permission_statement: "My own Docker lab — authorized 2026-05-01"
```

### 3. Start the Docker lab

```bash
make lab        # pulls and starts Metasploitable, DVWA, WebGoat
```

### 4. Generate fixture files (first time only)

```bash
bash tests/mock_network/generate_fixtures.sh
```

### 5. Scan and view

```bash
make dev        # runs both WebSocket and HTTP server on http://localhost:8080
make scan       # (legacy static mode)
# open http://localhost:8080 in your browser
```

### 6. Run tests

```bash
make test       # all 12 parser unit tests must pass
```

---

## Project Structure

```
nettopo/
├── scanner/            Python nmap subprocess + XML parser
├── enrichment/         CVE lookup, MAC vendor, risk scoring (Phase 3)
├── server/             WebSocket server + REST API (Phase 2)
├── frontend/           D3.js graph UI
├── data/               Scan sessions + NVD cache (gitignored)
├── tests/              Unit + integration tests + fixture XML files
├── docs/               Architecture, API reference, demo guide
├── main_static.py      Phase 1 entry point
├── config.yaml         All configuration
├── Makefile            Dev shortcuts
└── docker-compose.lab.yml  Vulnerable lab environment
```

---

## Make Targets

| Command | What it does |
|---------|-------------|
| `make scan` | Run nmap scan against configured subnet |
| `make test` | Run all unit tests with pytest |
| `make serve` | Serve frontend on http://localhost:8080 |
| `make lab` | Start Docker Compose vulnerable lab |
| `make clean` | Remove session files and cache |

---

## Build Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Scanner + Parser + Static Rendering | ✅ Complete |
| 2 | WebSocket Server + Live Graph Updates | ✅ Complete |
| 3 | CVE Enrichment + Risk Scoring | ⏳ Planned |
| 4 | Export + Demo Mode + Polish | ⏳ Planned |
| 5 | Bloodhound + PCAP + Extensions | ⏳ Optional |

---

## Development Environment

- Python 3.10+
- nmap 7.80+
- Docker + Docker Compose (for lab)
- Ubuntu 22.04 LTS or macOS 14+ recommended

Full setup instructions: see Session 1 in the Phase 1 Technical Plan.
