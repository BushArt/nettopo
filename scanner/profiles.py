"""
scanner/profiles.py — Named scan profile registry.

Maps profile identifiers to nmap argument strings.
Adding a new profile never requires touching runner.py.
"""

import pathlib

# Profile ID → nmap argument string
# These are the canonical Phase 1 profiles. Do not add profiles here that
# have not been tested against at least one fixture file.
_PROFILES: dict[str, str] = {
    "quick":   "-sn -T4",
    "ports":   "-sS -T4 --top-ports 100",
    "full":    "-sV -sC -T4 -p-",
    "os":      "-O -sV -T4 --top-ports 1000",
    "stealth": "-sS -T2 --top-ports 100 -f",
    "vuln":    "--script vuln -sV --top-ports 100",
}


def get_profile_args(profile_id: str, config: dict | None = None) -> list[str]:
    """
    Return nmap argument list for the given profile ID.

    Args:
        profile_id: One of the registered profile names (e.g. 'quick').
        config:     Parsed config.yaml dict. Used to validate nmap binary path.

    Returns:
        List of nmap argument strings (e.g. ['-sn', '-T4']).

    Raises:
        ValueError: If profile_id is not registered (not KeyError — avoids
                    leaking implementation details to callers).
        NmapNotFoundError: If nmap binary is not found at the configured path.
    """
    if profile_id not in _PROFILES:
        available = ", ".join(sorted(_PROFILES.keys()))
        raise ValueError(
            f"Unknown scan profile '{profile_id}'. "
            f"Available profiles: {available}"
        )

    # Validate nmap binary exists before returning args
    nmap_path = _get_nmap_path(config)
    if not pathlib.Path(nmap_path).exists():
        raise NmapNotFoundError(
            f"nmap binary not found at '{nmap_path}'. "
            f"Install with: sudo apt install nmap  (or update scanner.nmap_binary in config.yaml)"
        )

    return _PROFILES[profile_id].split()


def list_profiles() -> dict[str, str]:
    """Return a copy of the full profile registry (id → args string)."""
    return dict(_PROFILES)


def _get_nmap_path(config: dict | None) -> str:
    """Extract nmap binary path from config, falling back to default."""
    if config and "scanner" in config:
        return config["scanner"].get("nmap_binary", "/usr/bin/nmap")
    return "/usr/bin/nmap"


class NmapNotFoundError(FileNotFoundError):
    """Raised when the nmap binary cannot be found at the configured path."""
    pass
