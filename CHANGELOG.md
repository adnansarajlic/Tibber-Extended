# Changelog

Alla anmärkningsvärda ändringar i projektet kommer att dokumenteras i denna fil.

## [Unreleased]

### Added
- **Underenheter (Öre / Cent)**: Ny inställning för att visa priser i underenheter. Konverterar automatiskt `kr` till `öre` och `EUR` till `ct` så att priser och relaterade attribut (ex. `current_total`, `min`, `max`) visas som t.ex. "95 öre/kWh" istället för "0.95 kr/kWh".
- **Binära Automationssensorer**: Två nya smarta binära sensorer läggs automatiskt till (`binary_sensor.mitt_hem_best_price` och `peak_price`). Dessa slås automatiskt PÅ under de sammanhängande N-timmarna som är absolut billigast (eller dyrast). Den nya intelligensen tittar på **både idag och imorgon** (när priset släpps), vilket gör att maskinen själv kan skjuta en planerad start till dagen efter om det är billigare, eller hitta fönster över midnatten! Perfekt för elbil!
- **Konfigurerbara Måltimmar & Tidsfönster**: Bestäm helt själv i integrationens _Configure_-dialog om "billigast period" innebär 1, 2, 3 eller upp till 6 timmar (Standard är 3 timmar). Du kan dessutom tidsbegränsa sökningen, exempelvis till att endast leta dalar mellan 22:00 och 06:00.
- **Refresh-knapp**: En ny knappentitet (`button.[hemnamn]_update_prices`) för att manuellt kunna begära en prishämtning när som helst.
- **Utökad Loggning**: Mätning av API-svarstider i millisekunder samt extra information i loggarna vid fel och automagiska retries.
- **Native Price Timeline Card Stöd**: Sensorn exponerar nu attributet `data` (och aliaset `timeline_data`) formaterat exakt för att fungera plug-and-play med kortet `ha-price-timeline-card` från Lovelace. Kombinerar automatiskt "idag" och "imorgon" i en snygg graf utan extra konfiguration.

### Changed
- **Optimerad API-förfrågan**: Morgondagens priser hämtas nu enbart efter klockan 12:45 för att drastiskt minska datalasten och förhindra `504 Gateway Timeout` hos Tibber.
- **Timeout-gränser**: Ökade timeout-toleransen från 10s till 30s under installation, och från 30s till 45s i underliggande prisuppdateringar.

### Fixed
- **Stabilitet vid API-fel**: Lade till automatisk retry-logik (upp till 2 försök med 2 sekunders fördröjning) om en `504 Gateway Timeout` eller nätverksfel inträffar.
