"""SRAM-login met PKCE (S256), nonce en een gecontroleerd id_token (#1024, audit F-05; SECURITY.md S28).

De provider is nagebootst: discovery en JWKS via `_fetch_json`, token- en userinfo-eindpunt via een
`httpx2.MockTransport` onder de echte authlib-client (authlib 1.9 bouwt op httpx2, niet op httpx). Het id_token
is ondertekend met een RSA-sleutel uit de test.
"""

import base64
import functools
import hashlib
import json
import logging
import time
import urllib.parse
from collections import OrderedDict

import httpx2
import pytest
from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import FastAPI
from fastapi.testclient import TestClient
from joserfc import jwt
from joserfc.jwk import OctKey, RSAKey

import routes.auth
from auth import oidc
from config import Config
from core import foutmeldingen

ISSUER = "https://proxy.sram.test"
CLIENT_ID = "edudata-test"
CLIENT_SECRET = "client-geheim"
STATE, NONCE, VERIFIER = "staat-1", "nonce-1", "v" * 50
COOKIES = f"oidc_state={STATE}; oidc_nonce={NONCE}; oidc_verifier={VERIFIER}"
CALLBACK = f"/api/auth/oidc/callback?code=code-1&state={STATE}"
COOKIE_NAMEN = ("oidc_state", "oidc_nonce", "oidc_verifier")

SLEUTEL = RSAKey.generate_key(2048, parameters={"kid": "sleutel-1"})
VREEMDE_SLEUTEL = RSAKey.generate_key(2048, parameters={"kid": "sleutel-1"})
NIEUWE_SLEUTEL = RSAKey.generate_key(2048, parameters={"kid": "sleutel-2"})


def _discovery(**weg_of_anders) -> dict:
    config = {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "userinfo_endpoint": f"{ISSUER}/userinfo",
        "jwks_uri": f"{ISSUER}/jwks",
        "id_token_signing_alg_values_supported": ["RS256"],
        "code_challenge_methods_supported": ["S256"],
    }
    config.update(weg_of_anders)
    return {k: v for k, v in config.items() if v is not None}


def _id_token(sleutel=SLEUTEL, alg="RS256", **claims) -> str:
    nu = int(time.time())
    inhoud = {"iss": ISSUER, "aud": CLIENT_ID, "sub": "sub-123", "exp": nu + 300, "iat": nu, "nonce": NONCE}
    inhoud.update(claims)
    inhoud = {k: v for k, v in inhoud.items() if v is not None}
    return jwt.encode({"alg": alg, "kid": sleutel.kid}, inhoud, sleutel, algorithms=[alg])


class Provider:
    """De nagebootste SRAM-proxy: wat hij teruggeeft en wat hij binnenkreeg."""

    def __init__(self):
        self.discovery = _discovery()
        self.sleutels = [SLEUTEL]
        self.id_token: str | None = _id_token()
        self.userinfo = {"sub": "sub-123", "email": "anna@hu.nl", "name": "Anna de Vries"}
        self.token_status = 200
        self.token_verzoeken: list[dict] = []
        self.opgehaald: list[str] = []

    async def fetch_json(self, url: str):
        self.opgehaald.append(url)
        if url == Config.OIDC_DISCOVERY_URL:
            return self.discovery
        if url == self.discovery.get("jwks_uri"):
            return {"keys": [k.as_dict(private=False) for k in self.sleutels]}
        raise AssertionError(f"onverwachte url {url}")

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/token":
            self.token_verzoeken.append(dict(urllib.parse.parse_qsl(request.content.decode())))
            if self.token_status != 200:
                return httpx2.Response(self.token_status, json={"error": "invalid_grant"})
            antwoord = {"access_token": "toegang-1", "token_type": "Bearer", "expires_in": 300}
            if self.id_token is not None:
                antwoord["id_token"] = self.id_token
            return httpx2.Response(200, json=antwoord)
        if request.url.path == "/userinfo":
            return httpx2.Response(200, json=self.userinfo)
        return httpx2.Response(404)


