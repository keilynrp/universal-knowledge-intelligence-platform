# Estrategia Arquitectónica de Enriquecimiento Cienciométrico Predictivo
**Proyecto:** DB Disambiguador

---

## 1. Resumen Ejecutivo
El presente documento detalla la estrategia de evolución del software **DB Disambiguador** desde una herramienta de "limpieza pasiva de catálogos" hacia un **"Motor Activo de Enriquecimiento de Datos y Análisis Predictivo"**.

El objetivo central es integrar capacidades de consumo de metadatos desde las principales APIs de bases de datos cienciométricas (OpenAlex, PubMed, Scopus, Web of Science, etc.), permitiendo la extracción automatizada de indicadores de alto valor: conteo de citas, coautorías, índices de acceso abierto, y modelado de tópicos (Conceptos/Machine Learning).

Siguiendo los principios de **Arquitectura Pragmática**, se ha adoptado una estrategia iterativa de tres (3) fases, implementando el patrón "Adapter" y abstracciones de Normalización de Objetos de Datos (NDO), respaldado por un sistema de colas (Background Worker) para asegurar resiliencia y escalabilidad sin incurrir en penalizaciones por "Rate Limiting".

---

## 1.b Indicadores implementados (estado actual)

> `Operational` — refleja capacidades ya desplegadas. Para el detalle de releases ver `CHANGELOG.md`.

| Indicador | Campo | Descripción | Nota |
| --- | --- | --- | --- |
| **NIF (Open Proxy)** | `normalized_impact_factor` | Factor de impacto normalizado por campo, derivado del `2yr_mean_citedness` de OpenAlex y normalizado contra la mediana del campo (`nif_field`). | Es un **proxy abierto**, **no** el JIF de Clarivate. Etiquetado como "open proxy" en toda la UI. |
| **NIF Bayes (Open Proxy)** | `nif_bayes`, `nif_ci_low`, `nif_ci_high` | Companion bayesiano del NIF: shrinkage Empirical-Bayes Gamma-Poisson hacia la media del campo, con intervalo de credibilidad del 95%. Encoge revistas con muestra pequeña/ruidosa. | Se muestra **junto** al NIF (no lo reemplaza). `n` = conteo de works 2-años de OpenAlex. |
| **APC** | `apc_usd`, `apc_currency` | Cargo por procesamiento de artículo (article processing charge) desde OpenAlex/DOAJ. | |
| **Open Access (DOAJ)** | `is_in_doaj` | Indicador de revista en DOAJ. | |
| **Works count (revista)** | `works_count` | Conteo de works por ISSN (local, org-scoped). | ⚠️ distinto del conteo global 2-años de OpenAlex usado como `n` del bayes. |
| **Tipo de obra** | `enrichment_work_type` | `work.type` de OpenAlex (article, book, monograph, dissertation, dataset, preprint, …) agrupado en categorías y expuesto como facet filtrable. | |

Implementación clave:
- Normalización NIF / NIF Bayes: `backend/analyzers/journal_normalization.py` y `backend/analyzers/journal_normalization_bayes.py`.
- Mapeo de tipo de obra: `backend/services/work_type.py` (+ espejo `frontend/app/lib/workType.ts`).
- Backfills idempotentes: `backend/scripts/backfill_nif_bayes.py`, `backend/scripts/backfill_work_type.py` (ver `docs/operating/BACKFILL_RUNBOOK.md`).
- Superficies: dashboard `/analytics/journals`, modal de entidad, y ficha de detalle `/entities/[id]` (sección Revista + fila Tipo de obra).

---

## 2. Estrategia de Implementación Escalonada (Tiers)

Para prevenir el "Anti-Patrón de Sobre-Ingeniería", la asimilación de fuentes se prioriza por accesibilidad, restricciones transaccionales y viabilidad técnica:

