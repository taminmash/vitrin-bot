# Radar Job Source Research — 2026-07-23

This research applies the repository rule that an operational source must be
enabled, return real vacancies through a documented public interface, expose
deterministic identity and canonical URLs, and require neither login nor
restricted automation. Volume figures are directional estimates based on the
visible inventory and expected posting turnover at the time of research.

| Source | Official website | Region | Access | Auth | Stable ID / canonical URL | Access concerns | Complexity | Est. new vacancies/day | Implement |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LABORA / Punt LABORA | https://puntlabora.gva.es/puntlabora/ | Comunitat Valenciana | Dynamic HTML application | Registration needed for candidate services | Not verified in a stable public feed | No documented public API/RSS; application-centric flow | High | 20–80 | NO — no stable documented machine-readable vacancy endpoint verified |
| Lanbide | https://www.lanbide.euskadi.eus/inicio/ | Euskadi | Web application | Registration required to access offers | Not publicly verified | Official guidance says access to listed jobs requires demandante registration | High | 20–80 | NO — login-required vacancy access |
| SAE Andalucía | https://saempleo.es/ | Andalucía | Dynamic HTML application | Registration required for personalized area/application | Not verified in public feed | No documented public vacancy API/RSS; do not reverse engineer the application | High | 30–120 | NO — no compliant stable endpoint verified |
| Servicio Canario de Empleo | https://www.gobiernodecanarias.org/empleo/sce/principal/areas_tematicas/empleo/demanda_y_ofertas_de_empleo/buscador_ofertas_empleo.html | Canarias | Public HTML search | No login for search; registration for application | Stable detail identity not verified | Public page exists, but no documented feed/API or verified canonical per-offer IDs | Medium | 10–40 | NO — deterministic identity/canonical detail contract not verified |
| ECYL | https://empleocastillayleon.jcyl.es/ | Castilla y León | Web portal | Varies | Not verified | No current stable public vacancy feed/API found | High | 10–50 | NO — no compliant endpoint verified |
| Emprego Galicia | https://emprego.xunta.gal/es/demandantes/busca-empleo/busca-trabajo-en-galicia | Galicia | Public HTML search | Login required to submit | Offer numbers exist; search uses CSRF/session parameters | Search flow is session-bound and has no documented feed/API | High | 20–80 | NO — session/CSRF-dependent access is not repository-compatible |
| INAEM Aragón | https://inaem.aragon.es/ | Aragón | Web portal | Varies | Not verified | No documented stable public vacancy feed/API found | High | 10–50 | NO — no compliant endpoint verified |
| Servicio Navarro de Empleo | https://www.navarra.es/es/tramites/on/-/line/ofertas-de-empleo | Navarra | Linked employment platform | Registration required | Not publicly verified | Official page requires registration for the vacancy platform | High | 5–30 | NO — login-required source |
| 2K Madrid Careers | https://job-boards.greenhouse.io/2kmadrid | Madrid | Documented Greenhouse Job Board API (JSON) | None for GET | Greenhouse job ID and `absolute_url` | Public documented API; normal rate/availability risk only | Low | 0–2 | YES |
| Keyfactor Spain Careers | https://job-boards.greenhouse.io/keyfactorinc | Spain | Documented Greenhouse Job Board API (JSON) | None for GET | Greenhouse job ID and `absolute_url` | Global board requires deterministic Spain-location filter | Low | 0–2 | YES |
| Scopely Spain Careers | https://job-boards.greenhouse.io/scopely | Spain | Documented Greenhouse Job Board API (JSON) | None for GET | Greenhouse job ID and `absolute_url` | Global board requires deterministic Spain-location filter | Low | 2–8 | YES |
| Tripadvisor / TheFork Careers | https://job-boards.greenhouse.io/tripadvisor | Barcelona | Documented Greenhouse Job Board API (JSON) | None for GET | Greenhouse job ID and `absolute_url` | Global board; Spain subset was small and overlaps the selected Barcelona technology cohort | Low | 0–2 | NO — deferred to keep the first ATS batch bounded after three qualifying sources were selected |
| Lodgify Careers | https://jobs.lever.co/lodgify | Spain / Barcelona | Documented public Lever Postings API (JSON) | None for published GET postings | UUID and hosted Lever URL | Requires a second ATS parser and additional contract surface | Medium | 0–3 | NO — deferred; three lower-complexity Greenhouse sources satisfy this revision |

Greenhouse documents that Job Board API GET data is public and requires no
authentication:
https://developer.greenhouse.io/job-board.html

The implemented boards are allowlisted explicitly. The connector rejects
prospect posts, non-Spain locations, duplicate IDs, malformed records, and
canonical URLs outside Greenhouse's public job-board hosts. It never submits
applications or accesses candidate data.

EURES, Barcelona Activa, and Generalitat/SOC remain researched-but-not-
implemented in project documentation. They are intentionally absent from the
operational source registry.
