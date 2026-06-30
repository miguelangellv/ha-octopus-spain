"""Construcción e inyección de estadísticas de consumo/vertido en el recorder de HA."""

from datetime import datetime, timezone


def build_statistics(readings: list[dict], start_sum: float = 0.0, after: datetime | None = None) -> list[dict]:
    """Convierte lecturas horarias en estadísticas acumuladas.

    - readings: lista de {start, end, value} (value en kWh).
    - start_sum: suma acumulada previa (para continuar el histórico).
    - after: si se indica, descarta lecturas cuyo inicio sea <= after (UTC).

    Devuelve [{start(UTC), state, sum}] ordenado por tiempo.
    """
    stats: list[dict] = []
    running = start_sum
    for reading in sorted(readings, key=lambda x: x["start"]):
        start = reading["start"].astimezone(timezone.utc)
        if after is not None and start <= after:
            continue
        running += reading["value"]
        stats.append({"start": start, "state": reading["value"], "sum": running})
    return stats
