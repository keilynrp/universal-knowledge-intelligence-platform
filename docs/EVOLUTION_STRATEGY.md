# 🌐 Visión Estratégica: Universal Knowledge Intelligence Platform (UKIP)

**Documento:** Plano Arquitectónico de Evolución  
**Proyecto:** DB Disambiguador → UKIP  
**Creado:** 2026-03-05  
**Estado:** Documento vivo — Se actualiza con cada fase implementada

---

## 1. El Pivot Estratégico: De Herramienta a Plataforma

### 1.1 Estado Actual (DB Disambiguador v1)

| Dimensión | Estado actual |
|---|---|
| **Dominio** | Catálogos de productos e-commerce |
| **Datos** | SKUs, GTINs, Marcas, Modelos |
| **Propósito** | Limpieza y normalización |
| **Usuario** | Operadores de datos en retail |
| **Salida** | Excel limpio + reglas normalizadas |

### 1.2 Visión Objetivo (UKIP v2)

| Dimensión | Estado objetivo |
|---|---|
| **Dominio** | Agnóstico: Ciencias, Humanidades, Marketing, Salud, Ingeniería, Economía... |
| **Datos** | Cualquier entidad estructurable: Papers, Patentes, Genes, Ensayos, Empresas, Pacientes |
| **Propósito** | Inteligencia de decisión: Analizar, Predecir, Recomendar, Explicar |
| **Usuario** | Investigadores, Tomadores de decisiones, Analistas estratégicos |
| **Salida** | Artefactos estratégicos de alto valor (Reportes, Proyecciones, Consultas RAG) |

---

## 2. Los 5 Pilares del Nuevo Paradigma

### 🏛️ Pilar 1: Domain-Agnostic Data Engine
El motor de datos debe operar sobre **cualquier entidad** sin importar su dominio. La arquitectura clave es un **Schema Registry** dinámico:

```
Dominio → Schema → Entidades → Relaciones → Ontología
```

**Dominios previstos:**
- 🔬 Ciencias (Biología, Química, Física, Matemáticas)
- 🧬 Ciencias de la Salud y Bienestar
- 🎓 Ciencias Sociales y Humanidades
- 📊 Marketing, Ventas y Análisis de Mercado
- 🏢 Inteligencia Empresarial y Consultoría
- 🔗 Combinaciones multi-dominio (transdisciplinariedad)

### ⚙️ Pilar 2: Software-Agnostic Processing Pipeline
Inspirado en los principios de **Context Engineering**, el pipeline debe ser:

```
Ingesta → Limpieza → Harmonización → Análisis → Reconciliación → Entrega
```

Cada etapa debe ser **pluggable y reemplazable** sin afectar el resto del sistema. Patrones clave:
- **Adapters** para cualquier fuente de datos (APIs, archivos, bases de datos, streams)
- **Normalizers** configurables por dominio
- **Analyzers** intercambiables (estadísticos, semánticos, LLM-based)
- **Exporters** para distintos formatos y destinatarios

### 🧠 Pilar 3: Context Engineering Integration
La integración de LLMs no es solo un "chat". Es una **arquitectura de contexto estructurado**:

```
Context Window = System Prompt + Retrieved Docs (RAG) + Entity Memory + Tool Calls + User Query
```

**Componentes de Context Engineering:**
- **Context Builder:** Ensambla el contexto óptimo por tarea (análisis, resumen, predicción)
- **Memory Layer:** Contexto persistente de análisis previos y preferencias del investigador
- **Tool Registry:** Herramientas que el LLM puede invocar (calcular, buscar, comparar)
- **Prompt Templates:** Plantillas por dominio y tipo de análisis

### 📈 Pilar 4: Predictive Intelligence & ROI Artifacts
Transformar análisis en decisiones accionables con valor demostrable:

