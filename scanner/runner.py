"""
scanner/runner.py — Synchronous nmap subprocess launcher.

Phase 1 uses subprocess.run() for simplicity. subprocess.Popen() for
streaming is a Phase 2 concern. Do not introduce async here.
"""

import ipaddress
import json
import logging
import pathlib
import subprocess
import time
import uuid
from datetime import datetime, timezone

from scanner.profiles import get_profile_args, NmapNotFoundError

log = logging.getLogger(__name__)


# ─── Custom Exceptions ────────────────────────────────────────────────────────

class SubnetNotAllowedError(ValueError):
    """Raised when the target subnet is not in the allowed list."""
    pass


class PermissionStatementMissingError(RuntimeError):
    """Raised when config.legal.permission_statement is empty."""
    pass


class NmapExecutionError(RuntimeError):
    """Raised when nmap exits with a non-zero return code."""
    pass


# ─── Public API ───────────────────────────────────────────────────────────────

def run_scan(subnet: str, profile: str = "quick", config: dict | None = None) -> str:
    """
    Launch nmap against *subnet* using *profile* and return stdout XML.

    Legal guardrails (run in order before any subprocess is constructed):
      1. permission_statement must be non-empty in config.
      2. subnet must be within allowed_subnets whitelist.
      3. nmap binary must exist at configured path.

    Args:
        subnet:  Target CIDR range, e.g. '172.20.0.0/24'.
        profile: Named scan profile from scanner/profiles.py.
        config:  Parsed config.yaml dict. If None, RFC1918 defaults apply.

    Returns:
        Raw nmap XML output as a UTF-8 string.

    Raises:
        PermissionStatementMissingError, SubnetNotAllowedError,
        NmapNotFoundError, NmapExecutionError
    """
    config = config or {}

    # ── Guardrail 1: permission statement ────────────────────────────────────
    stmt = config.get("legal", {}).get("permission_statement", "")
    if not stmt or not stmt.strip():
        raise PermissionStatementMissingError(
            "config.legal.permission_statement is empty. "
            "Document your authorisation before scanning. See README.md#legal."
        )

    # ── Guardrail 2: subnet whitelist ─────────────────────────────────────────
    allowed = config.get("legal", {}).get(
        "allowed_subnets",
        ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
    )
    if not validate_subnet(subnet, allowed):
        raise SubnetNotAllowedError(
            f"Target subnet '{subnet}' is not in the allowed list: {allowed}. "
            "Only RFC1918 private ranges are permitted by default. "
            "See README.md#legal for more information."
        )

    # ── Build args (also validates nmap binary) ───────────────────────────────
    profile_args = get_profile_args(profile, config)
    args = build_nmap_args(profile_args, subnet)

    # ── Run scan ──────────────────────────────────────────────────────────────
    scan_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    log.info(f"[scan:{scan_id}] Starting — subnet={subnet} profile={profile}")
    log.info(f"[scan:{scan_id}] Command: {' '.join(args)}")

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute hard limit for Phase 1
        )
    except subprocess.TimeoutExpired:
        raise NmapExecutionError(
            f"nmap timed out after 300 seconds scanning '{subnet}'. "
            "Try a faster profile (e.g. 'quick') or a smaller subnet."
        )

    duration = (datetime.now(timezone.utc) - started_at).total_seconds()

    if result.returncode != 0:
        raise NmapExecutionError(
            f"nmap exited with code {result.returncode}.\n"
            f"stderr: {result.stderr.strip()}"
        )

    host_count = result.stdout.count("<host ")
    log.info(f"[scan:{scan_id}] Complete — duration={duration:.1f}s hosts~={host_count}")

    # ── Write append-only scan log ────────────────────────────────────────────
    _write_scan_log(
        scan_id=scan_id,
        subnet=subnet,
        profile=profile,
        permission=stmt,
        duration_s=round(duration, 2),
        host_count=host_count,
        config=config,
    )

    return result.stdout


def validate_subnet(subnet: str, allowed: list[str]) -> bool:
    """
    Return True if *subnet* is a subnet of any network in *allowed*.

    Args:
        subnet:  Target CIDR string.
        allowed: List of allowed CIDR strings.

    Returns:
        True if subnet is contained within at least one allowed network.

    Raises:
        ValueError: If *subnet* is not a valid CIDR string.
    """
    try:
        target = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        raise ValueError(f"'{subnet}' is not a valid CIDR notation.")

    for cidr in allowed:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
            if target.subnet_of(network):
                return True
        except ValueError:
            log.warning(f"Invalid CIDR in allowed_subnets: '{cidr}' — skipping.")

    return False


def build_nmap_args(profile_args: list[str], subnet: str) -> list[str]:
    """
    Construct the full nmap argument list.

    Output is always directed to stdout as XML (-oX -).
    """
    nmap_bin = "/usr/bin/nmap"  # profile validation already confirmed this exists
    return [nmap_bin] + profile_args + ["-oX", "-", subnet]


# ─── Private Helpers ──────────────────────────────────────────────────────────

def _write_scan_log(
    scan_id: str,
    subnet: str,
    profile: str,
    permission: str,
    duration_s: float,
    host_count: int,
    config: dict,
) -> None:
    """Append one JSON line to data/scan_log.jsonl."""
    output_dir = pathlib.Path(config.get("scanner", {}).get("output_dir", "data/sessions/"))
    log_path = output_dir.parent / "scan_log.jsonl"

    entry = {
        "scan_id":    scan_id,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "operator":   permission[:120],  # truncate for log readability
        "subnet":     subnet,
        "profile":    profile,
        "duration_s": duration_s,
        "host_count": host_count,
    }

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        log.warning(f"Could not write scan log: {e}")
