# Changelog

Alla anmärkningsvärda ändringar i projektet kommer att dokumenteras i denna fil.

## [Unreleased]

### Added
- **Refresh-knapp**: En ny knappentitet (`button.[hemnamn]_update_prices`) för att manuellt kunna begära en prishämtning när som helst.
- **Utökad Loggning**: Mätning av API-svarstider i millisekunder samt extra information i loggarna vid fel och automagiska retries.

### Changed
- **Optimerad API-förfrågan**: Morgondagens priser hämtas nu enbart efter klockan 12:45 för att drastiskt minska datalasten och förhindra `504 Gateway Timeout` hos Tibber.
- **Timeout-gränser**: Ökade timeout-toleransen från 10s till 30s under installation, och från 30s till 45s i underliggande prisuppdateringar.

### Fixed
- **Stabilitet vid API-fel**: Lade till automatisk retry-logik (upp till 2 försök med 2 sekunders fördröjning) om en `504 Gateway Timeout` eller nätverksfel inträffar.