| Artefacto | Técnica | Escenario |
|---|---|---|
| **Mapa de Impacto Cienciométrico** | Monte Carlo + OpenAlex | Universidad — Selección de proyectos de I+D |
| **Radar de Tendencias** | NLP + Topic Modeling | Empresa — Vigilancia tecnológica competitiva |
| **Scorecard de Riesgo/Retorno** | Análisis multi-criterio | Inversión — Due diligence académico |
| **Informe de Brechas de Conocimiento** | Análisis comparativo de corpus | I+D — Identificación de gaps en literatura |
| **Proyección ROI a 3/5/10 años** | Series temporales + MC | Dirección — Presupuestación de proyectos de I+D |
| **Panel de Reconciliación Semántica** | RAG + embeddings | Investigación — Deduplicación y merge de corpus |

### 🔗 Pilar 5: Open by Default, Premium by Choice
Los métodos base son libres y reproducibles; los proveedores premium son opcionales vía BYOK. La plataforma debe funcionar en modo cero-costo con OpenAlex + ChromaDB + sentence-transformers locales, y escalar a WoS + OpenAI cuando el contexto institucional lo permita.

---

## 3. Arquitectura de Software Propuesta (UKIP v2)

### 3.1 Nueva Estructura de Carpetas

```
ukip/
├── core/                           # Motor agnóstico central
│   ├── schema_registry.py          # Registro dinámico de esquemas por dominio
│   ├── pipeline.py                 # Orquestador del pipeline de procesamiento
│   ├── entity_model.py             # Modelo de entidad universal (reemplaza RawProduct)
│   └── context_engine.py           # Context Engineering: Builder, Memory, Tools
│
├── adapters/                       # Fuentes y destinos (entrada/salida)
│   ├── ingest/                     # Lectores de fuentes de datos
│   │   ├── excel_adapter.py        # Excel/CSV (ya existe)
│   │   ├── json_ld_adapter.py      # JSON-LD, RDF (ya existe)
│   │   ├── api_adapter.py          # Genérico para APIs REST externas
│   │   └── db_adapter.py           # Conexión a bases de datos externas
│   ├── enrichment/                 # Enriquecimiento cienciométrico (Fases 1-3)
│   └── llm/                        # LLM providers (OpenAI, Anthropic, Local, etc.)
│
├── analyzers/                      # Motores de análisis intercambiables
│   ├── quantitative/
│   │   ├── montecarlo.py           # ✅ Implementado — Proyecciones estocásticas
│   │   ├── correlation.py          # 🔵 Pendiente — Análisis multi-variable
│   │   └── time_series.py          # 🔵 Pendiente — Proyecciones temporales (ROI)
│   ├── qualitative/
│   │   ├── topic_modeling.py       # 🔵 Pendiente — BERTopic / LDA
│   │   ├── sentiment.py            # 🔵 Pendiente — Análisis de sentimiento
│   │   └── knowledge_gaps.py       # 🔵 Pendiente — Detección de brechas bibliométricas
│   └── semantic/
│       ├── rag_engine.py           # ✅ Implementado — RAG con ChromaDB
│       └── entity_linker.py        # 🔵 Pendiente — Reconciliación semántica
│
├── artifacts/                      # Generadores de salidas de alto valor
│   ├── templates/                  # 🔵 Pendiente — Plantillas por dominio
│   ├── report_builder.py           # 🔵 Pendiente — Informes PDF/HTML
│   ├── roi_calculator.py           # 🔵 Pendiente — Calculadora de ROI multi-escenario
│   └── export_engine.py            # 🔵 Pendiente — Exportación extendida
│
├── domains/                        # Configuraciones específicas por dominio
│   ├── science.yaml                # 🔵 Pendiente
│   ├── social_humanities.yaml      # 🔵 Pendiente
│   ├── healthcare.yaml             # 🔵 Pendiente
│   ├── business_intel.yaml         # 🔵 Pendiente
│   └── custom.yaml                 # 🔵 Pendiente — Plantilla para dominios personalizados
│
└── api/                            # FastAPI app (refactorizada progresivamente)
    ├── routers/
    │   ├── entities.py             # 🔵 Pendiente — CRUD agnóstico
    │   ├── analysis.py             # 🔵 Pendiente — Análisis cuantitativo + cualitativo
    │   ├── rag.py                  # ✅ Implementado
    │   └── artifacts.py            # 🔵 Pendiente — Generación de artefactos
    └── schemas/
        └── universal.py            # 🔵 Pendiente — Schemas Pydantic agnósticos
```

