# US-073 - Backup, restore, RTO/RPO, and disaster recovery
## 1. User story
Como responsable de operaciones, quiero restaurar UKIP dentro de objetivos aprobados para limitar perdida e interrupcion.
## 2. Control outcome
`ER-BCP-001`, de `identified` a `auditable`, bajo `EPIC-018`.
## 3. Scope
PostgreSQL, estado persistente, backups cifrados off-host y dependencias de recuperacion.
## 4. Acceptance criteria
- [ ] RTO/RPO aprobados; backups automaticos y alertables
- [ ] restore limpio y point-in-time ensayados
- [ ] estado restaurable y reconstruible inventariado
## 5. Failure and abuse cases
Backup corrupto, destino inaccesible, restauracion parcial y operador no autorizado.
## 6. Operational acceptance
Dos ciclos exitosos y un restore drill medido.
## 7. Evidence
Configuracion, logs, checksums, tiempos y attestation; retencion 12 meses.
## 8. Rollout and rollback
Activar por ambiente y conservar el mecanismo anterior hasta validar restore.
## 9. Definition of Enterprise Done
- [ ] recovery probado, observado y exportable
