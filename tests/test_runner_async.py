"""
Unit tests for async streaming nmap runner.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from scanner.runner import run_scan_async, SubnetNotAllowedError, PermissionStatementMissingError


@pytest.mark.asyncio
async def test_async_guardrails_permission_statement():
    """Test missing permission statement raises correct error"""
    with pytest.raises(PermissionStatementMissingError):
        async for _ in run_scan_async("172.20.0.0/24", config={"legal": {"permission_statement": ""}}):
            pass


@pytest.mark.asyncio
async def test_async_guardrails_subnet_whitelist():
    """Test public subnet is rejected"""
    config = {
        "legal": {
            "permission_statement": "test",
            "allowed_subnets": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
        }
    }

    with pytest.raises(SubnetNotAllowedError):
        async for _ in run_scan_async("8.8.8.0/24", config=config):
            pass


@pytest.mark.asyncio
async def test_async_running_against_allowed_subnet():
    """Test allowed subnet passes guardrails"""
    config = {
        "legal": {
            "permission_statement": "test",
            "allowed_subnets": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
        }
    }

    with patch('asyncio.create_subprocess_exec') as mock_exec, \
         patch('scanner.profiles.pathlib.Path.exists', return_value=True):
        mock_process = MagicMock()
        mock_lines = [b'<?xml version="1.0" encoding="UTF-8"?>\n', b'']
        async def mock_readline():
            if mock_lines:
                return mock_lines.pop(0)
            return b''
        async def mock_wait():
            return 0
        mock_process.stdout.readline = mock_readline
        mock_process.wait = mock_wait
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        received_lines = []
        async for line in run_scan_async("172.20.0.0/24", config=config):
            received_lines.append(line)

        assert len(received_lines) == 1
        assert received_lines[0] == '<?xml version="1.0" encoding="UTF-8"?>'


@pytest.mark.asyncio
async def test_async_multiple_lines_streamed():
    """Test multiple lines are yielded in order"""
    config = {
        "legal": {
            "permission_statement": "test",
            "allowed_subnets": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
        }
    }

    test_lines = [
        b'line1\n',
        b'<host>test</host>\n',
        b'line3\n',
        b''  # EOF
    ]

    with patch('asyncio.create_subprocess_exec') as mock_exec, \
         patch('scanner.profiles.pathlib.Path.exists', return_value=True):
        mock_process = MagicMock()
        async def mock_readline():
            return test_lines.pop(0)
        async def mock_wait():
            return 0
        mock_process.stdout.readline = mock_readline
        mock_process.wait = mock_wait
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        received = []
        async for line in run_scan_async("172.20.0.0/24", config=config):
            received.append(line)

        assert received == ["line1", "<host>test</host>", "line3"]


@pytest.mark.asyncio
async def test_async_process_cleanup_on_exception():
    """Test subprocess is killed properly on timeout"""
    config = {
        "legal": {
            "permission_statement": "test",
            "allowed_subnets": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
        }
    }

    with patch('asyncio.create_subprocess_exec') as mock_exec, \
         patch('scanner.profiles.pathlib.Path.exists', return_value=True):
        mock_process = MagicMock()
        async def mock_readline():
            await asyncio.sleep(0.01)
            return b''
        async def mock_wait():
            return None
        mock_process.stdout.readline = mock_readline
        mock_process.kill = MagicMock()
        mock_process.wait = mock_wait
        mock_process.returncode = None
        mock_exec.return_value = mock_process

        try:
            async for line in run_scan_async("172.20.0.0/24", config=config):
                pass
        except Exception:
            pass

        # Verify process was killed
        mock_process.kill.assert_called_once()