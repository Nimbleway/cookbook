#!/usr/bin/env python3
"""Entry point for the Live Docs Grounding Agent web app.

Run with: python app.py
Then open the printed URL in your browser.

This starts the FastAPI server in server.py, which reuses agent.py's
Task Agents API client/config logic unchanged — this file and server.py
are presentation-layer only.
"""

import uvicorn

HOST = "127.0.0.1"
PORT = 8420


def main() -> None:
    print(f"\n📚 Live Docs Grounding Agent\n   http://{HOST}:{PORT}\n")
    uvicorn.run("server:app", host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
