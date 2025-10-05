# Tibber Extended för Home Assistant

<p align="center">
  <img src="https://github.com/adnansarajlic/tibber-extended/raw/main/logo.png" alt="Tibber Extended Logo" width="200"/>
</p>

En kraftfull custom integration som hämtar elpriser och prisnivåer från Tibber's API med avancerade funktioner.

## ✨ Funktioner

- 🔄 Automatisk hämtning av dagens och morgondagens elpriser
- 📊 Prisnivåer (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE) direkt från Tibber
- ⏰ Flera konfigurerbara uppdateringstider (t.ex. kl 13:00 och 15:00)
- 🕐 Stöd för QUARTER_HOURLY (15 min) eller HOURLY upplösning
- 🏠 Anpassningsbara hemnamn för sensornamn
- 🆓 Demo-token inkluderad för testning
- 🌍 Svenskt och engelskt språkstöd
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

**OBS:** Du kan använda den inkluderade demo-token för testning, men den kan sluta fungera utan någon förvarning!

För produktionsanvändning, hämta din egen token:

1. Gå till [Tibber Developer Portal](https://developer.tibber.com/)
2. Logga in med ditt Tibber-konto
3. Skapa en ny token under "Access Token"
4. Kopiera token (börjar med något liknande: `5K4MVS-OjfWhK_4yrjOlFe1F6kJXPVf7eQYggo8ebAE`)

### 2. Lägg till Integration

1. Gå till **Inställningar** → **Enheter och tjänster**
2. Klicka på **+ LÄGG TILL INTEGRATION**
3. Sök efter **"Tibber Extended"**
4. Konfigurera:
   - **API Token**: Lämna tomt för demo-token, eller ange din egen
   - **Hemnamn**: T.ex. "Mitt Hem" (används i sensornamn)
   - **Prisupplösning**: QUARTER_HOURLY (15 min) eller HOURLY (60 min)
   - **Uppdateringstider**: T.ex. "13:00, 15:00" (kommaseparerade)

**Standardvärden:**
- Demo-token används om inget anges
- Hemnamn: "Mitt Hem"
- Upplösning: QUARTER_HOURLY
- Uppdateringstider: 13:00 och 15:00

### Varför flera uppdateringstider?

Tibber publicerar:
- **13:00-14:00**: Morgondagens priser släpps oftast här
- **15:00**: Extra kontroll om priser missades
- **20:00** (valfritt): För att säkerställa senaste data

## 📊 Sensorer

Integrationen skapar följande sensorer:

### 1. `sensor.[hemnamn]_current_price`
- **Beskrivning**: Aktuellt elpris just nu
- **Enhet**: kr/kWh
- **Ikon**: ⚡
- **Exempel**: `0.0956`

### 2. `sensor.[hemnamn]_current_level`
- **Beskrivning**: Aktuell prisnivå
- **Värden & Ikoner**: 
  - `VERY_CHEAP` ⬇️⬇️ - Mycket billigt
  - `CHEAP` ⬇️ - Billigt
  - `NORMAL` ➖ - Normalt
  - `EXPENSIVE` ⬆️ - Dyrt
  - `VERY_EXPENSIVE` ⬆️⬆️ - Mycket dyrt

### 3. `sensor.[hemnamn]_today_prices`
- **Beskrivning**: Dagens alla priser
- **State**: Antal prispoäng (t.ex. 96 för QUARTER_HOURLY)
- **Attribut**: 
  - `prices`: Lista med alla prispoäng
  - `resolution`: Upplösning
  - `min_price`: Lägsta pris idag
  - `max_price`: Högsta pris idag
  - `avg_price`: Medelpris idag

**Exempel på prispoäng:**
```json
{
  "total": 0.0956,
  "startsAt": "2025-10-05T00:00:00.000+02:00",
  "level": "VERY_CHEAP"
}
```

### 4. `sensor.[hemnamn]_tomorrow_prices`
- **Beskrivning**: Morgondagens alla priser
- **Attribut**: Samma struktur som today_prices
- **OBS**: Tom tills morgondagens priser publiceras (ca 13:00-14:00)

## 🤖 Automatiseringsexempel

### Starta tvättmaskin vid billigt pris

```yaml
automation:
  - alias: "Notifikation: Billigt elpris"
    trigger:
      - platform: state
        entity_id: sensor.mitt_hem_current_level
        to: "VERY_CHEAP"
    condition:
      - condition: time
        after: "06:00:00"
        before: "22:00:00"
    action:
      - service: notify.mobile_app_iphone
        data:
          title: "⚡ Mycket billigt elpris!"
          message: >
            Nu är elpriset {{ states('sensor.mitt_hem_current_price') }} kr/kWh. 
            Perfekt tid att starta tvättmaskin eller diskmaskin!

### Notifikation när morgondagens priser finns

```yaml
automation:
  - alias: "Notifikation: Morgondagens elpriser"
    trigger:
      - platform: state
        entity_id: sensor.mitt_hem_tomorrow_prices
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state | int > 0 }}"
      - condition: template
        value_template: "{{ trigger.from_state.state | int == 0 }}"
    action:
      - service: notify.mobile_app_iphone
        data:
          title: "📊 Morgondagens elpriser"
          message: >
            Morgondagens priser är nu tillgängliga!
            Min: {{ state_attr('sensor.mitt_hem_tomorrow_prices', 'min_price') }} kr/kWh
            Max: {{ state_attr('sensor.mitt_hem_tomorrow_prices', 'max_price') }} kr/kWh
            Medel: {{ state_attr('sensor.mitt_hem_tomorrow_prices', 'avg_price') }} kr/kWh
