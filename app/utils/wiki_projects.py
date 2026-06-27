from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv


load_dotenv()


WIKI_API_URL = (
    "https://api.enterprise.wikimedia.com/v2/projects"
)


def get_projects() -> dict:
    """
    Retrieve Wikimedia projects.
    """

    token = os.getenv("WIKI_ACCESS_TOKEN")

    if not token:
        raise ValueError(
            "WIKI_ACCESS_TOKEN not found in .env"
        )

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": (
            "Travelara/1.0 "
            "(support@travelara.ai)"
        ),
    }

    with httpx.Client(
        headers=headers,
        timeout=30,
        follow_redirects=True,
        http2=True,
    ) as client:

        response = client.get(
            WIKI_API_URL
        )

        print("STATUS:", response.status_code)

        response.raise_for_status()

        return response.json()


def main():

    data = get_projects()

    print(data)


if __name__ == "__main__":
    main()