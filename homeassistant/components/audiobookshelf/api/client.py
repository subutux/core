"""A Audiobookshelf API Client."""

import asyncio
from dataclasses import dataclass
import logging
import socket

import aiohttp

from .models import Audiobook, Episode, Library, Playable, Podcast

_LOGGER = logging.getLogger(__package__)

TIMEOUT = 10


class AudiobookshelfError(Exception):
    """Overall Error exception."""

    def __init__(self, *args) -> None:  # noqa: D107
        super().__init__(*args)


class AudiobookshelfConnectionError(AudiobookshelfError):
    """connection Error exception."""


class AudiobookshelfParseError(AudiobookshelfError):
    """Parse Error exception."""


class AudiobookshelfFailedResponseError(AudiobookshelfError):
    """Failed response Error exception."""


@dataclass
class Credential:
    """datclass to store possible credentials."""

    username: str | None = None
    password: str | None = None
    token: str | None = None

    def has_token(self) -> bool:
        """Check if the credential has a token set."""
        return self.token is not None

    def is_invalid(self) -> bool:
        """Check if the credential is valid."""
        return not (self.username or self.password) and not self.token


class AudiobookShelfClient:
    """API Client for AudiobookShelf."""

    def __init__(
        self, host: str, credentials: Credential, session: aiohttp.ClientSession
    ) -> None:
        """Initialize the Audiobookshelf client."""

        self.credentials = credentials
        self.host = host
        self._session = session

    async def login(self) -> bool:
        """Validate and try to login."""

        if self.credentials.has_token():
            return True

        if self.credentials.is_invalid():
            return False

        response = await self.request(
            "POST",
            "login",
            data={
                "username": self.credentials.username,
                "password": self.credentials.password,
            },
        )

        token = response.get("user", []).get("token", None)
        if token:
            self.credentials.token = token
            return True
        return False

    async def request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> dict:
        """Get information from the API."""

        if not headers:
            headers = {}
        if not self.credentials.has_token():
            if not self.login():
                raise AudiobookshelfError("Unable to login")

        headers = {**headers, "Authorization": f"Bearer {self.credentials.token}"}

        try:
            async with asyncio.timeout(TIMEOUT):  # loop=asyncio.get_event_loop()
                response = await self._session.request(
                    method,
                    f"{self.host}/{endpoint}",
                    headers=headers,
                    json=data,
                )
                if response.status >= 200 and response.status < 300:
                    return await response.json()

                response.raise_for_status()

        except TimeoutError as exception:
            _LOGGER.error(
                "Timeout error fetching information from %s - %s",
                endpoint,
                exception,
            )

            raise AudiobookshelfConnectionError from exception

        except (KeyError, TypeError) as exception:
            _LOGGER.error(
                "Error parsing information from %s - %s",
                endpoint,
                exception,
            )

            raise AudiobookshelfParseError from exception

        except aiohttp.ClientResponseError as exception:
            _LOGGER.error(
                "Failed response from %s - %s",
                endpoint,
                exception,
            )

            raise AudiobookshelfFailedResponseError from exception

        except (aiohttp.ClientError, socket.gaierror) as exception:
            _LOGGER.error(
                "Error fetching information from %s - %s",
                endpoint,
                exception,
            )
            raise AudiobookshelfConnectionError from exception

        return {}

    async def libraries(self) -> list[Library]:
        """Return available libraries."""

        response = await self.request("GET", "/api/libraries")
        return [
            Library(
                id=lib["id"],
                media_type=lib["mediaType"],
                name=lib["name"],
                provider=lib["provider"],
            )
            for lib in response.get("libraries", [])
        ]

    def cover_url_for_item(self, item_id: str) -> str:
        """Generate the url for the cover image of the item."""

        return f"{self.host}/api/items/{item_id}/cover?raw=0&format=jpeg&token={self.credentials.token}"

    def authenticated_playable_url(self, url: str) -> str:
        """Get an authenticated playable URL from abs."""

        return f"{self.host}{url}?token={self.credentials.token}"

    async def library(self, library_id: str) -> list[Podcast | Audiobook]:
        """Get library items."""

        items: list[Podcast | Audiobook] = []

        response = await self.request(
            "GET",
            f"/api/libraries/{library_id}/items?limit=0&sort=media.metadata.title&minified=1",
        )

        for result in response.get("results", []):
            if result["mediaType"] == "book":
                items.append(
                    Audiobook(
                        id=result["id"],
                        name=result["media"]["metadata"]["title"],
                        img=self.cover_url_for_item(result["id"]),
                    )
                )
            if result["mediaType"] == "podcast":
                items.append(
                    Podcast(
                        id=result["id"],
                        name=result["media"]["metadata"]["title"],
                        img=self.cover_url_for_item(result["id"]),
                    )
                )

        return items

    async def play_audiobook(
        self, item_id: str, supported_mime: list[str] | None = None
    ) -> Playable | None:
        """Get a playable for an audiobook."""

        if not supported_mime:
            supported_mime = [
                "audio/flac",
                "audio/mpeg",
                "audio/mp4",
                "audio/ogg",
                "audio/aac",
                "audio/webm",
            ]

        response = await self.request(
            "POST",
            f"api/items/{item_id}/play",
            data={
                "deviceInfo": {
                    "clientVersion": "0.0.1",
                    "deviceId": "home-assistant",
                    "clientName": "Home Assistant",
                },
                "supportedMimeTypes": supported_mime,
            },
        )
        if response:
            return Playable(
                id=response["id"],
                name=response["mediaMetadata"]["title"],
                url=self.authenticated_playable_url(
                    response["audioTracks"][0]["contentUrl"]
                ),
                img=self.cover_url_for_item(response["id"]),
                mime_type=response["audioTracks"][0]["mimeType"],
            )
        return None

    async def get_podcast_episodes(self, item_id: str) -> list[Episode]:
        """Get available podcast episodes."""
        response = await self.request(
            "GET", f"/api/items/{item_id}?expanded=1&include=downloads"
        )

        return [
            Episode(
                id=episode["id"],
                podcast_id=episode["libraryItemId"],
                episode=episode["episode"],
                title=episode["title"],
                img=self.cover_url_for_item(episode["libraryItemId"]),
            )
            for episode in response["media"]["episodes"]
        ]

    async def play_podcast(
        self, podcast_id: str, episode: str, supported_mime: list[str] | None = None
    ) -> Playable | None:
        """Get a playable for an audiobook."""

        if not supported_mime:
            supported_mime = [
                "audio/flac",
                "audio/mpeg",
                "audio/mp4",
                "audio/ogg",
                "audio/aac",
                "audio/webm",
            ]

        response = await self.request(
            "POST",
            f"api/items/{podcast_id}/play/{episode}",
            data={
                "deviceInfo": {
                    "clientVersion": "0.0.1",
                    "deviceId": "home-assistant",
                    "clientName": "Home Assistant",
                },
                "supportedMimeTypes": supported_mime,
            },
        )
        if response:
            return Playable(
                id=response["id"],
                name=response["mediaMetadata"]["title"],
                url=self.authenticated_playable_url(
                    response["audioTracks"][0]["contentUrl"]
                ),
                img=self.cover_url_for_item(response["id"]),
                mime_type=response["audioTracks"][0]["mimeType"],
            )
        return None
