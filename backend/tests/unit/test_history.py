"""Historial RF-24: validación de rango, estadísticas, muestreo y lista blanca de mensajes."""

from datetime import UTC, datetime, timedelta

import pytest

from app.application.errors import ValidationFailed
from app.application.history_service import (
    HistoryService,
    downsample,
    haversine_km,
)
from app.domain.fleet import Position
from app.infrastructure.wialon.mappers import message_to_position
from app.infrastructure.wialon.raw_models import parse_messages

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)


def _pos(minute: int, lat: float, lon: float, speed: float = 30.0) -> Position:
    return Position(lat, lon, speed, 90, NOW - timedelta(hours=2) + timedelta(minutes=minute))


class FakeTrackGateway:
    def __init__(self, points: list[Position]) -> None:
        self.points = points
        self.calls = 0

    async def track(self, vehicle_id: int, start: datetime, end: datetime) -> list[Position]:
        self.calls += 1
        return list(self.points)


def _service(points: list[Position]) -> tuple[HistoryService, FakeTrackGateway]:
    gateway = FakeTrackGateway(points)
    return HistoryService(gateway, clock=lambda: NOW), gateway


async def test_track_computes_stats_in_chronological_order() -> None:
    # Llegan desordenados: el servicio ordena por hora antes de medir.
    points = [_pos(2, 4.62, -74.08, 0), _pos(0, 4.60, -74.08, 40), _pos(1, 4.61, -74.08, 55)]
    service, _ = _service(points)

    track = await service.track(7, NOW - timedelta(hours=3), NOW)

    assert [p.latitude for p in track.points] == [4.60, 4.61, 4.62]
    assert track.total_points == 3
    assert track.distance_km == pytest.approx(2.22, abs=0.01)  # 0,02° de latitud ≈ 2,22 km
    assert track.max_speed_kmh == 55
    assert track.moving_minutes == 2.0


async def test_empty_track_has_zero_stats() -> None:
    service, _ = _service([])
    track = await service.track(7, NOW - timedelta(hours=1), NOW)
    assert (track.points, track.distance_km, track.max_speed_kmh) == ((), 0, 0.0)


@pytest.mark.parametrize(
    ("start", "end", "field"),
    [
        (NOW, NOW - timedelta(hours=1), "from"),  # invertido
        (NOW - timedelta(days=8), NOW, "to"),  # más de 7 días
        (NOW + timedelta(hours=1), NOW + timedelta(hours=2), "from"),  # futuro
        (datetime(2026, 11, 8), datetime(2026, 11, 9), "from"),  # sin zona horaria
    ],
)
async def test_invalid_range_fails_before_calling_provider(start: datetime, end: datetime, field: str) -> None:
    service, gateway = _service([])
    with pytest.raises(ValidationFailed) as exc:
        await service.track(7, start, end)
    assert field in exc.value.errors
    assert gateway.calls == 0


def test_downsample_keeps_first_and_last() -> None:
    points = [_pos(i, 4.0 + i / 1000, -74.0) for i in range(5000)]
    sampled = downsample(points, 2000)
    assert len(sampled) == 2000
    assert sampled[0] is points[0] and sampled[-1] is points[-1]
    assert downsample(points[:10], 2000) == tuple(points[:10])


def test_haversine_one_degree_latitude() -> None:
    assert haversine_km(_pos(0, 0, 0), _pos(0, 1, 0)) == pytest.approx(111.19, abs=0.01)


def test_parse_messages_whitelists_and_skips_invalid() -> None:
    raw = [
        {"t": 1762600000, "pos": {"x": -74.1, "y": 4.6, "s": 20, "c": 71, "z": 2558, "sc": 18}, "p": {"secret": 1}},
        {"t": 1762600010},  # sin posición (solo sensores)
        {"t": 1762600020, "pos": {"x": -74.1, "y": 95, "s": 20, "c": 0}},  # latitud imposible
    ]
    messages = parse_messages(raw)
    assert len(messages) == 1
    assert not hasattr(messages[0], "p")
    position = message_to_position(messages[0], measure_units=1)  # mph -> km/h
    assert position.speed_kmh == 32.2
    assert position.recorded_at == datetime.fromtimestamp(1762600000, tz=UTC)
