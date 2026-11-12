"""Native publishing adapters for LinkedIn, X, Facebook and Instagram.

Credentials are read from environment variables only (see .env.example).
Nothing is sent unless the caller explicitly asks for a live publish.
"""

from .adapters import ADAPTERS, PublishError, get_adapter

__all__ = ["ADAPTERS", "PublishError", "get_adapter"]
