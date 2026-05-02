#!/usr/bin/env bash
# generate_fixtures.sh — Generate all Phase 1 nmap fixture XML files.
#
# Prerequisites:
#   - Docker lab running: make lab
#   - nmap installed: nmap --version
#   - Run from project root: bash tests/mock_network/generate_fixtures.sh
#
# WARNING: These scans target the local Docker lab only (172.20.0.0/24).
# Never run against networks you do not own or have explicit permission to scan.

set -euo pipefail

FIXTURES="tests/fixtures"
LAB_SUBNET="172.20.0.0/24"
SINGLE_HOST="172.20.0.10"   # Metasploitable

echo "==> Generating Phase 1 fixture XML files..."
echo "    Target: $LAB_SUBNET (Docker lab)"
echo ""

# 1. Quick / ping scan
echo "[1/6] sample_nmap_quick.xml — ping scan..."
nmap -sn -T4 -oX "$FIXTURES/sample_nmap_quick.xml" "$LAB_SUBNET"

# 2. Ports scan
echo "[2/6] sample_nmap_ports.xml — top 100 ports..."
nmap -sT -T4 --top-ports 100 -oX "$FIXTURES/sample_nmap_ports.xml" "$LAB_SUBNET"

# 3. Full service scan
echo "[3/6] sample_nmap_full.xml — version detection, top 1000 ports..."
nmap -sT -sV -T4 --top-ports 1000 -oX "$FIXTURES/sample_nmap_full.xml" "$LAB_SUBNET"

# 4. OS fingerprint scan (requires sudo)
echo "[4/6] sample_nmap_os.xml — OS detection..."
sudo nmap -O -sV -T4 --top-ports 100 -oX "$FIXTURES/sample_nmap_os.xml" "$LAB_SUBNET"

# 5. Single host, all ports
echo "[5/6] sample_nmap_single.xml — single host, all ports..."
nmap -sT -sV -T4 -p- -oX "$FIXTURES/sample_nmap_single.xml" "$SINGLE_HOST"

# 6. Empty scan (unreachable subnet)
echo "[6/6] sample_nmap_empty.xml — empty result fixture..."
nmap -sn -T4 -oX "$FIXTURES/sample_nmap_empty.xml" 172.20.99.0/24 || true
# nmap exits 0 even on empty results; the || true is for safety

echo ""
echo "==> Done. Fixture files:"
ls -lh "$FIXTURES/"*.xml

echo ""
echo "Next step: git add tests/fixtures/ && git commit -m 'test: add Phase 1 fixture XML files'"
