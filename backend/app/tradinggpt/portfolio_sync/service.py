from __future__ import annotations

from collections.abc import Iterable

from .base import PortfolioProvider
from .models import PortfolioSnapshot
from .paper import PaperPortfolioProvider


class UnsupportedPortfolioSourceError(
    ValueError
):
    pass


class PortfolioSyncService:
    def __init__(
        self,
        *,
        providers: Iterable[
            PortfolioProvider
        ] | None = None,
    ) -> None:
        configured_providers = list(
            providers
            if providers is not None
            else [PaperPortfolioProvider()]
        )

        self._providers = {
            provider.source.upper(): provider
            for provider in configured_providers
        }

    def supports(
        self,
        source: str,
    ) -> bool:
        return source.upper() in self._providers

    def get_snapshot(
        self,
        *,
        source: str = "PAPER",
    ) -> PortfolioSnapshot:
        normalized_source = source.upper()
        provider = self._providers.get(
            normalized_source
        )

        if provider is None:
            raise UnsupportedPortfolioSourceError(
                "Unsupported portfolio source: "
                f"{normalized_source}."
            )

        return provider.get_snapshot()
