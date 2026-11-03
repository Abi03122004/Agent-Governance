"""Upstream LLM Provider Adapters with SSRF Protection and Response Normalization."""

import json
import time
import uuid
from typing import Any, Dict, List, Optional
import httpx

from agent_security.connectors.http_connector import validate_url, SSRFSecurityError
from agent_security.core.redaction import redact_string


class ProviderExecutionError(Exception):
    """Raised when upstream LLM execution fails."""
    def __init__(self, message: str, status_code: int = 502, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


class BaseProviderAdapter:
    async def execute(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        provider_api_key: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class OpenAIProviderAdapter(BaseProviderAdapter):
    """Adapter for OpenAI and OpenAI-compatible API endpoints."""
    UPSTREAM_URL = "https://api.openai.com/v1/chat/completions"

    async def execute(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        provider_api_key: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        validate_url(self.UPSTREAM_URL)
        payload = {
            "model": model,
            "messages": messages,
            **(parameters or {}),
        }
        headers = {
            "Authorization": f"Bearer {provider_api_key}",
            "Content-Type": "application/json",
            "User-Agent": "AgentGovernance-LLMProxy/1.0",
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(self.UPSTREAM_URL, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                raise ProviderExecutionError("Upstream provider timed out", status_code=504) from exc
            except httpx.RequestError as exc:
                raise ProviderExecutionError(f"Network error contacting provider: {str(exc)}", status_code=502) from exc

        if response.status_code >= 400:
            err_msg = "Upstream provider returned an error"
            try:
                err_json = response.json()
                if "error" in err_json and "message" in err_json["error"]:
                    err_msg = err_json["error"]["message"]
            except Exception:
                err_msg = response.text[:200]
            raise ProviderExecutionError(redact_string(err_msg), status_code=response.status_code)

        return response.json()


class GeminiProviderAdapter(BaseProviderAdapter):
    """Adapter for Google Gemini REST API (mapping to OpenAI-compatible format)."""

    async def execute(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        provider_api_key: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Normalize model name for Google API
        clean_model = model.replace("gemini/", "").replace("google/", "")
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={provider_api_key}"
        validate_url(f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent")

        # Map OpenAI messages to Gemini contents
        contents = []
        system_instruction = None
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": str(content)}]}
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": str(content)}]})
            else:
                contents.append({"role": "user", "parts": [{"text": str(content)}]})

        gemini_payload: Dict[str, Any] = {"contents": contents}
        if system_instruction:
            gemini_payload["systemInstruction"] = system_instruction
        
        gen_config = {}
        if parameters:
            if "temperature" in parameters:
                gen_config["temperature"] = parameters["temperature"]
            if "max_tokens" in parameters:
                gen_config["maxOutputTokens"] = parameters["max_tokens"]
        if gen_config:
            gemini_payload["generationConfig"] = gen_config

        headers = {"Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(endpoint, json=gemini_payload, headers=headers)
            except httpx.TimeoutException as exc:
                raise ProviderExecutionError("Upstream provider timed out", status_code=504) from exc
            except httpx.RequestError as exc:
                raise ProviderExecutionError(f"Network error contacting provider: {str(exc)}", status_code=502) from exc

        if response.status_code >= 400:
            err_msg = "Upstream provider returned an error"
            try:
                err_json = response.json()
                if "error" in err_json and "message" in err_json["error"]:
                    err_msg = err_json["error"]["message"]
            except Exception:
                err_msg = response.text[:200]
            raise ProviderExecutionError(redact_string(err_msg), status_code=response.status_code)

        data = response.json()
        generated_text = ""
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                generated_text = parts[0].get("text", "")

        # Format as standard OpenAI chat completion JSON
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": generated_text,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": data.get("usageMetadata", {}).get("promptTokenCount", 0),
                "completion_tokens": data.get("usageMetadata", {}).get("candidatesTokenCount", 0),
                "total_tokens": data.get("usageMetadata", {}).get("totalTokenCount", 0),
            },
        }


class AnthropicProviderAdapter(BaseProviderAdapter):
    """Adapter for Anthropic Messages API (mapping to OpenAI-compatible format)."""
    UPSTREAM_URL = "https://api.anthropic.com/v1/messages"

    async def execute(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        provider_api_key: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        validate_url(self.UPSTREAM_URL)
        clean_model = model.replace("anthropic/", "")
        
        system_content = None
        anthropic_messages = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_content = str(content)
            elif role == "assistant":
                anthropic_messages.append({"role": "assistant", "content": str(content)})
            else:
                anthropic_messages.append({"role": "user", "content": str(content)})

        payload: Dict[str, Any] = {
            "model": clean_model,
            "messages": anthropic_messages,
            "max_tokens": (parameters or {}).get("max_tokens", 1024),
        }
        if system_content:
            payload["system"] = system_content
        if parameters and "temperature" in parameters:
            payload["temperature"] = parameters["temperature"]

        headers = {
            "x-api-key": provider_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(self.UPSTREAM_URL, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                raise ProviderExecutionError("Upstream provider timed out", status_code=504) from exc
            except httpx.RequestError as exc:
                raise ProviderExecutionError(f"Network error contacting provider: {str(exc)}", status_code=502) from exc

        if response.status_code >= 400:
            err_msg = "Upstream provider returned an error"
            try:
                err_json = response.json()
                if "error" in err_json and "message" in err_json["error"]:
                    err_msg = err_json["error"]["message"]
            except Exception:
                err_msg = response.text[:200]
            raise ProviderExecutionError(redact_string(err_msg), status_code=response.status_code)

        data = response.json()
        generated_text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                generated_text += block.get("text", "")

        return {
            "id": data.get("id", f"chatcmpl-{uuid.uuid4().hex[:12]}"),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": generated_text,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
                "total_tokens": (data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0)),
            },
        }


def get_provider_adapter(provider: str) -> BaseProviderAdapter:
    """Resolve provider adapter by name."""
    p = provider.lower().strip()
    if p in {"openai", "azure_openai", "vllm", "groq", "together"}:
        return OpenAIProviderAdapter()
    if p in {"gemini", "google"}:
        return GeminiProviderAdapter()
    if p in {"anthropic", "claude"}:
        return AnthropicProviderAdapter()
    # Default to OpenAI compatible format
    return OpenAIProviderAdapter()

