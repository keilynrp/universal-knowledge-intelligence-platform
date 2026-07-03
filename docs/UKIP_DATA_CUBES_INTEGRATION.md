# 📊 Integración de Data Cubes OLAP en UKIP

**Documento Complementario:** Arquitectura de Análisis Multidimensional  
**Proyecto:** Universal Knowledge Intelligence Platform (UKIP)  
**Complementa:** `EVOLUTION_STRATEGY.md` (Fase 8+)  
**Creado:** 2026-03-05  
**Estado:** Propuesta técnica — Pendiente implementación

---

## 🎯 Objetivo del Documento

Este documento articula cómo integrar **análisis multidimensional tipo OLAP** (Data Cubes) dentro de la arquitectura UKIP, manteniendo los principios de:

- ✅ **Justified Complexity** — Solo agregar componentes cuando aporten valor medible
- ✅ **Domain-Agnostic Design** — Funcionar para cualquier dominio sin reescritura
- ✅ **Open by Default** — Stack libre (DuckDB/Polars) antes que soluciones propietarias
- ✅ **Artifact-Driven** — Toda complejidad debe terminar en artefactos accionables

---

## 1. ¿Por qué Data Cubes en UKIP?

### 1.1 El Problema que Resuelve

Actualmente (Fase 5), UKIP permite:
- ✅ Consultar entidades individuales vía RAG
- ✅ Proyectar citaciones futuras con Monte Carlo
- ✅ Visualizar métricas agregadas simples (total productos, marcas únicas)

**Lo que falta:**
- ❌ Análisis comparativos multi-dimensionales ("¿Cómo varía el impacto por región, año y área temática?")
- ❌ Drill-down/Roll-up interactivo (de país → región → institución)
- ❌ Análisis "what-if" sobre escenarios presupuestarios
- ❌ Exportación de reportes dinámicos para stakeholders

### 1.2 Casos de Uso Concretos por Dominio

| Dominio | Pregunta de Negocio | Dimensiones del Cubo |
|---------|---------------------|---------------------|
| **🎓 Academia** | ¿En qué áreas geográficas y temáticas tenemos mayor impacto publicacional? | [Región, Área Temática, Año, Tipo Publicación] |
| **🏥 Salud** | ¿Cuál es el gasto en investigación por enfermedad vs. carga de mortalidad? | [Enfermedad, Región, Año, Tipo Financiamiento] |
| **🏢 Business Intel** | ¿Qué verticales de producto generan mayor ROI por canal de marketing? | [Producto, Canal, Región, Trimestre] |
| **🔬 Vigilancia Tech** | ¿Cuáles tecnologías patentadas crecen más por país y sector industrial? | [Tecnología, País, Sector, Año] |

---

## 2. Arquitectura Propuesta: OLAP Pragmático

### 2.1 Stack Tecnológico (Open by Default)

```yaml
Componente OLAP:
  Motor SQL OLAP: DuckDB  # Embedded, cero configuración, 100% compatible con SQL estándar
  Procesamiento: Polars   # DataFrames ultrarrápidos para transformaciones
  Persistencia: SQLite → UniversalEntity  # Backend existente
  Visualización: 
    - Backend API: FastAPI endpoints con SQL GROUP BY CUBE
    - Frontend: Recharts + shadcn/ui (ya existentes)
  Fallback Premium: 
    - ClickHouse (si >10M filas)  # BYOK cloud
    - Apache Druid (si streaming)  # BYOK cloud
```

**Justificación de DuckDB:**
- ✅ Cero instalación — archivo binario embebido
- ✅ SQL OLAP completo (`CUBE`, `ROLLUP`, `GROUPING SETS`)
- ✅ Lee directamente Parquet, CSV, JSON sin ETL
- ✅ Integración nativa con Polars/Pandas
- ✅ 100x más rápido que SQLite en agregaciones complejas
- ✅ Licencia MIT — completamente libre

### 2.2 Integración en la Arquitectura UKIP Existente