### 🟢 Fase 1: Fuentes Abiertas y Gratuitas (Despliegue Actual)
Implementación inicial sobre APIs libres de barreras corporativas o muros de pago.
*   **OpenAlex API (Motor Principal Implementado):** Fuente abierta que indexa literatura científica mundial masivamente. Abundante en estructura de grafos.
*   **PubMed (NCBI E-utilities):** Escogido como candidato secundario en el dominio de la biología/medicina.
*   **ORCID & Unpaywall APIs:** Para validación de identidades autorales universales e índices de Acceso Abierto.

### 🟡 Fase 2: Web Scraping Restringido y APIs de Métricas Alternativas
Extensión a fuentes que operan en zonas grises de políticas de consumo o que evalúan el ecosistema "no académico".
*   **Scholarly (Google Scholar Wrapper en Python):** Susceptible fuertemente a mecanismos antibot (Captchas y baneos de IP). Requerirá un enrutamiento sobre arquitecturas de Proxies Rotativos.
*   **Altmetric.com:** Integración orientada al dominio del marketing predictivo y la influencia en redes/noticias (Menciones, engagement social).

### 🔴 Fase 3: APIs Premium e Institucionales con Paywall
Fuentes doradas (gold-standard) cerradas tras costosas suscripciones.
*   **Web of Science (WoS) (Clarivate) & Scopus (Elsevier):**
*   **Estrategia "Bring Your Own Key" (BYOK):** El sistema **no** proveerá tokens globales. La arquitectura debe solicitar al investigador que inserte sus propias llaves institucionales aprobadas (API Keys) a nivel de sesión o configuración global del usuario. La app actuará solo como conducto pasivo.

### 🟣 Fase 4: Descubrimiento de Patrones y Análisis Comparativo (Monte Carlo)
Evolución analítica para trascender la simple extracción de métricas, permitiendo modelado predictivo de impacto.
*   **Simulaciones Estocásticas (Método Monte Carlo):** Incorporación de un motor matemático para simular múltiples trayectorias de citación futuras basadas en la distribución histórica, permitiendo predecir la "vida útil" y el "perfil de impacto" de un grupo de conceptos o artículos.
*   **Análisis Comparativo Profundo:** Herramientas para correlacionar variables cienciométricas (ej. Open Access vs. Tasas de Citación, o Mapeo Geográfico vs. Tópicos).

### 🌌 Fase 5: Enriquecimiento Semántico & Arquitecturas RAG
Transformación del texto plano a un espacio vectorial interactivo alimentado por Large Language Models (LLMs).
*   **Vector Database Integration (Chroma / Pinecone):** Ingresar resúmenes (abstracts) y textos completos enriquecidos a una base de datos vectorial generando *embeddings* densos.
*   **Retrieval-Augmented Generation (RAG):** Integrar motores semánticos (tipo OpenAI o DeepSeek) que puedan "leer" todo el corpus científico importado y responder consultas complejas del investigador (QA) basándose estrictamente en la evidencia del catálogo, reduciendo alucinaciones y hallando "links" ocultos entre documentos dispares.

---

## 3. Arquitectura del Backend (Python / FastAPI)

Para mantener la aplicación desacoplada ante los constantes cambios estructurales que tienen las APIs de estos proveedores, construimos las siguientes piezas de infraestructura fundacional:

### 3.1 El Objeto Normalizado de Datos (Normalized Data Object - NDO)
**Componente:** `EnrichedRecord` (definido en `backend/schemas_enrichment.py`)

Las APIs cienciométricas no poseen estandarización. Para solucionar la colisión semántica, se creó el modelo `EnrichedRecord` apoyado en **Pydantic**:

```python
class EnrichedRecord(BaseModel):
    doi: Optional[str]               # Llave unívoca dorada
    title: str                       # Título de la publicación
    authors: List[str]               # Vector de autores
    citation_count: int              # Valor predictivo: Impacto
    concepts: List[str]              # Extracción NLP (Topicos, palabras clave > 0.4 score)
    source_api: str                  # Trazabilidad ("OpenAlex", "WoS")
    raw_response: dict               # Payload sucio original (Auditoría / Extracción tardía)
```

### 3.2 Patrón de Integración "Adapter"
**Componente:** `BaseScientometricAdapter` (en `backend/adapters/enrichment/base.py`)