### 3.2 Modelo de Entidad Universal

En lugar de `RawProduct` con campos específicos de e-commerce, el nuevo modelo unificado es:

```python
class UniversalEntity(Base):
    id                   # Identificador interno
    entity_type          # product | paper | patent | person | company | gene | trial | ...
    domain               # science | humanities | healthcare | business | custom

    # Identidad principal (siempre presente)
    primary_label        # Nombre/título principal
    secondary_label      # Nombres alternativos/alias
    canonical_id         # DOI | ISBN | GTIN | ORCID | RUT | custom

    # Metadata flexible (almacenada como JSON estructurado)
    attributes_json      # Todos los campos específicos del dominio

    # Enriquecimiento (generalización de las columnas actuales)
    enrichment_status    # none | pending | completed | failed
    enrichment_source    # openalex | wos | scholar | pubmed | custom
    enrichment_data_json # Payload normalizado (NDO)

    # Semántico
    vector_indexed       # Boolean — ¿está indexado en ChromaDB?
    embedding_model      # Modelo que generó el embedding

    # Procedencia y Calidad
    data_quality_score   # 0.0 - 1.0 índice de calidad calculado
    source_file          # Archivo de importación original
    import_timestamp     # Cuándo fue ingestado
    last_modified        # Último cambio
```

---

## 4. Refactorización del Dashboard Frontend

### 4.1 Nueva Arquitectura de Navegación

```
UKIP Dashboard
├── 🏠 Home (Overview)               ← KPIs globales, actividad reciente
├── 🗂️ Workspace                     ← Selección y configuración de dominio activo
│   ├── Schema Designer              ← Definir/cargar esquema de dominio
│   └── Import Wizard                ← Ingesta multi-formato con mapeo visual
├── 🔍 Entity Catalog                ← Vista universal (reemplaza Product Table)
├── 🧹 Data Intelligence             ← Desambiguación, harmonización, reglas
│   ├── Fuzzy Disambiguation
│   ├── Authority Control
│   └── Reconciliation Engine        ← Deduplicación semántica
├── 📊 Analytics Hub                 ← Centro de análisis
│   ├── Quantitative Analysis        ← Monte Carlo, correlaciones, ROI
│   ├── Qualitative Intelligence     ← Topics, sentiment, knowledge gaps
│   └── Predictive Dashboard         ← Expandido
├── 🌌 Semantic AI (RAG)             ← Ya implementado
├── 📋 Artifact Studio               ← Nuevo: reportes y artefactos de decisión
│   ├── Report Builder
│   ├── ROI Calculator
│   └── Export Center
└── ⚙️ Platform Settings
    ├── Integrations                 ← Ya existe (Datos + AI Providers)
    └── Domain Registry              ← Gestión de esquemas de dominio
```

### 4.2 Migración de Lenguaje UI

| Actual (e-commerce) | Nuevo (agnóstico) |
|---|---|
| "Product Catalog" | "Entity Catalog" |
| "Brands / Models" | "Labels / Identifiers" |
| "SKU / GTIN" | "Canonical ID / Domain Key" |
| "Store Integrations" | "Data Source Connections" |
| "Enrich with OpenAlex" | "Enrich Entity ⚡" |
| "Brand Disambiguation" | "Label Disambiguation" |

---

## 5. Casos de Uso de Alto Impacto por Escenario

### 🎓 Universidad / Investigación
> *"¿Cuáles proyectos de investigación de nuestra facultad tienen mayor potencial de impacto cienciométrico en los próximos 5 años?"*

**Pipeline:** Ingesta BD proyectos → Enriquecimiento WoS/OpenAlex → Monte Carlo por área → RAG: "¿Quiénes investigan nanotecnología?" → **Artefacto:** Scorecard de priorización de I+D

### 🏢 Empresa / Vigilancia Tecnológica
> *"¿Qué tecnologías emergentes patentadas en los últimos 3 años representan riesgo u oportunidad para nuestro negocio?"*

**Pipeline:** Ingesta USPTO/EPO → Topic Modeling → Correlación con tendencias internas → RAG sobre corpus de patentes → **Artefacto:** Radar de Vigilancia Tecnológica + Mapa de Riesgo

