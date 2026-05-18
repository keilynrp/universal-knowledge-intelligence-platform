## Why

SSO currently exists as a hard-coded login option backed by environment variables. Production operators need to control whether SSO is visible and usable without redeploying UI code, and administrators need a low-code Settings area that makes the current SSO readiness state understandable.

## What Changes

- Add an admin Settings tab for Authentication / SSO.
- Add persisted platform auth settings for SSO enablement, login-button visibility, provider label, auto-provisioning, default role, and allowed email domains.
- Add a public SSO status endpoint consumed by the login page.
- Gate `/sso/login` and `/sso/callback` by persisted settings and provider configuration.
- Keep OIDC secrets in environment variables for this slice; Settings may show readiness but SHALL NOT store client secrets yet.

## Capabilities

### New Capabilities
- `configurable-sso-settings`: Admin-controlled SSO visibility and behavior with public login-page status.

## Impact

- Backend: new singleton auth settings model, schemas, router, Alembic migration, SSO flow guards.
- Frontend: Settings tab for SSO controls, login page hides/shows SSO based on public status.
- Deployment: production still requires `SSO_CLIENT_ID`, `SSO_CLIENT_SECRET`, `SSO_METADATA_URL`, and `FRONTEND_URL`.

## Non-goals

- Storing OAuth client secrets in the database.
- Supporting SAML or SCIM.
- Full provider-specific setup wizard.
