"""AI providers. Each returns raw model text; validation happens in drafting.py.

* WatsonxProvider — IBM watsonx.ai chat API with an IBM Granite model (needs an IBM Cloud
  API key and a watsonx project ID).
* OllamaProvider — IBM Granite running locally through Ollama (no cloud account needed).
* LocalTemplateProvider — no model at all; produces a deterministic narrative.
"""
from __future__ import annotations

import threading
import time

import httpx


class ProviderError(Exception):
    """The provider could not produce output (network, auth, timeout, bad response)."""


class BaseProvider:
    name = "base"
    model: str | None = None
    uses_ai = False

    def complete(self, system: str, user: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def status(self) -> dict:
        return {"provider": self.name, "model": self.model, "uses_ai": self.uses_ai, "configured": True}


class LocalTemplateProvider(BaseProvider):
    name = "local-template"
    uses_ai = False

    def complete(self, system: str, user: str) -> str:
        raise ProviderError("The local template provider does not call a model")


class WatsonxProvider(BaseProvider):
    """IBM watsonx.ai, chat endpoint: POST {url}/ml/v1/text/chat?version=...

    Auth: the IBM Cloud API key is exchanged for a short-lived IAM bearer token, which is
    cached until shortly before it expires. The API key never leaves the server."""

    name = "ibm-watsonx"
    uses_ai = True
    IAM_URL = "https://iam.cloud.ibm.com/identity/token"
    API_VERSION = "2024-05-01"

    def __init__(self, url: str, apikey: str, project_id: str, model_id: str, timeout: int, client: httpx.Client | None = None):
        if not apikey or not project_id:
            raise ValueError("WATSONX_APIKEY and WATSONX_PROJECT_ID are required for AI_PROVIDER=watsonx")
        self.url = url.rstrip("/")
        self._apikey = apikey
        self.project_id = project_id
        self.model = model_id
        self.timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)
        self._token: str | None = None
        self._token_expiry = 0.0
        self._lock = threading.Lock()

    def _iam_token(self) -> str:
        with self._lock:
            if self._token and time.time() < self._token_expiry - 60:
                return self._token
            try:
                r = self._client.post(
                    self.IAM_URL,
                    data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": self._apikey},
                    headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
                )
            except httpx.HTTPError as e:
                raise ProviderError(f"Could not reach IBM Cloud IAM ({type(e).__name__})")
            if r.status_code != 200:
                raise ProviderError(f"IBM Cloud IAM rejected the API key (HTTP {r.status_code})")
            body = r.json()
            self._token = body["access_token"]
            self._token_expiry = float(body.get("expiration", time.time() + 3000))
            return self._token

    def complete(self, system: str, user: str) -> str:
        token = self._iam_token()
        payload = {
            "model_id": self.model,
            "project_id": self.project_id,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": 900,
            "temperature": 0,
        }
        try:
            r = self._client.post(
                f"{self.url}/ml/v1/text/chat",
                params={"version": self.API_VERSION},
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
        except httpx.TimeoutException:
            raise ProviderError("watsonx.ai did not respond in time")
        except httpx.HTTPError as e:
            raise ProviderError(f"Could not reach watsonx.ai ({type(e).__name__})")
        if r.status_code != 200:
            raise ProviderError(f"watsonx.ai returned HTTP {r.status_code}")
        try:
            return r.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError):
            raise ProviderError("watsonx.ai returned an unexpected response shape")

    def status(self) -> dict:
        return {"provider": self.name, "model": self.model, "uses_ai": True, "configured": True}


class OllamaProvider(BaseProvider):
    """IBM Granite served locally by Ollama: POST {url}/api/chat."""

    name = "ollama-granite"
    uses_ai = True

    def __init__(self, url: str, model: str, timeout: int, client: httpx.Client | None = None):
        self.url = url.rstrip("/")
        self.model = model
        self._client = client or httpx.Client(timeout=timeout)

    def complete(self, system: str, user: str) -> str:
        try:
            r = self._client.post(f"{self.url}/api/chat", json={
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
            })
        except httpx.TimeoutException:
            raise ProviderError("The local Granite model did not respond in time")
        except httpx.HTTPError as e:
            raise ProviderError(f"Could not reach Ollama at {self.url} ({type(e).__name__}). Is Ollama running?")
        if r.status_code == 404:
            raise ProviderError(f"Model '{self.model}' is not installed in Ollama. Run: ollama pull {self.model}")
        if r.status_code != 200:
            raise ProviderError(f"Ollama returned HTTP {r.status_code}")
        try:
            return r.json()["message"]["content"]
        except (KeyError, ValueError):
            raise ProviderError("Ollama returned an unexpected response shape")
