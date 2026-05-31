# Diseño — Reskin visual de `/analytics/researchers`

**Fecha:** 2026-05-30
**Tipo:** Rediseño de interfaz (frontend, visual-only)
**Alcance:** Reskin visual de la página `frontend/app/analytics/researchers/page.tsx` para adoptar la
estética del patrón de referencia ("VANTAGE ANALYTICS / Knowledge Intelligence",
`https://an-lisis-de-investigadores-918831598829.us-east1.run.app/`), reorganizando las funciones
existentes. **Sin nuevas funciones, sin cambios de backend, sin IA.**

## Decisiones de alcance (acordadas con el usuario)

1. **Solo reskin visual.** Se preservan todas las funciones actuales; no se añaden asistente IA,
   briefings, comparador de expertos ni filtrado interactivo del grafo.
2. **Respetar el shell de UKIP.** Se mantienen `PageHeader`, sidebar y `Header` globales. La estética
   del patrón se aplica únicamente al contenido de la página. No se añade una app-bar con marca propia.
3. **Preservar dark mode.** Se mantiene el mecanismo actual (clase `.dark` en `<html>` + variantes
   `dark:` de Tailwind). UKIP arranca en modo claro por defecto, igual que la referencia.

## Contexto técnico observado

- El `page.tsx` actual (573 líneas) usa Tailwind crudo (slate/white/blue/emerald/amber, `font-black`,
  `rounded-3xl`, `dark:` variants). **No** usa el sistema de design tokens `ukip-*` que emplean las
  primitivas más nuevas en `app/components/ui/`.
- Fuentes del proyecto: **Geist Sans + Geist Mono** (`next/font/google`), no Inter/JetBrains Mono.
  El efecto "micro-label mono" del patrón se logra con `font-mono` (Geist Mono) existente.
- La referencia es una app Vite + React + Tailwind v4, paleta slate/blue/emerald/amber en oklch —
  **misma paleta base** que UKIP. La diferencia es de composición y disciplina, no de color.
- Dark mode: controlado por `ThemeContext` (`document.documentElement.classList.toggle("dark", ...)`).
  El reskin sigue usando variantes `dark:` de Tailwind.

## 1. Lenguaje visual

Traducción de la "firma" del patrón al stack de UKIP:

| Eje | Actual | Reskin |
|-----|--------|--------|
| Micro-etiquetas | `text-xs font-black uppercase tracking-[0.14em]` | `text-[10px] font-mono uppercase tracking-wider text-slate-400` |
| Pesos tipográficos | `font-black` generalizado | `font-semibold`/`font-bold`; números grandes en `font-bold tabular-nums` |
| Bordes/sombras | `rounded-3xl border-slate-200 shadow-sm` | `rounded-xl ring-1 ring-slate-950/5 shadow-xs`; sub-tarjetas `shadow-3xs` |
| Botón primario | `bg-blue-600` chunky `font-black` | `bg-blue-600 font-semibold`, foco `focus:ring-4 focus:ring-blue-100` |
| Paleta | slate/blue/emerald/amber | idéntica; uso semántico (verde=alto, ámbar=medio, rojo=bajo) |

Helpers de tono existentes (`scoreTone`, `barColor`) se conservan tal cual (ya respetan dark mode).

## 2. Estructura / layout

Orden de secciones en la página (mismas funciones, reorganizadas):

1. **PageHeader** (UKIP, sin cambios).
2. **FilterPanel** — panel único "Filtros de Búsqueda" con el input de tema destacado + 6 filtros
   (source, yearFrom, yearTo, country, institution, minCitations) en grid con micro-labels mono.
   Añade botón **"Reiniciar filtros"** (solo UI: resetea el estado local `filters` a vacío).
3. **KpiStrip** — fila de tarjetas compactas (micro-label mono + número `tabular-nums`):
   Investigadores, Citas totales, Densidad red, Nivel de confianza, Mejor evidencia.
   Absorbe el actual row de 3 tarjetas.
4. **ExecutivePanel** — panel ancho con headline + `stakeholder_value` + barras de
   cobertura/alta-confianza/citas/densidad (mismos datos que `ExecutiveMetricCard`).
5. **TopicGraph** — sin cambios funcionales; restyle del contenedor + leyenda en chips mono.
6. **CalibrationBar** — feedback Útil/Revisar restyleado a chips mono.
7. **Ranking** — grid de `ResearcherCard` restyleadas: rank en chip mono, score grande
   `tabular-nums`, drivers con barras finas, evidencia como filas enlazadas.

## 3. Organización de archivos

Extraer sub-componentes desde el `page.tsx` (573 líneas) a `app/analytics/researchers/components/`:

- `FilterPanel.tsx` — barra de búsqueda + filtros + reiniciar.
- `KpiStrip.tsx` — fila de KPIs.
- `ExecutivePanel.tsx` — panel ejecutivo (antes `ExecutiveMetricCard`).
- `TopicGraph.tsx` — grafo SVG (movido sin cambios de lógica).
- `ResearcherCard.tsx` — tarjeta de investigador.
- `researchersTypes.ts` — tipos compartidos (`Researcher`, `ScoreDrivers`, `GraphPayload`, etc.).
- `page.tsx` queda como orquestador (~150 líneas): estado, `loadTopic`, registro de asistente, layout.

Helpers compartidos (`scoreTone`, `barColor`, `externalHref`, `buildQuery`, `DRIVER_LABELS`) van a
`researchersUtils.ts` o al archivo de tipos según corresponda.

## 4. Restricciones / no-objetivos

- **No** se modifican endpoints, schemas, ni la forma de los datos.
- **No** se cambia la lógica de `loadTopic`, `useAssistantContextRegistration`, ni el manejo de errores.
- **No** se introduce el sistema `ukip-*` en esta página (se mantiene Tailwind crudo para fidelidad
  con la referencia y mínima superficie de cambio).
- **No** se añaden dependencias nuevas.

## 5. Verificación

- Dev server + preview: comparar claro/oscuro en breakpoints 1440 / 768 / 375; verificar sin overflow,
  sin errores de consola, y que el flujo (buscar tema → ver KPIs/grafo/ranking) sigue funcionando.
- Si existe setup de testing en frontend, añadir tests de render para `KpiStrip` y `ResearcherCard`
  (presencia de labels y valores). Si no existe setup, la verificación visual en preview es la cobertura.
- Confirmar que ningún archivo supera ~400 líneas tras la extracción.
