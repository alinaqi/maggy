# Task: Build a URL Shortener Service

Create a Python URL shortener with these endpoints:
- POST /shorten — accepts a URL, returns a short code
- GET /{code} — redirects to the original URL
- GET /stats/{code} — returns click count

Use FastAPI. Store data in-memory (dict). Include input validation.
