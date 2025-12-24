# **Faber Skypad Integration für Home Assistant**

Diese Integration ermöglicht die Steuerung von Faber Dunstabzugshauben (getestet mit Modell Skypad) über Home Assistant. Da diese Geräte oft nur "dumme" IR/RF-Empfänger sind und keinen Status zurückmelden, bietet diese Integration intelligente Funktionen zur Statuserkennung mittels Strommessung.

## **Funktionen**

* **Lüftersteuerung:** An/Aus, 3 Geschwindigkeitsstufen \+ BOOST Modus.  
* **Lichtsteuerung:** An/Aus/Dimmen.  
* **Intelligenter Nachlauf:** \* Einstellbare Nachlaufzeit (Standard 30 Min).  
  * **NEU:** Eigene Sensoren für "Nachlauf Aktiv" und "Restzeit".  
  * Lüfter wird in HA als "Aus" angezeigt, während er physisch im Nachlauf läuft, um ein erneutes Einschalten zu ermöglichen.  
* **Strombasierte Statuserkennung (Empfohlen):**  
  * Erkennt automatisch, ob der Lüfter manuell (per Fernbedienung) eingeschaltet wurde.  
  * **NEU:** **Automatische Kalibrierung:** Lernt die Stromverbrauchswerte jeder Stufe, um den korrekten Status in Home Assistant anzuzeigen.  
  * **NEU:** **Dynamische Baseline:** Lernt den Ruheverbrauch (z.B. Licht an/aus), um den Lüfterstart zuverlässig zu erkennen.

## **Installation**

### **HACS (Empfohlen)**

1. Füge dieses Repository als "Custom Repository" in HACS hinzu.  
2. Suche nach "Faber Skypad" und installiere es.  
3. Starte Home Assistant neu.

### **Manuell**

1. Kopiere den Ordner custom\_components/faber\_skypad in deinen custom\_components Ordner.  
2. Starte Home Assistant neu.

## **Konfiguration**

Gehe zu **Einstellungen \-\> Geräte & Dienste \-\> Integration hinzufügen** und suche nach **Faber Skypad**.

### **Erforderliche Entitäten**

* **Remote Entity:** Eine remote.\* Entität (z.B. Broadlink, Harmony), die die Befehle sendet.  
  * Die Befehle müssen in base64 kodiert sein oder als Namen in der Remote hinterlegt sein.  
  * Erwartete Befehle: TURN\_ON\_OFF, INCREASE, DECREASE, BOOST, LIGHT, LIGHT\_DIM.

### **Optionale Entitäten**

* **Power Sensor:** Ein Sensor, der den aktuellen Stromverbrauch (in Watt) misst (z.B. Shelly Plug S, Shelly 1PM).  
  * *Alternativ:* Ein binärer Sensor (An/Aus), falls keine Watt-Messung möglich ist (eingeschränkte Funktionalität).

## **Kalibrierung (Neu in v1.2.0)**

Damit Home Assistant genau weiß, auf welcher Stufe die Haube läuft (wenn sie z.B. per Hand bedient wurde), kannst du einen Lernlauf starten.

1. Stelle sicher, dass die Haube **aus** ist (Licht kann an oder aus sein, am besten so, wie es meistens ist).  
2. Drücke in Home Assistant den Button **"Kalibrierung Starten"**.  
3. **Wichtig:** Bedienung während der Kalibrierung (ca. 60 Sekunden) vermeiden\!  
4. Der Prozess:  
   * Misst "Aus"-Verbrauch (Baseline).  
   * Schaltet Stufe 1 an \-\> Misst.  
   * Schaltet Stufe 2 an \-\> Misst.  
   * Schaltet Stufe 3 an \-\> Misst.  
   * Schaltet Boost an \-\> Misst.  
   * Schaltet aus.  
5. Danach werden die gelernten Werte in den Attributen des Lüfters gespeichert und für die Erkennung genutzt.

## **Entitäten**

Nach der Einrichtung stehen folgende Entitäten zur Verfügung:

| Entität | Typ | Beschreibung |
| :---- | :---- | :---- |
| fan.faber\_skypad | Lüfter | Hauptsteuerung für den Motor. |
| light.faber\_skypad\_light | Licht | Steuerung für das Licht. |
| switch.faber\_skypad\_run\_on | Schalter | Aktiviert/Deaktiviert die Nachlauf-Automatik. |
| number.faber\_skypad\_run\_on\_time | Nummer | Einstellung der Nachlaufzeit in Minuten. |
| binary\_sensor.faber\_skypad\_nachlauf\_aktiv | Binär Sensor | Zeigt an, ob der Nachlauf gerade aktiv ist. |
| sensor.faber\_skypad\_nachlauf\_ende | Sensor | Zeitstempel, wann der Nachlauf endet (Countdown). |
| button.faber\_skypad\_kalibrierung\_starten | Button | Startet den Kalibrierungs-Lauf. |

## **Hinweise**

* **Verzögerung:** Um zu verhindern, dass Befehle verschluckt werden, sendet die Integration Befehle mit einer Pause von 0.75 Sekunde.  
* **Boost:** Der Boost-Modus schaltet nach 5 Minuten (geräteseitig) automatisch zurück. Home Assistant simuliert diesen Timer ebenfalls.

## **Support**

Bei Problemen erstelle bitte ein Issue auf GitHub.

*Entwickelt für Faber Skypad, sollte aber mit den meisten Faber Hauben funktionieren, die die gleiche Logik (Eintasten-Bedienung für An/Aus) nutzen.*