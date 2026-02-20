from __future__ import annotations

import argparse

import uvicorn

from dnd_cli.server.app import create_app
from dnd_cli.server.config import ServerConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cryptclash-server", description="Crypt Clash online server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    return parser


def run() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = ServerConfig.from_env()
    app = create_app(config)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    run()
