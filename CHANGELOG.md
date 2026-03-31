# Changelog

Alla anmärkningsvärda ändringar i projektet kommer att dokumenteras i denna fil.

## [1.2.3] - 2026-03-31
 
### Fixed
- **Stabilitetsfix för aktiva fönster**: Åtgärdat ett kritiskt fel där "Best Price"-sensorer oavsiktligt räknades om exakt när deras fönster startade, vilket orsakade hopp till andra tider i förtid (när ny prisdata inkom under körning). Nu låses fönstret fast så länge det är *aktivt* (`period_end > now`).

## [1.2.2] - 2026-03-30
 
 ### Fixed
 - Åtgärdat `ValueError` för `entity_category`. Nu används `EntityCategory.DIAGNOSTIC` istället för en sträng.
 
-## [1.2.1] - 2026-03-30

### Fixed
- Åtgärdat `ModuleNotFoundError` för `RestoreEntity`. Importen flyttad från `components.restore_state` till `helpers.restore_state`.

## [1.2.0] - 2026-03-29

### Added
- **Persistent Storage**: Data hämtad från Tibber sparas nu lokalt på disken. Detta gör att integrationen kan starta snabbare och behålla historisk data utan att omedelbart behöva anropa API:et vid varje Home Assistant-omstart.
- **State Restoration**: Beräknade tidsfönster för "Best Price" sparas nu i Home Assistants state machine och återställs vid omstart.
- **Utökad stabilitet för sensorer**: Implementerat logik som förhindrar att ett planerat fönster "hoppar" till en annan tidpunkt när ny data kommer in, så länge det nuvarande valet fortfarande är giltigt och i framtiden.
- **Massiv testsvit-uppdatering**: Utökat testerna från 59 till 95 st för att täcka allt från storage-logik till API-retries och sensor-stabilitet. Testerna är nu uppdelade i flera filer för bättre underhåll.
- **Moderniserad CI**: Uppdaterat GitHub Actions för att köra tester på Python 3.12, 3.13 och 3.14 för att matcha de senaste standarderna i Home Assistant Core.

### Changed
- Refaktorerat koordinatorn för att använda Home Assistants officiella `Store`-helper för lagring.
- Centraliserat all test-infrastruktur i `conftest.py` för stabilare och snabbare testkörningar.

## [1.1.9] - 2026-03-28

### Added
- **Individuella tidsfönster per Best Price-spann**: Nu går det att styra exakt när olika sensorer ska vara aktiva genom att använda hakparenteser i inställningarna.
    - Exempel: `1, 3[22:00-06:00]` skapar en 1h-sensor (globalt fönster) och en 3h-sensor (begränsad till 22-06).
- **Tydligare inställningar**: De globala fälten för tidsbegränsning är nu märkta med "(Global)" för att tydliggöra att de fungerar som standardvärden om inget annat anges för ett specifikt spann.

### Changed
- Refaktorerat `utils.py` och `binary_sensor.py` för att stödja den nya avancerade konfigurationen.
- Utökat testsviten till 58 tester för att täcka den nya logiken.


## [1.1.8] - 2026-03-28

### Added
- **Automatisk städning av Best Price-sensorer**: När man ändrar eller tar bort ett tidsspann i inställningarna (t.ex. går från `1, 3` till bara `3`) kommer den föräldralösa entiteten (`best_price 1h`) nu automatiskt att tas bort från Home Assistant. Detta håller listan över entiteter ren och snygg.

### Fixed
- **Ruff Linting**: Åtgärdat alla linting-varningar och fel för att följa Home Assistants kodstandarder.
- **Robustare Tester**: Utökat test-sviten till 52 tester med täckning för automatisk städning.


## [1.1.7] - 2026-03-27

### Added
- **Stöd för multipla Best Price-sensorer**: Nu kan man konfigurera flera olika tidsspann för billigaste pris (t.ex. `1, 3, 6`) som resulterar i separata binära sensorer. Perfekt för att styra olika laster med olika behov.

### Changed
- Refaktorerat `best_price_target_hours` till `best_price_spans` (textfält istället för dropdown).

### Documentation
- Uppdaterat README med instruktioner för de nya multipla sensorerna.


## [1.1.6] - 2026-03-27

### Changed
- **Split av förbrukningssensor**: Den tidigare kombinerade månadsförbrukningssensorn har delats upp i två separata enheter: `Monthly Consumption` (kWh) och `Monthly Cost` (Valuta). Detta ger bättre kompatibilitet med HAs interna statistikverktyg och dashboards.
- **Hårdkodad schemaläggning**: Uppdateringstiderna är nu hårdkodade till 13, 14, 15 för enklare setup.
- **Boolean-fix för availability**: Säkerställt att sensorernas `available`-egenskap alltid returnerar en ren boolean, vilket fixar potentiella problem i HA:s state machine.

### Added
- **Utökad testsvit**: Lagt till 4 nya robusta tester (totalt 50 st) som verifierar schemaläggningslogik, Smart Caching edge-cases och sensorernas tillgänglighetsstatus.

### Documentation
- Uppdaterat README för att reflektera sensor-splitten och den automatiserade schemaläggningen.


## [1.1.4] - 2026-03-27

### Added
- **Månadsförbruknings-sensor**: Ny sensor som visar total kWh och ackumulerad kostnad för den pågående kalendermånaden.
- **Elnätsbolag-sensor**: Diagnostisk sensor som visar vilket elnätsbolag som ansvarar för din adress.
- **Pris-tröskel-sensor**: Ny binär sensor som aktiveras när elpriset går under ett användardefinierat gränsvärde (konfigurerbart via Options Flow).
- **Automationstöd**: Fullt stöd och dokumentation för hur de nya sensorerna kan användas i smarta hem-automatiseringar.

### Fixed
- **Robustare tester**: Utökat testsviten med `tests/test_new_features.py` som verifierar all ny logik för förbrukning och trösklar.

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
