# WBL Abfallkalender Lünen für Home Assistant

Custom Integration, die die Abfuhrtermine der Wirtschaftsbetriebe Lünen (WBL)
für deine Straße in Home Assistant anzeigt. Die Daten kommen aus dem
iCal-Export unter <https://wbl.de/abfallentsorgung/abfuhrtermine-2026>.

Die Integration läuft lokal in deinem Home Assistant. Nur die Termine werden
alle 12 Stunden bei wbl.de abgefragt.

## Was du bekommst

Pro Straße ein Gerät „WBL Abfall <Straße>“ mit:

| Entität | Inhalt |
|---|---|
| ein Sensor pro ausgewählter Tonne (Graue Tonne, Rote Tonne, Gelbe Tonne, Bio-Tonne, Blaue Tonne, Container …) | Datum der nächsten Leerung, Attribute `days_until` und `upcoming` |
| „Nächste Abholung“ | nächste Tonne(n) und wann, z. B. `Bio-Tonne · Fr. 13.11.` oder `Gelbe Tonne · morgen` |
| „Abfallkalender“ | alle Termine der ausgewählten Tonnen. Zustand **An** = heute ist Abholtag |

## Installation über HACS

1. HACS → **⋮ → Benutzerdefinierte Repositories**
2. `https://github.com/LawandK8/ha-wbl-luenen` eintragen, Typ **Integration** → **Hinzufügen**
3. „WBL Abfallkalender Lünen“ suchen → **Herunterladen**
4. Home Assistant neu starten

Ohne HACS: den Ordner `custom_components/wbl_luenen` nach
`/config/custom_components/` kopieren (z. B. mit der App „Samba share“) und
neu starten.

## Einrichten

**Einstellungen → Geräte & Dienste → Integration hinzufügen →
„WBL Abfallkalender Lünen“**

1. **Straße** eingeben, eine Hausnummer ist nicht nötig.
   Lange Straßen teilt die WBL nach Hausnummern auf
   (z. B. „Ahornstraße 1-13 und 2-18“). Dann kommt eine Auswahlliste.
2. **Tonnen ankreuzen**, die du wirklich hast. Nur diese bekommen Sensoren.
   Ändern kannst du das später unter **Konfigurieren**.

## Beispiel: Erinnerung am Vorabend

Im Automations-Editor unter **⋮ → In YAML bearbeiten** einfügen und die
Entity-ID anpassen:

```yaml
alias: Mülltonne rausstellen (WBL)
triggers:
  - trigger: time
    at: "19:00:00"
conditions:
  - condition: template
    value_template: >
      {{ state_attr('sensor.wbl_abfall_achenbachstrasse_next_collection', 'days_until') == 1 }}
actions:
  - action: notify.notify
    data:
      message: >
        Morgen: {{ state_attr('sensor.wbl_abfall_achenbachstrasse_next_collection', 'types') | join(', ') }} rausstellen!
```

## Grenzen

- Die WBL veröffentlicht Termine jahresweise. Sobald die Datei fürs
  nächste Jahr online ist, holt die Integration sie automatisch dazu.
- Es gibt keine offizielle API. Ändert die WBL ihre Seite, muss die
  Integration angepasst werden.

## Tests

Live-Tests gegen wbl.de:

```bash
pip install pytest-homeassistant-custom-component
pytest tests
```
