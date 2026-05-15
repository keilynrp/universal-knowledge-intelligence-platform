## ADDED Requirements

### Requirement: Public SSO login status
The platform SHALL expose a public, unauthenticated endpoint that tells the login page whether SSO should be offered.

#### Scenario: SSO is disabled
- **WHEN** persisted SSO settings have `sso_enabled=false`
- **THEN** the public status SHALL report SSO as disabled
- **THEN** the login page SHALL NOT render the SSO button

#### Scenario: SSO is hidden but configured
- **WHEN** `sso_enabled=true` and `sso_login_button_visible=false`
- **THEN** `/sso/login` MAY remain available
- **THEN** the login page SHALL NOT render the SSO button

#### Scenario: Provider is not configured
- **WHEN** required OIDC environment variables are missing
- **THEN** the public status SHALL report provider readiness as false
- **THEN** the login page SHALL NOT render the SSO button

### Requirement: Admin SSO settings
Administrators SHALL be able to update non-secret SSO behavior from Settings.

#### Scenario: Admin updates login visibility
- **WHEN** an admin updates `sso_login_button_visible`
- **THEN** the setting SHALL be persisted
- **THEN** subsequent login page loads SHALL reflect the new visibility

#### Scenario: Admin updates auto-provisioning policy
- **WHEN** an admin updates `sso_auto_provision`, `sso_default_role`, or `sso_allowed_domains`
- **THEN** the callback SHALL enforce those settings for new SSO users

### Requirement: Production-safe secret handling
The Settings UI SHALL NOT store OIDC client secrets in this slice.

#### Scenario: Admin views provider readiness
- **WHEN** `SSO_CLIENT_ID`, `SSO_CLIENT_SECRET`, and `SSO_METADATA_URL` are set
- **THEN** Settings SHALL show provider configuration as ready
- **THEN** secret values SHALL NOT be returned by the API
