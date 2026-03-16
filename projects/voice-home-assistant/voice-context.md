# Home Assistant — Voice Control Context

This document describes the home layout and key entity IDs for use by a voice control system.

## Home Overview

Single-family home with the following areas. All entity IDs follow the pattern `domain.area_feature`.

---

## Areas & Controllable Entities

### Bedroom (Master)
| What | Entity ID | Notes |
|---|---|---|
| Ceiling light | `light.bedroom_ceiling` | Inovelli dimmer |
| Bedside lights | `light.bedroom_side` | Inovelli dimmer |
| Bathroom lights | `light.master_bath_lights` | Inovelli dimmer |
| Closet lights | `light.master_closet` | Inovelli dimmer |
| WC exhaust fan | `fan.master_wc` | Inovelli fan switch |
| Bathroom exhaust fan | `fan.master_bathroom` | Inovelli fan switch |
| Projector | `media_player.bedroom_projector` | Fengmi MiProj L1 |
| Temperature | `sensor.bedroom_temperature` | |
| Humidity | `sensor.bedroom_humidity` | |

### Bedroom 2 (Adam)
| What | Entity ID | Notes |
|---|---|---|
| Main light | `light.adam_bedroom_main` | Inovelli dimmer |
| Closet light | `light.adam_closet` | Inovelli dimmer |

### Front Door / Entry Hall
| What | Entity ID | Notes |
|---|---|---|
| Entry hall lights | `light.entry_hall` | Inovelli dimmer |
| Front porch lights | `light.front_porch` | Inovelli dimmer |
| Front door contact | `binary_sensor.front_door_contact` | Open/closed |
| Doorbell motion | `binary_sensor.front_door_motion` | |
| Doorbell person | `binary_sensor.front_door_person` | AI detection |
| Doorbell camera | `camera.front_door_fluent` | Reolink doorbell |
| Front porch outlet | `switch.front_porch_outlet` | Outdoor plug |
| Gym ceiling fan | `fan.ceiling_gym_fan` | Bond Bridge (gym area) |

### Game Room
| What | Entity ID | Notes |
|---|---|---|
| Main lights | `light.game_room_main` | Inovelli dimmer |
| Accent lights | `light.game_room_accent` | Inovelli dimmer |
| Hallway lights | `light.hallway_main` | 1st floor hallway |
| TV | `media_player.game_room_tv` | Samsung Q80 65" |
| Temperature | `sensor.game_room_temperature` | |

### Garage
| What | Entity ID | Notes |
|---|---|---|
| Garage door | `cover.garage_door` | ratgdo (open/close/stop) |
| Remote lock | `lock.garage_remote_lock` | Disables remotes |
| Motion sensor | `binary_sensor.garage_motion` | |
| Interior camera | `camera.garage_fluent` | Reolink E1 Pro PTZ |
| Driveway camera | `camera.driveway` | Reolink Elite floodlight |
| Driveway floodlight | `light.driveway_floodlight` | |
| Temperature | `sensor.garage_temperature` | |

### Guest Room
| What | Entity ID | Notes |
|---|---|---|
| Ceiling fan | `fan.guest_room_ceiling` | Bond Bridge |
| Fan light | `light.guest_room_fan_light` | |

### Kitchen & Dining
| What | Entity ID | Notes |
|---|---|---|
| Kitchen main lights | `light.kitchen_main` | Inovelli dimmer |
| Kitchen counter lights | `light.kitchen_counter` | Inovelli dimmer |
| Dining room lights | `light.dining_room` | Inovelli dimmer |
| Dishwasher | `switch.dishwasher_power` | Bosch, Home Connect |

### Living Room
| What | Entity ID | Notes |
|---|---|---|
| Main lights | `light.living_room_main` | Inovelli dimmer |
| Secondary lights | `light.living_room_secondary` | Inovelli dimmer |
| Accent lights | `light.living_room_accent` | Inovelli dimmer |
| TV | `media_player.living_room_tv` | Sony BRAVIA 4K (Android TV) |
| Porch door (single) | `binary_sensor.porch_door_single` | Side entry contact |
| Porch door (double) | `binary_sensor.porch_door_double` | Side entry contact |
| Temperature | `sensor.living_room_temperature` | |

### My Room
| What | Entity ID | Notes |
|---|---|---|
| Shade 1 | `cover.my_room_shade_1` | Bond Bridge motorized shade |
| Shade 2 | `cover.my_room_shade_2` | Bond Bridge motorized shade |

