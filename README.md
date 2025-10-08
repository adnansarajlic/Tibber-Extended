# Tibber Extended för Home Assistant

<p align="center">
  <img src="https://github.com/adnansarajlic/tibber-extended/raw/main/logo.png" alt="Tibber Extended Logo" width="200"/>
</p>

En kraftfull custom integration som hämtar elpriser och prisnivåer från Tibber's API med avancerade funktioner.

## ✨ Funktioner

- 🔄 Automatisk hämtning av dagens och morgondagens elpriser
- 📊 Prisnivåer (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE) direkt från Tibber
- ⏰ Flera konfigurerbara uppdateringstider (t.ex. kl 13:00 och 15:00)
- 🕐 Stöd för QUARTER_HOURLY (15 min) eller HOURLY (60 min) upplösning
- 🏠 Anpassningsbara hemnamn för sensornamn
- 💱 Välj valuta (SEK, NOK, EUR, DKK)
- 🆓 Demo-token inkluderad för testning
- 🌍 Svenskt och engelskt språkstöd
- 📈 Detaljerad prisdata: total, energi, skatt
- ⚡ Automatisk uppdatering varje kvart/timme
- 🔧 Ändra inställningar utan att ta bort integration
- 📈 Automatisk beräkning av min/max/medelpris

## 📦 Installation via HACS

### Metod 1: HACS (Rekommenderat)

1. Öppna HACS i Home Assistant
2. Klicka på **"Integrations"**
3. Klicka på de tre prickarna längst upp till höger
4. Välj **"Custom repositories"**
5. Lägg till URL: `https://github.com/adnansarajlic/tibber-extended`
6. Välj kategori: **"Integration"**
7. Klicka **"ADD"**
8. Sök efter **"Tibber Extended"** och installera
9. Starta om Home Assistant

### Metod 2: Manuell Installation

1. Ladda ner senaste release från GitHub
2. Kopiera mappen `custom_components/tibber_extended` till din Home Assistant `config/custom_components` mapp
3. Starta om Home Assistant

## ⚙️ Konfiguration

### 1. Hämta din Tibber API Token (Valfritt)

**OBS:** Du kan använda den inkluderade demo-token för testning, men den kan sluta fungera utan förvarning!

För personlig användning med rätt elområde, hämta din egen token:

