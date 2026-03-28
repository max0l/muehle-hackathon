"""Helpers for opening or joining a Mühle game on the remote HTTP API."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from openapi_client import DefaultApi
from openapi_client.models.add_player200_response import AddPlayer200Response
from openapi_client.models.create_game201_response import CreateGame201Response

DEFAULT_PLAYER_NAME = "team 1"
DEFAULT_API_HOST = "http://172.28.40.187:40000"


def resolve_game_id(api: DefaultApi, game_id: Optional[UUID]) -> UUID:
    """Return ``game_id`` if set; otherwise create a game and print its id."""
    if game_id is not None:
        return game_id
    created: CreateGame201Response = api.create_game()
    print("Game created with id: ", created.id)
    return created.id


def join_as_player(
    api: DefaultApi,
    game_id: UUID,
    player_name: str,
) -> AddPlayer200Response:
    """Register as a player in the given game."""
    return api.add_player(game_id, player_name)
