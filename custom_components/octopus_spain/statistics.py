"""Build and inject consumption/export statistics into the HA recorder."""

from datetime import datetime, timezone

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.core import HomeAssistant

DOMAIN_SOURCE = "octopus_spain"


def build_statistics(readings: list[dict], start_sum: float = 0.0, after: datetime | None = None) -> list[dict]:
    """Turn hourly readings into cumulative statistics.

    - readings: list of {start, end, value} (value in kWh).
    - start_sum: previous cumulative sum (to continue an existing series).
    - after: if set, drop readings whose start is <= after (UTC).

    Returns [{start(UTC), state, sum}] sorted by time.
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


def _row_start_to_datetime(value) -> datetime:
    """A statistics row 'start' may be a timestamp (float) or a datetime."""
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromtimestamp(value, tz=timezone.utc)


async def async_import_statistics(hass: HomeAssistant, cups: str, flow: str, readings: list[dict]) -> None:
    """Inject readings as external statistics (flow is one of 'consumo'/'vertido')."""
    if not readings:
        return

    statistic_id = f"{DOMAIN_SOURCE}:{flow}_{cups.lower()}"

    last = await get_instance(hass).async_add_executor_job(get_last_statistics, hass, 1, statistic_id, True, {"sum"})
    start_sum = 0.0
    after: datetime | None = None
    if last.get(statistic_id):
        prev = last[statistic_id][0]
        start_sum = prev.get("sum") or 0.0
        after = _row_start_to_datetime(prev["start"])

    stats = build_statistics(readings, start_sum=start_sum, after=after)
    if not stats:
        return

    metadata = StatisticMetaData(
        has_mean=False,
        mean_type=StatisticMeanType.NONE,
        has_sum=True,
        name=f"Octopus {flow} {cups}",
        source=DOMAIN_SOURCE,
        statistic_id=statistic_id,
        unit_of_measurement="kWh",
    )
    data = [StatisticData(start=s["start"], state=s["state"], sum=s["sum"]) for s in stats]
    async_add_external_statistics(hass, metadata, data)
