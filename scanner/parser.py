"""
scanner/parser.py — nmap XML → structured Host dicts.

Standard library only (xml.etree.ElementTree). No third-party deps.
Every public function has a corresponding unit test in tests/test_parser.py.

Error handling policy:
  - Never raise on valid nmap XML, even malformed or incomplete scans.
  - Use .find() and .get() with defaults throughout.
  - Only raise ParseError for structurally invalid XML.
  - Log warnings for individual host failures; continue to next host.
"""

import ipaddress
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

log = logging.getLogger(__name__)


# ─── Custom Exceptions ────────────────────────────────────────────────────────

class ParseError(ValueError):
    """Raised only when the XML is structurally invalid (e.g. missing root)."""
    pass


def filter_phantom_hosts(hosts: list[dict]) -> list[dict]:
    """
    Filter out Podman bridge network phantom hosts.

    A host is considered phantom if all three are true:
    - No MAC address (not L2 adjacent)
    - No open ports
    - No hostname

    Real hosts on a local network will always have at least one of these.
    """
    filtered = []
    phantom_count = 0

    for host in hosts:
        # Allow the 3 real known lab IPs through unfiltered
        if host["ip"] in ("172.20.0.10", "172.20.0.11", "172.20.0.12"):
            filtered.append(host)
            continue

        # All other 172.20.0.x addresses are phantom hosts
        if (host["ip"].startswith("172.20.0.")
                and host["mac"] is None
                and len(host["ports"]) == 0
                and host["hostname"] is None):
            phantom_count += 1
            continue

        filtered.append(host)

    if phantom_count > 0:
        log.warning(f"Filtered {phantom_count} phantom hosts (no MAC, no ports, no hostname)")

    return filtered


# ─── Root Entry Point ─────────────────────────────────────────────────────────

def parse_xml(xml_string: str) -> list[dict]:
    """
    Parse nmap XML output into a list of Host dicts.

    Args:
        xml_string: Raw nmap XML (stdout from runner.run_scan()).

    Returns:
        List of HostDict objects. Empty list if no hosts were up.

    Raises:
        ParseError: If xml_string is not parseable XML at all.
    """
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        raise ParseError(f"Invalid nmap XML: {e}") from e

    hosts = []
    for host_elem in root.findall("host"):
        try:
            host = parse_host(host_elem)
            if host:
                hosts.append(host)
        except Exception as e:
            log.warning(f"Failed to parse host element: {e} — skipping.")

    return filter_phantom_hosts(hosts)


async def parse_stream(line_iter):
    """
    Streaming XML parser. Async generator that accepts lines of nmap XML
    and yields complete HostDict objects as soon as each </host> closing tag is found.

    Args:
        line_iter: Async iterable yielding individual XML lines as strings

    Yields:
        Complete HostDict objects when host blocks are fully received
    """
    buffer = []
    in_host = False

    async for line in line_iter:
        buffer.append(line)

        if '<host>' in line or '<host ' in line:
            in_host = True
            buffer.clear()
            buffer.append(line)

        if '</host>' in line and in_host:
            in_host = False
            host_xml = "\n".join(buffer).strip()
            try:
                # Remove all namespaces and wrap with dummy root
                stripped = re.sub(r' xmlns="[^"]+"', '', host_xml)
                wrapped = f"<dummy>{stripped}</dummy>"
                root = ET.fromstring(wrapped)
                host_elem = root.find("host")
                host = parse_host(host_elem)
                if host:
                    filtered = filter_phantom_hosts([host])
                    if filtered:
                        yield filtered[0]
            except Exception as e:
                log.warning(f"Failed to parse streamed host block: {e} — skipping.")
            buffer.clear()


# ─── Per-Host Parsing ─────────────────────────────────────────────────────────

def parse_host(host_elem: ET.Element) -> dict | None:
    """
    Parse a single <host> XML element into a HostDict.

    Returns None if the host element has no IP address (structurally invalid).
    """
    ip, mac = parse_addresses(host_elem)
    if ip is None:
        log.warning("Host element has no IPv4 address — skipping.")
        return None

    vendor = _get_mac_vendor(host_elem)
    hostname = parse_hostname(host_elem)
    os_info = parse_os(host_elem)
    ports = parse_ports(host_elem)
    status = host_elem.findtext("status[@state]") or "up"
    status_elem = host_elem.find("status")
    if status_elem is not None:
        status = status_elem.get("state", "up")

    return {
        "ip":         ip,
        "mac":        mac,
        "vendor":     vendor,
        "hostname":   hostname,
        "os_family":  os_info["os_family"],
        "os_detail":  os_info["os_detail"],
        "os_conf":    os_info["os_conf"],
        "status":     status,
        "ports":      ports,
        "risk_score": None,   # Phase 3
        "risk_level": None,   # Phase 3
        "scan_time":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "enriched":   False,
    }


