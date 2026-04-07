# Task: Add Pagination to an Existing API

You have a FastAPI endpoint that returns all items from a database. Refactor it to support cursor-based pagination with:
- `limit` parameter (default 20, max 100)
- `cursor` parameter (opaque string)
- Response includes `next_cursor` and `has_more`

Write the implementation and tests.
