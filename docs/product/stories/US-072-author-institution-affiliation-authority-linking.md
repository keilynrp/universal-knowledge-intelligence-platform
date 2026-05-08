# US-072 - Author-Institution Affiliation Authority Linking

## 1. User story

Como analista de research intelligence, quiero resolver autores e instituciones como autoridades conectadas para validar afiliaciones institucionales y su relacion directa con cada autor dentro de un portafolio academico.

## 2. Context

- Epic: `EPIC-004`
- Dependencias naturales:
  - `US-055` Author Resolution Engine MVP
  - `US-056` Explicit NIL Detection Layer
  - `US-057` Hierarchical Fallback for Concept Linking
- Base tecnica existente:
  - `POST /authority/authors/resolve` ya resuelve autores con `context_affiliation`
  - `POST /authority/resolve` ya resuelve `institution` y `organization`
  - `OpenAlexEntityResolver` ya consulta `/authors` y `/institutions`
  - `EntityRelationship` ya conecta entidades internas con `belongs-to`
  - `graph_materializer` ya crea nodos de autores, afiliaciones y relaciones internas desde import cientifico

## 3. Problem statement

El sistema actual usa la afiliacion como senal textual para mejorar el score del autor, pero no persiste una vinculacion auditable entre:

- el authority record del autor
- el authority record de la institucion
- la evidencia que justifica la relacion autor-institucion

Esto limita casos comerciales clave:

- consolidacion de autores por school, department o institucion
- validacion de afiliaciones institucionales
- reporting de portafolio por institucion normalizada
- deteccion de autores con afiliacion ambigua o no enlazable

## 4. Scope

### In scope

- Resolver una afiliacion institucional cuando se resuelve un autor con `context_affiliation`.
- Persistir una relacion auditable entre authority records de autor e institucion.
- Exponer la relacion en la respuesta de `POST /authority/authors/resolve`.
- Marcar la relacion como `pending`, `confirmed` o `rejected` sin confirmar automaticamente instituciones ambiguas.
- Reutilizar `AuthorityRecord`; no crear un subsistema de authority paralelo.
- Mantener ORCID como fuente solo para autores.
- Usar OpenAlex/VIAF/Wikidata/DBpedia para instituciones segun el resolver actual.

### Out of scope

- Resolver historial institucional completo del autor.
- Inferir departamentos o schools si la fuente no los expone.
- Crear un graph store externo.
- Introducir embeddings o `pgvector`.
- Reemplazar `EntityRelationship`.
- Cambiar el contrato actual de `POST /authority/resolve` para casos no author.

## 5. Proposed model

Crear una tabla nueva y pequena para vinculos entre authority records:

`authority_record_links`

Campos:

- `id`
- `org_id`
- `source_authority_record_id`
- `target_authority_record_id`
- `link_type`
- `confidence`
- `status`
- `evidence`
- `created_at`
- `confirmed_at`

Valores iniciales:

- `link_type = "affiliated-with"`
- `status = "pending" | "confirmed" | "rejected"`

Razon:

- `EntityRelationship` conecta entidades internas (`raw_entities`), no candidates externos.
- `AuthorityRecord` ya representa candidatos externos revisables.
- El link debe poder existir antes de que el usuario confirme o materialice entidades internas.

## 6. API contract

### 6.1 Extend author resolve request

Mantener compatibilidad con `AuthorResolveRequest`.

Agregar campos opcionales:

- `resolve_affiliation: bool = true`
- `affiliation_field_name: str = "affiliation"`

Si `context_affiliation` esta vacio, no se intenta resolver institucion.

### 6.2 Extend author resolve response

Agregar:

```json
{
  "affiliation_resolution": {
    "attempted": true,
    "records_created": 3,
    "winning_record": {
      "id": 456,
      "authority_source": "openalex",
      "authority_id": "I123",
      "canonical_label": "Universidad Nacional de Colombia",
      "confidence": 0.91,
      "resolution_status": "exact_match"
    },
    "link": {
      "id": 789,
      "source_authority_record_id": 123,
      "target_authority_record_id": 456,
      "link_type": "affiliated-with",
      "confidence": 0.84,
      "status": "pending",
      "evidence": [
        "context_affiliation:Universidad Nacional de Colombia",
        "author_affiliation_score:0.20",
        "institution_resolution_status:exact_match"
      ]
    }
  }
}
```

Si no hay afiliacion:

```json
{
  "affiliation_resolution": {
    "attempted": false,
    "reason": "missing_context_affiliation"
  }
}
```

### 6.3 New read endpoint

Agregar:

- `GET /authority/authors/review-queue/{record_id}/affiliations`

Respuesta:

- author record
- linked institution records
- link status
- evidence

### 6.4 Link review endpoints

Agregar:

- `POST /authority/links/{link_id}/confirm`
- `POST /authority/links/{link_id}/reject`

