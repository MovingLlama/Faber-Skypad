Faber Skypad IR Integration für Home Assistant

Eine benutzerdefinierte Home Assistant Integration (Custom Component) zur Steuerung von Faber Skypad Dunstabzugshauben.

Da diese Hauben oft nur über Infrarot (IR) gesteuert werden und keinen Status zurückmelden, implementiert diese Integration eine Smart-Logic, um den aktuellen Status (Stufe 1, 2, 3 oder Boost) zu simulieren und zu speichern.

✨ Funktionen

💨 Lüftersteuerung:

Ein/Aus

Geschwindigkeitsstufen 1, 2 und 3

Intelligente Berechnung der benötigten Tastendrücke (z.B. von Stufe 1 auf 3 sendet 2x "Stärker").

🚀 Boost Modus:

Aktiviert den Intensiv-Modus.

Automatischer Reset des Status in Home Assistant nach 5 Minuten (synchron zum Gerät).

💡 Lichtsteuerung:

Licht An/Aus.

🔌 Leistungsmessung (Optional):

Vorbereitet für Smart Plugs (mit Leistungsmessung).

Feature in Entwicklung: Automatische Status-Korrektur basierend auf dem Watt-Verbrauch.

⚙️ Voraussetzungen

Ein Infrarot-Sender, der bereits in Home Assistant integriert ist (z.B. Broadlink RM4 Mini).

Die remote.send_command Funktion muss für diesen Sender verfügbar sein.

📥 Installation

Option 1: Via HACS (Empfohlen)

Öffne HACS in deinem Home Assistant Dashboard.

Gehe zu Integrationen.

Klicke oben rechts auf das Menü (drei Punkte) ➡️ Benutzerdefinierte Repositories.

Füge die URL dieses Repositories hinzu.

Wähle als Kategorie Integration.

Klicke auf Hinzufügen und dann auf Herunterladen.

Starte Home Assistant neu.

Option 2: Manuell

Lade dieses Repository herunter.

Kopiere den Ordner custom_components/faber_skypad in deinen Home Assistant config/custom_components/ Ordner.

Starte Home Assistant neu.

🔧 Konfiguration

Die Integration unterstützt den Config Flow, kann also komplett über die Benutzeroberfläche eingerichtet werden. YAML ist nicht notwendig.

Gehe zu Einstellungen ➡️ Geräte & Dienste.

Klicke unten rechts auf Integration hinzufügen.

Suche nach Faber Skypad IR.

Fülle das Formular aus:

Name: Gib dem Gerät einen Namen (z.B. "Dunstabzug").

Remote Entity: Wähle deinen IR-Sender aus (z.B. remote.broadlink_rm4_mini).

Power Sensor (Optional): Falls du einen Stecker mit Verbrauchsmessung hast, wähle hier den Watt-Sensor aus.

🧠 Wie es funktioniert

Da Infrarot eine "Einbahnstraße" ist, weiß Home Assistant nicht, was du manuell am Gerät drückst.

Status-Speicher: Die Integration merkt sich den letzten gesendeten Befehl. Wenn du in der App "Stufe 3" wählst, weiß das System, dass es von "Stufe 1" zweimal das Signal "Stärker" senden muss.

Synchronisation: Sollte der Status in Home Assistant einmal nicht mit der Realität übereinstimmen (z.B. weil jemand manuell geschaltet hat), schalte den Lüfter in Home Assistant einfach einmal AUS und wieder AN. Das setzt den internen Zähler zurück.

📝 Lizenz

MIT License