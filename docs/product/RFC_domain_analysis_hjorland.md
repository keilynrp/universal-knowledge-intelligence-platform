# RFC: Dominios del Conocimiento como Unidad Epistémica en UKIP

**Alineación con la Teoría de Análisis de Dominio (Hjorland & Albrechtsen, 1995)**

| Campo | Valor |
|-------|-------|
| Status | Draft |
| Autor | Equipo UKIP |
| Fecha | 2026-05-18 |
| Relacionado | `docs/ontological_spectrum_spec.md`, `docs/SCIENTOMETRICS.md` |

---

## 1. Problema

El concepto de "dominio" en UKIP (`DomainSchema`) opera hoy como un **esquema estructural de datos**: define atributos, tipos y etiquetas para organizar la interfaz y validar campos de ingesta. Un dominio es, en la práctica, un formulario tipado.

```yaml
# Estado actual: dominio = schema de atributos
id: science
name: Science & Research
primary_entity: Publication
attributes:
  - name: title
    type: string
  - name: authors
    type: string
  # ... campos planos
```

Esta representación es necesaria pero insuficiente. No captura:

- **Qué cuenta como evidencia** en el dominio (jerarquía epistémica)
- **Cómo se organizan los conceptos** entre sí (estructura semántica)
- **Quiénes producen y validan el conocimiento** (comunidad discursiva)
- **Qué paradigmas coexisten** y cómo se distribuyen (pluralismo teórico)

