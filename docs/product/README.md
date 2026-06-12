# Product Documentation Hub

Este directorio contiene el sistema operativo de producto y delivery de UKIP.

## Documentos principales

- `docs/DOCUMENTATION_GOVERNANCE.md`: reglas de autoridad y uso de la documentacion.
- `PROGRAM_BACKLOG.md`: mapa maestro de epicas y lineas de producto.
- `COMMERCIAL_MVP.md`: foco comercial inicial y recorrido real de onboarding.
- `COMPLIANCE_GAP_REGISTER.md`: baseline de gaps enterprise y de compliance.
- `TENANT_SCOPING_MODEL.md`: modelo objetivo y olas de migracion para tenant isolation.
- `TRACEABILITY_MATRIX.md`: relacion entre vision, epicas, historias, sprints y evidencia.
- `ENTERPRISE_CONTROL_REGISTER.md`: autoridad sobre estado, prioridad, ownership y evidencia de controles enterprise.
- `ENTERPRISE_READINESS_PROGRAM.md`: autoridad sobre madurez, gates y politica de claims enterprise.
- `epics/EPIC-018-enterprise-assurance-and-operational-readiness.md`: ejecucion consolidada del programa enterprise.
- `STORY_MAP.md`: vista funcional resumida del backlog refinado.
- `epics/`: epicas activas del programa.
- `stories/`: historias de usuario activas o refinadas.
- `sprints/`: artefactos de sprint.
- `templates/EPIC_TEMPLATE.md`: plantilla para epicas.
- `templates/STORY_TEMPLATE.md`: plantilla para historias de usuario.
- `templates/SPRINT_TEMPLATE.md`: plantilla para plan y cierre de sprint.
- `templates/RELEASE_TEMPLATE.md`: plantilla para releases.

## Como usar este directorio

1. Identifica la epic en `PROGRAM_BACKLOG.md`.
2. Crea o referencia historias usando el template.
3. Planifica el sprint usando el template de sprint.
4. Actualiza `TRACEABILITY_MATRIX.md` cuando cambie el estado.
5. Si hubo valor entregado al usuario, refleja el resultado en `CHANGELOG.md`.

## Backfill inicial ya creado

- epicas iniciales en `docs/product/epics/`
- historias iniciales en `docs/product/stories/`
- sprint activo base en `docs/product/sprints/SPRINT-102.md`
- siguiente sprint operativo en `docs/product/sprints/SPRINT-103.md`
- siguiente sprint de hardening en `docs/product/sprints/SPRINT-104.md`
- siguiente sprint de tenant isolation en `docs/product/sprints/SPRINT-105.md`

## Regla de oro

Ninguna iniciativa nueva deberia entrar directamente al codigo sin pasar por:

- epic
- historia
- sprint
- trazabilidad

## Enterprise readiness

La fuente de verdad sigue este orden:

1. Control status: `docs/product/ENTERPRISE_CONTROL_REGISTER.md`
2. Programa y madurez: `docs/product/ENTERPRISE_READINESS_PROGRAM.md`
3. Ejecucion: `docs/product/epics/EPIC-018-enterprise-assurance-and-operational-readiness.md`
4. Portfolio: `docs/product/PROGRAM_BACKLOG.md`
5. Evidencia: `docs/product/TRACEABILITY_MATRIX.md`

La Runtime projection en `backend/enterprise_readiness.py` es una vista validada
del registro, no una fuente paralela. Los roadmaps historicos no gobiernan
prioridad ni madurez actual.

## Relacion con la capa historica

Si necesitas contexto de origen o decisiones previas:

- consulta `docs/reference/HISTORICAL_REFERENCE_INDEX.md`
- usa esos documentos como referencia, no como autoridad operativa primaria
