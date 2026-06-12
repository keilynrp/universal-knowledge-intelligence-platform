# US-078 - Deployment topology and data residency governance
## 1. User story
Como comprador institucional, quiero conocer donde fluye y reside mi informacion y como salgo.
## 2. Control outcome
`ER-DEP-001`, de `identified` a `auditable`, bajo `EPIC-018`.
## 3. Scope
Topologias, regiones, data flows, backups, subprocessors, telemetria y exit.
## 4. Acceptance criteria
- [ ] matriz y responsabilidades aprobadas
- [ ] cada clase de datos tiene ubicacion
- [ ] exit/export/delete ensayado
## 5. Failure and abuse cases
Replica fuera de region, backup omitido, PII en telemetria y claim imposible.
## 6. Operational acceptance
Validacion de topologia y customer-exit rehearsal.
## 7. Evidence
Diagramas, inventario, configuracion y resultado de salida.
## 8. Rollout and rollback
Publicar solo topologias verificadas.
## 9. Definition of Enterprise Done
- [ ] fronteras y salida auditables