```
┌──────────────────────────────────────────────────┐
│  UKIP Frontend (Next.js)                        │
│  ┌─────────────────────────────────────────┐   │
│  │ Analytics Hub                           │   │
│  │  ├─ Quantitative Analysis               │   │
│  │  │   └─ OLAP Cube Explorer ← NUEVO     │   │
│  │  ├─ Predictive Dashboard                │   │
│  │  └─ Artifact Studio                     │   │
│  └─────────────────────────────────────────┘   │
└────────────────────┬─────────────────────────────┘
                     │
┌────────────────────┴─────────────────────────────┐
│  FastAPI Backend                                 │
│  ┌─────────────────────────────────────────┐    │
│  │ api/routers/analytics.py ← EXTENDER     │    │
│  │  └─ /cube/query                         │    │
│  │  └─ /cube/dimensions                    │    │
│  │  └─ /cube/export                        │    │
│  └─────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────┐    │
│  │ analyzers/quantitative/ ← NUEVO         │    │
│  │  └─ olap_engine.py                      │    │
│  │     - build_cube()                       │    │
│  │     - query_cube()                       │    │
│  │     - export_pivot()                     │    │
│  └─────────────────────────────────────────┘    │
└────────────────────┬─────────────────────────────┘
                     │
┌────────────────────┴─────────────────────────────┐
│  Data Layer                                      │
│  ┌─────────────────────────────────────────┐    │
│  │ SQLite: UniversalEntity (OLTP)          │    │
│  │   └─ Source of Truth                    │    │
│  └─────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────┐    │
│  │ DuckDB: OLAP Cubes (materialized views) │    │
│  │   └─ /data/cubes/                       │    │
│  │      ├─ science_impact.duckdb            │    │
│  │      ├─ market_intel.duckdb              │    │
│  │      └─ custom_{domain}.duckdb           │    │
│  └─────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

---

## 3. Diseño del Modelo de Datos: Esquema Estrella Flexible

### 3.1 Estructura Base (Star Schema)

```sql
-- Tabla de Hechos (Fact Table) — Generada automáticamente desde UniversalEntity
CREATE TABLE fact_entity_metrics AS
SELECT 
    e.id as entity_key,
    e.entity_type,
    e.domain,
    
    -- Dimensiones FK (se infieren del attributes_json)
    json_extract(e.attributes_json, '$.year') as time_key,
    json_extract(e.attributes_json, '$.region') as geo_key,
    json_extract(e.attributes_json, '$.topic') as topic_key,
    
    -- Métricas (medidas numéricas)
    CAST(json_extract(e.enrichment_data_json, '$.citation_count') AS INTEGER) as citation_count,
    CAST(json_extract(e.enrichment_data_json, '$.h_index') AS FLOAT) as h_index,
    e.data_quality_score as quality_score,
    1 as entity_count  -- Para COUNT(*)
    
FROM universal_entities e
WHERE e.enrichment_status = 'completed';

-- Tabla de Dimensión: Tiempo
CREATE TABLE dim_time AS
SELECT DISTINCT
    json_extract(attributes_json, '$.year') as year,
    EXTRACT(QUARTER FROM json_extract(attributes_json, '$.date')) as quarter,
    EXTRACT(MONTH FROM json_extract(attributes_json, '$.date')) as month
FROM universal_entities;

-- Tabla de Dimensión: Geografía (jerárquica)
CREATE TABLE dim_geography AS
SELECT DISTINCT
    json_extract(attributes_json, '$.country') as country,
    json_extract(attributes_json, '$.region') as region,
    json_extract(attributes_json, '$.institution') as institution
FROM universal_entities;

-- Tabla de Dimensión: Tema/Concepto
CREATE TABLE dim_topic AS
SELECT DISTINCT
    json_extract(enrichment_data_json, '$.concepts[0].id') as topic_id,
    json_extract(enrichment_data_json, '$.concepts[0].display_name') as topic_name,
    json_extract(enrichment_data_json, '$.concepts[0].level') as topic_level
FROM universal_entities
WHERE enrichment_status = 'completed';
```

### 3.2 Configuración Dinámica por Dominio

Cada dominio define su **Cube Schema** en YAML:

```yaml
# domains/science.yaml
cube_schema:
  name: "science_impact_cube"
  fact_table: "fact_entity_metrics"
  
  dimensions:
    - name: "time"
      type: "temporal"
      hierarchy: ["year", "quarter", "month"]
      source: "attributes_json.date"
      
    - name: "geography"
      type: "hierarchical"
      hierarchy: ["country", "region", "institution"]
      source: "attributes_json.affiliation"
      
    - name: "topic"
      type: "categorical"
      hierarchy: ["field", "subfield", "concept"]
      source: "enrichment_data_json.concepts"
      
    - name: "entity_type"
      type: "categorical"
      values: ["article", "review", "preprint", "book"]
      
  measures:
    - name: "citation_count"
      aggregation: "SUM"
      format: "integer"
      
    - name: "h_index"
      aggregation: "AVG"
      format: "decimal(2)"
      
    - name: "quality_score"
      aggregation: "AVG"
      format: "percentage"
      
    - name: "entity_count"
      aggregation: "COUNT"
      format: "integer"
```

---

## 4. Implementación del Motor OLAP

### 4.1 Módulo: `analyzers/quantitative/olap_engine.py`

```python
"""
OLAP Engine para UKIP - Análisis Multidimensional
Basado en DuckDB para máxima performance sin configuración.
"""

import duckdb
import polars as pl
from pathlib import Path
from typing import List, Dict, Any
import yaml