Clase abstracta que dicta el contrato de implementación estricto para cualquier nueva fuente documental añadida en Fase 2 o 3. Este contrato obliga a la implementación de 3 métodos polimórficos de consulta:
1. `search_by_doi(doi)`
2. `search_by_title(title, limit)`
3. `search_by_author(name, limit)`

#### ✅ El Adaptador de OpenAlex
Utiliza `httpx` para requests sincrónicos encapsulados y se diseñó inyectando un parámetro clave para la Fase 1: El uso de la cabecera/query `mailto:` (Polite Etiquette), el cual permite el acceso al "Fast Lane" de OpenAlex, ofreciendo una mayor robustez y cuota por sobre los requests anónimos genéricos. El Parser estricto transforma el grafo caótico de JSON en un objeto `EnrichedRecord`.

---

## 4. Gestión Transaccional y Tolerancia a Fallos (Motor de Fondo / Worker)

Para evitar ataques accidentales de DDoS a las infraestructuras cienciométricas o cuellos de botella mediante bloqueos en la interfaz se estructuró una **Cola Asíncrona Lenta (Rate-limited Queue)** (`backend/enrichment_worker.py`):

1. **Inyección Dinámica de Columnas:** En `main.py`, al inicializarse la aplicación, una migración automática (`ALTER TABLE raw_products`) verifica e inyecta dinámicamente las columnas necesarias `enrichment_*`.
2. **Workers Perpetuos:** El worker inicia luego del evento `startup` de la aplicación principal y solicita una sesión temporal y controlada al motor SQL.
3. **Mecanismo de Polling Disciplinado:** 
   - El worker lee de 1 en 1, cualquier fila donde `enrichment_status == "pending"`.
   - Contacta a la API de turno (P/E OpenAlex), inserta los datos en SQLite y cierra sesión.
   - Aplica un `await asyncio.sleep(2)` para rate-limiting cortés. Si el servicio responde con error o agota registros, descansa 10 segundos antes del siguiente ciclo.

---

## 5. Implementación del Frontend (Componentes Visuales de Reacción)

La UX asimila la estrategia en dos vectores complementarios dentro del entorno **React / Next.js**, utilizando Tailwind CSS.

### 5.1 Analizador de Esquemas Multidimensionales
**Componente:** `DataSourceSchemaAnalyzer.tsx` (En `import-export`)

Antes del Análisis Predictivo, los datos deben importarse con seguridad con independencia del formato. Este componente permite hacer "Drag-and-Drop" y pre-analizar en el FrontEnd la estructura abstracta (keys) de formatos como *JSON-LD, XML anidados, RDF triples y Parquet Dataframes*.

### 5.2 Microinteracciones: Enriquecimiento Quirúrgico
**Componente:** `ProductTable.tsx` (Dashboard Raíz)

A los flujos del listado de la tabla maestra se les integró un botón de enriquecimiento granular (`Enrich Row ⚡`), inyectando paralelismo en caso de que los investigadores necesiten "forzar" extracciones selectivas inmediatas (Saltándose la cola masiva programada en el backend).

El Frontend mapea exitosamente el nuevo payload del modelo SQL subyacente y lo exhibe dinámicamente en el modal de Detalles Ampliados.

---

## 6. Siguientes Pasos Evolutivos (Roadmap a futuro)

1. **Implementación Física de la Fase 4 (Motor Monte Carlo):** Diseñar un nuevo worker estadístico en Python (probablemente usando `numpy` / `scipy`) que pueda ingerir las tasas de citación de un producto y proyectar su impacto a 5 y 10 años.
2. **Integración UI Fase 4:** Construcción de gráficas de distribución probabilística de citas (Campanas de Gauss / Percentiles) en el Dashboard de Analytics.
3. **Prototipado Fase 5 (RAG):** Evaluaciones de Bases de Datos Vectoriales ligeras embebidas en el proyecto (ej. Milvus Lite o ChromaDB local) para acoger los conceptos abstractos y vectorizarlos de manera gratuita y local sin externalizar datos.
