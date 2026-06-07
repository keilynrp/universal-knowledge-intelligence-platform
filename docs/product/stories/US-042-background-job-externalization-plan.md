# US-042 - External background-job runtime

## 1. User story

Como operador de una instalacion enterprise, quiero que el trabajo programado y
de larga duracion sobreviva reinicios y escale de forma independiente del API,
para evitar perdida, duplicacion y ejecucion silenciosamente incompleta.

## 2. Context

- Epic de origen: `EPIC-011`
- Programa de cierre: `EPIC-018`
- Control: `ER-OPS-001`
- OpenSpec change: `external-background-job-runtime`
- Sprint objetivo: `SPRINT-TBD`

## 3. Acceptance criteria

- [ ] existe inventario de producers, schedulers, handlers y estados de job
- [ ] existe decision documentada sobre broker, worker y scheduler
- [ ] cada job tiene identidad durable, tenant scope e idempotency key
- [ ] retries usan backoff y limite; fallos terminales son inspeccionables
- [ ] un reinicio del API no detiene ni duplica jobs aceptados
- [ ] workers soportan graceful shutdown y recuperacion de leases
- [ ] existe cancelacion gobernada y replay auditado
- [ ] API, scheduler y workers escalan de forma independiente
- [ ] health, queue depth, age, failures y saturation generan telemetria
- [ ] migration y rollback desde ejecucion in-process fueron ensayados
- [ ] el control completa una ventana operativa de 14 dias

## 4. Functional notes

- cubre enrichment, scheduled imports y scheduled reports
- retention purge y otros jobs se incorporan solo despues del runtime base
- conserva las APIs actuales donde sea viable
- evita una migracion big-bang

## 5. Technical notes

- `backend/enrichment_worker.py`
- `backend/services/enrichment_scheduler.py`
- `backend/routers/scheduled_imports.py`
- `backend/routers/scheduled_reports.py`
- `backend/main.py`
- la seleccion de tecnologia debe decidirse por semantica de entrega,
  operabilidad, soporte PostgreSQL/Redis y costo de recuperacion; no por
  popularidad

## 6. Non-functional requirements

- entrega al menos una vez con handlers idempotentes
- no se promete exactly-once
- aislamiento tenant en enqueue, claim, execute, result y replay
- persistencia durable de estado y auditoria
- degradacion visible cuando broker o worker no estan disponibles
- no aceptar silenciosamente trabajo que no pueda persistirse
- objetivo inicial: 99% de jobs aceptados llegan a estado terminal dentro de su SLO
- ningun job puede retener secretos en payloads, logs o dead-letter metadata

## 7. Definition of done

- [ ] PRD y OpenSpec aprobados
- [ ] ADR y threat/failure model aprobados
- [ ] implementado por slices reversibles
- [ ] pruebas de idempotencia, tenant isolation, crash recovery y concurrencia
- [ ] dashboard/alertas y runbook ejercitados
- [ ] rollback ensayado
- [ ] 14 dias de evidencia operativa
- [ ] control actualizado a `operated`

## 8. Evidence

- PRD: este documento
- Spec: `openspec/changes/external-background-job-runtime/`
- Registro: `docs/product/ENTERPRISE_CONTROL_REGISTER.md`
- Evidencia operativa: pendiente
