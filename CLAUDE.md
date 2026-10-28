# CLAUDE.md

Diese Datei gibt Claude Code Orientierung für die Arbeit in diesem Repository.

## Projektüberblick

Home-Assistant-Custom-Integration (`domain: faber_skypad`) zur Steuerung einer Faber-Skypad-Dunstabzugshaube per IR/RF über eine vorhandene `remote.*`-Entität (z. B. Broadlink). Die Haube meldet keinen Status zurück – optional wird der Zustand über einen Leistungssensor (Watt) bzw. einen Binärsensor erkannt. Verteilung über HACS (`hacs.json`) oder manuelles Kopieren nach `custom_components/`.

Reines Python, keine externen Requirements, keine Tests, kein Linter/Build-Setup. Testen erfolgt nur in einer echten Home-Assistant-Instanz.

## Struktur

```
custom_components/faber_skypad/
  __init__.py       Setup/Unload/Reload, FaberRuntimeData, Config-Migration v1 -> v2
  config_flow.py    ConfigFlow (VERSION = 2) + OptionsFlow: remote_entity (Pflicht), power_sensor (optional), sync_delay (nur Options)
  const.py          IR-Codes (Base64), Timing, SPEED_MAPPING, Kalibrier-/Matching-Schwellen
  fan.py            Kernlogik: Steuerung, Leistungs-Matching, Befehls-Retry, Kalibrierung, Nachlauf, Boost
  light.py          Licht (optimistischer Zustand, Toggle-Befehl CMD_LIGHT)
  switch.py         "Automatic Timer" (Nachlauf an/aus) + "Calibration" (Start/Abbruch)
  number.py         Nachlaufdauer in s (10–3600, Schritt 5)
  binary_sensor.py  Timer aktiv
  sensor.py         Timer-Ende (Timestamp) + Letzte Kalibrierung (Leistungswerte als Attribute)
  button.py         Sync Fan / Sync Light (senden nur, ohne State-Änderung) + Reset Calibration
  translations/     de.json, en.json, it.json
  brand/            icon.png, logo.png
.github/workflows/release.yml   Auto-Release bei jedem Push auf main
```

`icon.png`/`logo.png` im Root und im Komponentenordner sind Duplikate für README/HACS. `.idx/dev.nix` ist ein ungenutzter Firebase-Studio-Rest.

## Architektur

- **Geteilter Zustand:** `FaberRuntimeData` liegt in `hass.data[DOMAIN][entry_id]["runtime_data"]`. Enthält Nachlauf-Status (`run_on_enabled`, `run_on_seconds`, `run_on_active`, `run_on_finish_time`) sowie Referenzen auf `fan_entity` und `light_entity`. Entitäten, die auf Änderungen reagieren müssen, registrieren sich via `register_listener`; Änderungen werden mit `trigger_update()` verteilt.
- **Fan ist die zentrale Entität.** Switches, Buttons und Light greifen direkt auf `runtime_data.fan_entity` zu (inkl. privater Attribute wie `_is_calibrating`, `_power_profile`). Nachlauf-/Timer-Entitäten halten keinen eigenen Zustand, sondern lesen `runtime_data`.
- **Befehle senden:** `remote.send_command` mit `command: ["b64:<code>"]` und `hold_secs = CMD_HOLD_SECS` (0.4 s). Die IR-Codes sind fest in `const.py` hinterlegt. Nach jedem Befehl `DEFAULT_DELAY` (0.75 s) Pause. Fan und Light serialisieren ihre Steuerbefehle über `_command_lock` (öffentliche `async_*`-Methoden nehmen den Lock, interne Aufrufe nutzen die `_async_*`-Varianten) – gleichzeitige Service-Aufrufe würden sonst mehrfach umschalten. Pro Befehl existiert höchstens ein Retry-Prüf-Timer. Die Haube kennt nur Toggle-Befehle (`TURN_ON_OFF`, `LIGHT`) sowie `INCREASE`/`DECREASE`/`BOOST` – der HA-Zustand ist daher immer optimistisch/abgeleitet.
- **Retry-Logik (`fan.send_command_with_retry`):** Nur mit Leistungssensor und außerhalb der Kalibrierung. Merkt sich die Leistung vor dem Befehl; ändert sie sich nach 10 s (bzw. Sync-Verzögerung) nicht um ≥ 3 W, wird der Befehl erneut gesendet (höchstens `CMD_MAX_RETRIES`). Liefert der Sensor keinen Wert (z. B. falsche Entity-ID), wird ohne Retry gesendet – sonst würde jeder Retry das Gerät erneut umschalten. Auch Lichtbefehle laufen darüber.
- **Leistungs-Matching (`_match_power` → `_apply_detection`):**
  - Unkalibriert (`fan_1 == 0`): nur an/aus (`off + FALLBACK_THRESHOLD`), laufende Stufe bleibt erhalten.
  - Kalibriert: Zwei Hypothesen (Licht an/aus, Lichtleistung = `light_on - off`, Fallback 8 W) gegen alle Profile (`off`, `fan_1..3`, `fan_boost`). Bevorzugt die zum HA-Lichtzustand passende; nur wenn die nicht innerhalb der Toleranz passt, die andere eindeutig aber schon, wird auch der Lichtzustand korrigiert. Toleranz = halber kleinster Profilabstand, begrenzt auf `MIN_MATCH_TOLERANCE`..`MATCH_TOLERANCE`. Keine Zuordnung → nichts ändern.
  - Entprellung: Ein Zustand wird erst nach `DETECTION_SETTLE_TIME` übernommen, frühestens die Sync-Verzögerung (`sync_delay` im OptionsFlow, Standard `COMMAND_SETTLE_TIME`) nach einem eigenen Befehl und nicht, solange ein Befehl auf Retry-Bestätigung wartet. Jeder Befehl verwirft eine noch ausstehende Erkennung; beim Übernehmen wird mit dem aktuellen Messwert neu gematcht (sonst dreht ein Wert von vor dem Befehl den Zustand zurück). Die Retry-Prüfung wartet `max(RETRY_CHECK_DELAY, sync_delay)`.
  - Nicht-numerische Zustände (`on`/`off`) → Binärsensor-Pfad `_update_state_from_binary`.
