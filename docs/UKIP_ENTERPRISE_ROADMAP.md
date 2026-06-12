> **Status: Historical.** This dated roadmap does not govern current
> enterprise-readiness scope, priority, or maturity. Use
> `docs/product/ENTERPRISE_READINESS_PROGRAM.md` and
> `docs/product/ENTERPRISE_CONTROL_REGISTER.md`.

# 🚀 UKIP Enterprise-Ready Roadmap

**Documento:** Product & Design Specifications  
**Objetivo:** Alcanzar MVP Enterprise-Ready (9.5/10)  
**Estado Actual:** 8.5/10 — Funcional, necesita polish + analytics avanzados  
**Timeline Estimado:** 10 semanas (2.5 meses)  
**Fecha:** 2026-03-06  
**Owner:** Equipo Producto + Diseño + Desarrollo

---

## 📊 Estado Actual vs. Objetivo

### Scorecard de Madurez

| Dimensión | Actual | Objetivo | Gap |
|-----------|--------|----------|-----|
| **Funcionalidad Core** | 9/10 | 9/10 | ✅ OK |
| **Analytics & OLAP** | 5/10 | 9/10 | 🔴 Crítico |
| **UX/UI Polish** | 7/10 | 9/10 | 🟡 Importante |
| **Exportación Enterprise** | 4/10 | 9/10 | 🔴 Crítico |
| **Demo-Readiness** | 6/10 | 10/10 | 🟡 Importante |
| **Performance** | 7/10 | 9/10 | 🟡 Medio |
| **Documentación** | 8/10 | 9/10 | 🟢 Menor |

**Score Global:** 8.5/10 → **9.5/10**

---

## 🎯 Features Priorizados (MoSCoW Method)

### MUST HAVE (Crítico para Enterprise)
1. ✅ **OLAP Cube Analytics** — Sistema de análisis multidimensional
2. ✅ **Dashboard Ejecutivo** — Vista de alto nivel para decisores
3. ✅ **Export Enterprise** — PDF/Excel/PPT con branding
4. ✅ **Caso de Uso Demo** — Dataset + narrativa completa

### SHOULD HAVE (Alta prioridad)
5. ✅ **Concept Cloud Visualization** — Visualización de temas emergentes
6. ✅ **Impact Heatmap** — Análisis geográfico-temporal
7. ✅ **One-Click Demo Mode** — Onboarding instantáneo
8. ✅ **Performance Optimization** — Queries <2seg, UI <1seg

### COULD HAVE (Nice to have)
9. ⬜ **Collaborative Annotations** — Equipos pueden comentar proyectos
10. ⬜ **Email Alerts** — Notificaciones de nuevas publicaciones relevantes
11. ⬜ **Custom Branding** — Logo/colores institucionales

### WON'T HAVE (Out of scope para MVP)
- ❌ Authentication/RBAC — Implementar en v2.0
- ❌ Multi-tenancy — Single-tenant por ahora
- ❌ Mobile app — Desktop-first

---

## 📋 FEATURE #1: OLAP Cube Analytics

### 🎯 Objetivo de Negocio
Permitir a stakeholders analizar datos desde múltiples perspectivas sin escribir SQL ni depender de analistas.

### 👥 Usuarios Target
- Directores de I+D
- Comités de evaluación académica
- Analistas estratégicos
- CFOs evaluando ROI de investigación

### 📐 Especificación Técnica

#### Backend
```python
# Nuevo módulo: backend/analyzers/quantitative/olap_engine.py

class OLAPEngine:
    def __init__(self, domain: str):
        self.db = duckdb.connect(f'data/cubes/{domain}.duckdb')
    
    def query_cube(self, 
                   dimensions: List[str],
                   measures: List[str],
                   filters: Dict = None) -> pd.DataFrame:
        """
        Ejecuta query OLAP multidimensional.
        
        Args:
            dimensions: ['year', 'country', 'topic']
            measures: ['SUM(citations)', 'COUNT(*)', 'AVG(h_index)']
            filters: {'year': [2023, 2024], 'country': ['Mexico']}
        
        Returns:
            DataFrame con resultados agregados
        """
        # Implementación con SQL CUBE
        pass
```

#### API Endpoints
```python
# Nuevo router: backend/api/routers/analytics.py

@router.post("/cube/query")
async def query_cube(request: CubeQueryRequest):
    """
    POST /api/cube/query
    {
        "dimensions": ["year", "country"],
        "measures": ["SUM(citation_count)"],
        "filters": {"year": [2023, 2024]},
        "rollup": true
    }
    
    Response:
    {
        "data": [...],
        "row_count": 245,
        "execution_time_ms": 342
    }
    """
    pass

@router.get("/cube/dimensions/{domain}")
async def get_dimensions(domain: str):
    """Retorna dimensiones/medidas disponibles para un dominio."""
    pass
```

