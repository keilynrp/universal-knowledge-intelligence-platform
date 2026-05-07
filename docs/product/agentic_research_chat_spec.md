# Agentic Research Chat Spec

## Purpose

UKIP debe ofrecer un chatbot investigativo que permita consultar datos procesados o nuevas ingestas mediante NLQ, RAG y herramientas agenticas sin perder trazabilidad.

La meta no es crear un asistente generico. La meta es crear una interfaz de analisis conversacional conectada al portafolio real de conocimiento, capaz de responder, explicar fuentes, registrar evidencia y alimentar briefs/reportes.

## Product Thesis

Cuando un analista, investigador o stakeholder consulta un dataset, necesita pasar rapido de registros dispersos a respuestas contextualizadas:

- que datos existen
- que patrones emergen
- que registros sostienen una conclusion
- que preguntas analiticas se pueden responder con cubos OLAP
- que evidencia puede reutilizarse en un brief final

El chatbot debe operar como una capa de interpretacion trazable sobre:

- catalogos internos
- portales de catalogo
- detalle de registros
- import batches
- grafo materializado
- hidden patterns
- proyeccion de impacto
- report builder

## Existing Foundation

UKIP ya cuenta con piezas reutilizables:

- `POST /nlq/query`: traduce preguntas naturales a consultas OLAP sanitizadas.
- `POST /rag/query`: responde preguntas con RAG, contexto de dominio y memoria de sesion.
- `rag_engine.query_catalog_agentic`: soporta tool-calling mediante `tool_registry`.
- `ContextEngine`: genera contexto de dominio o recall de sesiones previas.
- `AnalysisContext`: puede convertirse en el contenedor inicial de trazas conversacionales.
- `PatternDiscoveryService`: expone patrones ocultos reutilizables en respuestas.
- `ImpactProjectionService`: expone lectura prospectiva para brief/reportes.

La implementacion debe orquestar estas piezas en vez de duplicarlas.

## User Stories

### US-ARC-001 - Chat sobre una ingesta

Como analista, quiero preguntar sobre una ingesta especifica para extraer hallazgos, brechas, patrones y registros relevantes sin revisar manualmente todo el catalogo.

Acceptance:

- El chat acepta `import_batch_id`.
- La respuesta declara el alcance consultado.
- Las fuentes usadas se devuelven como referencias navegables.
- La traza indica si uso RAG, NLQ, herramientas o contexto estructurado.

### US-ARC-002 - Chat en detalle de registro

Como investigador, quiero conversar con un registro puntual para entender su contexto, citas, metadatos, relaciones y potencial de uso en el brief.

Acceptance:

- El chat acepta `entity_id`.
- El prompt incluye campos canonicos del registro.
- La respuesta no inventa metadatos ausentes.
- La UI permite abrir fuentes/registros relacionados.

### US-ARC-003 - Chat para brief final

Como usuario de reportes, quiero guardar respuestas utiles del chat como evidencia para que puedan reutilizarse en el brief final.

Acceptance:

- Cada respuesta puede persistir una traza.
- La traza incluye pregunta, respuesta, fuentes, herramientas y alcance.
- Report Builder puede incluir una seccion `agentic_trace`.
- El usuario puede distinguir evidencia generada por IA de datos estructurados.

### US-ARC-004 - Chat agentico con herramientas

Como usuario avanzado, quiero activar modo agentico para que el asistente use herramientas del sistema cuando la pregunta requiere exploracion multi-paso.

Acceptance:

- La UI permite activar/desactivar `use_tools`.
- La respuesta muestra herramientas usadas.
- Hay limite de iteraciones.
- Si una herramienta falla, la respuesta lo informa sin romper la conversacion.

## Functional Scope

### In Scope

- Componente reutilizable de chat para dashboard, catalogos, portales y detalle de registro.
- Endpoint orquestador `POST /agentic-chat/query`.
- Seleccion de modo: `auto`, `rag`, `nlq`, `hybrid`.
- Scopes: `domain_id`, `import_batch_id`, `provider`, `portal_slug`, `entity_id`.
- Trazabilidad por respuesta.
- Integracion con RAG, NLQ, context snapshots y tool registry.
- Reutilizacion futura en Report Builder.

### Out of Scope

- Entrenamiento de modelos propios.
- Fine-tuning.
- Escritura automatica irreversible en datos canonicos.
- Acciones destructive sin confirmacion humana.
- Exposicion publica anonima del chat sin controles de tenant.

## API Contract

### Request

```json
{
  "question": "Que patrones ocultos hay en esta ingesta?",
  "mode": "auto",
  "domain_id": "science",
  "import_batch_id": 123,
  "provider": "wos",
  "portal_slug": "catalog-science",
  "entity_id": null,
  "top_k": 6,
  "use_tools": true,
  "persist_trace": true
}
```

### Response

```json
{
  "answer": "Se observan tres concentraciones tematicas...",
  "mode_used": "hybrid",
  "scope": {
    "domain_id": "science",
    "import_batch_id": 123,
    "provider": "wos",
    "portal_slug": "catalog-science",
    "entity_id": null
  },
  "trace_id": 987,
  "trace": {
    "rag_used": true,
    "nlq_used": true,
    "tools_used": ["catalog.search", "patterns.discover"],
    "context_blocks": ["domain_snapshot", "import_batch", "hidden_patterns"],
    "iterations": 2,
    "provider": "openai",
    "model": "gpt-4o-mini"
  },
  "sources": [
    {
      "entity_id": 42,
      "label": "Linked Data - The Story So Far",
      "score": 0.91,
      "source": "catalog"
    }
  ],
  "follow_up_questions": [
    "Que registros sostienen mejor esta conclusion?",
    "Como cambia el patron por proveedor?"
  ]
}
```

## Orchestration Logic