- **Kalibrierung:** Läuft als Task `_async_run_calibration` im geschlossenen Regelkreis: Jeder Befehl (`_calib_send_verified`) wird über die Leistungsänderung (≥ `CALIB_MIN_CHANGE` in erwarteter Richtung) bestätigt, sonst bis `CALIB_MAX_ATTEMPTS` wiederholt; Messwert = Median eines stabilen Fensters (`_calib_wait_stable`). Start: Lüfter und Licht werden per Umschalten + Richtungsprüfung sicher ausgeschaltet (`_calib_probe_off`) → off → Licht an → Licht aus → Stufe 1 → 2 → 3 → Boost → aus. Profil wird auf aufsteigende, unterscheidbare Werte geprüft und nur bei Erfolg in `config_entry.data["power_profile"]`/`["last_calibration"]` gespeichert; bei Fehler/Abbruch schaltet `_calib_restore_off` alles kontrolliert aus (Abbruch dort ignoriert) und es gibt eine `persistent_notification`. Während der Kalibrierung ignorieren Fan, Licht und Sync-Buttons Eingaben.
- **Nachlauf:** Beim Ausschalten mit aktivem Timer geht der Lüfter auf Stufe 1, HA zeigt ihn als „aus“, und nach `run_on_seconds` wird das endgültige Aus gesendet. Erneutes Einschalten während des Nachlaufs übernimmt den laufenden Lüfter ohne Toggle-Befehl.
- **Boost:** Gerät fällt nach 5 min selbst zurück; HA setzt `preset_mode` nach 300 s per Timer zurück.
- **Geschwindigkeit:** 3 Stufen ↔ 33/66/100 % (`SPEED_MAPPING`); Stufenwechsel durch wiederholtes `INCREASE`/`DECREASE` relativ zu `_current_speed_step`.

## Konventionen & Hinweise

- Jede Entität baut ihr eigenes `DeviceInfo` mit `identifiers={(DOMAIN, entry_id)}`; `unique_id` = `f"{entry_id}_<suffix>"`. Bestehende Suffixe nicht ändern (würde Entitäten in HA neu anlegen).
- Entitätsnamen: Switch/Number/Sensor/Binary-Sensor nutzen `_attr_translation_key` → neue Keys in **allen drei** Übersetzungsdateien (de/en/it) ergänzen. Fan, Light und Buttons nutzen fest codierte Namen.
- Kommentare/Logs sind gemischt Deutsch (ältere Dateien: `fan.py`, `light.py`, `const.py`, `__init__.py`) und Englisch (neuere Dateien). Beim Bearbeiten den Stil der jeweiligen Datei beibehalten.
- Änderungen am gespeicherten Datenformat: `ConfigFlow.VERSION` erhöhen und `async_migrate_entry` in `__init__.py` erweitern.
- Einstellungen liegen in `entry.data`. Der OptionsFlow schreibt direkt dorthin und leert `entry.options`; `__init__.py` mischt noch `{**entry.data, **entry.options}` für Einträge älterer Versionen. Jedes `async_update_entry` (auch Kalibrierung/Reset) löst über den Update-Listener einen Reload aus.
- Der OptionsFlow nutzt das von HA bereitgestellte `self.config_entry` (ab HA 2024.11, daher Mindestversion in `hacs.json`) und `suggested_value` statt `default`, damit der optionale Leistungssensor geleert werden kann.

## Release

Jeder Push auf `main` erzeugt über `.github/workflows/release.yml` automatisch ein GitHub-Release `v<MAJOR_MINOR>.<run_number - OFFSET>` (aktuell `MAJOR_MINOR="1.4"`, `OFFSET=14`) mit `faber_skypad.zip`. Die Version in `manifest.json` wird nur im ZIP überschrieben; der Wert im Repo ist veraltet. Für einen neuen Minor-Sprung `MAJOR_MINOR` und `OFFSET` im Workflow anpassen.
