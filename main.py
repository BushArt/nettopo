"""
Phase 2 entry point: runs WebSocket server + HTTP static file server in single event loop.
"""

import asyncio
import logging
import sys
from pathlib import Path

import yaml
from aiohttp import web

from server.ws_server import start_server as start_ws_server

logger = logging.getLogger(__name__)

HTTP_PORT = 8080
WEBSOCKET_PORT = 8765


async def start_http_server(host: str = '0.0.0.0', port: int = HTTP_PORT):
    """
    Start aiohttp static file server serving project root.
    """
    app = web.Application()

    # Serve entire project root as static files (same as `python -m http.server`)
    project_root = Path(__file__).parent
    app.add_routes([web.static('/', project_root, show_index=True)])

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"HTTP server running on http://{host}:{port}")


async def main():
    """
    Start both servers in shared event loop.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    # Load config
    config_path = Path(__file__).parent / 'config.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Start both servers
    await asyncio.gather(
        start_ws_server(config, port=WEBSOCKET_PORT),
        start_http_server(port=HTTP_PORT)
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down")
        sys.exit(0)