@pytest.fixture
def provider(monkeypatch):
    for naam, waarde in {
        "OIDC_PROVIDER": "sram",
        "OIDC_DISCOVERY_URL": f"{ISSUER}/.well-known/openid-configuration",
        "OIDC_CLIENT_ID": CLIENT_ID,
        "OIDC_CLIENT_SECRET": CLIENT_SECRET,
        "SERVER_URL": "https://edudata.test",
    }.items():
        monkeypatch.setattr(Config, naam, waarde)
    for naam, waarde in {"_discovery_cache": None, "_jwks_cache": None, "_pkce_warned": False}.items():
        monkeypatch.setattr(oidc, naam, waarde)
    nep = Provider()
    monkeypatch.setattr(oidc, "_fetch_json", nep.fetch_json)
    transport = httpx2.MockTransport(nep.handler)
    monkeypatch.setattr(oidc, "AsyncOAuth2Client", functools.partial(AsyncOAuth2Client, transport=transport))
    monkeypatch.setattr(routes.auth, "_oidc_user_cache", OrderedDict())
    return nep


@pytest.fixture
def client(provider):
    app = FastAPI()
    foutmeldingen.registreer(app)
    app.include_router(routes.auth.router)
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


@pytest.fixture
def tokens(monkeypatch):
    """Elk sessietoken dat de callback zou maken."""
    gemaakt: list[str] = []
    echt = routes.auth.make_token

    def maak(username, *args):
        gemaakt.append(username)
        return echt(username, *args)

    monkeypatch.setattr(routes.auth, "make_token", maak)
    return gemaakt


def _set_cookies(response) -> dict[str, str]:
    return {regel.split("=", 1)[0]: regel for regel in response.headers.get_list("set-cookie")}


def _cookiewaarde(regel: str) -> str:
    return regel.split(";", 1)[0].split("=", 1)[1]


def _alle_cookies_gewist(response) -> bool:
    gezet = _set_cookies(response)
    return all(naam in gezet and "Max-Age=0" in gezet[naam] for naam in COOKIE_NAMEN)


# ── Criterium 1 en 2: de login stuurt challenge en nonce, en bewaart ze in cookies ─────────────


def test_nieuwe_login_geheimen_zijn_drie_verschillende_willekeurige_waarden():
    eerste, tweede = oidc.nieuwe_login_geheimen(), oidc.nieuwe_login_geheimen()
    assert len(set(eerste)) == 3
    assert eerste != tweede
    assert 43 <= len(eerste.code_verifier) <= 128


