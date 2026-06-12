# US-080 - Capacity, load, and degradation envelope
## 1. User story
Como operador, quiero conocer limites y degradacion para comprometer workloads soportables.
## 2. Control outcome
`ER-PERF-001`, de `identified` a `operated`, bajo `EPIC-018`.
## 3. Scope
Perfiles, p95/p99, imports, analytics, jobs, almacenamiento y saturacion.
## 4. Acceptance criteria
- [ ] workloads representativos versionados
- [ ] limites medidos por topologia
- [ ] backpressure y alertas verificados
## 5. Failure and abuse cases
Queue growth, pool exhaustion, OOM, throttling y noisy neighbor.
## 6. Operational acceptance
Prueba repetible y ventana piloto sin saturacion inexplicada.
## 7. Evidence
Scripts, dataset, reporte, alertas y decision.
## 8. Rollout and rollback
Limites conservadores; rollback reduce concurrency.
## 9. Definition of Enterprise Done
- [ ] envelope publicado y observado
