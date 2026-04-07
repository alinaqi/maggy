# Task: Add API Key Authentication

Add API key authentication middleware to an existing FastAPI app:
- Keys stored in database with user association
- Rate limiting per key (100 req/min)
- Key rotation support (old key valid for 24h after rotation)
- Admin endpoint to create/revoke keys
