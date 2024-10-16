"""Expose Audiobookshelf entries as a media source."""

from __future__ import annotations

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from . import AudiobookShelfClient, AudiobookshelfConfigEntry, AudiobookshelfError
from .api.models import Audiobook, Podcast
from .const import DOMAIN

ABS_MIMETYPE_TO_MIMETYPE = {
    "application/vnd.apple.mpegurl": "audio/mpeg",
}


async def async_get_media_source(hass: HomeAssistant) -> AudiobookshelfMediaSource:
    """Set up Audiobookshelf media source."""
    # Audiobookshelf supports only a single config entry
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    return AudiobookshelfMediaSource(hass, entry)


class AudiobookshelfMediaSource(MediaSource):
    """Setup Audiobookshelf media source."""

    name = "Audiobookshelf"

    def __init__(self, hass: HomeAssistant, entry: AudiobookshelfConfigEntry) -> None:
        """Init audiobookshelf media source."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.entry = entry

    @property
    def abs(self) -> AudiobookShelfClient:
        """Get the AudiobookshelfClient instance."""
        return self.entry.runtime_data

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Return media."""

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.CHANNEL,
            media_content_type=MediaType.MUSIC,
            title=self.entry.title,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=[*await self._async_build_libraries(item)],
        )

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a media item to a playable item."""
        category, _, abs_id = (item.identifier or "").partition("/")

        try:
            match category:
                case "audiobook":
                    playable = await self.abs.play_audiobook(abs_id)
                    if playable:
                        return PlayMedia(playable.url, playable.mime_type)
                case "podcast":
                    podcast_id, _, episode = abs_id.partition(":")
                    playable = await self.abs.play_podcast(podcast_id, episode)
                    if playable:
                        return PlayMedia(playable.url, playable.mime_type)

        except AudiobookshelfError as exception:
            raise Unresolvable(f"Cannot fetch item {item.identifier}") from exception

        raise Unresolvable("Failed to fetch!")

    async def _async_build_libraries(
        self, item: MediaSourceItem
    ) -> list[BrowseMediaSource]:
        """Get the libraries as root folders."""
        # Example: library/lib_c1u6t4p45c35rf0nzd
        category, _, abs_id = (item.identifier or "").partition("/")

        if category == "library" and abs_id:
            items: list[BrowseMediaSource] = []

            for library_item in await self.abs.library(abs_id):
                match library_item:
                    case Audiobook():
                        items.append(
                            BrowseMediaSource(
                                domain=DOMAIN,
                                identifier=f"audiobook/{library_item.id}",
                                media_class=MediaClass.TRACK,
                                media_content_type=MediaType.TRACK,
                                title=library_item.name,
                                can_play=True,
                                can_expand=False,
                                thumbnail=library_item.img,
                            )
                        )
                    case Podcast():
                        items.append(
                            BrowseMediaSource(
                                domain=DOMAIN,
                                identifier=f"podcast/{library_item.id}",
                                media_class=MediaClass.DIRECTORY,
                                media_content_type=MediaType.PODCAST,
                                title=library_item.name,
                                can_play=False,
                                can_expand=True,
                                thumbnail=library_item.img,
                            )
                        )

            return items

        if category == "item" and abs_id:
            return []

        if category == "podcast" and abs_id:
            episodes = await self.abs.get_podcast_episodes(abs_id)

            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"podcast/{episode.podcast_id}:{episode.id}",
                    media_class=MediaClass.PODCAST,
                    media_content_type=MediaType.EPISODE,
                    title=episode.title,
                    can_play=True,
                    can_expand=False,
                    thumbnail=episode.img,
                )
                for episode in episodes
            ]

        libraries = await self.abs.libraries()

        return [
            BrowseMediaSource(
                domain=DOMAIN,
                identifier=f"library/{library.id}",
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.MUSIC,
                title=library.name,
                can_play=False,
                can_expand=True,
            )
            for library in libraries
        ]
