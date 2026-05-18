# Professioneel hosten

Deze pagina beschrijft hoe je `onderwijsdata-chat` productierijp maakt. De lokale standaardinstelling (SQLite, wachtwoordlogin) is bedoeld voor ontwikkeling en demo's. Voor een gedeelde, institutionele omgeving zijn er drie componenten om te vervangen.

---

## Overzicht

| Component | Lokaal (standaard) | Productie |
|-----------|-------------------|-----------|
| Database | SQLite (`chat_history.db`) | PostgreSQL (beheerde cloud-service) |
| Authenticatie | Gebruikersnaam/wachtwoord in `.env` | OAuth via Azure AD / SURFconext |
| Bestandsopslag | Niet opgeslagen | Azure Blob Storage of AWS S3 |

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

Voeg toe aan `.env` (of omgevingsvariabelen van de hostingplatform):

```dotenv
CHAINLIT_AUTH_SECRET="<chainlit create-secret>"

OAUTH_AZURE_AD_CLIENT_ID=<application-id>
OAUTH_AZURE_AD_CLIENT_SECRET=<client-secret>
OAUTH_AZURE_AD_TENANT_ID=<tenant-id>

# Alleen medewerkers van jouw instelling toelaten:
OAUTH_AZURE_AD_ENABLE_SINGLE_TENANT=true

# Zorg dat de callback-URL klopt:
CHAINLIT_URL=https://jouwdomein.nl
```

Vervang vervolgens in `auth.py` de wachtwoord-callback door een OAuth-callback:

```python
@cl.oauth_callback
def oauth_callback(
    provider_id: str,
    token: str,
    raw_user_data: dict,
    default_user: cl.User,
) -> cl.User | None:
    # Sta alleen gebruikers van jouw tenant toe
    return default_user
```

### SURFconext

SURFconext werkt via SAML/OIDC. Raadpleeg de [SURFconext documentatie](https://www.surf.nl/surfconext) voor het aanvragen van een koppeling. In de praktijk loopt dit via het SURF-instellingsloket.

---

## 3. Bestandsopslag — grafieken

Plotly-grafieken worden standaard niet opgeslagen bij herstel van een gesprek. Koppel een blob-opslag om dit op te lossen.

### Azure Blob Storage

```bash
uv add azure-storage-file-datalake azure-identity aiohttp
```

In `data_layer.py`:

```python
from chainlit.data.storage_clients.azure import AzureStorageClient

storage_client = AzureStorageClient(
    account_url="https://<account>.dfs.core.windows.net",
    container="chainlit-elements",
)

@cl.data_layer
def get_data_layer_instance():
    url = build_conninfo(os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    return SQLAlchemyDataLayer(conninfo=url, storage_provider=storage_client)
```

### AWS S3

```bash
uv add boto3
```

```python
from chainlit.data.storage_clients.s3 import S3StorageClient

storage_client = S3StorageClient(bucket="chainlit-elements")
```

---

## 4. Deployment

### Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync --no-dev
EXPOSE 8000
CMD ["uv", "run", "chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000", "-h"]
```

Geef omgevingsvariabelen mee via Docker of je platform — nooit in de image zelf:

```bash
docker run -p 8000:8000 \
  -e CHAINLIT_AUTH_SECRET="..." \
  -e DATABASE_URL="postgresql+asyncpg://..." \
  -e AZURE_AI_API_KEY="..." \
  onderwijsdata-chat
```

### Azure Container Apps

```bash
az containerapp create \
  --name onderwijsdata-chat \
  --resource-group mijn-rg \
  --image ghcr.io/cedanl/onderwijsdata-chat:latest \
  --env-vars \
      CHAINLIT_AUTH_SECRET=secretref:chainlit-secret \
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

- [ ] `CHAINLIT_AUTH_SECRET` ingesteld als omgevingsvariabele (niet in repo)
- [ ] `DATABASE_URL` wijst naar PostgreSQL (niet SQLite)
- [ ] OAuth geconfigureerd (Azure AD of SURFconext)
- [ ] `CHAINLIT_URL` ingesteld op het publieke domein
- [ ] `chat_history.db` staat in `.gitignore`
- [ ] API keys als secrets in het hostingplatform, niet in code
- [ ] (Optioneel) blob-opslag gekoppeld voor grafiekpersistentie
