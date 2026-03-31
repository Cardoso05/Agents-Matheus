"""Busca web — abstração para pesquisa na internet."""

import json
import logging
import os
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)


def buscar_web(query: str, num_results: int = 5) -> str:
    """
    Busca na web e retorna resultados formatados.

    Tenta usar a API do Brave Search (BRAVE_API_KEY no env).
    Fallback: retorna mensagem indicando que busca web não está configurada.
    """
    brave_key = os.getenv("BRAVE_API_KEY")
    if brave_key:
        return _brave_search(query, num_results, brave_key)

    return (
        f"⚠️ Busca web não configurada. Configure BRAVE_API_KEY no .env.\n"
        f"Query que seria buscada: '{query}'"
    )


def _brave_search(query: str, num_results: int, api_key: str) -> str:
    """Busca usando Brave Search API."""
    try:
        params = urllib.parse.urlencode({
            "q": query,
            "count": num_results,
            "text_decorations": "false",
            "search_lang": "pt-br",
        })
        url = f"https://api.search.brave.com/res/v1/web/search?{params}"

        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key,
        })

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        results = data.get("web", {}).get("results", [])
        if not results:
            return f"Nenhum resultado encontrado para: '{query}'"

        lines = [f"🔍 **Resultados para:** '{query}'\n"]
        for i, r in enumerate(results[:num_results], 1):
            title = r.get("title", "Sem título")
            desc = r.get("description", "")
            url = r.get("url", "")
            lines.append(f"{i}. **{title}**")
            if desc:
                lines.append(f"   {desc}")
            if url:
                lines.append(f"   🔗 {url}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Erro na busca Brave: {e}")
        return f"❌ Erro na busca web: {e}"