El resultado es un desequilibrio: UKIP es potente en análisis **cuantitativo** (citation counts, co-occurrence PMI, Cramer's V, Monte Carlo) pero carece de instrumentos para análisis **cualitativo** que contextualicen esas métricas dentro de las dinámicas reales de producción de conocimiento.

---

## 2. Marco Teórico: Analisis de Dominio

Hjorland y Albrechtsen (1995) proponen que un dominio del conocimiento no es una categoría taxonómica estática, sino una **comunidad discursiva** — un grupo social que comparte prácticas, lenguaje especializado, criterios de validación y tradiciones epistemológicas.

### 2.1 Los 11 enfoques de Hjorland (2002)

| # | Enfoque | Descripción | Relevancia UKIP |
|---|---------|-------------|-----------------|
| 1 | Guías de literatura y portales temáticos | Compilaciones especializadas por dominio | Alta — catálogo UKIP ya organiza por dominio |
| 2 | Clasificaciones especializadas | Esquemas de organización internos del dominio | Alta — `DomainSchema.attributes` |
| 3 | Indexación y recuperación | Vocabularios controlados, tesauros | Alta — enrichment_concepts, RAG |
| 4 | Estudios empíricos de usuarios | Necesidades de información de la comunidad | Media — no implementado |
| 5 | Estudios bibliométricos | Análisis cuantitativo de publicaciones | **Ya implementado** (topic modeling, OLAP, co-autoría) |
| 6 | Estudios históricos | Evolución temporal del dominio | Media — timeline en dashboard |
| 7 | Estudios de géneros documentales | Tipologías de documentos y su función | Baja — `document_type` existe pero sin semántica |
| 8 | Estudios epistemológicos y críticos | Paradigmas, escuelas de pensamiento | **No implementado — gap principal** |
| 9 | Terminología y lenguajes especializados | Análisis del vocabulario del dominio | Parcial — disambiguation, pero sin relaciones |
| 10 | Estructuras de comunicación académica | Canales, prácticas de publicación | Baja |
| 11 | Cognición profesional | Modelos mentales de los expertos | Baja |

### 2.2 El equilibrio cuali-cuanti

Hjorland argumenta que el análisis bibliométrico (enfoque 5) es insuficiente sin el análisis epistemológico (enfoque 8). Las métricas de citación no distinguen entre:

- Una cita que **apoya** una tesis vs. una que la **refuta**
- Un paper altamente citado por ser **fundacional** vs. por ser **controversial**
- Productividad en un paradigma **dominante** vs. en uno **emergente**

El análisis de dominio propone que estas distinciones solo son posibles cuando el sistema comprende las **tradiciones epistémicas** del dominio y puede situar cada entidad dentro de ellas.

---

## 3. Propuesta: Tres capas epistémicas sobre DomainSchema

Extender `DomainSchema` con tres capas opcionales que enriquecen la semántica del dominio sin romper la estructura existente. Cada capa es independiente y se activa progresivamente.

### 3.1 Capa 1 — Estructura epistémica

**Propósito:** Modelar los paradigmas teóricos y la jerarquía de evidencia del dominio.

```yaml
epistemology:
  paradigms:
    - id: empiricist
      label: "Empiricist / Positivist"
      description: "Privilegia evidencia experimental, replicabilidad, significancia estadística"
      indicators:
        terms: ["randomized", "controlled trial", "p-value", "statistical significance",
                "hypothesis testing", "sample size", "effect size"]
        document_types: ["randomized controlled trial", "meta-analysis", "systematic review"]
        journals_affinity: ["The Lancet", "NEJM", "Nature"]

    - id: constructivist
      label: "Social Constructivist"
      description: "Privilegia contexto social, narrativa, reflexividad del investigador"
      indicators:
        terms: ["discourse analysis", "situated knowledge", "reflexivity",
                "qualitative", "ethnography", "hermeneutics", "phenomenology"]
        document_types: ["case study", "ethnographic study", "narrative review"]
        journals_affinity: ["Social Studies of Science", "Science as Culture"]

    - id: critical
      label: "Critical Theory"
      description: "Examina relaciones de poder, inequidad, sesgos estructurales"
      indicators:
        terms: ["power relations", "hegemony", "decolonial", "feminist epistemology",
                "bias", "equity", "justice", "marginalized"]
        document_types: ["critical review", "commentary", "position paper"]

  evidence_hierarchy:
    - level: 1
      label: "Systematic Review / Meta-analysis"
      weight: 1.0
    - level: 2
      label: "Randomized Controlled Trial"
      weight: 0.85
    - level: 3
      label: "Cohort / Longitudinal Study"
      weight: 0.70
    - level: 4
      label: "Case-Control Study"
      weight: 0.55
    - level: 5
      label: "Case Report / Series"
      weight: 0.40
    - level: 6
      label: "Expert Opinion / Editorial"
      weight: 0.25
```

**Mecánica de clasificación:**

1. Para cada entidad enriquecida, analizar `abstract` + `enrichment_concepts` + `document_type` contra los `indicators` de cada paradigma
2. Calcular un vector de afinidad paradigmática (scores normalizados, no exclusivos — un paper puede ser 0.7 empiricist + 0.3 critical)
3. Persistir en `attributes_json.epistemic_profile`

**Análisis habilitado:**

- Distribución de paradigmas en el corpus (diversidad epistémica)
- Evolución temporal de paradigmas (giro constructivista en los 90s, etc.)
- Correlación entre paradigma y métricas de impacto (los empiricistas citan mas? los criticos menos?)
- Detección de lagunas epistémicas ("este corpus no tiene perspectiva critica")

### 3.2 Capa 2 — Estructura semántica de conceptos

**Propósito:** Modelar relaciones jerárquicas y asociativas entre los conceptos del dominio, superando la lista plana actual.

```yaml
concept_relations:
  # Fuente primaria: ontología de conceptos de OpenAlex
  external_ontology:
    provider: openalex
    uri_prefix: "https://openalex.org/concepts/"
    relation_types:
      - id: broader
        label: "Broader concept (IS-A inverse)"
        example: "Machine Learning → Artificial Intelligence"
      - id: narrower
        label: "Narrower concept (IS-A)"
        example: "Artificial Intelligence → Machine Learning"
      - id: related
        label: "Associative relation"
        example: "Machine Learning ↔ Statistics"

  # Conceptos ancla del dominio (semillas para navegación jerárquica)
  anchor_concepts:
    - id: "C41008148"
      label: "Computer Science"
      role: "top-level domain anchor"
    - id: "C154945302"
      label: "Artificial Intelligence"
      role: "sub-domain anchor"
    - id: "C119857082"
      label: "Machine Learning"
      role: "active research front"

  # Umbrales para análisis
  thresholds:
    min_cooccurrence_for_relation: 3
    min_confidence_for_hierarchy: 0.6
```

**Mecánica:**

1. Al enriquecer vía OpenAlex, los conceptos ya vienen con `level` (0-5, donde 0 es mas general). Persistir el `level` junto al concepto.
2. Usar la API de conceptos de OpenAlex (`/concepts/{id}`) para obtener `ancestors` y `related_concepts` bajo demanda.
3. Materializar un grafo local de conceptos del corpus (solo los conceptos que aparecen en entidades del tenant).

**Análisis habilitado:**

- Navegación facetada jerárquica ("Computer Science" → drill down a "Machine Learning" → "Deep Learning")
- Mapa de cobertura conceptual (que áreas del árbol están representadas, cuales ausentes)
- Detección de frentes de investigación emergentes (conceptos de nivel bajo con crecimiento acelerado)
- Distancia semántica entre entidades (basada en posición en el árbol de conceptos)

### 3.3 Capa 3 — Comunidad discursiva

**Propósito:** Modelar las características de la comunidad que produce y valida el conocimiento en el dominio.

```yaml
discourse_community:
  # Fuentes de autoridad reconocidas
  authority_sources:
    identity: ["orcid", "viaf", "openalex"]
    bibliographic: ["doi", "isbn", "pmid"]
    institutional: ["ror", "grid", "wikidata"]

  # Canales de comunicación privilegiados
  communication_channels:
    tier_1:
      label: "Core journals"
      description: "Venues con mayor concentración de producción del dominio"
      auto_detect: true  # calcular desde el corpus (top journals por frecuencia)
      manual_seeds: ["Nature", "Science", "PLOS ONE"]
    tier_2:
      label: "Conference proceedings"
      description: "Actas de congresos relevantes"
      manual_seeds: []
    tier_3:
      label: "Preprints and grey literature"
      manual_seeds: ["arXiv", "bioRxiv", "SSRN"]

  # Criterios de validación del dominio
  validation_practices:
    - id: peer_review
      label: "Peer Review"
      weight: 1.0
      detectable: false  # no inferible desde metadatos
    - id: reproducibility
      label: "Reproducibility / Data Sharing"
      weight: 0.8
      detectable: true
      indicators: ["data availability", "code repository", "replication"]
    - id: open_access
      label: "Open Access Publication"
      weight: 0.6
      detectable: true
      field: "is_open_access"

  # Metricas de salud de la comunidad (calculadas, no configuradas)
  health_metrics:
    - id: gini_authorship
      label: "Gini coefficient of authorship concentration"
      description: "0 = producción distribuida, 1 = concentrada en pocos autores"
    - id: international_collaboration_rate
      label: "Rate of multi-country co-authorships"
    - id: newcomer_rate
      label: "Fraction of first-time authors per year"
    - id: epistemic_diversity
      label: "Shannon entropy over paradigm distribution"
```

**Mecánica:**

1. `communication_channels.auto_detect` calcula los top journals/venues del corpus actual
2. `health_metrics` se computan como agregaciones sobre el corpus (Gini sobre distribución de papers por autor, tasa de coautoría internacional desde country extraction existente)
3. `epistemic_diversity` usa los perfiles de Capa 1 para calcular entropia de Shannon

**Análisis habilitado:**

- Panel de "salud del dominio" con indicadores de concentración, diversidad, apertura
- Detección de gatekeeping (pocas revistas/autores concentran la producción)
- Evolución temporal de practicas de validación (crecimiento de Open Access, data sharing)
- Comparación entre dominios (Science vs. Healthcare vs. custom)

---

## 4. Impacto en la Arquitectura

### 4.1 Modelo de datos

```
DomainSchema (existente)
├── id, name, description, primary_entity, icon
├── attributes: List[AttributeSchema]          ← sin cambios
│
├── epistemology: Optional[EpistemologyConfig]  ← NUEVO (Capa 1)
│   ├── paradigms: List[Paradigm]
│   └── evidence_hierarchy: List[EvidenceLevel]
│
├── concept_relations: Optional[ConceptRelationsConfig]  ← NUEVO (Capa 2)
│   ├── external_ontology: OntologySource
│   ├── anchor_concepts: List[AnchorConcept]
│   └── thresholds: ConceptThresholds
│
└── discourse_community: Optional[DiscourseConfig]  ← NUEVO (Capa 3)
    ├── authority_sources: AuthoritySources
    ├── communication_channels: ChannelTiers
    ├── validation_practices: List[ValidationPractice]
    └── health_metrics: List[HealthMetric]
```

Las tres capas son **opcionales** (`Optional`). Un dominio sin ellas sigue funcionando exactamente como hoy. Esto garantiza retrocompatibilidad total.

### 4.2 Archivos afectados

| Componente | Cambio |
|------------|--------|
| `backend/schema_registry.py` | Extender `DomainSchema` con modelos Pydantic para las 3 capas |
| `backend/domains/*.yaml` | Agregar secciones `epistemology`, `concept_relations`, `discourse_community` a `science.yaml` como referencia |
| `backend/analyzers/epistemic_classifier.py` | **Nuevo** — clasificador de afinidad paradigmática basado en text matching |
| `backend/analyzers/concept_hierarchy.py` | **Nuevo** — materialización de grafo de conceptos desde OpenAlex |
| `backend/analyzers/domain_health.py` | **Nuevo** — cómputo de metricas de salud de la comunidad |
| `backend/routers/analytics.py` | Nuevos endpoints para métricas epistémicas y de salud |
| `backend/enrichment_worker.py` | Post-enrichment hook para clasificación epistémica |
| `frontend/app/analytics/domain-analysis/` | **Nuevo** — panel de análisis de dominio |

### 4.3 Dependencias externas

| Dependencia | Propósito | Costo |
|-------------|-----------|-------|
| OpenAlex Concepts API | Jerarquía de conceptos, relaciones | Gratis (polite pool) |
| Ninguna nueva librería | Text matching con stdlib + existentes (numpy) | 0 |

### 4.4 Integración con capacidades existentes

| Capacidad existente | Enriquecimiento con Domain Analysis |
|---------------------|--------------------------------------|
| Topic Modeling (`topic_modeling.py`) | Contextualizar topics dentro de la jerarquía de conceptos |
| Co-authorship Network (`coauthorship.py`) | Overlay de paradigmas sobre la red (autores empiricistas vs. constructivistas?) |
| Correlation Analysis (`correlation.py`) | Correlacionar paradigma con citation_count, open_access, year |
| OLAP Cube (`olap.py`) | Nueva dimensión `paradigm` para cortes epistémicos |
| Authority Resolution (`authority/`) | Enriquecer con contexto de comunidad discursiva |
| RAG Chat (`ai_rag.py`) | Contextualizar respuestas con el marco epistémico del dominio |

---

## 5. Plan de Implementación Incremental

### Fase A — Capa 1: Estructura epistémica (MVP)

**Alcance:** Clasificación de paradigmas por text matching en abstracts/conceptos.

1. Extender `DomainSchema` con `epistemology` opcional
2. Configurar paradigmas en `science.yaml`
3. Implementar `epistemic_classifier.py` (term frequency sobre indicators)
4. Hook post-enrichment que clasifica y persiste `epistemic_profile`
5. Endpoint `GET /analyzers/epistemic-distribution/{domain_id}`
6. Widget de distribución de paradigmas en frontend

**Entregable:** Gráfico de barras/donut mostrando distribución de paradigmas en el corpus, con drill-down temporal.

### Fase B — Capa 2: Jerarquía de conceptos

**Alcance:** Navegación jerárquica de conceptos con datos de OpenAlex.

1. Extender `DomainSchema` con `concept_relations` opcional
2. Implementar `concept_hierarchy.py` (fetch + cache de ancestros desde OpenAlex)
3. Materializar subgrafo local de conceptos del corpus
4. Endpoint `GET /analyzers/concept-tree/{domain_id}`
5. Tree view / sunburst de conceptos en frontend

**Entregable:** Árbol de conceptos navegable con conteos de entidades por nodo.

### Fase C — Capa 3: Métricas de comunidad

**Alcance:** Dashboard de salud del dominio.

1. Extender `DomainSchema` con `discourse_community` opcional
2. Implementar `domain_health.py` (Gini, tasas de colaboración, diversidad)
3. Endpoint `GET /analyzers/domain-health/{domain_id}`
4. Dashboard de salud con indicadores y tendencias temporales

**Entregable:** Panel de indicadores de concentración, diversidad epistémica, apertura.

---

## 6. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Clasificación de paradigmas imprecisa por text matching superficial | Alta | Medio | Iniciar con indicadores conservadores; iterar con feedback de expertos; escalar a embeddings/LLM en v2 |
| Overhead de API al obtener jerarquía de conceptos | Media | Bajo | Cache agresivo; materialización batch; rate limiting existente |
| Complejidad conceptual excesiva para usuarios no expertos | Media | Alto | Capas opcionales; UI simplificada con tooltips explicativos; modo "avanzado" |
| Paradigmas no aplicables a dominios no científicos | Baja | Bajo | Configuración por dominio; healthcare y default pueden omitir `epistemology` |

---

## 7. Criterios de Aceptación

### Fase A (MVP)
- [ ] `science.yaml` incluye al menos 3 paradigmas con indicators
- [ ] El clasificador asigna afinidad paradigmática a >80% de entidades con abstract
- [ ] La distribución de paradigmas es visible en el frontend
- [ ] El OLAP cube permite cortar por paradigma
- [ ] Sin regresiones en tests existentes

### Fase B
- [ ] Al menos 2 niveles de jerarquía de conceptos navegables
- [ ] Sunburst o tree view funcional
- [ ] Cache de conceptos evita >1 request/concepto/semana a OpenAlex

### Fase C
- [ ] Al menos 4 métricas de salud calculadas
- [ ] Dashboard con tendencia temporal
- [ ] Comparación entre 2+ dominios

---

## 8. Referencias

1. Hjorland, B., & Albrechtsen, H. (1995). Toward a new horizon in information science: Domain-analysis. *Journal of the American Society for Information Science*, 46(6), 400-425.
2. Hjorland, B. (2002). Domain analysis in information science: Eleven approaches — traditional as well as innovative. *Journal of Documentation*, 58(4), 422-462.
3. Hjorland, B. (2017). Domain analysis. *Knowledge Organization*, 44(6), 436-464.
4. Tennis, J. T. (2003). Two axes of domains for domain analysis. *Knowledge Organization*, 30(3/4), 191-195.
5. Smiraglia, R. P. (2015). *Domain Analysis for Knowledge Organization*. Chandos Publishing.
6. OpenAlex Concepts API: https://docs.openalex.org/api-entities/concepts

---

## 9. Glosario

| Término | Definición en contexto UKIP |
|---------|----------------------------|
| **Dominio del conocimiento** | Comunidad discursiva con prácticas, lenguaje y criterios de validación compartidos (Hjorland, 1995) — no solo un schema de datos |
| **Paradigma epistémico** | Tradición teórica que define qué cuenta como evidencia valida (empiricismo, constructivismo, teoría critica, etc.) |
| **Jerarquía de evidencia** | Ordenamiento de tipos documentales por rigor metodológico (meta-análisis > ensayo controlado > opinión experta) |
| **Comunidad discursiva** | Grupo social que produce, valida y consume conocimiento en un dominio |
| **Diversidad epistémica** | Grado de pluralismo paradigmático en un corpus, medido como entropía de Shannon sobre la distribución de paradigmas |
| **Frente de investigación** | Concepto de nivel específico (nivel 3-5 en OpenAlex) con crecimiento acelerado reciente |
| **Gini de autoría** | Coeficiente de concentración: 0 = producción equitativa, 1 = un solo autor domina |
