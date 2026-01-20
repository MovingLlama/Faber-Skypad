# **Faber Skypad Integration for Home Assistant**

This integration allows controlling Faber cooker hoods (tested with the Skypad model) via Home Assistant. Since these devices are often just "dumb" IR/RF receivers and do not report their status, this integration provides intelligent functions for status detection using power measurement.

## **Features**

*   **Fan Control:** On/Off, 3 speed levels + BOOST mode.
*   **Light Control:** On/Off.
*   **Intelligent Timer:** * Adjustable timer duration (default 30 min).
    *   **NEW:** Separate sensors for "Timer Active" and "Remaining Time".
    *   The fan is shown as "Off" in HA while it is physically running in timer mode, to allow it to be turned on again.
*   **Power-Based Status Detection (Recommended):**
    *   Automatically detects if the fan has been turned on manually (via remote control).
    *   **NEW:** **Automatic Calibration:** Learns the power consumption values for each speed level to display the correct status in Home Assistant.
    *   **NEW:** **Dynamic Baseline:** Learns the idle power consumption (e.g., light on/off) to reliably detect when the fan starts.

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

*   **Remote Entity:** A `remote.*` entity (e.g., Broadlink, Harmony) that sends the commands.
    *   The commands must be base64 encoded or stored as names in the remote entity.
    *   Expected commands: `TURN_ON_OFF`, `INCREASE`, `DECREASE`, `BOOST`, `LIGHT`.

### **Optional Entities**

*   **Power Sensor:** A sensor that measures the current power consumption in Watts (e.g., Shelly Plug S, Shelly 1PM).
    *   *Alternatively:* A binary sensor (On/Off) if power measurement is not possible (limited functionality).

## **Calibration (New in v1.2.0)**

To let Home Assistant know exactly which speed the hood is running at (e.g., if it was operated manually), you can start a calibration process.

1.  Make sure the hood is **off** (the light can be on or off, preferably in its usual state).
2.  In Home Assistant, press the **"Start Calibration"** button.
3.  **Important:** Avoid operating the hood during calibration (approx. 60 seconds)!
4.  The process:
    *   Measures "Off" consumption (baseline).
    *   Turns on speed 1 -> Measures.
    *   Turns on speed 2 -> Measures.
    *   Turns on speed 3 -> Measures.
    *   Turns on Boost -> Measures.
    *   Turns off.
5.  Afterward, the learned values are saved in the fan's attributes and used for detection.

## **Entities**

After setup, the following entities are available:

| Entity | Type | Description |
| :--- | :--- | :--- |
| `fan.faber_skypad` | Fan | Main control for the motor. |
| `light.faber_skypad_light` | Light | Control for the light. |
| `switch.faber_skypad_run_on` | Switch | Enables/Disables the automatic timer. |
| `number.faber_skypad_run_on_time` | Number | Sets the timer duration in minutes. |
| `binary_sensor.faber_skypad_timer_active` | Binary Sensor | Indicates if the timer is currently active. |
| `sensor.faber_skypad_timer_end` | Sensor | Timestamp of when the timer will end (countdown). |
| `button.faber_skypad_start_calibration`| Button | Starts the calibration process. |

## **Notes**

*   **Delay:** To prevent commands from being missed, the integration sends commands with a 0.75-second pause.
*   **Boost:** The boost mode automatically switches back after 5 minutes (device-side). Home Assistant also simulates this timer.

## **Support**

For problems, please create an Issue on GitHub.

*Developed for Faber Skypad, but should work with most Faber hoods that use the same logic (single-button operation for On/Off).*