# Heating Prices – Heizöl, Pellets & Erdgas für Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Validate](https://github.com/F30onAir/ha-heating-prices/actions/workflows/validate.yml/badge.svg)](https://github.com/F30onAir/ha-heating-prices/actions/workflows/validate.yml)
[![Tests](https://github.com/F30onAir/ha-heating-prices/actions/workflows/tests.yml/badge.svg)](https://github.com/F30onAir/ha-heating-prices/actions/workflows/tests.yml)

Aktuelle **Heizöl-, Pellet- und Erdgaspreise** direkt in Home Assistant, mit einer
Dashboard-Karte, die Verlauf, Trend und den Wärmepreis pro kWh vergleicht.
Alle Daten stammen aus **offenen, amtlichen Quellen**. Es gibt kein Scraping von
Händlerseiten und es wird kein API-Schlüssel gebraucht.

*English below.*

![Dashboard-Karte](docs/card.png)

## Funktionen

- **Heizöl** – wöchentlicher Durchschnittspreis inkl. aller Steuern für 27 EU-Länder,
  mit Verlauf seit 2005
- **Holzpellets** – monatlicher DEPI-Preis für Deutschland, bundesweit oder regional
  (Nord/Ost, Mitte, Süd) für 3, 6 oder 26 Tonnen
- **Erdgas** – Haushaltspreis von Eurostat für 27 EU-Länder, mit dem monatlichen
  Gaspreisindex auf den aktuellen Monat hochgerechnet
- **Preisbewertung** – günstig / normal / teuer im Vergleich zu den letzten 12 Monaten
- **Wärmepreis-Vergleich** – alle Brennstoffe in ct pro kWh Wärme und der aktuell günstigste
- **Eigener Preis** – trage ein, was du zahlst, und sieh die Abweichung zum Markt
- **Dashboard-Karte** inklusive. Sie wird automatisch registriert, ohne manuelle Ressource
- Funktioniert auch bei Ausfällen: Der letzte Stand bleibt gespeichert und wird als „veraltet“ markiert

## Installation

### Über HACS (empfohlen)

[![Repository in HACS öffnen](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=F30onAir&repository=ha-heating-prices&category=integration)

1. HACS öffnen → oben rechts **⋮ → Benutzerdefinierte Repositories**
2. `https://github.com/F30onAir/ha-heating-prices` mit Typ **Integration** hinzufügen
3. **Heating Prices** herunterladen und Home Assistant neu starten

### Manuell

Den Ordner `custom_components/heating_prices` nach `config/custom_components/` kopieren
und Home Assistant neu starten.

## Einrichtung

[![Integration hinzufügen](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=heating_prices)

**Einstellungen → Geräte & Dienste → Integration hinzufügen → Heating Prices**

1. Land und Brennstoffe wählen
2. Bei Pellets: Region und Liefermenge
3. Bei Erdgas: Jahresverbrauch (Band D1, D2 oder D3)

Über **Konfigurieren** kannst du später deine eigenen Preise eintragen.

## Sensoren

Für jeden Brennstoff entsteht ein Gerät mit diesen Sensoren:

| Sensor | Beispiel | Beschreibung |
|---|---|---|
| Preis | `175,01 €/100 L` | Aktueller Preis, Attribute mit Min/Max/Ø über 12 Monate |
| Preis pro kWh Wärme | `17,50 ct/kWh` | Für den Vergleich zwischen den Brennstoffen |
| Veränderung | `2,2 %` | Gegenüber der Vorwoche bzw. dem Vormonat |
| Preisbewertung | `Teuer` | Günstig / Normal / Teuer im Vergleich zu 12 Monaten |

Bei mehreren Brennstoffen kommt **Günstigster Brennstoff** dazu.

## Dashboard-Karte

Die Karte steht nach der Installation in der Kartenauswahl als **Heating Prices** bereit.
Alternativ in YAML:

```yaml
type: custom:heating-prices-card
# alle Angaben sind optional
title: Heizpreise
fuels: [heating_oil, pellets, natural_gas]
range: 1y            # 6m, 1y, 3y oder max
show_comparison: true
entry_id: ...        # nur nötig, wenn mehrere Länder eingerichtet sind
```

## Beispiel: Benachrichtigung bei günstigem Heizöl

```yaml
triggers:
  - trigger: state
    entity_id: sensor.heizol_preisbewertung
    to: low
actions:
  - action: notify.notify
    data:
      title: Heizöl ist gerade günstig
      message: >-
        {{ states('sensor.heizol_preis') }} €/100 L –
        günstig im Vergleich zu den letzten 12 Monaten.
```

## Datenquellen

| Brennstoff | Quelle | Aktualisierung | Lizenz |
|---|---|---|---|
| Heizöl | [EU Weekly Oil Bulletin](https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en) (Europäische Kommission) | wöchentlich | Wiedergabe mit Quellenangabe erlaubt |
| Holzpellets | [DEPI-Pelletpreis](https://www.depi.de/pelletpreis-wirtschaftlichkeit/) (Deutsches Pelletinstitut) | monatlich | Honorarfrei mit Quellenangabe |
| Erdgas | [Eurostat nrg_pc_202 und prc_hicp_minr](https://ec.europa.eu/eurostat/databrowser/view/nrg_pc_202/default/table) | halbjährlich und Index monatlich | CC BY 4.0 |

Die Integration fragt die Quellen alle 6 Stunden ab. Die große Heizöl-Historie (ca. 4,5 MB)
wird höchstens einmal im Monat geladen.

**Warum keine tagesaktuellen Händlerpreise?** Portale wie HeizOel24 oder HeizPellets24
verbieten in ihren AGB den automatisierten Abruf. Diese Integration nutzt deshalb nur
Quellen, deren Daten ausdrücklich weiterverwendet werden dürfen.

**Warum ist der Gaspreis „geschätzt“?** Eurostat veröffentlicht Haushaltsgaspreise nur
halbjährlich. Der letzte amtliche Wert wird mit dem monatlichen Gaspreisindex
(HVPI) fortgeschrieben. Der amtliche Wert steht im Attribut `official_price`.

**Wärmepreis:** Umrechnung mit 10 kWh pro Liter Heizöl und 4,9 kWh pro kg Pellets
(Heizwert). Wirkungsgrade der Heizung sind nicht berücksichtigt.

## Haftungsausschluss

Alle Angaben ohne Gewähr. Die Preise sind Durchschnittswerte, dein Angebot vor Ort kann
abweichen. Dieses Projekt steht in keiner Verbindung zu den genannten Datenquellen.

---

## English

**Heating Prices** brings heating oil, wood pellet and natural gas prices into
Home Assistant, using open data only:

- **Heating oil**: weekly consumer prices incl. taxes for 27 EU countries (EU Weekly Oil Bulletin), history back to 2005
- **Wood pellets**: monthly DEPI price for Germany, nationwide or by region
- **Natural gas**: Eurostat household price for 27 EU countries, carried forward with the monthly gas price index (marked as an estimate)

Each fuel gets sensors for price, price per kWh of heat, change and a 12-month price
rating (low/normal/high). A dashboard card (`custom:heating-prices-card`) is registered
automatically. It shows trends, sparklines, a per-kWh comparison and your own price
compared with the market.

Install through HACS as a custom repository (category *Integration*), restart, then add
**Heating Prices** under *Settings → Devices & services*. The UI is available in English
and German.

## License

Code: [MIT](LICENSE). Price data belongs to the respective sources (see above).