#### Frontend Component
```typescript
// Nuevo componente: frontend/app/analytics/olap/page.tsx

interface OLAPCubeExplorerProps {
  domain: string;
}

export default function OLAPCubeExplorer({ domain }: OLAPCubeExplorerProps) {
  // UI con:
  // - Dimension Selector (multi-select checkboxes)
  // - Measure Selector (citation_count, h_index, etc.)
  // - Filter Panel (años, países, temas)
  // - Results Grid (ag-grid o TanStack Table)
  // - Export Button (Excel, CSV, JSON)
  
  return (
    <div className="grid grid-cols-12 gap-6">
      <aside className="col-span-3">
        <DimensionPanel />
        <MeasurePanel />
        <FilterPanel />
      </aside>
      <main className="col-span-9">
        <ResultsGrid data={cubeData} />
        <ExportToolbar />
      </main>
    </div>
  );
}
```

### 🎨 Diseño UI/UX

#### Wireframe Principal
```
┌─────────────────────────────────────────────────────────────┐
│  📊 OLAP Analytics — Science Impact                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─ Configuration ──────┐  ┌─ Results ─────────────────┐   │
│  │                       │  │                           │   │
│  │ Dimensions:           │  │ 🔍 Showing 245 rows      │   │
│  │ ☑ Year                │  │                           │   │
│  │ ☑ Country             │  │ ┌─────┬─────┬─────────┐ │   │
│  │ ☐ Institution         │  │ │Year │Ctry │Citations│ │   │
│  │ ☑ Topic               │  │ ├─────┼─────┼─────────┤ │   │
│  │                       │  │ │2024 │MX   │  1,234  │ │   │
│  │ Measures:             │  │ │2024 │BR   │    892  │ │   │
│  │ ☑ Citation Count      │  │ │2023 │MX   │  2,103  │ │   │
│  │ ☑ H-Index             │  │ │...  │...  │  ...    │ │   │
│  │ ☐ Quality Score       │  │ └─────┴─────┴─────────┘ │   │
│  │                       │  │                           │   │
│  │ Filters:              │  │ [📥 Export Excel]         │   │
│  │ Year: 2020-2024       │  │ [📊 Visualize]           │   │
│  │ Country: [All]        │  │ [💾 Save Query]          │   │
│  │                       │  │                           │   │
│  │ [▶ Run Query]         │  │                           │   │
│  └───────────────────────┘  └───────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Interacciones Clave
1. **Drag & Drop Dimensions** — Usuario arrastra dimensión a "Rows" o "Columns"
2. **Click to Drill-Down** — Click en celda abre nivel siguiente de jerarquía
3. **Right-Click Context Menu** — "Filter by this value", "Exclude", "Drill-down"
4. **Export Options** — Excel (multi-hoja), CSV, JSON, Copy to clipboard

### ✅ Criterios de Aceptación

**Funcionales:**
- [ ] Usuario puede seleccionar 1-5 dimensiones simultáneamente
- [ ] Usuario puede aplicar filtros por rango (años) y lista (países)
- [ ] Queries con 1M+ registros responden en <3 segundos
- [ ] Resultados se pueden exportar a Excel con formato
- [ ] Drill-down funciona en dimensiones jerárquicas (País → Región → Institución)

**No Funcionales:**
- [ ] UI responsive en pantallas 1920x1080 y 2560x1440
- [ ] Tabla soporta scroll virtual para 10,000+ filas
- [ ] Loading states durante queries (skeleton UI)
- [ ] Error handling elegante (queries inválidos, timeout)

**Performance:**
- [ ] Query simple (<3 dimensiones): <1 segundo
- [ ] Query complejo (5 dimensiones + CUBE): <3 segundos
- [ ] Export Excel (1,000 filas): <2 segundos
- [ ] Initial page load: <1 segundo

### 🔧 Stack Técnico
- **Backend:** DuckDB (OLAP engine) + Polars (transformaciones)
- **API:** FastAPI con streaming para queries grandes
- **Frontend:** TanStack Table v8 + shadcn/ui
- **Export:** ExcelJS (client-side) o python-openpyxl (server-side)

### 📅 Timeline & Estimación

| Fase | Tareas | Esfuerzo | Responsable |
|------|--------|----------|-------------|
| **Semana 1-2** | Backend OLAP engine + API | 80h | Backend Dev |
| **Semana 3-4** | Frontend componentes | 60h | Frontend Dev |
| **Semana 5** | Integración + testing | 40h | Full Stack |
| **Semana 6** | Export features + polish | 20h | Frontend Dev |

**Total:** 200 horas-persona (~6 semanas con 1 dev full-time)

### 📊 Métricas de Éxito
- 80%+ de usuarios usan OLAP en primera semana
- Tiempo promedio de análisis: <5 minutos (vs. 2 horas con Excel)
- NPS de feature: >8/10

---

## 📋 FEATURE #2: Dashboard Ejecutivo

### 🎯 Objetivo de Negocio
Proveer vista de alto nivel que responda "¿Cómo va mi investigación?" en <10 segundos.

### 👥 Usuarios Target
- VPs de I+D
- Rectores/Decanos
- Directores de departamento
- Stakeholders externos (inversores, board)

### 📐 Especificación Técnica

#### Componentes del Dashboard

**Hero Section — KPIs Principales**
```typescript
interface DashboardKPIs {
  totalPublications: number;
  enrichedRate: number;          // % enriquecidas
  avgCitations5y: number;
  totalResearchers: number;
  topRegion: string;
  topTopic: string;
  trendDirection: 'up' | 'down' | 'stable';  // vs. año anterior
}

