"""Supabase Client Factory for BRD Agent backend.

This is the only place in the codebase that initializes the raw Supabase client.
Caches the client instance as a singleton.
"""

from typing import Optional
from supabase import Client, create_client

from app.config import validate_supabase_config

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """Return the cached Supabase client singleton, creating it if necessary.

    Returns:
        Client: Authenticated Supabase client instance using service_role key.

    Raises:
        ValueError: If SUPABASE_URL or SUPABASE_SERVICE_KEY is missing from environment.
    """
    global _supabase_client
    if _supabase_client is None:
        url, service_key = validate_supabase_config()
        _supabase_client = create_client(url, service_key)
    return _supabase_client


def reset_supabase_client() -> None:
    """Reset the cached client singleton (useful for testing or reconfiguring)."""
    global _supabase_client
    _supabase_client = None