1. Gå till [Tibber Developer Portal](https://developer.tibber.com/settings/access-token)
2. Logga in med ditt Tibber-konto
3. Skapa en ny token om den inte redan finns under "Access Token"
4. Kopiera token

### 2. Lägg till Integration

1. Gå till **Inställningar** → **Enheter och tjänster**
2. Klicka på **+ LÄGG TILL INTEGRATION**
3. Sök efter **"Tibber Extended"**
4. Konfigurera:
   - **API Token**: Lämna tomt för demo-token, eller ange din egen
   - **Hemnamn**: T.ex. "Mitt Hem" (används i sensornamn)
   - **Prisupplösning**: QUARTER_HOURLY (15 min) eller HOURLY (60 min)
   - **Valuta**: SEK, NOK, EUR eller DKK
   - **Uppdateringstider**: T.ex. "13:00, 15:00" (kommaseparerade)

**Standardvärden:**
- Demo-token används om inget anges
- Hemnamn: "Mitt Hem"
- Upplösning: QUARTER_HOURLY
- Valuta: SEK
- Uppdateringstider: 13:00 och 15:00

### Varför flera uppdateringstider?

Tibber publicerar:
- **13:00-14:00**: Morgondagens priser släpps oftast här
- **15:00**: Extra kontroll om priser missades
- **20:00** (valfritt): För att säkerställa senaste data

## 📊 Sensor

Integrationen skapar EN sensor per hem:

### `sensor.[hemnamn]_electricity_price`

**State:** Aktuellt totalpris (kr/kWh eller vald valuta)

**Uppdateras automatiskt:**
- QUARTER_HOURLY: Varje 15:e minut
- HOURLY: Varje timme

**Attribut:**
```json
{
  "current_total": 0.0956,
  "current_energy": 0.0650,
  "current_tax": 0.0306,
  "current_level": "VERY_CHEAP",
  "current_starts_at": "2025-10-06T04:00:00.000+02:00",
  "currency": "SEK",
  "resolution": "QUARTER_HOURLY",
  
  "today": {
    "count": 96,
    "prices": [
      {
        "total": 0.0956,
        "energy": 0.0650,
        "tax": 0.0306,
        "startsAt": "2025-10-06T00:00:00.000+02:00",
        "level": "VERY_CHEAP"
      },
      ...
    ],
    "total": {
      "min": 0.0848,
      "max": 0.6634,
      "avg": 0.1234
    },
    "energy": {
      "min": 0.0548,
      "max": 0.6334,
      "avg": 0.0934
    }
  },
  
  "tomorrow": {
    "count": 96,
    "prices": [...],
    "total": {...},
    "energy": {...}
  }
}
```

## 🤖 Automatiseringsexempel

### Starta tvättmaskin vid billigt pris

```yaml
alias: "Notifikation: Billigt elpris"
description: ""
triggers:
  - trigger: state
    entity_id:
      - sensor.mitt_hem_electricity_price
    attribute: current_level
    to: VERY_CHEAP
conditions:
  - condition: time
    after: "06:00:00"
    before: "22:00:00"
actions:
  - action: notify.mobile_app_iphone
    metadata: {}
    data:
      title: ⚡ Mycket billigt elpris!
      message: >
        Nu är elpriset {{ states('sensor.mitt_hem_electricity_price') }}
        kr/kWh.  Perfekt tid att starta tvättmaskin eller diskmaskin!
```

### Hitta billigaste 3-timmarsperioden idag

```yaml
template:
  - sensor:
      - name: "Billigaste 3-timmarsperioden"
        state: >
          {% set today_data = state_attr('sensor.mitt_hem_electricity_price', 'today') %}
          {% if today_data and today_data.prices and today_data.prices | length > 12 %}
            {% set prices = today_data.prices %}
            {% set ns = namespace(best_start=none, best_sum=999) %}
            {% for i in range(0, (prices | length) - 12) %}
              {% set window_sum = prices[i:i+12] | map(attribute='total') | sum %}
              {% if window_sum < ns.best_sum %}
                {% set ns.best_start = i %}
                {% set ns.best_sum = window_sum %}
              {% endif %}
            {% endfor %}
            {% if ns.best_start is not none %}
              {{ (as_timestamp(prices[ns.best_start].startsAt) | timestamp_custom('%H:%M')) }}
            {% endif %}
          {% else %}
            Ej tillgängligt
          {% endif %}
        attributes:
          avg_price: >
            {% set today_data = state_attr('sensor.mitt_hem_electricity_price', 'today') %}
            {% if today_data and today_data.prices and today_data.prices | length > 12 %}
              {% set prices = today_data.prices %}
              {% set ns = namespace(best_start=none, best_sum=999) %}
              {% for i in range(0, (prices | length) - 12) %}
                {% set window_sum = prices[i:i+12] | map(attribute='total') | sum %}
                {% if window_sum < ns.best_sum %}
                  {% set ns.best_start = i %}
                  {% set ns.best_sum = window_sum %}
                {% endif %}
              {% endfor %}
              {{ (ns.best_sum / 12) | round(4) }}
            {% endif %}
          end_time: >
            {% set today_data = state_attr('sensor.mitt_hem_electricity_price', 'today') %}
            {% if today_data and today_data.prices and today_data.prices | length > 12 %}
              {% set prices = today_data.prices %}
              {% set ns = namespace(best_start=none, best_sum=999) %}
              {% for i in range(0, (prices | length) - 12) %}
                {% set window_sum = prices[i:i+12] | map(attribute='total') | sum %}
                {% if window_sum < ns.best_sum %}
                  {% set ns.best_start = i %}
                  {% set ns.best_sum = window_sum %}
                {% endif %}
              {% endfor %}
              {% if ns.best_start is not none %}
                {{ (as_timestamp(prices[ns.best_start + 11].startsAt) | timestamp_custom('%H:%M')) }}
              {% endif %}
            {% endif %}
          period_description: >
            {% set today_data = state_attr('sensor.mitt_hem_electricity_price', 'today') %}
            {% if today_data and today_data.prices and today_data.prices | length > 12 %}
              {% set prices = today_data.prices %}
              {% set ns = namespace(best_start=none, best_sum=999) %}
              {% for i in range(0, (prices | length) - 12) %>
                {% set window_sum = prices[i:i+12] | map(attribute='total') | sum %}
                {% if window_sum < ns.best_sum %}
                  {% set ns.best_start = i %}
                  {% set ns.best_sum = window_sum %}
                {% endif %}
              {% endfor %}
              {% if ns.best_start is not none %}
                {{ (as_timestamp(prices[ns.best_start].startsAt) | timestamp_custom('%H:%M')) }} - {{ (as_timestamp(prices[ns.best_start + 11].startsAt) | timestamp_custom('%H:%M')) }}
              {% endif %}
            {% endif %}

```

### Värmepump - Kör under billiga timmar

```yaml
automation:
  - alias: "Värmepump - Boost under billiga timmar"
    trigger:
      - platform: time_pattern
        minutes: "/15"
    condition:
      - condition: numeric_state
        entity_id: sensor.mitt_hem_electricity_price
        below: 0.09  # Under 9 öre/kWh
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.varmepump
        data:
          temperature: 24

  - alias: "Värmepump - Normal under dyra timmar"
    trigger:
      - platform: time_pattern
        minutes: "/15"
    condition:
      - condition: numeric_state
        entity_id: sensor.mitt_hem_electricity_price
        above: 0.15  # Över 15 öre/kWh
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.varmepump
        data:
          temperature: 20
```

### Visa priser i Apexcharts kort

![Apexcharts Card exempel](image.png)

```yaml
type: custom:apexcharts-card
apex_config:
  legend:
    show: false
experimental:
  color_threshold: true
graph_span: 48h
header:
  title: Elpris idag/imorgon (Tibber)
  show: true
  show_states: true
span:
  start: day
now:
  show: true
  label: Just nu
show:
  last_updated: true
series:
  - entity: sensor.myrvagen_electricity_price
    color_threshold:
      - value: 1.5
        color: "#B13A33"
      - value: 1
        color: "#1982C4FF"
      - value: 0
        color: "#03c03c"
    name: Idag
    type: column
    show:
      extremas: time
      in_header: false
      legend_value: false
    color: "#03c03c"
    float_precision: 2
    data_generator: |
      return entity.attributes.today.prices.map((entry, index) => {
        return [new Date(entry["startsAt"]).getTime(), entry["total"]];
      });
  - entity: sensor.myrvagen_electricity_price
    color_threshold:
      - value: 1.5
        color: "#B13A33"
      - value: 1
        color: "#1982C4FF"
      - value: 0
        color: "#03c03c"
    name: Imorgon
    type: column
    show:
      extremas: time
      in_header: false
      legend_value: false
    color: "#03c03c"
    float_precision: 2
    data_generator: |
      return entity.attributes.tomorrow.prices.map((entry, index) => {
        return [new Date(entry["startsAt"]).getTime(), entry["total"]];
      });
  - entity: sensor.myrvagen_electricity_price
    name: Just nu
    type: column
    show:
      in_chart: false
    float_precision: 2
```

## 🤝 Bidra

Bidrag är välkomna! 

- 🐛 Rapportera buggar via [GitHub Issues](https://github.com/adnansarajlic/tibber-extended/issues)
- 💡 Föreslå nya funktioner
- 🔧 Skicka Pull Requests

## 📄 Licens

MIT License - Se [LICENSE](LICENSE) för detaljer

## 🙏 Tack till

- [Tibber](https://tibber.com/) för deras fantastiska API
- Home Assistant-communityn för inspiration och hjälp

## 📞 Support

- **GitHub Issues**: [github.com/adnansarajlic/tibber-extended/issues](https://github.com/adnansarajlic/tibber-extended/issues)
- **Home Assistant Community**: [community.home-assistant.io](https://community.home-assistant.io/)

---

**⚠️ Viktigt:** Denna integration är inte officiellt supporterad av Tibber. Demo-token tillhandahålls för testning men kan sluta fungera.


**🔒 Säkerhet:** Din API-token lagras säkert i Home Assistant's krypterade storage.
