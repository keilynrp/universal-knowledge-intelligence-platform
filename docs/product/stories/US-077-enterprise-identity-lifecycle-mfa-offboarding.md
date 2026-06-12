# US-077 - Enterprise identity lifecycle, MFA, and offboarding
## 1. User story
Como administrador enterprise, quiero provisionar, cambiar y revocar acceso de forma gobernada.
## 2. Control outcome
`ER-IAM-001`, de `identified` a `operated`, bajo `EPIC-018`.
## 3. Scope
MFA, joiner/mover/leaver, SCIM o alternativa, sesiones, API keys y break-glass.
## 4. Acceptance criteria
- [ ] MFA gobernable por tenant y rol
- [ ] baja revoca sesiones y keys dentro del SLA
- [ ] break-glass limitado, alertado y auditado
## 5. Failure and abuse cases
Cuenta huerfana, token activo, SCIM replay y abuso de emergencia.
## 6. Operational acceptance
Drills de alta, cambio, baja y break-glass.
## 7. Evidence
Eventos IAM, drills, IdP y excepciones.
## 8. Rollout and rollback
Flags por tenant; rollback preserva revocaciones.
## 9. Definition of Enterprise Done
- [ ] lifecycle y revocacion operados
