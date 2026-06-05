# EPIC-016 - Data Lifecycle and Privacy Controls

## 1. Summary

Dar a UKIP controles de ciclo de vida de datos respaldados por politica (retencion, export de sujeto y borrado/derecho al olvido) con evidencia auditable, para destrabar conversaciones legales y de procurement enterprise.

## 2. Problem

- la plataforma puede importar, mutar y exportar datos, pero no tiene un workflow respaldado por politica para retencion, borrado de sujeto y evidencia de ciclo de vida
- esto bloquea conversaciones tipo GDPR y genera ambiguedad en la revision legal de un cliente
- es el gap P0 `data_lifecycle_controls` del registro de enterprise readiness

## 3. Objective

Pasar de "podemos tocar datos" a "operamos el ciclo de vida del dato con politica, workflows admin y evidencia", de forma tenant-scoped sobre el cimiento de EPIC-012.

## 4. User value

Como cliente institucional o equipo legal/procurement, quiero que UKIP pueda exportar y borrar los datos de un sujeto/tenant bajo politica y con evidencia, para cumplir requisitos de privacidad sin trabajo manual ni riesgo.

## 5. Scope

Incluye:

- politica de ciclo de vida documentada (retencion, SLA de borrado, evidencia retenida)
- registro de eventos de ciclo de vida (auditoria org-scoped) para export/borrado/purga
- export de sujeto/tenant (DSAR) en formato portable, abarcando todas las superficies
- borrado / derecho al olvido en cascada (DB + ChromaDB + cubes/caches) con confirmacion y evidencia
- purga por retencion programada + configuracion de retencion

Excluye:

- audit evidence pack tamper-evident (gap P1 separado, EPIC de auditoria)
- residencia de datos y pack legal/DPA (gaps P1 separados)
- billing y certificaciones de compliance

## 6. Success criteria

- existe politica de ciclo de vida documentada y versionada
- un admin puede exportar todos los datos de un sujeto/tenant en un bundle portable
- un admin puede borrar los datos de un sujeto/tenant y no queda residuo en ningun store (DB, ChromaDB, cubes, cache)
- cada export/borrado/purga deja un registro de evidencia org-scoped (quien, que, cuando, alcance)
- la retencion vencida se purga de forma programada con evidencia

## 7. Technical impact

- nuevo modelo `DataLifecycleEvent` + migracion (org-scoped)
- nuevos endpoints admin de export y borrado (`backend/routers/`)
- borrado en cascada reutilizando el inventario de superficies de EPIC-012 y el helper `tenant_access`
- integracion con `VectorStoreService.delete_document` (ChromaDB) y stores derivados (DuckDB/Redis)
- job de retencion (se apoya en la externalizacion de US-042)
- docs de politica en `docs/operating/`

## 8. Risks

- riesgo: completitud de la cascada de borrado; omitir un store deja residuo y rompe el derecho al olvido
- impacto: fallo de compliance pese a UI "exitosa"
- mitigacion: partir del inventario de superficies de EPIC-012 y un test que verifique cero registros del sujeto en cada store tras el borrado
- riesgo: el borrado es destructivo e irreversible
- mitigacion: confirmacion fuerte, alcance explicito, registro de evidencia y posible periodo de gracia / soft-delete previo

## 9. Stories

| ID | Story | Estado |
|---|---|---|
| US-070 | Fundamento de auditoria de ciclo de vida + politica documentada | To do |
| US-071 | Export de sujeto/tenant (DSAR) en bundle portable | To do |
| US-072 | Borrado / derecho al olvido en cascada con evidencia | To do |
| US-073 | Purga por retencion programada + configuracion | To do |

## 10. Sprint allocation

| Sprint | Objetivo |
|---|---|
| SPRINT-107 | Fundamento de ciclo de vida: auditoria + politica + export |
| SPRINT-108 | Borrado en cascada + purga por retencion |

## 11. Evidence

Artefactos objetivo (se completaran a medida que cada slice se entregue):

- `backend/models.py` (`DataLifecycleEvent`)
- `alembic/versions/*_data_lifecycle_events.py`
- `backend/routers/data_lifecycle.py` (export + deletion admin endpoints)
- `backend/services/data_lifecycle.py` (cascade inventory + executor)
- `docs/operating/DATA_LIFECYCLE_POLICY.md`
- `backend/tests/test_epic016_data_lifecycle_export.py`
- `backend/tests/test_epic016_data_lifecycle_deletion.py`
- actualizacion de `backend/enterprise_readiness.py` (mover `data_lifecycle_controls` a resolved)