class OLAPEngine:
    """Motor de análisis OLAP sobre UniversalEntity."""
    
    def __init__(self, domain: str = "science"):
        self.domain = domain
        self.db_path = Path(f"data/cubes/{domain}_cube.duckdb")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(self.db_path))
        
        # Cargar configuración del dominio
        config_path = Path(f"domains/{domain}.yaml")
        with open(config_path) as f:
            self.config = yaml.safe_load(f)["cube_schema"]
    
    def build_cube(self, sqlite_path: str = "data/database.db"):
        """
        Materializa el cubo desde SQLite UniversalEntity.
        Solo se ejecuta cuando hay nuevos datos enriquecidos.
        """
        # 1. Conectar a SQLite source
        self.con.execute(f"ATTACH '{sqlite_path}' AS source (TYPE SQLITE)")
        
        # 2. Crear tabla de hechos
        fact_sql = self._generate_fact_table_sql()
        self.con.execute(f"CREATE OR REPLACE TABLE fact_metrics AS {fact_sql}")
        
        # 3. Crear tablas de dimensiones
        for dim in self.config["dimensions"]:
            dim_sql = self._generate_dimension_table_sql(dim)
            self.con.execute(dim_sql)
        
        # 4. Indexar dimensiones para joins rápidos
        self._create_indexes()
        
        print(f"✅ Cubo {self.domain} materializado exitosamente")
    
    def query_cube(self, 
                   dimensions: List[str],
                   measures: List[str],
                   filters: Dict[str, Any] = None,
                   rollup: bool = False) -> pl.DataFrame:
        """
        Ejecuta query OLAP con soporte para CUBE/ROLLUP.
        
        Ejemplo:
            query_cube(
                dimensions=["year", "country", "topic"],
                measures=["SUM(citation_count)", "COUNT(*)"],
                filters={"year": [2023, 2024]},
                rollup=True
            )
        """
        # Construir SELECT
        select_clause = ", ".join(dimensions + measures)
        
        # Construir WHERE
        where_clause = self._build_where_clause(filters) if filters else "1=1"
        
        # Decidir GROUP BY CUBE o ROLLUP
        group_clause = f"GROUP BY {'ROLLUP' if rollup else 'CUBE'}({', '.join(dimensions)})"
        
        sql = f"""
        SELECT {select_clause}
        FROM fact_metrics f
        WHERE {where_clause}
        {group_clause}
        ORDER BY {dimensions[0]} DESC
        """
        
        # Ejecutar y retornar como Polars DataFrame
        result = self.con.execute(sql).pl()
        return result
    
    def export_pivot(self, 
                     rows: List[str], 
                     columns: str, 
                     values: str,
                     aggfunc: str = "SUM") -> pl.DataFrame:
        """
        Genera tabla pivoteada para exportación a Excel/CSV.
        
        Ejemplo:
            export_pivot(
                rows=["country", "institution"],
                columns="year",
                values="citation_count",
                aggfunc="SUM"
            )
        """
        # DuckDB PIVOT syntax
        row_clause = ", ".join(rows)
        
        sql = f"""
        PIVOT fact_metrics
        ON {columns}
        USING {aggfunc}({values})
        GROUP BY {row_clause}
        """
        
        return self.con.execute(sql).pl()
    
    def drill_down(self, dimension: str, parent_value: str) -> pl.DataFrame:
        """
        Drill-down en una dimensión jerárquica.
        
        Ejemplo: drill_down("geography", "Mexico") → regiones de México
        """
        dim_config = next(d for d in self.config["dimensions"] if d["name"] == dimension)
        hierarchy = dim_config["hierarchy"]
        
        # Encontrar nivel actual del parent_value
        current_level_idx = self._find_hierarchy_level(dimension, parent_value)
        next_level = hierarchy[current_level_idx + 1]
        
        sql = f"""
        SELECT DISTINCT {next_level}
        FROM dim_{dimension}
        WHERE {hierarchy[current_level_idx]} = '{parent_value}'
        """
        
        return self.con.execute(sql).pl()
    
    # === Métodos Privados ===
    
    def _generate_fact_table_sql(self) -> str:
        """Genera SQL para construir fact table desde UniversalEntity."""
        measures_sql = []
        for measure in self.config["measures"]:
            source = measure.get("source", f"enrichment_data_json.{measure['name']}")
            measures_sql.append(
                f"CAST(json_extract(enrichment_data_json, '$.{measure['name']}') AS NUMERIC) as {measure['name']}"
            )
        
        dimensions_sql = []
        for dim in self.config["dimensions"]:
            source_path = dim["source"].replace(".", "_")
            dimensions_sql.append(
                f"json_extract({dim['source'].split('.')[0]}, '$.{dim['source'].split('.')[1]}') as {dim['name']}_key"
            )
        
        return f"""
        SELECT 
            e.id as entity_key,
            e.domain,
            {', '.join(dimensions_sql)},
            {', '.join(measures_sql)}
        FROM source.universal_entities e
        WHERE e.enrichment_status = 'completed'
          AND e.domain = '{self.domain}'
        """
    
    def _generate_dimension_table_sql(self, dim_config: Dict) -> str:
        """Genera SQL para crear tabla de dimensión."""
        if dim_config["type"] == "hierarchical":
            hierarchy_cols = ", ".join(dim_config["hierarchy"])
            return f"""
            CREATE OR REPLACE TABLE dim_{dim_config['name']} AS
            SELECT DISTINCT {hierarchy_cols}
            FROM fact_metrics
            """
        elif dim_config["type"] == "temporal":
            return f"""
            CREATE OR REPLACE TABLE dim_{dim_config['name']} AS
            SELECT DISTINCT
                EXTRACT(YEAR FROM {dim_config['hierarchy'][0]}) as year,
                EXTRACT(QUARTER FROM {dim_config['hierarchy'][0]}) as quarter,
                EXTRACT(MONTH FROM {dim_config['hierarchy'][0]}) as month
            FROM fact_metrics
            """
        else:  # categorical
            return f"""
            CREATE OR REPLACE TABLE dim_{dim_config['name']} AS
            SELECT DISTINCT {dim_config['name']}
            FROM fact_metrics
            """
    
    def _create_indexes(self):
        """Crea índices en dimensiones para joins rápidos."""
        for dim in self.config["dimensions"]:
            self.con.execute(f"CREATE INDEX IF NOT EXISTS idx_{dim['name']} ON dim_{dim['name']}({dim['hierarchy'][0]})")
    
    def _build_where_clause(self, filters: Dict[str, Any]) -> str:
        """Convierte filtros dict a SQL WHERE."""
        conditions = []
        for key, value in filters.items():
            if isinstance(value, list):
                conditions.append(f"{key} IN ({', '.join(map(str, value))})")
            else:
                conditions.append(f"{key} = {value}")
        return " AND ".join(conditions)
    
    def _find_hierarchy_level(self, dimension: str, value: str) -> int:
        """Encuentra el índice del nivel jerárquico de un valor."""
        dim_config = next(d for d in self.config["dimensions"] if d["name"] == dimension)
        hierarchy = dim_config["hierarchy"]
        
        for idx, level in enumerate(hierarchy):
            result = self.con.execute(f"SELECT COUNT(*) FROM dim_{dimension} WHERE {level} = '{value}'").fetchone()
            if result[0] > 0:
                return idx
        return 0


