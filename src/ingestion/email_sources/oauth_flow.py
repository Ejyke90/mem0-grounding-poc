"""One-time OAuth authorization CLI for Gmail and Yahoo.

Usage:
    python -m src.ingestion.email_sources.oauth_flow --provider gmail
    python -m src.ingestion.email_sources.oauth_flow --provider yahoo

Run once per provider from a terminal on this machine. The flow opens a
browser for the provider's consent screen; afterwards, the token is cached
under oauth_token_dir and all fetches work non-interactively.
"""

import argparse

from src.ingestion.email_sources.oauth_manager import (
    run_gmail_oauth_flow,
    run_yahoo_oauth_flow,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the one-time OAuth2 authorization flow for an email provider."
    )
    parser.add_argument(
        "--provider", required=True, choices=["gmail", "yahoo"], help="Email provider to authorize"
    )
    args = parser.parse_args()

    if args.provider == "gmail":
        run_gmail_oauth_flow()
    else:
        run_yahoo_oauth_flow()


if __name__ == "__main__":
    main()
