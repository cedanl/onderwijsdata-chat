# Professioneel hosten

Deze pagina beschrijft hoe je `onderwijsdata-chat` productierijp maakt. De lokale standaardinstelling (SQLite, wachtwoordlogin) is bedoeld voor ontwikkeling en demo's.

---

## Overzicht

| Component | Lokaal (standaard) | Productie |
|-----------|-------------------|-----------|
| Database | SQLite (`app.db`) | PostgreSQL (beheerde cloud-service) |
| Authenticatie | Gebruikersnaam/wachtwoord in `.env` | SURF SRAM-login via OIDC (wachtwoordlogin blijft mogelijk als fallback) |

---

## 1. Database — PostgreSQL

SQLite is single-user en niet geschikt voor gelijktijdige toegang door meerdere gebruikers.

### Kies een aanbieder

| Aanbieder | Geschikt voor |
|-----------|---------------|
| **Azure Database for PostgreSQL** | Azure-omgevingen, SURF Research Cloud |
| **Supabase** | Snel opzetten, gratis tier beschikbaar |
| **AWS RDS** | AWS-omgevingen |
| **Self-hosted** | On-premise of eigen server |

### Instellen

De app leest de `POSTGRES_URI` omgevingsvariabele (een gewone libpq-URI; de app gebruikt `psycopg2`):

```dotenv
POSTGRES_URI=postgresql://gebruiker:wachtwoord@host:5432/onderwijsdata_chat
```

Zonder `POSTGRES_URI` valt de app terug op SQLite (`DATABASE_PATH`, standaard `app.db`).

De app maakt de tabellen automatisch aan bij de start (`CREATE TABLE IF NOT EXISTS` in `persistence/db.py`). Alleen de database en de databasegebruiker moeten al bestaan; op een eigen Postgres-server kun je die aanmaken met `scripts/db-init.sql`. Op SURF SDP levert het platform de database en de URI al — zie [Deployment](deployment.md).

!!! warning "Nooit `app.db` committen"
    Het SQLite-bestand staat in `.gitignore`. Houd dat zo — databasebestanden horen niet in de repo.

---

## 2. Authenticatie

Er zijn twee manieren van inloggen, die naast elkaar kunnen bestaan:

- **SURF SRAM via OIDC** — institutionele accounts. Actief zodra `OIDC_PROVIDER` en de overige OIDC-variabelen zijn ingesteld (zie [Configuratie → Authenticatie](configuratie/index.md#chatgeschiedenis-authenticatie)). De implementatie staat in `auth/oidc.py` en `routes/auth.py`; de testomgeving draait hiermee.
- **Gebruikersnaam/wachtwoord** via `CHAT_USERS`, met HMAC-tokens. Handig lokaal, voor demo-accounts en als fallback.

Beide vereisen `CHAT_SECRET` voor het ondertekenen van tokens.

---

## 3. Deployment

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync --no-dev
RUN cd frontend && npm ci && npm run build
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

Geef omgevingsvariabelen mee via Docker of je platform — nooit in de image zelf:

```bash
docker run -p 8000:8000 \
  -e CHAT_SECRET="..." \
  -e CHAT_USERS="admin:wachtwoord" \
  -e AZURE_AI_API_KEY="..." \
  -e MODEL="azure_ai/claude-sonnet-4-6" \
  -e AVAILABLE_MODELS="azure_ai/claude-haiku-4-5,azure_ai/claude-sonnet-4-6,azure_ai/gpt-4o" \
  onderwijsdata-chat
```

### Azure Container Apps

```bash
az containerapp create \
  --name onderwijsdata-chat \
  --resource-group mijn-rg \
  --image ghcr.io/cedanl/onderwijsdata-chat:latest \
  --env-vars \
      CHAT_SECRET=secretref:chat-secret \
      CHAT_USERS=secretref:chat-users \
      AZURE_AI_API_KEY=secretref:api-key \
  --ingress external --target-port 8000
```

### SURF Research Cloud

1. Maak een component aan met het Docker-image
2. Koppel een managed PostgreSQL-instantie
3. Stel omgevingsvariabelen in via de SURF-interface

---

## Checklist productiedeployment

- [ ] `CHAT_SECRET` ingesteld als omgevingsvariabele (niet in repo)
- [ ] `CHAT_USERS` ingesteld met sterke wachtwoorden
- [ ] API keys als secrets in het hostingplatform, niet in code
- [ ] `AVAILABLE_MODELS` ingesteld als de provider meerdere model-deployments heeft
- [ ] `app.db` staat in `.gitignore`