# === Funciones de utilidad ===

def refresh_all_cubes():
    """Refresca todos los cubos de dominios activos."""
    domains = ["science", "healthcare", "business"]  # Cargar dinámicamente
    
    for domain in domains:
        try:
            engine = OLAPEngine(domain)
            engine.build_cube()
        except Exception as e:
            print(f"❌ Error refrescando cubo {domain}: {e}")


def export_cube_to_excel(engine: OLAPEngine, filepath: str):
    """Exporta cubo completo a Excel con múltiples hojas."""
    import xlsxwriter
    
    workbook = xlsxwriter.Workbook(filepath)
    
    # Hoja 1: Datos agregados
    df_summary = engine.query_cube(
        dimensions=["year", "topic"],
        measures=["SUM(citation_count)", "COUNT(*)"]
    )
    
    worksheet = workbook.add_worksheet("Summary")
    df_summary.write_excel(workbook, worksheet)
    
    # Hoja 2: Pivot por geografía
    df_geo = engine.export_pivot(
        rows=["country"],
        columns="year",
        values="citation_count"
    )
    
    worksheet = workbook.add_worksheet("Geographic Pivot")
    df_geo.write_excel(workbook, worksheet)
    
    workbook.close()
```

### 4.2 API Endpoints: `api/routers/analytics.py`

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from analyzers.quantitative.olap_engine import OLAPEngine

router = APIRouter(prefix="/cube", tags=["OLAP Analytics"])


class CubeQueryRequest(BaseModel):
    domain: str = "science"
    dimensions: List[str]
    measures: List[str]
    filters: Optional[Dict[str, Any]] = None
    rollup: bool = False


class DrillDownRequest(BaseModel):
    domain: str = "science"
    dimension: str
    parent_value: str


@router.post("/query")
async def query_cube(request: CubeQueryRequest):
    """
    Ejecuta query OLAP multidimensional.
    
    Ejemplo:
        POST /cube/query
        {
            "domain": "science",
            "dimensions": ["year", "country"],
            "measures": ["SUM(citation_count)", "AVG(h_index)"],
            "filters": {"year": [2023, 2024]},
            "rollup": true
        }
    """
    try:
        engine = OLAPEngine(request.domain)
        df = engine.query_cube(
            dimensions=request.dimensions,
            measures=request.measures,
            filters=request.filters,
            rollup=request.rollup
        )
        
        return {
            "data": df.to_dicts(),
            "row_count": len(df),
            "dimensions": request.dimensions,
            "measures": request.measures
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dimensions/{domain}")
async def get_available_dimensions(domain: str):
    """Retorna dimensiones y medidas disponibles para un dominio."""
    engine = OLAPEngine(domain)
    return {
        "domain": domain,
        "dimensions": engine.config["dimensions"],
        "measures": engine.config["measures"]
    }


@router.post("/drill-down")
async def drill_down_dimension(request: DrillDownRequest):
    """
    Drill-down en una dimensión jerárquica.
    
    Ejemplo:
        POST /cube/drill-down
        {
            "domain": "science",
            "dimension": "geography",
            "parent_value": "Mexico"
        }
    """
    engine = OLAPEngine(request.domain)
    df = engine.drill_down(request.dimension, request.parent_value)
    
    return {
        "dimension": request.dimension,
        "parent": request.parent_value,
        "children": df.to_dicts()
    }


@router.post("/export/pivot")
async def export_pivot_table(
    domain: str,
    rows: List[str],
    columns: str,
    values: str,
    aggfunc: str = "SUM"
):
    """Genera tabla pivoteada para descarga."""
    engine = OLAPEngine(domain)
    df = engine.export_pivot(rows, columns, values, aggfunc)
    
    return {
        "data": df.to_dicts(),
        "pivot_config": {
            "rows": rows,
            "columns": columns,
            "values": values,
            "aggregation": aggfunc
        }
    }


@router.post("/refresh/{domain}")
async def refresh_cube(domain: str):
    """Refresca (reconstruye) el cubo OLAP para un dominio."""
    try:
        engine = OLAPEngine(domain)
        engine.build_cube()
        return {"status": "success", "domain": domain}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 5. Componente Frontend: OLAP Cube Explorer

### 5.1 Ubicación en la UI

```
Analytics Hub
└── Quantitative Analysis
    ├── Monte Carlo Projections (ya existe)
    └── OLAP Cube Explorer ← NUEVO
        ├── Dimension Selector (multi-select)
        ├── Measure Selector (checkboxes)
        ├── Filter Panel (dynamic)
        ├── Results Grid (ag-grid o TanStack Table)
        └── Export Options (Excel, CSV, JSON)