### 🏥 Salud / Evidencia Clínica
> *"¿Cuál es el panorama de literatura sobre tratamientos para la condición X y cuáles tienen mayor nivel de evidencia?"*

**Pipeline:** Ingesta PubMed/Cochrane → Knowledge Gaps → Clasificación por nivel de evidencia → RAG sobre corpus → **Artefacto:** Evidence Matrix + Companion de Revisión Sistemática

### 💼 Consultoría / Due Diligence
> *"¿Cuál es el perfil cienciométrico y de innovación del equipo investigador de esta startup biotecnológica?"*

**Pipeline:** Ingesta perfiles ORCID + patentes → Enriquecimiento multi-fuente → Herramienta → **Artefacto:** Perfil de Capital Intelectual + ROI estimado de inversión

---

## 6. Roadmap de Implementación (Fases 6–10)

### ✅ Completado (Fases 1–5)
- [x] Motor de enriquecimiento cienciométrico 3 fases (OpenAlex, Scholar, WoS)
- [x] Monte Carlo para proyecciones estocásticas de citación
- [x] Panel RAG con ChromaDB + 6 proveedores LLM (BYOK)
- [x] Panel de gestión de integraciones (E-commerce + AI Providers)

### 🔵 Fase 6: Refactorización de Identidad y UI (Próxima)
- [ ] Migrar lenguaje de UI: Product → Entity, Brand → Label, etc.
- [ ] Implementar componente `WorkspaceSelector` (dominio activo)
- [ ] Actualizar sidebar con nueva arquitectura de navegación

### ⬜ Fase 7: Domain Schema Registry
- [ ] Diseñar SchemaRegistry con YAML/JSON dinámico
- [ ] UI de "Schema Designer" para dominios custom
- [ ] Implementar 4 dominios base: Science, Humanities, Healthcare, Business

### ⬜ Fase 8: Universal Entity Model
- [ ] Diseñar y migrar `RawProduct` → `UniversalEntity`
- [ ] Migrar datos existentes de manera retrocompatible
- [ ] Actualizar todos los endpoints y schemas Pydantic

### ⬜ Fase 9: Analyzers Avanzados
- [ ] `topic_modeling.py` — BERTopic sobre abstracts
- [ ] `knowledge_gaps.py` — Análisis comparativo de corpus
- [ ] `correlation.py` — Análisis multi-variable entre campos del catálogo

### ⬜ Fase 10: Artifact Studio
- [ ] `report_builder.py` — Reportes PDF/HTML generados desde análisis
- [ ] `roi_calculator.py` — Modelos de ROI múltiple escenario
- [ ] Templates de artefactos por dominio (academia, empresa, salud)

### ⬜ Fase 11: Context Engineering Layer
- [ ] `context_engine.py` — Builder de contextos estructurados para LLMs
- [ ] Memory Layer para persistir contexto de análisis entre sesiones
- [ ] Tool Registry para que el LLM invoque funciones del sistema

---

## 7. Principios Guía del Nuevo Paradigma

1. **Domain-First Design:** El dominio del usuario define el comportamiento del sistema, no al revés.
2. **Context Engineering como infraestructura:** El contexto no es accidental, es diseñado, medido y optimizado.
3. **Artefactos = ROI:** Todo análisis debe terminar en un artefacto accionable con valor demostrable.
4. **Agnóstico en datos, experto en métodos:** El sistema no asume el tipo de dato, pero sí conoce profundamente los métodos de análisis aplicables.
5. **Open by Default, Premium by Choice:** Los métodos base son libres; los proveedores premium son BYOK.
6. **Reproducibilidad:** Todo análisis debe ser reproducible, versionable y auditable.
7. **Justified Complexity:** Heredado de la Arquitectura Pragmática — ningún componente existe sin justificación clara.

---

## 8. Historial de Actualizaciones

| Fecha | Versión | Descripción del cambio |
|---|---|---|
| 2026-03-05 | v1.0 | Documento inicial — Plano estratégico de evolución UKIP |

*Este documento se actualiza en cada sesión de trabajo donde se avance en la implementación de las fases estratégicas.*
