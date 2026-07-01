# Professioneel hosten

Deze pagina beschrijft hoe je `onderwijsdata-chat` productierijp maakt. De lokale standaardinstelling (SQLite, wachtwoordlogin) is bedoeld voor ontwikkeling en demo's. Voor een gedeelde, institutionele omgeving zijn er drie componenten om te vervangen.

---

## Overzicht

| Component | Lokaal (standaard) | Productie |
|-----------|-------------------|-----------|
| Database | SQLite (`chat_history.db`) | PostgreSQL (beheerde cloud-service) |
| Authenticatie | Gebruikersnaam/wachtwoord in `.env` | OAuth via Azure AD / SURFconext |

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

```dotenv
DATABASE_URL=postgresql+asyncpg://gebruiker:wachtwoord@host:5432/onderwijschat
```

De app maakt de tabellen automatisch aan bij de eerste start. Geen handmatige migratie nodig.

!!! warning "Nooit `chat_history.db` committen"
    Het SQLite-bestand staat in `.gitignore`. Houd dat zo — databasebestanden horen niet in de repo.

---

## 2. Authenticatie — OAuth

Voor institutionele omgevingen is OAuth de aangewezen methode. Gebruikers loggen in met hun bestaande account (Microsoft, SURFconext).

### Azure Active Directory

Registreer een app in de [Azure Portal](https://portal.azure.com):

1. **Azure Portal** → Azure Active Directory → App-registraties → Nieuwe registratie
2. Redirect URI: `https://jouwdomein.nl/auth/oauth/azure-ad/callback`
3. Maak een client secret aan onder "Certificaten en geheimen"

Voeg toe aan `.env` (of omgevingsvariabelen van het hostingplatform):

```dotenv
CHAT_SECRET=<willekeurige lange string>

OAUTH_AZURE_AD_CLIENT_ID=<application-id>
OAUTH_AZURE_AD_CLIENT_SECRET=<client-secret>
OAUTH_AZURE_AD_TENANT_ID=<tenant-id>
```

OAuth-integratie vereist aanpassingen in `auth.py` — de huidige implementatie ondersteunt alleen gebruikersnaam/wachtwoord-authenticatie.

### SURFconext

SURFconext werkt via SAML/OIDC. Raadpleeg de [SURFconext documentatie](https://www.surf.nl/surfconext) voor het aanvragen van een koppeling. In de praktijk loopt dit via het SURF-instellingsloket.

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
  -e DATABASE_URL="postgresql+asyncpg://..." \
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
      DATABASE_URL=secretref:db-url \
      AZURE_AI_API_KEY=secretref:api-key \
  --ingress external --target-port 8000
```

### SURF Research Cloud

1. Maak een component aan met het Docker-image
2. Koppel een managed PostgreSQL-instantie
3. Stel omgevingsvariabelen in via de SURF-interface
4. Gebruik SURFconext voor authenticatie (zie sectie 2)

---

## Checklist productiedeployment

- [ ] `CHAT_SECRET` ingesteld als omgevingsvariabele (niet in repo)
- [ ] `DATABASE_URL` wijst naar PostgreSQL (niet SQLite)
- [ ] OAuth geconfigureerd (Azure AD of SURFconext)
- [ ] `chat_history.db` staat in `.gitignore`
- [ ] API keys als secrets in het hostingplatform, niet in code
- [ ] `AVAILABLE_MODELS` ingesteld als de provider meerdere model-deployments heeft