```

### 5.2 Wireframe de Interacción

```
┌─────────────────────────────────────────────────────────────┐
│  📊 OLAP Cube Explorer — Science Impact Analysis            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Domain: [Science ▼]                    [Refresh Cube]      │
│                                                              │
│  ┌─ Dimensions ────────────────┐  ┌─ Measures ──────────┐  │
│  │ ☑ Year                      │  │ ☑ Citation Count    │  │
│  │ ☑ Country                   │  │ ☑ H-Index           │  │
│  │ ☐ Institution               │  │ ☐ Quality Score     │  │
│  │ ☑ Topic                     │  │ ☑ Entity Count      │  │
│  │ ☐ Entity Type               │  └──────────────────────┘  │
│  └──────────────────────────────┘                           │
│                                                              │
│  ┌─ Filters ───────────────────────────────────────────┐    │
│  │ Year: [2020] to [2024]                             │    │
│  │ Country: [Mexico, Colombia, Argentina] ▼           │    │
│  │ Topic: [All]                                       │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Analysis Type: ○ CUBE  ● ROLLUP                            │
│                                                              │
│  [Run Query]  [Export to Excel]  [Save as Template]         │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│  Results (245 rows)                                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Year │ Country  │ Topic      │ Citations │ Count    │   │
│  ├──────┼──────────┼────────────┼───────────┼──────────┤   │
│  │ 2024 │ Mexico   │ AI/ML      │ 1,234     │ 45       │   │
│  │ 2024 │ Mexico   │ Biotech    │ 892       │ 23       │   │
│  │ 2024 │ Colombia │ AI/ML      │ 567       │ 12       │   │
│  │ 2023 │ Mexico   │ AI/ML      │ 2,103     │ 78       │   │
│  │ ...  │          │            │           │          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  💡 Click on any row to drill-down into details             │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 Ejemplo de Código React (con shadcn/ui)

```typescript
// app/analytics/olap/page.tsx

'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Select } from '@/components/ui/select';
import { DataTable } from '@/components/ui/data-table';

export default function OLAPCubeExplorer() {
  const [domain, setDomain] = useState('science');
  const [selectedDims, setSelectedDims] = useState(['year', 'country']);
  const [selectedMeasures, setSelectedMeasures] = useState(['citation_count']);
  const [filters, setFilters] = useState({});
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const runQuery = async () => {
    setLoading(true);
    const response = await fetch('/api/cube/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        domain,
        dimensions: selectedDims,
        measures: selectedMeasures.map(m => `SUM(${m})`),
        filters,
        rollup: true
      })
    });
    
    const data = await response.json();
    setResults(data.data);
    setLoading(false);
  };

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">OLAP Cube Explorer</h1>
      
      {/* Domain Selector */}
      <Select value={domain} onValueChange={setDomain}>
        <option value="science">Science Impact</option>
        <option value="healthcare">Healthcare Research</option>
        <option value="business">Business Intelligence</option>
      </Select>

      {/* Dimensions & Measures */}
      <div className="grid grid-cols-2 gap-4 my-4">
        <div className="border p-4 rounded">
          <h3 className="font-semibold mb-2">Dimensions</h3>
          {['year', 'country', 'institution', 'topic'].map(dim => (
            <div key={dim} className="flex items-center space-x-2">
              <Checkbox 
                checked={selectedDims.includes(dim)}
                onCheckedChange={(checked) => {
                  if (checked) setSelectedDims([...selectedDims, dim]);
                  else setSelectedDims(selectedDims.filter(d => d !== dim));
                }}
              />
              <label>{dim}</label>
            </div>
          ))}
        </div>
        
        <div className="border p-4 rounded">
          <h3 className="font-semibold mb-2">Measures</h3>
          {['citation_count', 'h_index', 'quality_score'].map(measure => (
            <div key={measure} className="flex items-center space-x-2">
              <Checkbox 
                checked={selectedMeasures.includes(measure)}
                onCheckedChange={(checked) => {
                  if (checked) setSelectedMeasures([...selectedMeasures, measure]);
                  else setSelectedMeasures(selectedMeasures.filter(m => m !== measure));
                }}
              />
              <label>{measure}</label>
            </div>
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-2 mb-4">
        <Button onClick={runQuery} disabled={loading}>
          {loading ? 'Running...' : 'Run Query'}
        </Button>
        <Button variant="outline">Export to Excel</Button>
      </div>

      {/* Results Table */}
      <DataTable data={results} columns={selectedDims.concat(selectedMeasures)} />
    </div>
  );
}
```

