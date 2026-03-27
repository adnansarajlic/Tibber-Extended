# Changelog

Alla anmärkningsvärda ändringar i projektet kommer att dokumenteras i denna fil.

## [1.1.2] - 2026-03-27

### Added
- **Robust Tidszonshantering via API**: Integrationen hämtar nu `timeZone` (t.ex. `Europe/Stockholm`) direkt från Tibbers API. Detta säkerställer att midnattsskift, prisuppdateringar och `fetch_tomorrow`-logik alltid sker vid rätt tidpunkt, oavsett var din Home Assistant-server är placerad fysiskt eller vilken tidszon den är inställd på.
- **Smart Caching**: Implementerat en intelligent växel som kollar om aktuell prisdata för idag och imorgon redan finns i minnet innan ett API-anrop görs. Detta minskar antalet onödiga anrop och sparar på din API-kvota.
- **Jitter (Slumpmässig fördröjning)**: Lagt till en slumpmässig fördröjning på 1–60 sekunder vid schemalagda uppdateringar för att undvika "thundering herd"-problem och göra integrationens trafikprofil mer naturlig.
- **Unik User-Agent**: Vi skickar nu med `HomeAssistant/Tibber-Extended (v1.1.2)` i alla anrop för att identifiera integrationen korrekt mot Tibbers servrar, vilket underlättar felsökning och stabilitet bakom VPN.
- **Manual Refresh Bypass**: Den manuella refresh-knappen tvingar nu alltid fram ett nytt API-anrop och hoppar över den smarta cachningen, för de gånger du vill ha absolut senaste data direkt.
- **Underenheter (Öre / Cent)**: Ny inställning för att visa priser i underenheter. Konverterar automatiskt `kr` till `öre` och `EUR` till `ct`.
- **Binära Automationssensorer**: Smarta binära sensorer som tittar på både idag och imorgon.
- **Refresh-knapp**: En ny knappentitet för manuell uppdatering.
- **Native Price Timeline Card Stöd**: Attributet `data` (och aliaset `timeline_data`) formaterat för plug-and-play med `ha-price-timeline-card`.

### Changed
- **Shared ClientSession**: Integrationen använder nu Home Assistants globala `aiohttp`-session vilket ger bättre prestanda, snabbare handskakningar och högre stabilitet vid användning av VPN.
- **Exponential Backoff**: Vid API-fel eller Rate Limiting (429) väntar nu integrationen progressivt längre (2, 4, 8 sekunder) och respekterar Tibbers `Retry-After`-headrar.
- **Optimerad API-förfrågan**: Morgondagens priser hämtas nu enbart efter klockan 12:45.
- **Timeout-gränser**: Ökade timeout till 45s för bättre tolerans vid segt nätverk.

### Fixed
- **Linting (E701)**: Fixat 111 stycken lint-fel för att följa PEP8-standard och säkerställa hög kodkvalitet.
- **Stabilitet vid API-fel**: Förbättrad felhantering och loggning vid 5xx-fel.
- **Apex Charts Krasch**: Raderat dubblett-attributet `template_data` som kunde orsaka krascher i vissa dashboards.
