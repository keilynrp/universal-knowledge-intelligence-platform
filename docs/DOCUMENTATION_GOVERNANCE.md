# Documentation Governance

Politica oficial para mantener coherencia documental en UKIP.

## 1. Objetivo

Evitar que el proyecto pierda hilo conductor por mezclar:

- vision estrategica
- memoria historica
- ejecucion de producto
- evidencia tecnica

Este documento define que documentacion manda, que documentacion contextualiza y como debe trabajar el equipo de agentes.

## 2. Clasificacion oficial

### A. Documentacion viva

Es la que gobierna el trabajo actual del proyecto.

Incluye:

- sistema operativo de delivery
- backlog maestro
- trazabilidad
- templates
- onboarding tecnico
- futuros artefactos activos de sprint, epicas, historias y releases

### B. Documentacion historica y de referencia

Es la que preserva:

- contexto de origen
- decisiones de pivot
- evaluaciones externas
- propuestas previas
- roadmaps ya no operativos
- analisis de dominio o investigacion

## 3. Regla de autoridad

Cuando un agente necesite tomar decisiones:

1. primero consulta documentacion viva
2. si falta contexto, consulta documentacion historica
3. si hay contradiccion, gana la documentacion viva
4. si la documentacion viva esta incompleta, se actualiza

## 4. Regla de escritura

Antes de crear o modificar documentos, clasifica el contenido:

- si sirve para ejecutar trabajo actual -> documentacion viva
- si preserva memoria o razonamiento previo -> referencia historica
- si describe una salida publicada -> changelog o release note
- si formaliza una decision tecnica de largo plazo -> arquitectura o ADR

## 5. Comportamiento esperado de los agentes

Todo agente debe:

- leer primero `AGENT_WORKING_PROTOCOL.md`
- leer primero `docs/README.md`
- seguir `docs/DOCUMENTATION_GOVERNANCE.md`
- usar `docs/product/PROGRAM_BACKLOG.md` para ubicar epicas
- usar `docs/product/TRACEABILITY_MATRIX.md` para mantener trazabilidad
- usar templates oficiales para epicas, historias, sprints y releases
- evitar crear documentos paralelos que dupliquen autoridad

Todo agente debe evitar:

- usar documentos historicos como fuente operativa principal
- abrir roadmaps alternos no integrados al backlog maestro
- registrar cambios de producto solo en changelog sin trazabilidad previa

## 6. Estados recomendados para documentos

Usa estas etiquetas conceptuales al describir documentos:

- `Operational`: fuente de verdad actual
- `Reference`: contexto util, no normativo
- `Historical`: memoria institucional
- `Deprecated`: no usar salvo para arqueologia documental

## 7. Mantenimiento minimo

- cada nueva epic actualiza `PROGRAM_BACKLOG.md`
- cada nueva historia relevante actualiza trazabilidad
- cada sprint activo usa la plantilla oficial
- cada cambio visible al usuario actualiza `CHANGELOG.md`
- cada documento historico importante debe figurar en el indice historico

## 8. Criterio para sanear documentos viejos

Cuando un documento antiguo siga siendo valioso pero ya no deba gobernar trabajo:

1. no se elimina
2. se clasifica como `Reference` o `Historical`
3. se enlaza desde `docs/reference/HISTORICAL_REFERENCE_INDEX.md`
4. su contenido operativo vigente se migra a la capa viva

## 9. Resultado esperado

La documentacion debe permitir responder siempre:

- hacia donde va UKIP
- que estamos construyendo ahora
- por que existe este trabajo
- en que epic e historia cae
- como se conecta con la arquitectura y el valor entregado

## 10. Enterprise readiness authority

Para enterprise readiness, la autoridad es:

1. Control status: `docs/product/ENTERPRISE_CONTROL_REGISTER.md`
2. Madurez y claim policy: `docs/product/ENTERPRISE_READINESS_PROGRAM.md`
3. Ejecucion del programa: `docs/product/epics/EPIC-018-enterprise-assurance-and-operational-readiness.md`
4. Unidades de delivery: historias `US-042` y `US-073` a `US-081`
5. Secuencia de portafolio: `docs/product/PROGRAM_BACKLOG.md`
6. Control-to-evidence mapping: `docs/product/TRACEABILITY_MATRIX.md`
7. Runtime projection: `backend/enterprise_readiness.py`

La proyeccion runtime nunca reemplaza ni eleva el estado del registro de controles.