---

## 6. Integración en el Roadmap UKIP

### 6.1 Ubicación en las Fases de Evolución

| Fase Original | Nueva Integración OLAP |
|--------------|------------------------|
| ✅ Fase 1-5 | Ya implementado (base) |
| 🔵 Fase 6 | Refactorización UI → Incluir "OLAP Cube Explorer" en Analytics Hub |
| 🔵 Fase 7 | Domain Schema Registry → **Incluir cube_schema en cada domain.yaml** |
| ⬜ **Fase 8+** | **Implementación completa de OLAP Engine** |
|  | • Migrar a UniversalEntity con campos JSON flexibles |
|  | • Implementar `olap_engine.py` |
|  | • Crear endpoints `/cube/*` |
|  | • Diseñar componente frontend OLAPCubeExplorer |
| ⬜ Fase 9 | Analyzers Avanzados → **Integrar Topic Modeling en dimensión automática** |
| ⬜ Fase 10 | Artifact Studio → **Reportes exportan directamente desde cubos OLAP** |

### 6.2 Dependencias Técnicas

```yaml
Requisitos previos:
  - ✅ UniversalEntity con attributes_json flexible (Fase 8)
  - ✅ Domain Schema Registry (Fase 7)
  - ✅ Enriquecimiento completo (Fases 1-5)

Implementación OLAP:
  Backend:
    - Instalar: pip install duckdb polars xlsxwriter
    - Crear: analyzers/quantitative/olap_engine.py
    - Extender: api/routers/analytics.py
    - Configurar: domains/*.yaml (agregar cube_schema)
  
  Frontend:
    - Crear: app/analytics/olap/page.tsx
    - Componentes: OLAPCubeExplorer, DimensionSelector, FilterPanel
    - Librerías: shadcn/ui DataTable, Recharts para viz
```

---

## 7. Casos de Uso Completos con OLAP

### 7.1 Caso Academia: Análisis de Impacto Regional

**Pregunta:** ¿Qué países de LATAM tienen mayor impacto cienciométrico en AI/ML?

**Flujo:**
```python
# 1. Usuario configura query en UI
dimensions = ["country", "year", "topic"]
measures = ["SUM(citation_count)", "AVG(h_index)", "COUNT(*)"]
filters = {"topic": "AI/ML", "country": ["Mexico", "Brazil", "Chile", "Argentina"]}

# 2. Backend ejecuta
engine = OLAPEngine("science")
df = engine.query_cube(dimensions, measures, filters, rollup=True)

# 3. Frontend renderiza tabla + gráfico de barras (Recharts)
# 4. Usuario hace drill-down en "Mexico" → ve instituciones mexicanas
# 5. Exporta a Excel para presentar a comité de I+D
```

**Artefacto generado:** Excel con 3 hojas:
- Summary: Agregados por país y año
- DrillDown_Mexico: Instituciones mexicanas detalladas
- Visualization: Gráfico de barras comparativo

### 7.2 Caso Vigilancia Tecnológica: Radar de Patentes

**Pregunta:** ¿Qué tecnologías patentadas crecen más rápido por sector?

**Flujo:**
```python
dimensions = ["technology_class", "year", "country"]
measures = ["COUNT(*)", "AVG(forward_citations)"]
filters = {"year": [2020, 2021, 2022, 2023, 2024]}

df = engine.query_cube(dimensions, measures, filters)

# Calcular tasa de crecimiento YoY
df = df.with_columns([
    (pl.col("count") / pl.col("count").shift(1) - 1).alias("growth_rate")
])

# TOP 10 tecnologías con mayor crecimiento
top_tech = df.sort("growth_rate", descending=True).head(10)
```

**Artefacto:** Dashboard interactivo con heatmap de crecimiento por tecnología/año

### 7.3 Caso Consultoría: ROI de Portafolio de I+D

**Pregunta:** ¿Qué proyectos financiados generan mayor retorno por dólar invertido?

**Flujo:**
```python
dimensions = ["project_id", "funding_source", "year"]
measures = ["SUM(citations)", "SUM(patent_count)", "SUM(funding_amount)"]

df = engine.query_cube(dimensions, measures)

# Calcular ROI custom
df = df.with_columns([
    (pl.col("SUM(citations)") * 1000 + pl.col("SUM(patent_count)") * 50000) 
    / pl.col("SUM(funding_amount)")
    .alias("roi_index")
])

# Ranking de proyectos por ROI
ranking = df.sort("roi_index", descending=True)
```