def test_de_login_url_bevat_s256_challenge_nonce_en_state(client):
    response = client.get("/api/auth/oidc/login")
    assert response.status_code == 307
    url = urllib.parse.urlsplit(response.headers["location"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{ISSUER}/authorize"
    params = dict(urllib.parse.parse_qsl(url.query))
    cookies = {naam: _cookiewaarde(regel) for naam, regel in _set_cookies(response).items()}

    assert params["code_challenge_method"] == "S256"
    assert params["state"] == cookies["oidc_state"]
    assert params["nonce"] == cookies["oidc_nonce"]
    verifier = cookies["oidc_verifier"]
    assert 43 <= len(verifier) <= 128
    verwacht = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert params["code_challenge"] == verwacht
    assert verifier not in response.headers["location"]
    assert len({cookies["oidc_state"], cookies["oidc_nonce"], verifier}) == 3


def test_de_login_zet_drie_korte_strikte_cookies(client):
    gezet = _set_cookies(client.get("/api/auth/oidc/login"))
    assert set(gezet) == set(COOKIE_NAMEN)
    for regel in gezet.values():
        kenmerken = {deel.strip().lower() for deel in regel.split(";")[1:]}
        assert {"httponly", "secure", "samesite=lax", "max-age=600"} <= kenmerken


# ── Criterium 3 en 5: verifier naar de provider; een geldig id_token geeft dezelfde login als eerder ─


def test_een_geldige_login_geeft_token_en_gebruikersdata(client, provider, tokens):
    response = client.get(CALLBACK, headers={"Cookie": COOKIES})

    assert response.status_code == 302
    assert provider.token_verzoeken[0]["code_verifier"] == VERIFIER
    assert provider.token_verzoeken[0]["code"] == "code-1"
    locatie = response.headers["location"]
    assert locatie.startswith("/#token=")
    user_data = json.loads(urllib.parse.unquote(locatie.split("&user_data=", 1)[1]))
    assert user_data["username"] == "anna@hu.nl"
    assert user_data["name"] == "Anna de Vries"
    assert user_data["email_domein"] == "hu.nl"
    assert tokens == ["anna@hu.nl"]
    assert routes.auth._get_oidc_user("anna@hu.nl") == user_data
    assert _alle_cookies_gewist(response)


def test_zonder_email_is_sub_de_gebruikersnaam(client, provider, tokens):
    provider.userinfo = {"sub": "sub-123", "name": "Anna"}
    response = client.get(CALLBACK, headers={"Cookie": COOKIES})
    assert response.headers["location"].startswith("/#token=")
    assert tokens == ["sub-123"]


def test_een_aud_lijst_met_de_client_id_telt(client, provider, tokens):
    provider.id_token = _id_token(aud=["andere-dienst", CLIENT_ID], azp=CLIENT_ID)
    response = client.get(CALLBACK, headers={"Cookie": COOKIES})
    assert response.headers["location"].startswith("/#token=")


# ── Criterium 4: elke afwijking geeft 400, zonder sessie ────────────────────────────────────────


def _geen_sessie(response, tokens) -> None:
    assert response.status_code == 400
    assert "location" not in response.headers
    assert "#token=" not in response.text
    assert tokens == []
    assert not routes.auth._oidc_user_cache
    assert _alle_cookies_gewist(response)


@pytest.mark.parametrize(
    "cookies",
    [
        f"oidc_state={STATE}; oidc_nonce={NONCE}",
        f"oidc_state={STATE}; oidc_verifier={VERIFIER}",
        f"oidc_nonce={NONCE}; oidc_verifier={VERIFIER}",
        f"oidc_state=andere-staat; oidc_nonce={NONCE}; oidc_verifier={VERIFIER}",
    ],
    ids=["zonder-verifier", "zonder-nonce", "zonder-state", "andere-state"],
)
def test_een_ontbrekende_cookie_geeft_400_zonder_de_provider_te_vragen(client, provider, tokens, cookies):
    response = client.get(CALLBACK, headers={"Cookie": cookies})
    _geen_sessie(response, tokens)
    assert provider.token_verzoeken == []


@pytest.mark.parametrize(
    "id_token",
    [
        pytest.param(lambda: None, id="geen-id_token"),
        pytest.param(lambda: _id_token(VREEMDE_SLEUTEL), id="andere-sleutel"),
        pytest.param(lambda: _id_token(iss="https://nep.test"), id="andere-iss"),
        pytest.param(lambda: _id_token(aud="andere-dienst"), id="andere-aud"),
        pytest.param(lambda: _id_token(aud=None), id="zonder-aud"),
        pytest.param(lambda: _id_token(exp=int(time.time()) - 3600), id="verlopen"),
        pytest.param(lambda: _id_token(exp=None), id="zonder-exp"),
        pytest.param(lambda: _id_token(nonce="andere-nonce"), id="andere-nonce"),
        pytest.param(lambda: _id_token(nonce=None), id="zonder-nonce"),
        pytest.param(lambda: _id_token(sub=None), id="zonder-sub"),
        pytest.param(lambda: _id_token(azp="andere-dienst"), id="andere-azp"),
        pytest.param(
            lambda: _id_token(OctKey.import_key(CLIENT_SECRET.encode() * 4, {"kid": "sleutel-1"}), alg="HS256"),
            id="hmac-met-clientgeheim",
        ),
        pytest.param(lambda: "geen.jwt.token", id="onleesbaar"),
    ],
)
def test_een_ongeldig_id_token_geeft_400_zonder_sessie(client, provider, tokens, caplog, id_token):
    provider.id_token = id_token()
    caplog.set_level(logging.DEBUG)
    response = client.get(CALLBACK, headers={"Cookie": COOKIES})
    _geen_sessie(response, tokens)
    # Criterium 6: geen token en geen sleutelmateriaal in het log.
    sleutel_n = SLEUTEL.as_dict(private=False)["n"]
    for record in caplog.records:
        tekst = record.getMessage()
        assert "toegang-1" not in tekst and sleutel_n not in tekst
        assert provider.id_token is None or provider.id_token not in tekst


def test_een_andere_sub_in_userinfo_geeft_400(client, provider, tokens):
    provider.userinfo = {"sub": "iemand-anders", "email": "anna@hu.nl"}
    _geen_sessie(client.get(CALLBACK, headers={"Cookie": COOKIES}), tokens)


def test_userinfo_zonder_sub_geeft_400(client, provider, tokens):
    provider.userinfo = {"email": "anna@hu.nl"}
    _geen_sessie(client.get(CALLBACK, headers={"Cookie": COOKIES}), tokens)


# ── Criterium 6: een fout van de provider houdt de redirect ─────────────────────────────────────


def test_een_providerfout_op_het_tokeneindpunt_stuurt_terug_met_oidc_error(client, provider, tokens, caplog):
    provider.token_status = 400
    caplog.set_level(logging.DEBUG)
    response = client.get(CALLBACK, headers={"Cookie": COOKIES})
    assert response.status_code == 302
    assert response.headers["location"] == "/?oidc_error=1"
    assert tokens == []
    assert _alle_cookies_gewist(response)
    assert any(r.getMessage().startswith("OIDC code exchange failed: ") for r in caplog.records)


def test_een_fout_van_de_provider_in_de_callback_wist_de_cookies(client, tokens):
    response = client.get("/api/auth/oidc/callback?error=access_denied", headers={"Cookie": COOKIES})
    assert response.headers["location"] == "/?oidc_error=1"
    assert tokens == []
    assert _alle_cookies_gewist(response)


# ── Criterium 7: discovery en JWKS ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("veld", ["jwks_uri", "issuer"])
def test_discovery_zonder_jwks_uri_of_issuer_geeft_geen_login(client, provider, tokens, veld):
    provider.discovery = _discovery(**{veld: None})
    login = client.get("/api/auth/oidc/login")
    assert login.status_code == 302
    assert login.headers["location"] == "/?oidc_error=1"
    assert not login.headers.get_list("set-cookie")

    _geen_sessie(client.get(CALLBACK, headers={"Cookie": COOKIES}), tokens)
    assert provider.token_verzoeken == []


def test_de_jwks_wordt_bewaard_zoals_de_discovery(client, provider):
    for _ in range(2):
        assert client.get(CALLBACK, headers={"Cookie": COOKIES}).headers["location"].startswith("/#token=")
    assert provider.opgehaald.count(provider.discovery["jwks_uri"]) == 1
    assert provider.opgehaald.count(Config.OIDC_DISCOVERY_URL) == 1


def test_een_onbekende_kid_haalt_de_jwks_een_keer_opnieuw(client, provider):
    assert client.get(CALLBACK, headers={"Cookie": COOKIES}).headers["location"].startswith("/#token=")
    provider.sleutels = [NIEUWE_SLEUTEL]  # sleutelrotatie bij de provider
    provider.id_token = _id_token(NIEUWE_SLEUTEL)
    assert client.get(CALLBACK, headers={"Cookie": COOKIES}).headers["location"].startswith("/#token=")
    assert provider.opgehaald.count(provider.discovery["jwks_uri"]) == 2


def test_een_kid_die_ook_na_opnieuw_ophalen_onbekend_is_geeft_400(client, provider, tokens):
    provider.id_token = _id_token(NIEUWE_SLEUTEL)
    _geen_sessie(client.get(CALLBACK, headers={"Cookie": COOKIES}), tokens)
    assert provider.opgehaald.count(provider.discovery["jwks_uri"]) == 2


def test_discovery_zonder_s256_waarschuwt_een_keer_en_stuurt_s256_toch(client, provider, monkeypatch, caplog):
    provider.discovery = _discovery(code_challenge_methods_supported=["plain"])
    caplog.set_level(logging.WARNING, logger="auth.oidc")
    for _ in range(2):
        monkeypatch.setattr(oidc, "_discovery_cache", None)
        response = client.get("/api/auth/oidc/login")
        assert "code_challenge_method=S256" in response.headers["location"]
    assert [r.getMessage() for r in caplog.records].count(
        "OIDC discovery noemt S256 niet in code_challenge_methods_supported"
    ) == 1