### Mode `rag`

- Embeds the question.
- Retrieves catalog chunks from vector store.
- Injects structured scope context when available.
- Returns grounded answer and sources.

### Mode `nlq`

- Uses available OLAP dimensions.
- Translates question to a sanitized cube query.
- Executes the query.
- Returns aggregate result and explanation.

### Mode `hybrid`

- Runs NLQ when the question is metric/aggregate oriented.
- Runs RAG when the question asks for explanation, evidence or source-level grounding.
- Combines both outputs into one answer.
- Stores both traces.

### Mode `auto`

The service classifies the question with lightweight deterministic heuristics before invoking the LLM:

- Aggregate intent: "cuantos", "distribucion", "por dominio", "top", "tasa", "porcentaje" -> NLQ or hybrid.
- Evidence intent: "cuales registros", "fuentes", "por que", "evidencia" -> RAG.
- Exploration intent: "patrones", "brechas", "recomendaciones", "impacto" -> agentic hybrid.

## Context Blocks

The orchestrator may inject:

- `domain_snapshot`: metrics from AnalyticsService.
- `import_batch_summary`: counts, provider, created_at, quality/enrichment coverage.
- `entity_profile`: canonical fields and enrichment fields for a selected record.
- `hidden_patterns`: output from PatternDiscoveryService.
- `impact_projection`: Monte Carlo impact projection summary.
- `graph_context`: high-level graph degree/relationships when available.
- `portal_context`: portal slug, filters, facets and visible collection scope.

Each context block must be declared in the response trace.

## Traceability Model

Minimum trace fields:

- `question`
- `answer`
- `scope`
- `mode_used`
- `sources`
- `tools_used`
- `context_blocks`
- `provider`
- `model`
- `created_by`
- `created_at`

Recommended persistence:

- Store trace snapshots in `AnalysisContext` for MVP.
- Prefix labels with `agentic-chat:`.
- Later, migrate to a dedicated `AgenticChatSession` and `AgenticChatMessage` model if conversation history needs first-class querying.

## Report Builder Integration

Add a future report section:

```txt
agentic_trace
```

The section should summarize:

- most relevant saved questions
- key answers
- cited records
- tools used
- limitations/confidence notes

Report copy must say clearly:

> Esta seccion resume respuestas asistidas por IA generadas sobre datos del portafolio UKIP. Las fuentes y herramientas usadas quedan registradas para auditoria.

## UI Placement

### Dashboard

Compact narrative assistant panel:

- "Pregunta sobre tu portafolio"
- recommended prompts based on current data health
- ability to save useful answer to brief

### Catalog Internal View

Contextual panel or drawer:

- scope defaults to current catalog filters
- supports selected records
- can answer "que tienen en comun estos registros?"

### Portal View

Read-only assistant:

- scope limited to portal collection
- no admin-only actions
- optional public visibility disabled by default

### Record Detail

Record-level assistant:

- scope defaults to `entity_id`
- answers about metadata, citations, provenance, enrichment and relationships

## UX Rules

- No more than one primary AI assistant surface per page.
- Always show scope before answering.
- Always show sources when sources exist.
- Always expose "guardar en brief" only after a response exists.
- Avoid generic placeholder claims like "I found insights" without evidence.
- If context is insufficient, say what is missing and suggest the next action.
- Agentic mode must visibly show tools used in collapsed form.

## Security And Governance

- Require authentication for internal chat.
- Public portal chat remains disabled until explicit governance is added.
- Respect tenant/org boundaries in every scope query.
- Never expose raw provider API keys.
- Rate-limit chat endpoints.
- Validate `entity_id`, `import_batch_id` and `portal_slug` ownership.
- Limit tool iterations to avoid runaway loops.
- Log errors without storing sensitive prompt payloads in plain operational logs.

## Technical Plan

### Phase 1 - Orchestrator MVP

- Create `backend/services/agentic_research_chat.py`.
- Add `POST /agentic-chat/query`.
- Reuse `rag_engine.query_catalog_agentic`.
- Reuse NLQ translation/execution through a shared service helper.
- Return normalized trace payload.
- Persist optional trace in `AnalysisContext`.

### Phase 2 - UI Component

- Create reusable `AgenticResearchChat`.
- Add it first to dashboard or catalog detail.
- Support scope props: `domainId`, `importBatchId`, `portalSlug`, `entityId`.
- Render answer, sources, tools used and save-to-brief affordance.

### Phase 3 - Brief/Reports

- Add `agentic_trace` report section.
- Surface saved chat traces as evidence.
- Allow trace selection in Report Builder.

### Phase 4 - Portal And Advanced Agent Tools

- Add portal-scoped read-only chat.
- Add catalog tools for selected records.
- Add graph and pattern discovery tools to `tool_registry`.

## Acceptance Criteria

- A user can ask a question scoped to a domain, import batch or entity.
- The response states scope and sources.
- The response trace identifies RAG, NLQ, tools and context blocks used.
- Agentic mode can be disabled.
- Saved traces can be reused by Report Builder.
- Existing `/rag/query` and `/nlq/query` continue working.
- No data mutations happen without explicit user action.
- Empty or unindexed datasets return helpful next steps instead of generic failure.

## Open Technical Questions

- Should long-running agentic runs become async jobs if tool chains exceed 5 seconds?
- Should public portal chat require a separate consent/governance flag?
- Should vector index metadata include `import_batch_id`, `portal_slug` and canonical provider for better scoped retrieval?
- Should saved traces be versioned when source records change?

## Recommended Next Implementation

Implement Phase 1 and Phase 2 together:

- backend endpoint with trace payload
- reusable frontend chat panel
- dashboard or catalog detail placement

This gives immediate analyst value while preserving the option to deepen Report Builder and portal usage in the next iteration.