**Artefacto:** Scorecard PDF con recomendaciones de renovación/cancelación de proyectos

---

## 8. Ventajas Competitivas del Enfoque UKIP

| Aspecto | Soluciones tradicionales | UKIP + OLAP |
|---------|-------------------------|-------------|
| **Setup** | Semanas de configuración (Tableau, Power BI) | Minutos — cero configuración |
| **Costo** | $70-150 USD/usuario/mes | $0 (DuckDB + Polars) |
| **Dominio** | Genéricos, requieren customización | Domain-aware desde diseño |
| **Enriquecimiento** | Manual o ETL externo | Automático con adaptadores |
| **Predictivo** | Separado, requiere Python/R | Integrado (Monte Carlo, Time Series) |
| **RAG/AI** | No incluido | Nativo — consultas en lenguaje natural |
| **Exportabilidad** | Limitada a formatos propietarios | Excel, CSV, JSON, Parquet, SQL |
| **Reproducibilidad** | Depende de licencias | 100% código abierto, versionable |

---

## 9. Consideraciones de Performance y Escala

### 9.1 Límites de DuckDB (Guía de Escalamiento)

| Escenario | Volumen de Datos | Solución |
|-----------|------------------|----------|
| **MVP/PoC** | <1M entidades | DuckDB embedded (actual propuesta) |
| **Producción Pequeña** | 1M-10M entidades | DuckDB + particionamiento por año/dominio |
| **Producción Mediana** | 10M-100M entidades | Migrar a ClickHouse (BYOK cloud) |
| **Producción Grande** | >100M entidades | Apache Druid o Snowflake (BYOK) |

### 9.2 Estrategia de Materialización

```python
# Refrescar cubos de manera incremental
class IncrementalCubeRefresh:
    def refresh(self, last_updated_at: datetime):
        """Solo procesa entidades nuevas desde last_updated_at."""
        sql = f"""
        INSERT INTO fact_metrics
        SELECT ... FROM universal_entities
        WHERE enrichment_status = 'completed'
          AND last_modified > '{last_updated_at}'
        """
        self.con.execute(sql)

# Programar refresh cada noche (cron o Celery Beat)
# 0 2 * * * python scripts/refresh_cubes.py
```

---

## 10. Hoja de Ruta de Implementación

### Fase 8.1: Fundamentos OLAP (Semana 1-2)

- [ ] Instalar dependencias: `pip install duckdb polars xlsxwriter`
- [ ] Crear `analyzers/quantitative/olap_engine.py` (versión básica)
- [ ] Agregar `cube_schema` a `domains/science.yaml`
- [ ] Implementar `build_cube()` con query hardcodeado
- [ ] Test manual con query simple en Jupyter

### Fase 8.2: API Endpoints (Semana 3)

- [ ] Crear `api/routers/analytics.py` con `/cube/query`
- [ ] Implementar `/cube/dimensions` (metadata)
- [ ] Agregar validación de requests con Pydantic
- [ ] Documentar en Swagger con ejemplos
- [ ] Test con Postman/curl

### Fase 8.3: Frontend Básico (Semana 4)

- [ ] Crear `app/analytics/olap/page.tsx`
- [ ] Implementar DimensionSelector (checkboxes)
- [ ] Implementar MeasureSelector
- [ ] Conectar a API `/cube/query`
- [ ] Renderizar resultados en tabla simple (shadcn DataTable)

### Fase 8.4: Features Avanzados (Semana 5-6)

- [ ] Implementar drill-down/roll-up
- [ ] Agregar export a Excel con múltiples hojas
- [ ] Visualización básica con Recharts (bar chart)
- [ ] Filter Panel dinámico basado en dimensiones
- [ ] Guardar queries como "templates"

### Fase 8.5: Integración Multi-Dominio (Semana 7-8)

- [ ] Crear `domains/healthcare.yaml` con cube_schema
- [ ] Crear `domains/business.yaml`
- [ ] Validar que el mismo código funciona para N dominios
- [ ] Documentar en `docs/OLAP_USER_GUIDE.md`

---

## 11. Checklist de Validación de Viabilidad

Antes de implementar, verificar:

