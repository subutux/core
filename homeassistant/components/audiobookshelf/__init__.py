"""The Audiobookshelf integration."""

from __future__ import annotations

import socket

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api.client import AudiobookShelfClient, AudiobookshelfError, Credential

PLATFORMS: list[Platform] = []

type AudiobookshelfConfigEntry = ConfigEntry[AudiobookShelfClient]  # noqa: F821


async def async_setup_entry(
    hass: HomeAssistant, entry: AudiobookshelfConfigEntry
) -> bool:
    """Set up Audiobookshelf from a config entry."""

    session = async_get_clientsession(hass)
    adp = AudiobookShelfClient(
        entry.data[CONF_HOST],
        Credential(
            username=entry.data[CONF_USERNAME], password=entry.data[CONF_PASSWORD]
        ),
        session,
    )

    try:
        await adp.login()
    except (
        KeyError,
        TypeError,
        aiohttp.ClientError,
        socket.gaierror,
        AudiobookshelfError,
    ) as err:
        raise ConfigEntryNotReady("Could not connect") from err

    entry.runtime_data = adp

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AudiobookshelfConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
