"""
Asyncio WebSocket server for NetTopo Phase 2.

Listens on port 8765, accepts start_scan events, streams host_discovered events
to client as nmap discovers hosts.
"""

import sys
from pathlib import Path

# Add project root to sys.path so scanner/ is importable when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import json
import logging
import time
from typing import Optional
from datetime import datetime

import websockets
from websockets.exceptions import ConnectionClosed

from scanner.runner import run_scan_async
from scanner.parser import parse_stream
from scanner.profiles import get_profile_args

logger = logging.getLogger(__name__)

WEBSOCKET_PORT = 8765
PING_INTERVAL = 30
PROGRESS_INTERVAL = 5


async def scan_handler(websocket, subnet: str, profile: str = 'quick', config: dict = None):
    """
    Handle a single scan request, stream events to client.
    """
    started_at = time.monotonic()
    host_count = 0
    scan_id = datetime.utcnow().isoformat() + 'Z'

    await websocket.send(json.dumps({
        'type': 'scan_started',
        'scan_id': scan_id,
        'subnet': subnet,
        'profile': profile,
        'started_at': datetime.utcnow().isoformat() + 'Z'
    }))

    async def progress_reporter():
        """Send scan_progress events every PROGRESS_INTERVAL seconds"""
        while True:
            elapsed = time.monotonic() - started_at
            await websocket.send(json.dumps({
                'type': 'scan_progress',
                'pct_complete': 0,
                'hosts_found': host_count,
                'elapsed_s': int(elapsed)
            }))
            await asyncio.sleep(PROGRESS_INTERVAL)

    progress_task = asyncio.create_task(progress_reporter())

    try:
        async for host in parse_stream(run_scan_async(subnet, profile, config)):
            host_count += 1
            await websocket.send(json.dumps({
                'type': 'host_discovered',
                'data': host
            }))

    finally:
        progress_task.cancel()
        try:
            await progress_task
        except asyncio.CancelledError:
            pass

    duration = time.monotonic() - started_at
    await websocket.send(json.dumps({
        'type': 'scan_complete',
        'scan_id': scan_id,
        'total_hosts': host_count,
        'duration_s': int(duration)
    }))


async def handler(websocket, config: dict = None):
    """
    Main connection handler.
    """
    logger.info("WebSocket client connected")

    try:
        async for message in websocket:
            try:
                event = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    'type': 'scan_error',
                    'error': 'invalid_json',
                    'message': 'Message is not valid JSON'
                }))
                continue

            if event.get('type') == 'start_scan':
                subnet = event.get('subnet')
                profile = event.get('profile', 'quick')

                if not subnet:
                    await websocket.send(json.dumps({
                        'type': 'scan_error',
                        'error': 'missing_subnet',
                        'message': 'Missing required subnet field'
                    }))
                    continue

                try:
                    await scan_handler(websocket, subnet, profile, config)
                except Exception as e:
                    await websocket.send(json.dumps({
                        'type': 'scan_error',
                        'error': 'scan_failed',
                        'message': str(e)
                    }))

    except ConnectionClosed:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket handler error: {e}")


async def start_server(config: dict = None, host: str = '0.0.0.0', port: int = WEBSOCKET_PORT):
    """
    Start WebSocket server.
    """
    logger.info(f"Starting WebSocket server on ws://{host}:{port}")

    async def _handler(websocket):
        await handler(websocket, config)

    async with websockets.serve(
        _handler,
        host,
        port,
        ping_interval=PING_INTERVAL,
        ping_timeout=PING_INTERVAL * 2
    ):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    import yaml
    from pathlib import Path

    logging.basicConfig(level=logging.INFO)

    config_path = Path(__file__).parent.parent / 'config.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)

    asyncio.run(start_server(config))