- [x] ✅ **UniversalEntity existe** — Schema flexible con attributes_json
- [x] ✅ **Domain Schema Registry funcional** — domains/*.yaml configurables
- [x] ✅ **Enriquecimiento funciona** — Tenemos datos para analizar
- [x] ✅ **FastAPI backend operativo** — API lista para extender
- [x] ✅ **Frontend Next.js estable** — UI lista para nuevo módulo
- [ ] ⬜ **DuckDB instalado** — Pendiente `pip install duckdb`
- [ ] ⬜ **Polars instalado** — Pendiente `pip install polars`

**Estado:** 5/7 requisitos cumplidos — **Viable para implementación inmediata**

---

## 11-bis. Guía de dimensionalidad y rendimiento (implementación actual)

> Refleja el motor ya en producción (`backend/olap.py`, `query_cube`). No es
> teoría: es cómo conviene usar el cubo tal como está construido hoy.

**El cubo topa en 2 dimensiones `group_by` a propósito.** El límite lo dicta la
**calidad del resultado**, no la CPU: sobre DuckDB in-memory, agrupar por 2-3
columnas es trivial (microsegundos sobre decenas de miles de filas).

| Dimensiones | Recomendación |
|-------------|---------------|
| **1** | Ideal para dims de alta cardinalidad (`keywords`, `institution`, `journal`, `authors`) como dimensión primaria. |
| **2** | Sweet spot interactivo (cross-tab). Preferir que al menos una sea de baja cardinalidad. |
| **3** | Solo para export/análisis, nunca en pantalla; y solo dims de baja cardinalidad. |
| **4+** | No aconsejable en el cubo genérico — usar una consulta analítica/materializada dedicada. |

**Lo que se degrada al subir dimensiones (no es CPU):**

1. **Dispersión + truncado.** La malla resultante puede llegar a C₁×C₂×… celdas
   pero se corta en `LIMIT 200`. Cruzar dims de alta cardinalidad produce una
   malla enorme con casi todo `count=1`, cuya cola larga se descarta en silencio
   → los porcentajes engañan.
2. **Legibilidad.** Más de 2 dims deja de ser una tabla pivote interpretable.
3. **Explosión multi-valor.** Las dims `multi_valued` (keywords, institution) ya
   multiplican filas vía `UNNEST`; por eso cruzar **dos** multi-valor está
   **bloqueado** (ambiguo y costoso).

**Regla práctica de cardinalidad:**
- Cruza dims de **baja** cardinalidad: `year`, `work_type`, `validation_status`, `paradigm`.
- Usa las de **alta** cardinalidad como dimensión primaria única o como **filtro** (drill-down).
- Patrón ideal para multi-valor: `keywords × year` (un multi-valor × una baja cardinalidad).

**El verdadero cuello de botella de escalabilidad** no es el número de
dimensiones sino el `read_sql_table("raw_entities")` + parseo de JSON por fila en
**cada** consulta (O(filas), independiente de la aridad). Si el corpus crece a
cientos de miles, optimizar eso (cachear el DataFrame proyectado o empujar la
agregación a la base) es lo que importa — mucho antes que subir el cap de 2.

---

## 12. Conclusión y Próximos Pasos

### Resumen Ejecutivo

La integración de **Data Cubes OLAP** en UKIP es:

✅ **Técnicamente viable** — Stack ya preparado, dependencias mínimas  
✅ **Arquitectónicamente coherente** — Se alinea con Domain-Agnostic Design  
✅ **Sin over-engineering** — DuckDB es pragmático, no requiere infraestructura  
✅ **Alto ROI inmediato** — Casos de uso claros con artefactos accionables  

### Acción Recomendada

**Implementar en Fase 8 (después de migración a UniversalEntity)**

Orden sugerido:
1. Completar Fase 7 (Schema Registry) — **1-2 semanas**
2. Implementar OLAP Engine básico (Fase 8.1-8.2) — **2 semanas**
3. Frontend minimal (Fase 8.3) — **1 semana**
4. Iterar con features avanzados según feedback — **2-3 semanas**

**Timeline total estimado:** 6-8 semanas para OLAP funcional en producción

---

## Anexo A: Glosario OLAP

| Término | Definición |
|---------|-----------|
| **Fact Table** | Tabla central con métricas numéricas (hechos) |
| **Dimension Table** | Tablas con atributos descriptivos (quién, qué, cuándo, dónde) |
| **Measure** | Valor numérico agregable (SUM, AVG, COUNT) |
| **CUBE** | Operación que genera todos los subtotales posibles |
| **ROLLUP** | Operación que genera subtotales jerárquicos |
| **Drill-Down** | Navegar de nivel agregado a detallado |
| **Roll-Up** | Navegar de detallado a agregado |
| **Slice** | Filtrar el cubo por un valor de dimensión |
| **Dice** | Filtrar por múltiples dimensiones simultáneamente |
| **Pivot** | Rotar dimensiones (filas ↔ columnas) |

---

## Anexo B: Referencias Técnicas

- [DuckDB Documentation](https://duckdb.org/docs/)
- [DuckDB OLAP Features](https://duckdb.org/docs/sql/query_syntax/grouping_sets)
- [Polars User Guide](https://pola-rs.github.io/polars-book/)
- [Kimball Dimensional Modeling](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/)

---

**Historial de Cambios**

| Fecha | Versión | Descripción |
|-------|---------|-------------|
| 2026-03-05 | v1.0 | Documento inicial — Propuesta de integración OLAP en UKIP |

---

**Mantenimiento del Documento**

Este documento debe actualizarse cuando:
- Se implementen fases OLAP (actualizar checklist ✅)
- Se agreguen nuevos dominios con cube_schema
- Se encuentren limitaciones de performance (actualizar sección 9)
- Aparezcan nuevos casos de uso (actualizar sección 7)
