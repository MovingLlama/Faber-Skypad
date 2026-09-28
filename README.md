<p align="center">
  <img src="https://raw.githubusercontent.com/MovingLlama/Faber-Skypad/main/logo.png" alt="Faber Skypad Logo" width="150" height="150">
</p>

# **Faber Skypad Integration for Home Assistant**

This integration allows controlling Faber cooker hoods (tested with the Skypad model) via Home Assistant. Since these devices are often just "dumb" IR/RF receivers and do not report their status, this integration provides intelligent functions for status detection using power measurement.

## **Features**

*   **Fan Control:** On/Off, 3 speed levels + BOOST mode.
*   **Light Control:** On/Off (optimistic state tracking, fully independent of power sensor noise).
*   **Intelligent Timer:**
    *   Adjustable timer duration (default 60 seconds).
    *   Separate sensors for "Timer Active" and "Remaining Time".
    *   The fan is shown as "Off" in HA while it is physically running in timer mode, to allow it to be turned on again.
*   **Power-Based Status Detection (Recommended):**
    *   Automatically detects if the fan has been turned on manually (via remote control).
    *   **Automatic Calibration:** Learns the power consumption values for each speed level in 6 simple steps.
    *   **Robust Speed Matching:** Uses the active light state in Home Assistant to dynamically subtract the light's power consumption before matching the fan speed. This ensures reliable fan speed detection regardless of whether the light is on or off.

## **Installation**

### **HACS (Recommended)**

1.  Add this repository as a "Custom Repository" in HACS.
2.  Search for "Faber Skypad" and install it.
3.  Restart Home Assistant.

### **Manual**

1.  Copy the `custom_components/faber_skypad` folder into your `custom_components` folder.
2.  Restart Home Assistant.

## **Configuration**

Go to **Settings -> Devices & Services -> Add Integration** and search for **Faber Skypad**.

### **Required Entities**

*   **Remote Entity:** A `remote.*` entity that sends the IR commands (e.g., Broadlink).
    *   The IR codes for the Faber Skypad (`TURN_ON_OFF`, `INCREASE`, `DECREASE`, `BOOST`, `LIGHT`) are built into the integration and sent as raw Base64 codes (`b64:...` via `remote.send_command`). No commands need to be learned or stored in the remote.
    *   The remote integration must therefore support sending `b64:` codes (e.g., Broadlink).

### **Optional Entities**

*   **Power Sensor:** A sensor that measures the current power consumption in Watts (e.g., Shelly Plug S, Shelly 1PM).
    *   *Alternatively:* A binary sensor (On/Off) if power measurement is not possible (limited functionality).

Both entities can be changed later via **Configure** on the integration; the power sensor can also be removed there.

## **Calibration**

To let Home Assistant know exactly which speed the hood is running at (e.g., if it was operated manually), you can run the calibration process.

1.  The hood and light can be in any state – the calibration switches both off by itself first.
2.  In Home Assistant, turn on the **"Calibration"** switch.
3.  **Important:** Avoid operating the hood during calibration (approx. 2–4 minutes)! Light, fan and sync buttons are blocked while it runs.
4.  The process:
    *   Toggles fan and light once and uses the power change to find out whether they were on, then switches both off -> Measures "Off" consumption (baseline).
    *   Turns on the Light -> Measures light baseline.
    *   Turns off the Light, turns on Fan Speed 1 -> Measures.
    *   Turns on Fan Speed 2 -> Measures.
    *   Turns on Fan Speed 3 -> Measures.
    *   Turns on Boost -> Measures.
    *   Turns off.

    Every command is confirmed via the power sensor and resent up to 3 times if nothing changes. Each value is the median of a stable reading window. If a command can't be confirmed or the values are implausible (each level must be clearly above the previous one), the calibration is aborted, the hood is switched off and the previous profile is kept – you'll get a notification in Home Assistant. Turning the switch off cancels the calibration and switches the hood off.
5.  Afterward, the learned values are saved in the config entry and used for detection.

## **Entities**

After setup, the following entities are available:

| Entity | Type | Description |
| :--- | :--- | :--- |
| `fan.faber_skypad` | Fan | Main control for the motor. |
| `light.faber_skypad_light` | Light | Control for the light. |
| `switch.faber_skypad_run_on` | Switch | Enables/Disables the automatic timer. |
| `switch.faber_skypad_calibration` | Switch | Starts, stops, or cancels the calibration process. |
| `number.faber_skypad_run_on_time` | Number | Sets the timer duration in seconds. |
| `binary_sensor.faber_skypad_timer_active` | Binary Sensor | Indicates if the timer is currently active. |
| `sensor.faber_skypad_timer_end` | Sensor | Timestamp of when the timer will end (countdown). |
| `sensor.faber_skypad_last_calibration` | Sensor | Shows the timestamp and learned values of the last calibration. |
| `button.faber_skypad_sync_fan` | Button | Sends the fan command (without changing HA state, for manual sync). |
| `button.faber_skypad_sync_light` | Button | Sends the light command (without changing HA state, for manual sync). |
| `button.faber_skypad_reset_calibration` | Button | Deletes the learned power values and the last calibration timestamp. |

## **Notes**

*   **Delay:** To prevent commands from being missed, the integration sends commands with a 0.75-second pause.
*   **Boost:** The boost mode automatically switches back after 5 minutes (device-side). Home Assistant also simulates this timer.

## **Support**

For problems, please create an Issue on GitHub.

*Developed for Faber Skypad, but should work with most Faber hoods that use the same logic (single-button operation for On/Off).*