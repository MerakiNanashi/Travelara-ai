import httpx
from dotenv import load_dotenv
import os

load_dotenv()

# required for tokens; saved in .env
ADMIN = os.getenv("WIKI_ADMIN")
PASS = os.getenv("WIKI_PASS")


WIKIMEDIA_AUTH_URL = (
    "https://auth.enterprise.wikimedia.com/v1/login"
)


def get_wikimedia_tokens(
    username: str,
    password: str,
) -> dict:
    """
    Authenticate with Wikimedia Enterprise API
    and return access/id/refresh tokens.
    """

    payload = {
        "username": username,
        "password": password,
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Travelara/1.0",
    }

    with httpx.Client(
        headers=headers,
        timeout=30,
        follow_redirects=True,
        http2=True,
    ) as client:

        response = client.post(
            WIKIMEDIA_AUTH_URL,
            json=payload,
        )

        response.raise_for_status()

        return response.json()


def main():

    tokens = get_wikimedia_tokens(
        username=ADMIN,
        password=PASS,
    )

    # print(tokens)

    print(tokens['access_token'], '\n')
    print(tokens['refresh_token'], '\n')
    # Add tokens to .env


if __name__ == "__main__":
    main()