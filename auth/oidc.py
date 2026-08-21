"""
OIDC/SURFconext authentication support (placeholder for future implementation).

This module provides the foundation for integrating SURFconext OIDC authentication.
Currently, the application uses simple username/password auth via CHAT_USERS.

For SDP deployment, we'll integrate:
1. SURFconext OIDC client via oauth2-proxy sidecar OR
2. Direct FastAPI OIDC integration via authlib

Configuration examples:
- oauth2-proxy sidecar: handled at Kubernetes level
- Direct OIDC: configure via OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_ISSUER_URL
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def is_oidc_configured() -> bool:
    """Check if OIDC is configured."""
    from config import Config
    return bool(Config.OIDC_CLIENT_ID and Config.OIDC_CLIENT_SECRET and Config.OIDC_ISSUER_URL)


def get_oidc_config() -> Optional[dict]:
    """
    Get OIDC configuration if available.

    Returns:
        Dict with OIDC settings or None if not configured.
    """
    from config import Config

    if not is_oidc_configured():
        return None

    return {
        "client_id": Config.OIDC_CLIENT_ID,
        "client_secret": Config.OIDC_CLIENT_SECRET,
        "issuer_url": Config.OIDC_ISSUER_URL,
        "provider": "surfconext",  # hardcoded for now
    }


# TODO: Implement SURFconext OIDC integration
# Options:
# 1. oauth2-proxy sidecar in Helm deployment (Kubernetes-level auth)
# 2. Authlib-based OIDC in FastAPI (app-level auth)
#
# Recommended for SDP: option 1 (sidecar) for better separation of concerns
# The sidecar handles authentication, app handles authorization/sessions
#
# Implementation checklist:
# - [ ] User context extraction from request headers (X-Remote-User, etc.)
# - [ ] Session management per authenticated user
# - [ ] Conversation filtering by user
# - [ ] Workbook filtering by user
# - [ ] User profile storage (optional)
# - [ ] Rate limiting per user
# - [ ] Audit logging of user actions