### Office
| What | Entity ID | Notes |
|---|---|---|
| Speaker | `media_player.office_speaker` | Music Assistant |
| Temperature | `sensor.office_temperature` | |

### Patio
| What | Entity ID | Notes |
|---|---|---|
| Patio speaker | `media_player.patio_speaker` | Linkplay (native) |
| Patio speaker (MA) | `media_player.patio_speaker_ma` | Music Assistant |
| Back yard camera | `camera.back_yard_fluent` | Reolink E560 PTZ floodlight |

### Pool
| What | Entity ID | Notes |
|---|---|---|
| Pool heat | `climate.pool_heat` | Pentair EasyTouch2 |
| Spa heat | `climate.spa_heat` | |
| Pool light | `light.pool_light` | |
| Waterfall pump | `switch.pool_waterfall` | |
| Main pump | `switch.pool_main` | |
| Air temperature | `sensor.pool_air_temperature` | Sensor at pool |
| Salt level | `sensor.pool_chlorinator_salt` | |
| Alert | `binary_sensor.pool_active_alert` | |

### Yard / Irrigation
| What | Entity ID | Notes |
|---|---|---|
| Sprinkler zone 1 | `switch.yard_sprinkler_zone_1` | Rain Bird |
| Sprinkler zone 2 | `switch.yard_sprinkler_zone_2` | |
| Sprinkler zone 3 | `switch.yard_sprinkler_zone_3` | |
| Sprinkler zone 4 | `switch.yard_sprinkler_zone_4` | |
| Sprinkler zone 5 | `switch.yard_sprinkler_zone_5` | |
| Sprinkler zone 6 | `switch.yard_sprinkler_zone_6` | |
| Irrigation calendar | `calendar.yard_irrigation` | Scheduled runs |
| Rain delay | `number.yard_rain_delay` | Days to skip watering |
| Rain sensor | `binary_sensor.yard_rain_sensor` | |

### Attic
| What | Entity ID | Notes |
|---|---|---|
| Camera | `camera.attic_fluent` | Reolink E1 Pro PTZ |
| Temperature | `sensor.attic_temperature` | |
| Humidity | `sensor.attic_humidity` | |

---

## Whole-Home

| What | Entity ID | Notes |
|---|---|---|
| Thermostat | `climate.my_home_fl_thermostat` | Aprilaire 8840M, HVAC modes: off/heat/cool |
| Alarm panel | `alarm_control_panel.alarmo` | Alarmo, state: disarmed |

---

## Media Players Summary

| Friendly Name | Entity ID | Location |
|---|---|---|
| Living Room TV | `media_player.living_room_tv` | Living Room (Sony BRAVIA, Android TV) |
| Game Room TV | `media_player.game_room_tv` | Game Room (Samsung Q80 65") |
| Gym TV | `media_player.gym_tv` | Gym / Entry (Samsung 6 Series 40") |
| Bedroom Projector | `media_player.bedroom_projector` | Bedroom (Fengmi MiProj L1) |
| Patio Speaker | `media_player.patio_speaker` | Patio (Linkplay) |
| Patio Speaker (MA) | `media_player.patio_speaker_ma` | Patio (Music Assistant) |
| Office Speaker | `media_player.office_speaker` | Office (Music Assistant) |

---

## Notes for Voice Control

- **Lights**: All Inovelli switches support brightness dimming. Use `light.turn_on` with `brightness_pct`.
- **Fans**: Support speed control (`percentage`) and in some cases preset modes.
- **Thermostat** (`climate.my_home_fl_thermostat`): Supports `off`, `heat`, `cool` modes. Fan modes: `auto`, `on`, `Circulate`. Preset modes: `none`, `Vacation`, `Permanent`.
- **Garage door** (`cover.garage_door`): Use `cover.open_cover`, `cover.close_cover`, `cover.stop_cover`.
- **Shades** (`cover.my_room_shade_*`): Same cover service calls as garage door.
- **Alarm** (`alarm_control_panel.alarmo`): Use `alarm_control_panel.alarm_arm_away`, `alarm_disarm`, etc.
- **Bond Bridge devices** (`fan.ceiling_gym_fan`, `fan.guest_room_ceiling`, `cover.my_room_shade_*`): All route through the Bond Bridge hub — if Bridge is offline, these won't respond.
- **Irrigation** (`switch.yard_sprinkler_zone_*`): Currently offline (Rain Bird WiFi issue being resolved). Do not attempt to control until connectivity is confirmed.
