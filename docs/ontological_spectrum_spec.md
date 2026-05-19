# UKIP Ontological Spectrum & External Benchmarking - Technical Specification

> [!NOTE]
> Este documento establece la arquitectura conceptual profunda para la integración y armonización de metadatos cienciométricos duros con ontologías y reglas de catalogación establecidas de las Ciencias de la Información, formando lo que denominaremos el **Espectro Ontológico de UKIP**.

## 1. Contexto Estratégico

El motor de extracción de UKIP continuará su transición desde un modelo relacional y de datos planos (orientado puramente a "papers y métricas de citación") hacia un verdadero **Grafo de Conocimiento Universal Semántico (Linked Open Data)**. Esta evolución es el puente crítico e ineludible para implementar capacidades comerciales de alto impacto prescriptivo, primordialmente el submódulo de **Native External Benchmarking**. 

Esta feature exige pre-calcular matemáticamente si la trayectoria de un investigador aprueba los complejos regímenes de agencias como el SNI (México), el REF (Reino Unido) o la ANECA (España). Para que un motor así garantice la infalibilidad y carezca de sesgo durante una auditoría institucional, las métricas no deben leerse como texto plano, sino estar vinculadas con rigor a reglas de catalogación estandarizadas a nivel global bibliotecario. 

## 2. Pila Arquitectónica: El Espectro Ontológico

El modelo de datos y el motor ingestor de UKIP se estructurarán interconectando tres grandes ejes semánticos:

### Capa I: Identidad Biunívoca y Resolución de Autoridades
El objetivo de mitigación consiste en aniquilar el ruido en torno a nombres de autoría ambiguos, usando identificadores globales robustos y saliendo de la dependencia exclusiva de correos electrónicos.

*   **ORCID (Open Researcher and Contributor ID):** Eje y espina dorsal de la trazabilidad contemporánea.
*   **VIAF (Virtual International Authority File):** Implementación técnica para la alineación del registro del investigador frente a las bases de datos de todas las bibliotecas nacionales del mundo (unificación histórica).
*   **Library of Congress Name Authority File (LCNAF):** Integración estricta para resolver disputas de identidad históricas o de nombres muy comunes con una precisión de clase forense.
*   **Europeana:** Ampliación del espectro para cobijar identidades, creadores y catalogadores enfocados en Humanidades y las Bellas Artes, quienes no suelen tener visibilidad en APIs científicas duras (como PubMed o arXiv).

> [!IMPORTANT]  
> En el diseño de base de datos de UKIP, todos los perfiles (`Nodos Autor`) deben forzosamente tratarse mediante un "Resolutor de Autoridad" que fusione los datos dispares contra estas URIs globales antes de alimentar la base local o vectorial.

### Capa II: Modelado Bibliográfico Categórico (LRM / RDA / BIBFRAME)
UKIP abandonará las estructuras donde "todo archivo o URL es tratado igual" para abrazar el rigor del canon bibliográfico moderno.

*   **BIBFRAME y LRM (Library Reference Model):** Se inyectan las jerarquías orgánicas a las obras científicas (Modelo WEMI):
    *   **Work (Obra):** El núcleo intelectual o conceptual abstracto.
    *   **Expression (Expresión):** La realización alfanumérica/lenguaje (Ej. La traducción al mandarín de un artículo inglés).
    *   **Manifestation (Manifestación):** La edición del formato como producto tangible (Ej. Libro de imprenta 2026 vs Web Preprint).
    *   **Item (Ítem):** El ejemplar electrónico alojado y subido privadamente en un repositorio.

> [!CAUTION]
> **Calibración Antifraude del Benchmarking:** Las agencias de financiamiento califican de forma draconiana el peso del conocimiento. Múltiples benchmarks otorgan "Puntaje Nivel A" a una obra original, pero "Puntaje Nivel C" a una traducción técnica de la misma. Al implementar enlaces estructurales RDF (como la relación semántica `bf:translationOf`), UKIP calibra el dictamen crediticio de forma autónoma y erradica el conteo doble en los expedientes de evaluación institucional.

### Capa III: Topología Semántica de Dominios
Para cualificar fielmente el tamaño del impacto de un perfil y generar descubrimientos de red (Networking).

*   **Library of Congress Subject Headings (LCSH):** Dicta la normalización suprema de los campos de conocimiento. Unificará etiquetas caóticas de importación como "A.I.", "A.I", y "Inteligencia Artificial" bajo un solo macro-nodo de conocimiento inmutable, posibilitando búsquedas entre silos multidisciplinarios y mapas de cruce perfectos.

## 3. Arquitectura del Motor de Evaluación (El Benchmarking Engine)

Al montar las bases del Espectro Ontológico, el **Native Benchmark Framework** debe modelarse tecnológicamente evaluando triplas lógicas programables:

### Capa de Inferencia Predictiva (Simulación Semántica)
El motor escudriña el catálogo entero del usuario modelando las aserciones semánticas:
1.  **Sujeto:** Dr. X (Validación Cruzada `URI:ORCID` + `URI:VIAF`).
2.  **Relación / Predicado Bibliográfico:** Publicó Autoría Principal Primaria (Validación de Obra `BIBFRAME:Work`).
3.  **Ontología Categórica:** Sobre Sub-Especialidad Y (Enlace a `URI:LCSH`).
4.  **Disparador del Framenwork (Trigger):** Evaluación cruzada de reglas dinámicas insertadas (Regla SNI/REF 2026-A) => *Asigna +300 Puntos a la Progresión del Nivel SNI-2.*

### Entrega de Valor y Explotaciones Finales en el Software:

1. **Expedientes de Verificación "Lista Blanca":** Un reporte automático que dice con certeza de LRM/RDA por qué un investigador SÍ cumple con todos los rigores para recibir bono este trimestre. Ahorro de decenas de semanas a Comités de revisión e investigación.
2. **Headhunting y Fichajes "Moneyball":** El algoritmo cruza y busca prospectos de currículums para reclutamiento que matemáticamente estén a un peldaño de explotar indicadores de subvenciones, ofreciendo *scouting* predictivo brutal a las directivas de las universidades.
3. **Romper el Silo Corporativo:** Este Espectro Ontológico convertirá a UKIP en el traductor universal y automático de la Institución: logrando acoplar simultáneamente los KPI y finanzas de la **Vicerrectoría de Investigación** con los altos estándares de catalogación de la **Dirección Global de Bibliotecas**.
