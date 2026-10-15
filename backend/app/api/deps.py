"""FastAPI dependencies for injecting repository and LLM clients.

Configured to support straightforward overriding in unit and integration tests
via `app.dependency_overrides`.
"""

from app.db.repository import ProjectRepository
from app.db.supabase_client import get_supabase_client
from app.llm.gemini_client import GeminiClient


def get_repository() -> ProjectRepository:
    """Dependency providing a connected ProjectRepository instance."""
    client = get_supabase_client()
    return ProjectRepository(client)


def get_gemini_client() -> GeminiClient:
    """Dependency providing a configured GeminiClient instance."""
    return GeminiClient()
