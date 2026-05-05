"""
tests/test_parser.py — Unit tests for scanner/parser.py

All 12 tests must pass before parser.py is considered complete.
Run: pytest tests/test_parser.py -v --tb=short

Fixtures are loaded from tests/fixtures/. Generate them first:
  nmap -sn -T4 -oX tests/fixtures/sample_nmap_quick.xml 172.20.0.0/24
  (see Section 4.2 of the Phase 1 plan for full generation commands)
"""

import ipaddress
import pathlib
import re
import pytest

from scanner.parser import parse_xml, parse_stream, classify_os_family, ParseError

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def load(filename: str) -> str:
    path = FIXTURES / filename
    if not path.exists():
        pytest.skip(f"Fixture not yet generated: {filename}  —  run nmap to create it")
    return path.read_text(encoding="utf-8")


# ── 1 ─────────────────────────────────────────────────────────────────────────

def test_parse_returns_list():
    xml = load("sample_nmap_quick.xml")
    result = parse_xml(xml)
    assert isinstance(result, list)
    assert len(result) > 0


# ── 2 ─────────────────────────────────────────────────────────────────────────

def test_host_has_required_fields():
    xml = load("sample_nmap_quick.xml")
    hosts = parse_xml(xml)
    required = {"ip", "mac", "hostname", "os_family", "status", "ports", "scan_time", "enriched"}
    for host in hosts:
        missing = required - host.keys()
        assert not missing, f"Host {host.get('ip')} is missing fields: {missing}"


# ── 3 ─────────────────────────────────────────────────────────────────────────

def test_ip_is_valid_ipv4():
    xml = load("sample_nmap_quick.xml")
    hosts = parse_xml(xml)
    for host in hosts:
        try:
            ipaddress.ip_address(host["ip"])
        except ValueError:
            pytest.fail(f"'{host['ip']}' is not a valid IPv4 address")


# ── 4 ─────────────────────────────────────────────────────────────────────────

def test_ports_are_parsed():
    xml = load("sample_nmap_ports.xml")
    hosts = parse_xml(xml)
    hosts_with_ports = [h for h in hosts if h["ports"]]
    assert len(hosts_with_ports) > 0, "Expected at least one host with open ports"
    for host in hosts_with_ports:
        for port in host["ports"]:
            assert "port"    in port
            assert "proto"   in port
            assert "state"   in port
            assert "service" in port
            assert isinstance(port["port"], int)


# ── 5 ─────────────────────────────────────────────────────────────────────────

def test_os_family_classification():
    assert classify_os_family("Linux 2.6.x")                    == "Linux"
    assert classify_os_family("Ubuntu 20.04")                   == "Linux"
    assert classify_os_family("Debian 11")                      == "Linux"
    assert classify_os_family("Windows 10")                     == "Windows"
    assert classify_os_family("Microsoft Windows Server 2019")  == "Windows"
    assert classify_os_family("Cisco IOS 15.x")                 == "Network"
    assert classify_os_family("Juniper Junos")                  == "Network"
    assert classify_os_family("Some Unknown Device")            == "Unknown"
    assert classify_os_family("")                               == "Unknown"
    assert classify_os_family(None)                             == "Unknown"


# ── 6 ─────────────────────────────────────────────────────────────────────────

def test_cpe_strings_extracted():
    xml = load("sample_nmap_full.xml")
    hosts = parse_xml(xml)
    all_cpes = [
        cpe
        for host in hosts
        for port in host["ports"]
        for cpe in port["cpes"]
    ]
    if len(all_cpes) == 0:
        pytest.skip(
            "No CPE strings in fixture — regenerate against a real target with "
            "nmap -sT -sV --top-ports 100. Will pass on TryHackMe (exit criterion 6)."
        )
    for cpe in all_cpes:
        assert cpe.startswith("cpe:/"), f"CPE does not start with 'cpe:/': {cpe}"


# ── 7 ─────────────────────────────────────────────────────────────────────────

def test_empty_scan_returns_empty_list():
    xml = load("sample_nmap_empty.xml")
    result = parse_xml(xml)
    assert result == [], f"Expected [], got {result}"


# ── 8 ─────────────────────────────────────────────────────────────────────────

def test_mac_address_format():
    xml = load("sample_nmap_ports.xml")
    hosts = parse_xml(xml)
    mac_pattern = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){5}$")
    for host in hosts:
        if host["mac"] is not None:
            assert mac_pattern.match(host["mac"]), \
                f"MAC '{host['mac']}' does not match expected format XX:XX:XX:XX:XX:XX"


# ── 9 ─────────────────────────────────────────────────────────────────────────

def test_enriched_field_is_false():
    xml = load("sample_nmap_quick.xml")
    hosts = parse_xml(xml)
    for host in hosts:
        assert host["enriched"] is False, \
            f"Host {host['ip']} has enriched={host['enriched']}, expected False"


# ── 10 ────────────────────────────────────────────────────────────────────────

def test_invalid_xml_raises_parse_error():
    malformed = "<<< this is not valid XML >>>"
    with pytest.raises(ParseError):
        parse_xml(malformed)


# ── 11 ────────────────────────────────────────────────────────────────────────

def test_single_host_scan():
    xml = load("sample_nmap_single.xml")
    hosts = parse_xml(xml)
    assert len(hosts) == 1, f"Expected exactly 1 host, got {len(hosts)}"
    assert len(hosts[0]["ports"]) > 0, "Single host scan should have open ports"


# ── 12 ────────────────────────────────────────────────────────────────────────

def test_no_os_detection_returns_none():
    xml = load("sample_nmap_quick.xml")
    hosts = parse_xml(xml)
    # quick/ping scan rarely returns OS data — hosts without OS block must return None
    for host in hosts:
        if host["os_detail"] is None:
            assert host["os_family"] is None, \
                f"Host {host['ip']}: os_detail is None but os_family is '{host['os_family']}'"
            assert host["os_conf"] is None, \
                f"Host {host['ip']}: os_detail is None but os_conf is '{host['os_conf']}'"


@pytest.mark.asyncio
async def test_parse_stream_yields_identical_hosts():
    """Test parse_stream() yields exactly the same hosts as parse_xml()"""
    xml = load("sample_nmap_quick.xml")
    lines = xml.splitlines()

    async def mock_line_iter():
        for line in lines:
            yield line

    streamed_hosts = []
    async for host in parse_stream(mock_line_iter()):
        streamed_hosts.append(host)

    static_hosts = parse_xml(xml)

    # Verify same count
    assert len(streamed_hosts) == len(static_hosts)

    # Verify each host is identical
    for streamed, static in zip(streamed_hosts, static_hosts):
        # ignore scan_time which is generated at parse time
        streamed.pop("scan_time")
        static.pop("scan_time")
        assert streamed == static