<HeroKPIs data={kpis} />
```

**Section 1: Impact Over Time**
```typescript
<ImpactTimeChart 
  data={citationsByYear}
  type="area"              // Area chart with confidence bands
  showProjection={true}    // Incluye proyección Monte Carlo
/>
```

**Section 2: Geographic Distribution**
```typescript
<ImpactHeatmap 
  data={citationsByCountryYear}
  rows="country"
  columns="year"
  colorScale="greenToRed"
/>
```

**Section 3: Topic Landscape**
```typescript
<ConceptCloud 
  concepts={topConcepts}
  sizeBy="citation_count"
  colorBy="field"
  maxConcepts={50}
  interactive={true}       // Click para filtrar
/>
```

**Section 4: Top Performers**
```typescript
<TopPerformersTable 
  data={topResearchers}
  columns={['name', 'h_index', 'citations', 'trend']}
  rowCount={10}
  sortable={true}
/>
```

### 🎨 Diseño UI/UX

#### Layout Desktop (1920x1080)
```
┌────────────────────────────────────────────────────────────┐
│  🏠 UKIP Dashboard                          [Refresh] [⚙]  │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │📊 12,450 │ │🔬 79%    │ │📈 23.4   │ │🌍 LATAM  │     │
│  │Pubs      │ │Enriched  │ │Cites/5y  │ │Top Region│     │
│  │+5% ↑     │ │+12% ↑    │ │+8% ↑     │ │45% share │     │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘     │
│                                                             │
│  ┌─ Impact Over Time ────────────────────────────────┐    │
│  │  [Area Chart: Citations 2020-2029 with projection]│    │
│  └────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─ Geographic ──────┐  ┌─ Topic Landscape ──────────┐    │
│  │ [Heatmap]         │  │ [Concept Cloud]             │    │
│  │ Country × Year    │  │ Interactive word sizes      │    │
│  └───────────────────┘  └─────────────────────────────┘    │
│                                                             │
│  ┌─ Top Researchers ────────────────────────────────┐     │
│  │ Name          │ H-Index │ Citations │ Trend      │     │
│  │ García, M.    │   42    │  5,234    │ ↑ +15%    │     │
│  │ Silva, J.     │   38    │  4,892    │ ↑ +8%     │     │
│  └───────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────┘
```

### ✅ Criterios de Aceptación

**Funcionales:**
- [ ] Hero KPIs se actualizan en tiempo real al cambiar filtros globales
- [ ] Cada sección tiene tooltip explicativo (ⓘ icon)
- [ ] Click en concepto del cloud filtra todo el dashboard
- [ ] Gráficos son interactivos (hover muestra valores exactos)
- [ ] Botón "Export Dashboard" genera PDF/PPT

**No Funcionales:**
- [ ] Dashboard completo carga en <1.5 segundos
- [ ] Animaciones suaves (no laggy)
- [ ] Dark mode support
- [ ] Responsive down to 1366x768

**Datos:**
- [ ] KPIs refrescan cada 5 minutos automáticamente
- [ ] Opción de "Force Refresh" disponible
- [ ] Cache de queries para performance

### 🔧 Stack Técnico
- **Charts:** Recharts (ligero) o Visx (D3-based, más control)
- **Concept Cloud:** react-wordcloud o D3 custom
- **Heatmap:** react-calendar-heatmap o plotly.js
- **State Management:** Zustand (global filters)

### 📅 Timeline & Estimación

| Fase | Tareas | Esfuerzo | Responsable |
|------|--------|----------|-------------|
| **Semana 1** | Hero KPIs + API endpoint | 20h | Full Stack |
| **Semana 1-2** | Impact Time Chart | 16h | Frontend Dev |
| **Semana 2** | Heatmap + Concept Cloud | 24h | Frontend Dev |
| **Semana 3** | Top Performers + integration | 20h | Full Stack |
| **Semana 3** | Export PDF/PPT | 20h | Backend Dev |

**Total:** 100 horas-persona (~3 semanas)

### 📊 Métricas de Éxito
- 90%+ usuarios visitan dashboard en primera sesión
- Tiempo en página: >2 minutos (engagement)
- Export usado por 50%+ de usuarios ejecutivos

---

## 📋 FEATURE #3: Export Enterprise

### 🎯 Objetivo de Negocio
Stakeholders necesitan llevarse artefactos tangibles para reuniones/reportes.

### 👥 Usuarios Target
- Todos los usuarios, especialmente:
  - C-level (necesitan reportes board)
  - Analistas (reportes a superiores)
  - Consultores externos (entregables a clientes)

### 📐 Especificación Técnica

#### Formatos Soportados

**1. Excel Multi-Hoja**
```python
# backend/exporters/excel_exporter.py