```

### Hitta billigaste 3-timmarsperioden idag

```yaml
template:
  - sensor:
      - name: "Billigaste 3-timmarsperioden"
        state: >
          {% set prices = state_attr('sensor.mitt_hem_today_prices', 'prices') %}
          {% if prices and prices | length > 12 %}
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
            {% set prices = state_attr('sensor.mitt_hem_today_prices', 'prices') %}
            {% if prices and prices | length > 12 %}
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
        entity_id: sensor.mitt_hem_current_price
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
        entity_id: sensor.mitt_hem_current_price
        above: 0.15  # Över 15 öre/kWh
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.varmepump
        data:
          temperature: 20
```

## 🔧 Felsökning

### Ingen data hämtas

1. ✅ Kontrollera att integrationen är korrekt installerad
2. ✅ Om du använder egen token, verifiera den på [developer.tibber.com](https://developer.tibber.com/)
3. ✅ Kolla Home Assistant loggar: **Inställningar** → **System** → **Loggar**
4. ✅ Sök efter "tibber_extended" i loggarna

### Demo-token slutar fungera

Demo-token kan när som helst sluta fungera. Lösning:
1. Gå till **Inställningar** → **Enheter och tjänster**
2. Hitta **"Tibber Extended"**
3. Klicka på **KONFIGURERA**
4. Ta bort integrationen och lägg till igen med egen token

### Prisnivåer visas som "UNKNOWN"

Detta kan hända om:
- Tibber inte har publicerat prisdata ännu (vänta till 13:00-14:00)
- API-token är ogiltig eller saknar behörighet
- Nätverksproblem mellan Home Assistant och Tibber

### Ändra uppdateringstider

1. Gå till **Inställningar** → **Enheter och tjänster**
2. Hitta **"Tibber Extended"**
3. Klicka på **⚙️ KONFIGURERA**
4. Ändra "Uppdateringstider" (t.ex. "13:00, 15:00, 20:00")

### Debug-läge

Aktivera debug-loggar i `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.tibber_extended: debug
```

Starta om Home Assistant och kolla loggarna.

## 📈 Statistik och Historik

Du kan skapa långtidsstatistik med utility meter:

```yaml
utility_meter:
  electricity_cost_daily:
    source: sensor.mitt_hem_current_price
    cycle: daily
  
  electricity_cost_monthly:
    source: sensor.mitt_hem_current_price
    cycle: monthly
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

**⚠️ Viktigt:** Denna integration är inte officiellt supporterad av Tibber. Demo-token tillhandahålls för testning men kan sluta fungera när som helst.

**🔒 Säkerhet:** Din API-token lagras säkert i Home Assistant's krypterade storage.