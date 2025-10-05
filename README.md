# Tibber Extended för Home Assistant

En custom integration som hämtar elpriser och prisnivåer från Tibber's API med stöd för kvarts- och timupplösning.

## ✨ Funktioner

- 🔄 Automatisk hämtning av dagens och morgondagens elpriser
- 📊 Prisnivåer (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE)
- ⏰ Konfigurerbar uppdateringstid (standard kl. 15:00)
- 🕐 Stöd för QUARTER_HOURLY (15 min) eller HOURLY upplösning
- 🏠 Stöd för flera hem på samma Tibber-konto
- 🌍 Svenskt och engelskt språkstöd

## 📦 Installation via HACS

### Metod 1: HACS (Rekommenderat)

1. Öppna HACS i Home Assistant
2. Klicka på "Integrations"
3. Klicka på de tre prickarna längst upp till höger
4. Välj "Custom repositories"
5. Lägg till URL: `https://github.com/adnansarajlic/tibber-extended`
6. Välj kategori: "Integration"
7. Klicka "ADD"
8. Sök efter "Tibber Extended" och installera
9. Starta om Home Assistant

### Metod 2: Manuell Installation

1. Ladda ner eller klona detta repository
2. Kopiera mappen `custom_components/tibber_extended` till din Home Assistant `custom_components` mapp
3. Starta om Home Assistant

## ⚙️ Konfiguration

### Hämta din Tibber API Token

1. Gå till [Tibber Developer Portal](https://developer.tibber.com/)
2. Logga in med ditt Tibber-konto
3. Skapa en ny token eller använd en befintlig
4. Kopiera token (börjar med något liknande: `5K4MVS-OjfWhK_4yrjOlFe1F6kJXPVf7eQYggo8ebAE`)

### Lägg till Integration

1. Gå till **Inställningar** → **Enheter och tjänster**
2. Klicka på **+ LÄGG TILL INTEGRATION**
3. Sök efter "Tibber Extended"
4. Ange din API-token
5. Välj inställningar:
   - **Prisupplösning**: QUARTER_HOURLY (15 min) eller HOURLY (60 min)
   - **Uppdateringstimme**: Vilken timme uppdatering ska ske (0-23)
   - **Uppdateringsminut**: Vilken minut uppdatering ska ske (0-59)

Standard är 15:00 (kl. 15.00) vilket är när Tibber brukar publicera morgondagens priser.

## 📊 Sensorer

Integrationen skapar följande sensorer för varje hem:

### 1. `sensor.tibber_[hemnamn]_current_price`
- **Beskrivning**: Aktuellt elpris just nu
- **Enhet**: kr/kWh
- **Uppdateras**: Varje kvart (eller timme beroende på upplösning)

### 2. `sensor.tibber_[hemnamn]_current_level`
- **Beskrivning**: Aktuell prisnivå
- **Värden**: 
  - `VERY_CHEAP` - Mycket billigt
  - `CHEAP` - Billigt
  - `NORMAL` - Normalt
  - `EXPENSIVE` - Dyrt
  - `VERY_EXPENSIVE` - Mycket dyrt

### 3. `sensor.tibber_[hemnamn]_today_prices`
- **Beskrivning**: Dagens alla priser
- **Attribut**: 
  - `prices`: Lista med alla prispoäng för dagen
  - `resolution`: Upplösning (QUARTER_HOURLY/HOURLY)

Varje prispoäng innehåller:
```json
{
  "total": 0.0956,
  "startsAt": "2025-10-05T00:00:00.000+02:00",
  "level": "VERY_CHEAP"
}
```

### 4. `sensor.tibber_[hemnamn]_tomorrow_prices`
- **Beskrivning**: Morgondagens alla priser
- **Attribut**: Samma struktur som today_prices

## 🤖 Automatiseringsexempel

### Starta tvättmaskin när priset är billigt

```yaml
automation:
  - alias: "Starta tvättmaskin vid lågt elpris"
    trigger:
      - platform: state
        entity_id: sensor.tibber_hemnamn_current_level
        to: "VERY_CHEAP"
    condition:
      - condition: time
        after: "06:00:00"
        before: "22:00:00"
    action:
      - service: notify.mobile_app
        data:
          title: "Lågt elpris!"
          message: "Nu är elpriset mycket lågt ({{ states('sensor.tibber_hemnamn_current_price') }} kr/kWh). Bra tid att starta tvättmaskin!"
```

### Notifikation när morgondagens priser finns

```yaml
automation:
  - alias: "Morgondagens elpriser tillgängliga"
    trigger:
      - platform: state
        entity_id: sensor.tibber_hemnamn_tomorrow_prices
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state | int > 0 }}"
    action:
      - service: notify.mobile_app
        data:
          title: "Morgondagens elpriser"
          message: "Morgondagens priser är nu tillgängliga. Totalt {{ states('sensor.tibber_hemnamn_tomorrow_prices') }} prispoäng."
```

### Hitta billigaste timmen idag

```yaml
sensor:
  - platform: template
    sensors:
      cheapest_hour_today:
        friendly_name: "Billigaste timmen idag"
        value_template: >
          {% set prices = state_attr('sensor.tibber_hemnamn_today_prices', 'prices') %}
          {% if prices %}
            {% set min_price = prices | map(attribute='total') | min %}
            {% set cheapest = prices | selectattr('total', 'eq', min_price) | list | first %}
            {{ as_timestamp(cheapest.startsAt) | timestamp_custom('%H:%M') }}
          {% else %}
            Okänd
          {% endif %}
        attribute_templates:
          price: >
            {% set prices = state_attr('sensor.tibber_hemnamn_today_prices', 'prices') %}
            {% if prices %}
              {{ prices | map(attribute='total') | min }}
            {% endif %}
```

### Slå på värmepump under billiga timmar

```yaml
automation:
  - alias: "Värmepump - Billiga timmar"
    trigger:
      - platform: time_pattern
        minutes: "/15"  # Kolla var 15:e minut
    condition:
      - condition: or
        conditions:
          - condition: state
            entity_id: sensor.tibber_hemnamn_current_level
            state: "VERY_CHEAP"
          - condition: state
            entity_id: sensor.tibber_hemnamn_current_level
            state: "CHEAP"
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.varmepump
        data:
          temperature: 23
```

## 🔧 Felsökning

### Ingen data hämtas

1. Kontrollera att din API-token är korrekt
2. Verifiera att du har tillgång till Tibber API på [developer.tibber.com](https://developer.tibber.com/)
3. Kolla Home Assistant loggar: **Inställningar** → **System** → **Loggar**

### Prisnivåer visas som "UNKNOWN"

Detta kan hända om:
- Tibber inte har publicerat prisdata ännu (morgondagens priser publiceras ca kl 13:00-14:00)
- API-token saknar behörighet
- Nätverksproblem

### Ändra uppdateringstid

1. Gå till **Inställningar** → **Enheter och tjänster**
2. Hitta "Tibber Extended"
3. Klicka på **KONFIGURERA**
4. Ändra timme/minut för uppdatering

## 🤝 Bidra

Bidrag är välkomna! Skapa gärna issues eller pull requests på GitHub.

## 📄 Licens

MIT License

## 🙏 Tack till

- [Tibber](https://tibber.com/) för deras fantastiska API
- Home Assistant-communityn

## 📞 Support

- GitHub Issues: [https://github.com/yourusername/tibber-extended/issues](https://github.com/yourusername/tibber-extended/issues)
- Home Assistant Community: [community.home-assistant.io](https://community.home-assistant.io/)

---

**Obs!** Denna integration är inte officiellt supporterad av Tibber.
