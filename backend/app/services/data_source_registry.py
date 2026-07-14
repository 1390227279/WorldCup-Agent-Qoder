"""Trusted external source registry; callers select an ID, never an arbitrary URL."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FetchSource:
    id: str
    name: str
    url: str
    expected_content_types: tuple[str, ...]


FETCH_SOURCES: dict[str, FetchSource] = {
    "openfootball_worldcup_2022": FetchSource(
        id="openfootball_worldcup_2022",
        name="openfootball",
        url="https://raw.githubusercontent.com/openfootball/worldcup/master/2022--qatar/cup.json",
        expected_content_types=("application/json", "text/plain"),
    ),
}


def get_fetch_source(source_id: str) -> FetchSource | None:
    return FETCH_SOURCES.get(source_id)
