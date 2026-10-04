"""Selezione esplicita dei soli quattro client reali supportati."""


def create_real_client(provider, settings):
    if provider == "openai":
        from .llm import OpenAIClient
        return OpenAIClient(settings)
    if provider == "anthropic":
        from .anthropic_client import AnthropicClient
        return AnthropicClient(settings)
    if provider == "gemini":
        from .gemini_client import GeminiClient
        return GeminiClient(settings)
    if provider == "ollama":
        from .ollama_client import OllamaClient
        return OllamaClient(settings)
    raise ValueError("Provider reale non supportato.")
