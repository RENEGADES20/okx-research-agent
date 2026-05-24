from __future__ import annotations

import argparse
import json

from .app import run
from .models import EventInput
from .service import EPIAgentService


def main() -> None:
    parser = argparse.ArgumentParser(prog="epi-agent")
    subcommands = parser.add_subparsers(dest="command", required=True)

    analyze = subcommands.add_parser("analyze", help="Create an Event Card from an event summary")
    analyze.add_argument("summary")
    analyze.add_argument("--source-type", default="manual")
    analyze.add_argument("--source-url")
    analyze.add_argument("--offline", action="store_true", help="Skip live Polymarket calls")

    server = subcommands.add_parser("serve", help="Run the local dashboard/API")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8080)

    recent = subcommands.add_parser("recent", help="Show recent Event Cards")
    recent.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()
    service = EPIAgentService()

    if args.command == "analyze":
        card = service.submit_event(
            EventInput(args.summary, source_type=args.source_type, source_url=args.source_url),
            live_markets=not args.offline,
        )
        print(json.dumps(card.to_dict(), ensure_ascii=False, indent=2))
    elif args.command == "serve":
        run(host=args.host, port=args.port)
    elif args.command == "recent":
        print(json.dumps(service.recent_cards(limit=args.limit), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