class EnterpriseExcelExporter:
    def export(self, data: Dict, template: str = "default") -> bytes:
        """
        Genera Excel con:
        - Hoja 1: Executive Summary (KPIs, gráficos)
        - Hoja 2: Detailed Data (tabla completa)
        - Hoja 3: Pivot Tables (pre-configuradas)
        - Hoja 4: Charts (standalone)
        - Hoja 5: Methodology (cómo se calculó)
        
        Incluye:
        - Logo institucional
        - Colores branded
        - Fórmulas vivas (no valores estáticos)
        - Tablas formateadas (header freeze, filters)
        """
        wb = openpyxl.Workbook()
        
        # Summary sheet
        ws_summary = wb.active
        ws_summary.title = "Executive Summary"
        self._add_logo(ws_summary)
        self._add_kpis(ws_summary, data['kpis'])
        
        # Data sheet
        ws_data = wb.create_sheet("Detailed Data")
        self._export_dataframe(ws_data, data['records'])
        
        # Charts sheet
        ws_charts = wb.create_sheet("Visualizations")
        self._add_charts(ws_charts, data)
        
        return wb.save_bytes()
```

**2. PDF Report**
```python
# backend/exporters/pdf_exporter.py

class PDFReportGenerator:
    def generate(self, data: Dict, template: str = "executive") -> bytes:
        """
        Genera PDF profesional con:
        - Portada (logo, título, fecha, autor)
        - Índice automático
        - Executive Summary (1 página)
        - Secciones con gráficos embebidos
        - Apéndice con metodología
        - Footer con paginación
        
        Templates disponibles:
        - "executive": 5-10 páginas, enfoque C-level
        - "technical": 20-30 páginas, detalle completo
        - "slide-deck": Formato presentación (16:9)
        """
        from reportlab.lib import pagesizes
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
        
        # Configurar documento
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=pagesizes.letter)
        
        # Construir story
        story = []
        story.append(self._cover_page(data))
        story.append(self._executive_summary(data))
        story.append(self._impact_analysis(data))
        story.append(self._appendix(data))
        
        doc.build(story)
        return buffer.getvalue()
```

**3. PowerPoint Presentation**
```python
# backend/exporters/pptx_exporter.py

class PowerPointExporter:
    def export(self, data: Dict) -> bytes:
        """
        Genera PPTX con:
        - Slide 1: Título
        - Slide 2: Executive Summary (KPIs)
        - Slide 3-5: Análisis por dimensión
        - Slide 6: Proyecciones futuras
        - Slide 7: Recomendaciones
        - Slide 8: Appendix (metodología)
        
        Características:
        - Template con colores institucionales
        - Gráficos embebidos como imágenes
        - Tablas formateadas
        - Notas del presentador automáticas
        """
        from pptx import Presentation
        from pptx.util import Inches, Pt
        
        prs = Presentation('templates/ukip_template.pptx')
        
        # Title slide
        slide1 = prs.slides.add_slide(prs.slide_layouts[0])
        title = slide1.shapes.title
        title.text = f"Research Impact Analysis — {data['institution']}"
        
        # KPI slide
        slide2 = prs.slides.add_slide(prs.slide_layouts[5])  # Blank
        self._add_kpi_graphics(slide2, data['kpis'])
        
        return prs.save_bytes()
