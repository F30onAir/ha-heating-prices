"""Tests for the price alert blueprint shipped in blueprints/."""

from __future__ import annotations

from pathlib import Path
import shutil

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_mock_service

BLUEPRINT = (
    Path(__file__).parents[2]
    / "blueprints"
    / "automation"
    / "heating_prices"
    / "price_alert.yaml"
)
RATING = "sensor.heizol_preisbewertung"
ATTRIBUTES = {"price": 159.9, "unit": "€/100 L", "period": "2026-11-02"}


async def _setup(hass: HomeAssistant, tmp_path: Path, inputs: dict) -> list:
    hass.config.config_dir = str(tmp_path)
    target = tmp_path / "blueprints" / "automation" / "heating_prices"
    target.mkdir(parents=True)
    shutil.copy(BLUEPRINT, target / "price_alert.yaml")
    calls = async_mock_service(hass, "notify", "send_message")
    hass.states.async_set(RATING, "normal", ATTRIBUTES)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "heating_prices/price_alert.yaml",
                    "input": {
                        "rating_sensor": RATING,
                        "notify_target": ["notify.iphone"],
                        **inputs,
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()
    return calls


async def test_notifies_when_cheap(hass: HomeAssistant, tmp_path: Path) -> None:
    """A change to "low" sends a message with the price."""
    calls = await _setup(hass, tmp_path, {})

    hass.states.async_set(RATING, "low", ATTRIBUTES)
    await hass.async_block_till_done()

    assert len(calls) == 1
    data = calls[0].data
    assert data["entity_id"] == ["notify.iphone"]
    assert "159,90 €/100 L" in data["message"]
    assert data["title"].endswith("Günstig")


async def test_ignores_other_ratings_and_restarts(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """High prices are ignored by default, and so is coming back online."""
    calls = await _setup(hass, tmp_path, {})

    hass.states.async_set(RATING, "high", ATTRIBUTES)
    await hass.async_block_till_done()
    hass.states.async_set(RATING, "unavailable", {})
    await hass.async_block_till_done()
    hass.states.async_set(RATING, "low", ATTRIBUTES)
    await hass.async_block_till_done()

    assert calls == []


async def test_notifies_when_expensive_if_chosen(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Users can opt in to alerts about high prices."""
    calls = await _setup(hass, tmp_path, {"ratings": ["low", "high"]})

    hass.states.async_set(RATING, "high", ATTRIBUTES)
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["title"].endswith("Teuer")
