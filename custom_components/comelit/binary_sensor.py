"""Support for sensors."""

from __future__ import annotations

from typing import cast

from aiocomelit.api import ComelitVedoZoneObject
from aiocomelit.const import BRIDGE, AlarmZoneState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import (
    ComelitBaseCoordinator,
    ComelitConfigEntry,
    ComelitSerialBridge,
    ComelitVedoSystem,
)
from .utils import DeviceType, alarm_device_listener

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ComelitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Comelit VEDO presence sensors."""

    coordinator: ComelitBaseCoordinator
    if config_entry.data.get(CONF_TYPE, BRIDGE) == BRIDGE:
        coordinator = cast(ComelitSerialBridge, config_entry.runtime_data)
        # Only setup if bridge has VEDO alarm enabled
        if not coordinator.vedo_pin:
            return
    else:
        coordinator = cast(ComelitVedoSystem, config_entry.runtime_data)

    if (data := coordinator.alarm_data) is None:
        return

    def _add_new_entities(new_objects: list[DeviceType], dev_type: str) -> None:
        """Add entities for new monitors."""
        entities = [
            ComelitBinarySensorEntity(coordinator, zone, config_entry.entry_id)
            for zone in data["alarm_zones"].values()
            # if zone.index in new_objects
        ]
        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        alarm_device_listener(coordinator, _add_new_entities, "alarm_zones")
    )


class ComelitBinarySensorEntity(
    CoordinatorEntity[ComelitVedoSystem | ComelitSerialBridge], BinarySensorEntity
):
    """Sensor device."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(
        self,
        coordinator: ComelitVedoSystem | ComelitSerialBridge,
        zone: ComelitVedoZoneObject,
        config_entry_entry_id: str,
    ) -> None:
        """Init sensor entity."""
        self._zone_index = zone.index
        super().__init__(coordinator)
        # Use config_entry.entry_id as base for unique_id
        # because no serial number or mac is available
        self._attr_unique_id = f"{config_entry_entry_id}-presence-{zone.index}"
        self._attr_device_info = coordinator.platform_device_info(zone, "zone")
        assert self.coordinator.alarm_data is not None

    @property
    def _zone(self) -> ComelitVedoZoneObject:
        """Return zone object."""
        if not self.coordinator.alarm_data:
            raise RuntimeError("Alarm data not available")
        return self.coordinator.alarm_data["alarm_zones"][self._zone_index]

    @property
    def available(self) -> bool:
        """Return True if alarm is available."""
        if self._zone.human_status in [
            AlarmZoneState.FAULTY,
            AlarmZoneState.UNAVAILABLE,
            AlarmZoneState.UNKNOWN,
        ]:
            return False
        return super().available

    @property
    def is_on(self) -> bool:
        """Presence detected."""
        if not self.coordinator.alarm_data:
            raise RuntimeError("Alarm data not available")

        return (
            self.coordinator.alarm_data["alarm_zones"][self._zone_index].status_api
            == "0001"
        )