```

### 🎨 Diseño UI/UX

#### Export Dialog
```
┌──────────────────────────────────────────┐
│  📥 Export Report                        │
├──────────────────────────────────────────┤
│                                          │
│  Format:                                 │
│  ○ Excel (.xlsx)                         │
│  ● PDF (.pdf)         [Recommended]      │
│  ○ PowerPoint (.pptx)                    │
│  ○ CSV (data only)                       │
│                                          │
│  Template:                               │
│  [Executive Summary  ▼]                  │
│    • Executive Summary (5-10 pages)      │
│    • Technical Report (20-30 pages)      │
│    • Slide Deck (8-12 slides)            │
│                                          │
│  Include:                                │
│  ☑ Cover page with logo                 │
│  ☑ Executive summary                     │
│  ☑ Charts and visualizations             │
│  ☑ Detailed data tables                  │
│  ☑ Methodology appendix                  │
│  ☐ Raw data (Excel only)                 │
│                                          │
│  Branding:                               │
│  Logo: [Upload] [current_logo.png]       │
│  Colors: [Primary: #1E40AF]             │
│          [Secondary: #10B981]            │
│                                          │
│  [Cancel]              [Generate Report] │
└──────────────────────────────────────────┘
```

### ✅ Criterios de Aceptación

**Funcionales:**
- [ ] Excel incluye 5 hojas bien formateadas
- [ ] PDF tiene tabla de contenidos clickeable
- [ ] PowerPoint usa template con branding
- [ ] Todos los formatos incluyen fecha/autor/versión
- [ ] Gráficos se exportan en alta resolución (300 DPI)

**No Funcionales:**
- [ ] Export de 1,000 registros: <5 segundos
- [ ] Export de 10,000 registros: <15 segundos
- [ ] Archivos generados <5MB (para enviar por email)
- [ ] Funciona en Chrome, Firefox, Safari

**Usabilidad:**
- [ ] Botón "Export" visible en todas las vistas clave
- [ ] Preview de export antes de descargar
- [ ] Opción de guardar configuración como "template"

### 🔧 Stack Técnico
- **Excel:** python-openpyxl (server) o ExcelJS (client)
- **PDF:** ReportLab o WeasyPrint
- **PowerPoint:** python-pptx
- **Charts rendering:** Plotly (server-side) o canvas-to-image (client)

### 📅 Timeline & Estimación

| Fase | Tareas | Esfuerzo | Responsable |
|------|--------|----------|-------------|
| **Semana 1** | Excel exporter + templates | 24h | Backend Dev |
| **Semana 1-2** | PDF generator + styling | 32h | Backend Dev |
| **Semana 2** | PowerPoint exporter | 20h | Backend Dev |
| **Semana 2** | Frontend UI (dialog, preview) | 16h | Frontend Dev |
| **Semana 3** | Integration + testing | 8h | QA |

**Total:** 100 horas-persona (~3 semanas)

### 📊 Métricas de Éxito
- 70%+ de sesiones incluyen al menos 1 export
- Formato más usado: PDF (executive summary)
- Satisfacción con calidad de exports: >8/10

---

## 📋 FEATURE #4: Caso de Uso Demo

### 🎯 Objetivo de Negocio
Tener un dataset + narrativa lista para mostrar el valor de UKIP en <5 minutos.

### 👥 Usuarios Target
- Prospectos (sales demos)
- Nuevos usuarios (onboarding)
- Prensa/blog posts

### 📐 Especificación Técnica

#### Dataset Demo

**Características:**
- 1,000 publicaciones científicas
- 80% enriquecidas (OpenAlex + synthetic data)
- Múltiples dominios:
  - Ciencias (400): AI/ML, Biotecnología, Nanotecnología
  - Salud (300): Oncología, Neurociencia, Salud Pública
  - Ingeniería (300): Energías Renovables, Materiales, Robótica
- Distribución geográfica realista:
  - LATAM: 45% (México 20%, Brasil 15%, Chile 10%)
  - Europa: 30%
  - Asia: 15%
  - Norteamérica: 10%
- Rango temporal: 2018-2024
- Citaciones: Distribución log-normal (realistic)

**Generación:**
```python
# scripts/generate_demo_dataset.py

import pandas as pd
import numpy as np
from faker import Faker

class DemoDatasetGenerator:
    def generate(self, n_records: int = 1000):
        """
        Genera dataset demo realista.
        
        Outputs:
        - data/demo/publications.xlsx
        - data/demo/metadata.json (descripción del dataset)
        """
        fake = Faker()
        
        records = []
        for i in range(n_records):
            record = {
                'id': f'DEMO-{i:05d}',
                'title': self._generate_title(),
                'authors': self._generate_authors(),
                'year': np.random.choice(range(2018, 2025), p=[0.1, 0.1, 0.15, 0.2, 0.25, 0.15, 0.05]),
                'country': self._sample_country(),
                'field': self._sample_field(),
                'citations': self._sample_citations(),
                'doi': f'10.{np.random.randint(1000,9999)}/{fake.uuid4()[:8]}',
                'abstract': self._generate_abstract(),
            }
            records.append(record)
        
        df = pd.DataFrame(records)
        df.to_excel('data/demo/publications.xlsx', index=False)
        
        return df
```

#### Narrativa de Caso de Uso

**Escenario:** Universidad Nacional de Innovación (fictional)

**Problema:**
> "La UNI tiene 5 facultades con 2,000+ proyectos de investigación activos. 
> El comité de I+D debe decidir cómo reasignar $10M de presupuesto anual 
> basado en impacto científico, pero el análisis toma 3 meses de trabajo manual."

**Solución con UKIP:**

1. **Import (2 minutos)**
   - Suben Excel con 2,000 proyectos
   - UKIP detecta automáticamente columnas relevantes

2. **Enrichment (30 minutos automático)**
   - Sistema enriquece 1,600 proyectos (80%) vía OpenAlex
   - Restantes 400 se marcan para revisión manual

3. **Analysis (5 minutos)**
   - Dashboard muestra que:
     - Facultad de Ciencias tiene 45% de publicaciones pero solo 30% de presupuesto
     - Proyectos de AI/ML tienen 3x más citaciones que promedio
     - Brasil está superando a México en colaboraciones

4. **Projection (2 minutos)**
   - Monte Carlo proyecta que top 50 proyectos generarán 12,000 citaciones en 5 años
   - Reasignación propuesta: +$2M a Ciencias, -$1M a áreas de bajo impacto

5. **Decision (inmediato)**
   - Export PDF con recomendaciones
   - Comité aprueba reasignación en siguiente reunión

**Resultado:**
- ⏱ Tiempo de análisis: 3 meses → 1 hora
- 💰 Costo: $50K analistas → $0 (automatizado)
- 📈 Impacto proyectado: +35% en citaciones @ 5 años
- ✅ Decisión data-driven, no política

### 🎨 Diseño UI/UX

#### "One-Click Demo" Button

```
┌────────────────────────────────────────┐
│  UKIP — Universal Knowledge Platform  │
├────────────────────────────────────────┤
│                                        │
│     Welcome to UKIP!                   │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ 🚀 Try Demo (1-click)            │ │
│  │                                  │ │
│  │ Loads sample dataset with        │ │
│  │ 1,000 scientific publications    │ │
│  │                                  │ │
│  │ [Launch Demo Environment]        │ │
│  └──────────────────────────────────┘ │
│                                        │
│  Or:                                   │
│  • Upload your own data                │
│  • Connect to OpenAlex API             │
│                                        │
└────────────────────────────────────────┘
```

**Flujo al hacer click:**
1. Loading screen: "Preparing demo environment..." (3 segundos)
2. Import automático del dataset
3. Trigger enrichment background (muestra progreso)
4. Redirect a Dashboard con datos ya poblados
5. Tour guiado opcional (tooltips interactivos)

### ✅ Criterios de Aceptación

**Funcionales:**
- [ ] Dataset demo tiene distribuciones realistas (no random)
- [ ] One-click demo funciona sin configuración previa
- [ ] Narrativa PDF tiene antes/después claro
- [ ] Demo environment es aislado (no afecta datos reales)

**Contenido:**
- [ ] Narrativa es creíble y bien escrita
- [ ] Números son realistas (verificar con expertos)
- [ ] Screenshots de alta calidad (no pixelados)
- [ ] Caso de uso aplicable a múltiples industrias

**Técnico:**
- [ ] Demo loads en <5 segundos
- [ ] Dataset se puede resetear con 1 click
- [ ] Funciona offline (datos embebidos)

### 🔧 Stack Técnico
- **Dataset:** Pandas + Faker para generación
- **Storage:** Embebido en `/data/demo/` del repositorio
- **Demo mode:** Feature flag en frontend

### 📅 Timeline & Estimación

| Fase | Tareas | Esfuerzo | Responsable |
|------|--------|----------|-------------|
| **Semana 1** | Generar dataset realista | 12h | Data Analyst |
| **Semana 1** | Escribir narrativa + PDF | 8h | Product Manager |
| **Semana 2** | Implementar one-click demo | 16h | Full Stack |
| **Semana 2** | Tour guiado interactivo | 8h | Frontend Dev |
| **Semana 2** | Screenshots + polish | 4h | Designer |

**Total:** 48 horas-persona (~1.5 semanas)

### 📊 Métricas de Éxito
- 90%+ de nuevos usuarios prueban demo
- Tiempo promedio en demo: >5 minutos
- Conversión demo → upload own data: >40%

---

## 📋 FEATURES #5-8: Quick Wins

### Feature #5: Concept Cloud Visualization

**Esfuerzo:** 6-8 horas  
**ROI:** Alto (wow factor visual)  
**Stack:** react-wordcloud o D3.js  

**Spec:**
```typescript
<ConceptCloud 
  concepts={data.concepts}
  sizeBy="citation_count"    // Tamaño = citaciones
  colorBy="field"             // Color = área científica
  maxConcepts={50}
  interactive={true}          // Click filtra dashboard
  animateOnLoad={true}
/>
```

**Criterios:**
- [ ] Renderiza 50+ conceptos sin lag
- [ ] Colores distinguibles (paleta científica)
- [ ] Tooltip muestra stats al hover

---

### Feature #6: Impact Heatmap

**Esfuerzo:** 8-10 horas  
**ROI:** Muy alto (stakeholders aman heatmaps)  
**Stack:** plotly.js o recharts  

**Spec:**
```typescript
<ImpactHeatmap 
  data={citationsByCountryYear}
  rows="country"
  columns="year"
  colorScale="greens"         // Verde = alto impacto
  showValues={true}           // Números en celdas
  sortBy="total_desc"         // Ordenar por total
/>
```

**Criterios:**
- [ ] Color scale intuitivo (verde/rojo)
- [ ] Click en celda drill-down a detalles
- [ ] Export como PNG para reportes

---

### Feature #7: One-Click Demo Mode

**Esfuerzo:** 16-20 horas  
**ROI:** Crítico para onboarding  
**Stack:** Feature flag + seed data  

**Spec:**
- Botón prominente en landing page
- Carga 1,000 registros pre-enriched
- Tour interactivo (5 tooltips)
- Modo "sandbox" aislado

**Criterios:**
- [ ] Demo load <5 segundos
- [ ] Tour guiado opcional (skip)
- [ ] Reset demo con 1 click

---

### Feature #8: Performance Optimization

**Esfuerzo:** 24-32 horas  
**ROI:** Necesario para escala  

**Optimizaciones:**

1. **Backend:**
   - [ ] Index en columnas frecuentemente filtradas
   - [ ] Cache de queries OLAP (Redis opcional)
   - [ ] Pagination server-side (no client)
   - [ ] Async enrichment con progress updates

2. **Frontend:**
   - [ ] Code splitting por ruta
   - [ ] Lazy load de gráficos pesados
   - [ ] Virtual scrolling en tablas >1,000 filas
   - [ ] Debounce en inputs de búsqueda

3. **Database:**
   - [ ] VACUUM SQLite periódicamente
   - [ ] Migrar a PostgreSQL si >100K records

**Targets:**
- [ ] OLAP query <2 segundos (p95)
- [ ] RAG response <5 segundos (p95)
- [ ] Dashboard initial load <1 segundo
- [ ] Time to Interactive <2 segundos

---

## 📅 Gantt Chart — 10 Semanas

```
Semana │ 1  │ 2  │ 3  │ 4  │ 5  │ 6  │ 7  │ 8  │ 9  │ 10 │
───────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
OLAP   │████│████│████│████│████│████│    │    │    │    │
       │ Backend │ Frontend │Test│Polh│    │    │    │    │
───────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
Dashbd │    │    │████│████│████│    │    │    │    │    │
       │    │    │ Dev │ Dev │Test│    │    │    │    │    │
───────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
Export │    │    │    │    │████│████│████│    │    │    │
       │    │    │    │    │XLS │PDF │PPT │    │    │    │
───────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
Demo   │████│████│    │    │    │    │    │    │    │    │
       │Data│Narr│    │    │    │    │    │    │    │    │
───────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
Quick  │    │    │    │    │    │    │████│████│    │    │
Wins   │    │    │    │    │    │    │Hmap│Clud│    │    │
───────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┤
Perf   │    │    │    │    │    │    │    │    │████│████│
Opt    │    │    │    │    │    │    │    │    │Back│Fron│
───────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘

Legend: ████ = Active work
```

---

## 🎯 Recursos Necesarios

### Team Composition

| Rol | Dedicación | Semanas | Total Horas |
|-----|-----------|---------|-------------|
| **Backend Developer** | Full-time | 10 | 400h |
| **Frontend Developer** | Full-time | 10 | 400h |
| **Product Designer** | 50% | 6 | 120h |
| **QA Engineer** | 25% | 10 | 100h |
| **Product Manager** | 25% | 10 | 100h |

**Total:** ~1,120 horas-persona

### Budget Estimado (si outsourcing)

| Item | Costo |
|------|-------|
| Development | $50K - $70K |
| Design | $10K - $15K |
| QA | $5K - $8K |
| PM | $8K - $12K |
| **TOTAL** | **$73K - $105K** |

*(Asumiendo rates de $50-80/hora)*

### Infraestructura

| Servicio | Costo Mensual |
|----------|---------------|
| Hosting (AWS/GCP) | $100-200 |
| Database (managed) | $50-100 |
| CDN (assets) | $20-50 |
| Monitoring (Sentry) | $30 |
| **TOTAL** | **$200-380/mes** |

---

## ✅ Definition of Done (DoD)

Un feature se considera "Done" cuando:

**Code:**
- [ ] Code reviewed por al menos 1 persona
- [ ] Tests unitarios escritos (coverage >80%)
- [ ] Tests e2e para flujos críticos
- [ ] No linter errors ni warnings
- [ ] Documentado en `/docs`

**UX:**
- [ ] Diseño aprobado por Product Designer
- [ ] Responsive en desktop (1920x1080, 1366x768)
- [ ] Loading states implementados
- [ ] Error states implementados
- [ ] Accessibility básico (keyboard navigation)

**Performance:**
- [ ] Lighthouse score >90 (Performance)
- [ ] Queries <3 segundos (p95)
- [ ] No memory leaks (verificado con DevTools)

**QA:**
- [ ] Testeado en Chrome, Firefox, Safari
- [ ] Casos edge documentados y manejados
- [ ] Rollback plan definido

**Product:**
- [ ] Demo grabado (video 2-5 min)
- [ ] Release notes escritos
- [ ] Stakeholders notificados

---

## 📊 Métricas de Producto (KPIs)

### Adoption Metrics

| Métrica | Target | Cómo Medir |
|---------|--------|------------|
| **Weekly Active Users** | 100+ | Google Analytics |
| **Feature Adoption (OLAP)** | 80%+ | Mixpanel events |
| **Time to First Value** | <10 min | User onboarding funnel |
| **Demo Conversion** | 40%+ | Demo → Upload own data |

### Engagement Metrics

| Métrica | Target | Cómo Medir |
|---------|--------|------------|
| **Session Duration** | >15 min | Google Analytics |
| **Queries per Session** | 8+ | Backend logs |
| **Export Rate** | 70%+ | Export button clicks |
| **Return Rate (D7)** | 60%+ | Cohort analysis |

### Satisfaction Metrics

| Métrica | Target | Cómo Medir |
|---------|--------|------------|
| **NPS** | >50 | In-app survey |
| **Feature Satisfaction** | >8/10 | Post-feature survey |
| **Support Tickets** | <5/week | Zendesk |
| **Churn Rate** | <10% | User retention |

---

## 🚨 Riesgos y Mitigaciones

### Riesgo #1: OLAP Performance con >1M registros

**Probabilidad:** Media  
**Impacto:** Alto  
**Mitigación:**
- Implementar particionamiento por año
- Agregar materialización incremental
- Plan B: Migrar a ClickHouse si DuckDB no escala

### Riesgo #2: Scope Creep

**Probabilidad:** Alta  
**Impacto:** Medio  
**Mitigación:**
- Mantener MoSCoW strict
- Weekly product reviews
- Buffer de 2 semanas en timeline

### Riesgo #3: Dataset Demo no es creíble

**Probabilidad:** Media  
**Impacto:** Alto (afecta ventas)  
**Mitigación:**
- Validar con 2-3 académicos reales
- Usar datos parcialmente reales (anonimizados)
- A/B test narrativa con prospectos

### Riesgo #4: Team Availability

**Probabilidad:** Media  
**Impacto:** Alto  
**Mitigación:**
- Cross-training entre devs
- Documentación exhaustiva
- Milestones con buffers

---

## 📝 Preguntas para el Equipo (Discussion Guide)

### Para Product Manager:
1. ¿El orden de prioridades (OLAP → Dashboard → Export) refleja necesidades de stakeholders?
2. ¿Hay features críticos que faltan en este roadmap?
3. ¿El caso de uso demo es representativo de nuestro ICP (Ideal Customer Profile)?

### Para Diseño:
1. ¿Las wireframes propuestas son suficientemente detalladas?
2. ¿Necesitan más tiempo para explorar alternativas UI?
3. ¿Tenemos componentes reusables o empezamos from scratch?

### Para Desarrollo:
1. ¿Las estimaciones (200h OLAP, 100h Dashboard) son realistas?
2. ¿Hay dependencias técnicas que no están consideradas?
3. ¿Prefieren implementar features en paralelo o secuencial?

### Para Stakeholders/CEO:
1. ¿El timeline de 10 semanas es aceptable o necesitan faster?
2. ¿El budget estimado ($73K-$105K) está dentro de lo planeado?
3. ¿Hay alguna demo/evento que requiera adelantar features específicos?

---

## 🎯 Next Steps

### Inmediatos (Esta semana):
1. ✅ **Revisar este documento** con todo el equipo
2. ✅ **Priorizar discusiones** de las preguntas arriba
3. ✅ **Asignar owners** a cada feature
4. ✅ **Crear tickets** en Jira/Linear/GitHub Issues
5. ✅ **Setup tracking** (Mixpanel, Google Analytics)

### Semana 1:
1. ✅ Kickoff meeting (2 horas)
2. ✅ Comenzar Feature #1 (OLAP backend)
3. ✅ Comenzar Feature #4 (Dataset demo)
4. ✅ Design sprints para Dashboard

### Semana 2:
1. ✅ Primera demo interna (OLAP básico funcionando)
2. ✅ Feedback loop con stakeholders
3. ✅ Ajustar roadmap si necesario

---

## 📚 Apéndices

### Apéndice A: Referencias Técnicas
- [DuckDB OLAP Guide](https://duckdb.org/docs/sql/query_syntax/grouping_sets)
- [TanStack Table Docs](https://tanstack.com/table/v8)
- [Recharts Documentation](https://recharts.org/)
- [ReportLab User Guide](https://www.reportlab.com/docs/reportlab-userguide.pdf)

### Apéndice B: Competencia Benchmark

| Competitor | OLAP | Dashboard | Export | Demo | Precio |
|-----------|------|-----------|--------|------|--------|
| **Tableau** | ✅ | ✅ | ✅ | ✅ | $70/user/mo |
| **Power BI** | ✅ | ✅ | ✅ | ✅ | $10/user/mo |
| **Looker** | ✅ | ✅ | 🟡 | ✅ | Custom |
| **UKIP** | 🔵 | 🟡 | 🟡 | 🟡 | TBD |

🔵 = En desarrollo | 🟡 = Básico | ✅ = Completo

### Apéndice C: User Stories

**Epic:** OLAP Analytics

- **US-001:** Como analista, quiero seleccionar múltiples dimensiones para analizar datos desde diferentes perspectivas
- **US-002:** Como director, quiero drill-down en una región para ver instituciones específicas
- **US-003:** Como CFO, quiero exportar análisis a Excel para incluir en board deck
- **US-004:** Como investigador, quiero filtrar por año y tema para analizar tendencias temporales

*(Total: 47 user stories detalladas en backlog)*

---

**Última actualización:** 2026-03-06  
**Versión:** 1.0  
**Próxima revisión:** Semana 3 (mid-sprint check-in)

---

## ✅ Aprobaciones

| Rol | Nombre | Firma | Fecha |
|-----|--------|-------|-------|
| Product Manager | _______ | _______ | _______ |
| Tech Lead | _______ | _______ | _______ |
| Design Lead | _______ | _______ | _______ |
| CEO/Stakeholder | _______ | _______ | _______ |
