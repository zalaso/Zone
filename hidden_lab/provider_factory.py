"""Selezione esplicita dei client reali; nessun fallback di provider o billing."""

from .provider_base import validate_remote_settings


def create_real_client(provider, settings, *, gemini_output_mode="schema", chatgpt_store=None, api_key=None):
    if api_key is not None and provider not in ('openai', 'anthropic', 'gemini'):
        raise ValueError('Chiave API ammessa solo per provider API.')
    if chatgpt_store is not None and provider != "chatgpt":
        raise ValueError("Archivio ChatGPT ammesso solo per il provider chatgpt.")
    if provider != "gemini" and gemini_output_mode != "schema":
        from .protocol import ValidationError
        raise ValidationError("La modalità JSON alternativa è disponibile solo con Gemini.")
    if provider in ("openai", "anthropic", "gemini", "chatgpt") and settings.timeout > 120:
        validate_remote_settings(settings)
    if provider == "openai":
        from .llm import OpenAIClient
        return OpenAIClient(settings, **({'api_key': api_key} if api_key is not None else {}))
    if provider == "chatgpt":
        from .chatgpt_client import ChatGPTClient
        return ChatGPTClient(settings, store=chatgpt_store)
    if provider == "anthropic":
        from .anthropic_client import AnthropicClient
        return AnthropicClient(settings, **({'api_key': api_key} if api_key is not None else {}))
    if provider == "gemini":
        from .gemini_client import GeminiClient
        return GeminiClient(settings, output_mode=gemini_output_mode, **({'api_key': api_key} if api_key is not None else {}))
    if provider == "ollama":
        from .ollama_client import OllamaClient
        return OllamaClient(settings)
    raise ValueError("Provider reale non supportato.")
