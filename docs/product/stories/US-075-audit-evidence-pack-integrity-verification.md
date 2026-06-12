# US-075 - Audit evidence pack and integrity verification
## 1. User story
Como auditor, quiero evidencia tenant-scoped verificable sin reconstruccion manual.
## 2. Control outcome
`ER-AUD-001`, de `identified` a `auditable`, bajo `EPIC-018`.
## 3. Scope
Manifest, export, redaccion, integridad, retencion, autorizacion y verificador.
## 4. Acceptance criteria
- [ ] export respeta tenant, ventana, release y control
- [ ] hashes detectan alteracion
- [ ] secretos y PII innecesaria se excluyen
## 5. Failure and abuse cases
Cross-tenant export, archivo removido, hash alterado y acceso no auditado.
## 6. Operational acceptance
Un tercero interno verifica el pack sin acceso a base de datos.
## 7. Evidence
Pack, resultado del verificador, audit log y politica.
## 8. Rollout and rollback
Iniciar read-only e invalidar packs ante cambios materiales.
## 9. Definition of Enterprise Done
- [ ] evidencia exportable, atribuible e integrity-verifiable
