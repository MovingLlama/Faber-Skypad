# **Faber Skypad IR Integration für Home Assistant**

Eine benutzerdefinierte Home Assistant Integration (Custom Component) zur Steuerung von **Faber Skypad** Dunstabzugshauben.

Da diese Hauben oft nur über Infrarot (IR) gesteuert werden und keinen Status zurückmelden, implementiert diese Integration eine **Smart-Logic**, um den aktuellen Status (Stufe 1, 2, 3 oder Boost) zu simulieren und zu speichern.

## **✨ Funktionen**

* **💨 Lüftersteuerung:**  
  * Ein/Aus  
  * Geschwindigkeitsstufen 1, 2 und 3  
  * Intelligente Berechnung der benötigten Tastendrücke (z.B. von Stufe 1 auf 3 sendet 2x "Stärker").  
* **⏱️ Intelligenter Nachlauf (Neu):**  
  * Konfigurierbare Nachlaufzeit (in Minuten).  
  * Wenn aktiviert: Beim Ausschalten wechselt der Lüfter automatisch auf **Stufe 1** und läuft die eingestellte Zeit nach, bevor er ganz ausgeht.  
  * Ideal, um Restfeuchtigkeit nach dem Kochen zu entfernen.  
* **🚀 Boost Modus:**  
  * Aktiviert den Intensiv-Modus.  
  * Automatischer Reset des Status in Home Assistant nach 5 Minuten (synchron zum Gerät).  
* **💡 Lichtsteuerung:**  
  * Licht An/Aus.  
* **🔌 Leistungsmessung (Optional):**  
  * Vorbereitet für Smart Plugs (mit Leistungsmessung).  
  * *Feature in Entwicklung:* Automatische Status-Korrektur basierend auf dem Watt-Verbrauch.

## **⚙️ Voraussetzungen**

* Ein Infrarot-Sender, der bereits in Home Assistant integriert ist (z.B. **Broadlink RM4 Mini**).  
* Die remote.send\_command Funktion muss für diesen Sender verfügbar sein.

## **📥 Installation**

### **Option 1: Via HACS (Empfohlen)**

1. Öffne HACS in deinem Home Assistant Dashboard.  
2. Gehe zu **Integrationen**.  
3. Klicke oben rechts auf das Menü (drei Punkte) ➡️ **Benutzerdefinierte Repositories**.  
4. Füge die URL dieses Repositories hinzu.  
5. Wähle als Kategorie **Integration**.  
6. Klicke auf **Hinzufügen** und dann auf **Herunterladen**.  
7. Starte Home Assistant neu.

### **Option 2: Manuell**

1. Lade dieses Repository herunter.  
2. Kopiere den Ordner custom\_components/faber\_skypad in deinen Home Assistant config/custom\_components/ Ordner.  
3. Starte Home Assistant neu.

## **🔧 Konfiguration & Nutzung**

Die Integration unterstützt den **Config Flow**, kann also komplett über die Benutzeroberfläche eingerichtet werden.

1. Gehe zu **Einstellungen** ➡️ **Geräte & Dienste**.  
2. Klicke unten rechts auf **Integration hinzufügen**.  
3. Suche nach **Faber Skypad IR**.

### **Nach der Installation**

Die Integration erstellt ein Gerät mit folgenden Entitäten:

* **Lüfter (Fan):** Zur Steuerung der Geschwindigkeit.  
* **Licht (Light):** Für die Beleuchtung.  
* **Nachlauf (Switch):** Ein Schalter, um die Nachlauffunktion generell zu aktivieren oder deaktivieren.  
* **Nachlaufzeit (Number):** Ein Eingabefeld (Slider/Box), um die Minuten für den Nachlauf einzustellen (z.B. 5 Minuten).

### **So funktioniert der Nachlauf**

1. Aktiviere den Schalter **Nachlauf**.  
2. Stelle die **Nachlaufzeit** ein (z.B. 10 Minuten).  
3. Wenn du fertig mit Kochen bist, schalte den Lüfter in Home Assistant **AUS**.  
4. Der Lüfter geht **nicht** aus, sondern schaltet auf **Stufe 1**.  
5. Nach 10 Minuten schaltet er sich automatisch komplett ab.  
6. *Hinweis:* Drückst du während des Nachlaufs erneut auf "Aus", schaltet er sofort ab.

## **🧠 Wie es funktioniert**

Da Infrarot eine "Einbahnstraße" ist, weiß Home Assistant nicht, was du manuell am Gerät drückst.

* **Status-Speicher:** Die Integration merkt sich den letzten gesendeten Befehl. Wenn du in der App "Stufe 3" wählst, weiß das System, dass es von "Stufe 1" zweimal das Signal "Stärker" senden muss.  
* **Synchronisation:** Sollte der Status in Home Assistant einmal nicht mit der Realität übereinstimmen (z.B. weil jemand manuell geschaltet hat), schalte den Lüfter in Home Assistant einfach einmal **AUS** und wieder **AN**. Das setzt den internen Zähler zurück.

## **📝 Lizenz**

MIT License