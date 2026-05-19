Manually create or update an iCPG intent (ReasonNode) for a file before implementing.

Usage:
```
/icpg-intent "Add OAuth2 PKCE flow" --file src/auth.py
/icpg-intent "Refactor to extract middleware" --invariants "All routes must pass through auth"
```

This records a ReasonNode before you start coding. The Stop hook then links symbols to this intent. Subsequent edits show this intent as a guardrail.

To see existing intents:
```
/icpg-why src/auth.py
```