No deben cambiar automaticamente el estado del author record ni del institution record.

## 7. Resolution algorithm

Cuando `POST /authority/authors/resolve` recibe `context_affiliation` y `resolve_affiliation=true`:

1. Resolver autor como hoy.
2. Persistir author authority records como hoy.
3. Tomar el winning author record.
4. Resolver `context_affiliation` con `entity_type="institution"`.
5. Persistir institution authority records con `field_name=affiliation_field_name`.
6. Tomar el winning institution record.
7. Crear un `authority_record_links` entre ambos si:
   - existe winning author record
   - existe winning institution record
   - el institution record no es `internal_nil`
8. Calcular `link.confidence` con una heuristica inicial:
   - `0.50 * author.confidence`
   - `0.40 * institution.confidence`
   - `0.10 * author.score_breakdown.affiliation`
9. Marcar `link.status="pending"`.
10. Incluir link y evidencia en la respuesta.

## 8. Review behavior

- Confirmar un author record no confirma automaticamente la institucion.
- Confirmar una institucion no confirma automaticamente el link.
- Confirmar el link significa: "esta afiliacion autor-institucion es valida para este contexto".
- Rechazar el link no rechaza al autor ni a la institucion.
- Si author o institution quedan `rejected`, los links asociados deben seguir visibles pero no deben contarse como confirmados.

## 9. Scoring and evidence

Evidencia minima del link:

- `context_affiliation:<value>`
- `author_record:<source>:<id>`
- `institution_record:<source>:<id>`
- `author_confidence:<score>`
- `institution_confidence:<score>`
- `author_affiliation_score:<score>`

El primer baseline no debe intentar coautoria, topics ni historial temporal.

## 10. UI implications

Primera entrega UI minima:

- En la cola de autores, mostrar afiliacion resuelta si existe.
- En el comparador de autor, agregar seccion compacta `Affiliation authority`.
- Permitir confirmar/rechazar el link sin salir del review queue.

No construir una pantalla nueva si la cola actual puede absorber el flujo.

## 11. Migration

Agregar migracion Alembic para:

- crear `authority_record_links`
- indices:
  - `org_id`
  - `source_authority_record_id`
  - `target_authority_record_id`
  - `link_type`
  - `status`

La migracion no debe backfillear links historicos.

## 12. Tests

Backend tests requeridos:

- author resolve sin `context_affiliation` no intenta resolver institucion.
- author resolve con `context_affiliation` persiste institution records.
- author resolve con `context_affiliation` crea un link pending.
- si institution resolution devuelve NIL/no candidates, no crea link valido.
- confirm link cambia solo el link.
- reject link cambia solo el link.
- tenant scoping impide leer o mutar links de otra org.
- response mantiene compatibilidad con campos existentes.

Frontend tests requeridos:

- review queue renderiza affiliation authority cuando viene en response.
- confirm/reject link invoca endpoints correctos.
- estado de loading/error no bloquea acciones del author record.

## 13. Acceptance criteria

- [ ] `POST /authority/authors/resolve` puede resolver autor + institucion en una sola operacion cuando recibe `context_affiliation`.
- [ ] la institucion se persiste como `AuthorityRecord` independiente.
- [ ] la relacion autor-institucion se persiste como link auditable.
- [ ] el link tiene confidence, evidence y status.
- [ ] el usuario puede confirmar o rechazar el link sin alterar automaticamente los records relacionados.
- [ ] los casos sin afiliacion o con institucion NIL quedan representados sin errores.
- [ ] no se introduce infraestructura nueva.
- [ ] tests backend cubren el flujo positivo, NIL, review y tenant scoping.

## 14. Implementation checkpoints

### Checkpoint 1 - Data contract

- modelo `AuthorityRecordLink`
- schemas de response/request
- migracion
- serializers

### Checkpoint 2 - Backend flow

- resolver helper para institution affiliation
- integracion en `resolve_author_profile`
- link confidence/evidence
- endpoints de read/confirm/reject

### Checkpoint 3 - Tests

- unit tests del helper
- API tests del flujo author + affiliation
- tenant scoping tests

### Checkpoint 4 - UI minimal

- mostrar affiliation authority en author review
- acciones confirm/reject link
- estados de loading/error

### Checkpoint 5 - Documentation

- actualizar evidence de esta historia
- actualizar `AUTHOR_RESOLUTION_ENGINE_MVP.md` con la extension author-institution

## 15. Open questions

- Debe `affiliated-with` representar la afiliacion al momento de una publicacion, o una afiliacion general del autor?
- Conviene agregar `context_year` al link para diferenciar afiliaciones historicas?
- Cuando exista una entidad interna de author e institution, debemos materializar tambien `EntityRelationship(belongs-to)` automaticamente o dejarlo para un job explicito?
