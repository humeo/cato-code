# /setup

Validate the local CatoCode SaaS deployment and print the canonical onboarding flow.

## What it does

1. Verifies the required environment is present:
   - `ANTHROPIC_API_KEY`
   - `GITHUB_APP_ID`
   - `GITHUB_APP_PRIVATE_KEY`
   - `GITHUB_APP_CLIENT_ID`
   - `GITHUB_APP_CLIENT_SECRET`
   - `SESSION_SECRET_KEY`
2. Runs:

```bash
uv run catocode setup --probe
```

3. Reports the next user-facing steps:
   - open the frontend
   - `Connect GitHub`
   - `Install App`
   - click `Watch` on the repositories to onboard

## Notes

- `setup` validates the SaaS control plane; it does not auto-watch repositories.
- In local development, prefer `uv` for Python commands and `bun` for frontend commands.