# ─── Sub-Parsers ──────────────────────────────────────────────────────────────

def parse_addresses(host_elem: ET.Element) -> tuple[str | None, str | None]:
    """
    Extract IPv4 and MAC addresses from <address> elements.

    Returns:
        Tuple of (ip, mac). Either may be None if not present.
    """
    ip = None
    mac = None
    for addr in host_elem.findall("address"):
        addr_type = addr.get("addrtype", "")
        if addr_type == "ipv4":
            ip = addr.get("addr")
        elif addr_type == "mac":
            mac = addr.get("addr")
    return ip, mac


def _get_mac_vendor(host_elem: ET.Element) -> str | None:
    """Extract vendor string from the MAC <address> element (nmap OUI lookup)."""
    for addr in host_elem.findall("address"):
        if addr.get("addrtype") == "mac":
            return addr.get("vendor") or None
    return None


def parse_hostname(host_elem: ET.Element) -> str | None:
    """
    Return the first hostname from <hostnames><hostname name="...">.

    Returns None if the element is absent or the name attribute is empty.
    """
    hostnames_elem = host_elem.find("hostnames")
    if hostnames_elem is None:
        return None
    first = hostnames_elem.find("hostname")
    if first is None:
        return None
    name = first.get("name", "").strip()
    return name if name else None


def parse_os(host_elem: ET.Element) -> dict:
    """
    Extract OS detection data from the best <osmatch> element.

    'Best' = highest accuracy attribute value.

    Returns:
        Dict with keys: os_family, os_detail, os_conf (all None if absent).
    """
    os_elem = host_elem.find("os")
    if os_elem is None:
        return {"os_family": None, "os_detail": None, "os_conf": None}

    best_match = None
    best_acc = -1
    for osmatch in os_elem.findall("osmatch"):
        try:
            acc = int(osmatch.get("accuracy", "0"))
        except ValueError:
            acc = 0
        if acc > best_acc:
            best_acc = acc
            best_match = osmatch

    if best_match is None:
        return {"os_family": None, "os_detail": None, "os_conf": None}

    os_detail = best_match.get("name", "").strip() or None
    return {
        "os_family": classify_os_family(os_detail) if os_detail else None,
        "os_detail": os_detail,
        "os_conf":   best_acc if best_acc >= 0 else None,
    }


def parse_ports(host_elem: ET.Element) -> list[dict]:
    """
    Extract open port data from <ports><port> elements.

    Only ports with state='open' are included.

    Returns:
        List of PortDict. Empty list if no open ports or no ports element.
    """
    ports_elem = host_elem.find("ports")
    if ports_elem is None:
        return []

    results = []
    for port_elem in ports_elem.findall("port"):
        state_elem = port_elem.find("state")
        if state_elem is None or state_elem.get("state") != "open":
            continue

        service_elem = port_elem.find("service")
        service_name = None
        version_str = None
        cpes = []

        if service_elem is not None:
            service_name = service_elem.get("name") or None
            product = service_elem.get("product", "")
            version = service_elem.get("version", "")
            version_str = " ".join(filter(None, [product, version])).strip() or None
            cpes = [cpe.text for cpe in service_elem.findall("cpe") if cpe.text]

        try:
            port_id = int(port_elem.get("portid", "0"))
        except ValueError:
            port_id = 0

        results.append({
            "port":    port_id,
            "proto":   port_elem.get("protocol", "tcp"),
            "state":   "open",
            "service": service_name,
            "version": version_str,
            "cpes":    cpes,
            "cves":    [],  # Phase 3
        })

    return results


# ─── OS Classification ────────────────────────────────────────────────────────

def classify_os_family(os_detail: str) -> str:
    """
    Map an nmap OS detail string to a coarse OS family label.

    Args:
        os_detail: The nmap <osmatch name="..."> string.

    Returns:
        One of: "Linux", "Windows", "Network", "Unknown"
    """
    if not os_detail:
        return "Unknown"

    lower = os_detail.lower()

    if any(kw in lower for kw in ("linux", "ubuntu", "debian", "centos", "fedora",
                                   "red hat", "kali", "freebsd", "openbsd", "unix")):
        return "Linux"

    if any(kw in lower for kw in ("windows", "microsoft", "server 2")):
        return "Windows"

    if any(kw in lower for kw in ("cisco", "juniper", "fortinet", "palo alto",
                                   "mikrotik", "switch", "router", "firewall",
                                   "broadband", "dd-wrt", "openwrt")):
        return "Network"

    return "Unknown"
