# Tibber Extended för Home Assistant

<p align="center">
  <img src="https://github.com/adnansarajlic/tibber-extended/raw/main/logo.png" alt="Tibber Extended Logo" width="200"/>
</p>

En kraftfull custom integration som hämtar elpriser från Tibber's GraphQL API med alla tillgängliga datafält.

## ✨ Funktioner

- 🔄 Automatisk hämtning av dagens och morgondagens elpriser
- 📊 Prisnivåer (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE) direkt från Tibber
- ⏰ Flera konfigurerbara uppdateringstider (t.ex. kl 13:00 och 15:00)
- 🕐 Stöd för QUARTER_HOURLY (15 min) eller HOURLY upplösning
- 🏠 Anpassningsbara hemnamn för sensornamn
- 💱 Välj valuta (SEK, NOK, EUR, DKK)
- 🆓 Demo-token inkluderad för testning
- 🌍 Svenskt och engelskt språkstöd
- 📈 Detaljerad prisdata: total, energi, skatt
- ⚡ Automatisk uppdatering varje kvart/timme
- 🔧 Ändra inställningar utan att ta bort integration

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

**OBS:** Du kan använda den inkluderade demo-token för testning, men den kan sluta fungera när som helst!

**Demo-token:** `3A77EECF61BD445F47241A5A36202185C35AF3AF58609E19B53F3A8872AD7BE1-1`

För personlig användning, hämta din egen token:

1. Gå till [Tibber Developer Portal](https://developer.tibber.com/)
2. Logga in med ditt Tibber-konto
3. Skapa en ny token under "Access Token"
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