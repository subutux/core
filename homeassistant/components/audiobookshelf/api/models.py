"""Collection of models returned by the client."""

from dataclasses import dataclass


@dataclass
class Library:
    """dataclass representing basic info about a library."""

    id: str
    name: str
    media_type: str
    provider: str


@dataclass
class Podcast:
    """Represents a Audiobookshelf podcast."""

    id: str
    name: str
    img: str


@dataclass
class Audiobook:
    """Represents a Audiobookshelf Audiobook."""

    id: str
    name: str
    img: str


@dataclass
class Playable:
    """Represents a Playable item from Audiobookshelf."""

    id: str
    name: str
    img: str
    url: str
    mime_type: str


@dataclass
class Episode:
    """Represents a Audiobookshelf podcast episode."""

    id: str
    podcast_id: str
    episode: str
    title: str
    img: str
