"""CLI for the SmartSignalHub-aware assistant."""

from __future__ import annotations

import argparse

from .engine import answer_question
from .regression import run_regression
from .server import DEFAULT_HOST, DEFAULT_PORT, serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m platform_v2.tools.ai_assistant")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask_parser = subparsers.add_parser("ask", help="Ask a SmartSignalHub runtime question.")
    ask_parser.add_argument("question", nargs="+", help="Natural-language question.")
    ask_parser.add_argument("--model", default=None, help="Optional answer composer, e.g. ollama:qwen2.5-coder:7b")

    serve_parser = subparsers.add_parser("serve", help="Run the local browser chat server.")
    serve_parser.add_argument("--host", default=DEFAULT_HOST, help=f"Bind host. Default: {DEFAULT_HOST}")
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Bind port. Default: {DEFAULT_PORT}")
    serve_parser.add_argument("--model", default=None, help="Optional answer composer, e.g. ollama:qwen2.5-coder:7b")

    subparsers.add_parser("regression", help="Run assistant routing regression checks.")

    args = parser.parse_args(argv)
    if args.command == "ask":
        question = " ".join(args.question).strip()
        print(answer_question(question, model=args.model))
        return 0
    if args.command == "serve":
        serve(host=args.host, port=args.port, model=args.model)
        return 0
    if args.command == "regression":
        print(run_regression())
        return 0
    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
