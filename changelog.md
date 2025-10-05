# Changelog

Alla betydande ändringar i Tibber Extended dokumenteras här.

Formatet är baserat på [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
och projektet följer [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-10-05

### 🎉 Första officiella release!

#### ✨ Tillagt
- **Demo-token som standard**: Användare kan lämna token-fältet tomt för att använda Tibbers officiella demo-token
- **Anpassningsbara hemnamn**: Ge ditt hem ett eget namn som används i alla sensornamn (t.ex. "Mitt Hem", "Villan")
- **Flera uppdateringstider**: Stöd för flera API-anrop per dag, konfigurerbart via kommaseparerade tider (t.ex. "13:00, 15:00, 20:00")
- **4 sensorer per hem**:
  - `current_price`: Aktuellt elpris i kr/kWh
  - `current_level`: Prisnivå (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE)
  - `today_prices`: Alla dagens priser med statistik (min, max, medel)
  - `tomorrow_prices`: Morgondagens priser med statistik
- **Dynamiska ikoner**: Sensorer ändrar ikon baserat på prisnivå (pilar upp/ner)
- **Prisstatistik**: Automatisk beräkning av min/max/medelpris i sensor-attribut
- **Svensk och engelsk översättning**: Fullständigt flerspråksstöd
- **GraphQL API-integration**: Hämtar data direkt från Tibbers officiella API
- **Konfigurerbar upplösning**: Välj mellan QUARTER_HOURLY (15 min) eller HOURLY (60 min)
- **Config Flow**: Grafiskt konfigurationsgränssnitt med validering
- **Options Flow**: Ändra inställningar efter installation utan att ta bort integrationen
- **Tidbaserade triggers**: Automatiska uppdateringar vid konfigurerade tider
- **Felhantering**: Robust hantering av API-fel och timeouts
- **HACS-kompatibel**: Redo för installation via HACS

#### 🔧 Tekniskt
- Använder Home Assistant's DataUpdateCoordinator för effektiv datahantering
- Async/await för alla API-anrop
- Proper entity naming med unique_id för återställning
- CoordinatorEntity för automatisk uppdatering av alla sensorer
- Time-based triggers istället för polling
- Validering av tidsformat (HH:MM)
- Token-validering vid setup

#### 📚 Dokumentation
- Omfattande README med installationsinstruktioner
- Automatiseringsexempel för vanliga användningsfall
- Felsökningsguide
- API-dokumentation
- Kodexempel för templates och dashboards

#### 🎨 Design
- Stöd för custom ikon (Tibber TE-logotyp)
- Moderna ikoner för olika prisnivåer
- Tydlig UI-text på svenska och engelska

### 🔒 Säkerhet
- API-token lagras krypterat i Home Assistant
- Ingen lokal lagring av känslig data
- HTTPS för alla API-anrop
- Token-validering före användning

### ⚙️ Konfiguration
#### Standardvärden
- **Token**: Tibber demo-token om inget anges
- **Hemnamn**: "Mitt Hem"
- **Upplösning**: QUARTER_HOURLY (15 min intervall)
- **Uppdateringstider**: 13:00 och 15:00

### 📋 Kända begränsningar
- Demo-token kan sluta fungera när som helst (använd egen token för produktion)
- Morgondagens priser finns först ca 13:00-14:00
- Max 3 uppdateringstider rekommenderas för att inte överbelasta API

### 🐛 Bugfixar
- Ingen (första release)

---

## [Unreleased]

### Planerade funktioner för framtida versioner

#### v1.1.0 (Nästa minor version)
- [ ] Stöd för historiska priser (senaste 7 dagarna)
- [ ] Prisvarningar via notifikationer
- [ ] Fördefinierade automatiseringsblueprintser
- [ ] Dashboard-kort för Lovelace

#### v1.2.0
- [ ] Statistik och trendanalys
- [ ] Jämförelse mellan dagar/veckor
- [ ] Prognoser baserat på historik
- [ ] Export av data till CSV/JSON

#### v2.0.0 (Breaking changes)
- [ ] Stöd för flera Tibber-konton samtidigt
- [ ] Integration med Home Assistant Energy Dashboard
- [ ] Advanced scheduling engine
- [ ] REST API för externa system

### Önskemål från community
- Lägg till via [GitHub Issues](https://github.com/adnansarajlic/tibber-extended/issues)

---

## Versionsnumrering

Vi följer [Semantic Versioning](https://semver.org/):
- **MAJOR** version (X.0.0) - Breaking changes
- **MINOR** version (0.X.0) - Nya funktioner, bakåtkompatibelt
- **PATCH** version (0.0.X) - Bugfixar, bakåtkompatibelt

## Support

För support, bug reports eller feature requests:
- GitHub Issues: https://github.com/adnansarajlic/tibber-extended/issues
- GitHub Discussions: https://github.com/adnansarajlic/tibber-extended/discussions

---

**Tack för att du använder Tibber Extended! 🎉**