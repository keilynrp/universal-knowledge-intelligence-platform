## 1. Spec

- [x] 1.1 Define requirements for public SSO visibility and admin configuration.
- [x] 1.2 Define requirements for production-safe secret handling.

## 2. Backend

- [x] 2.1 Add singleton `PlatformAuthSettings` model and migration.
- [x] 2.2 Add response/update schemas.
- [x] 2.3 Add public and admin auth settings endpoints.
- [x] 2.4 Gate SSO login/callback with settings and provider readiness.

## 3. Frontend

- [x] 3.1 Add Settings tab for Authentication / SSO.
- [x] 3.2 Make login SSO button use public settings instead of always rendering.
- [x] 3.3 Add translations for new Settings and login status text.

## 4. Verification

- [ ] 4.1 Run backend tests for SSO settings.
- [x] 4.2 Run frontend build.
- [x] 4.3 Rebuild/restart frontend/backend containers.
