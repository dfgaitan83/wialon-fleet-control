"""Paginación del lado del servidor, común a todos los listados (ARQ-04).

Mismo contrato en toda la API: ``{items, total, page, page_size}``.
"""

from dataclasses import dataclass

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100  # tope: nadie puede pedir 1 millón de filas de una vez


@dataclass(frozen=True)
class PageRequest:
    page: int = 1  # empieza en 1 (lo natural para el usuario)
    page_size: int = DEFAULT_PAGE_SIZE

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True)
class Page[T]:
    items: list[T]
    total: int
    page: int
    page_size: int
