# Compliance Gap Register

Registro historico base de gaps de compliance y enterprise readiness para
`US-048`.

El source of truth operativo actual es
`docs/product/ENTERPRISE_CONTROL_REGISTER.md`. Este documento conserva el
baseline comercial original y no debe usarse para afirmar madurez actual.

## 1. Objetivo

Hacer explicito que UKIP todavia no debe venderse como plataforma enterprise-complete y dejar un mapa priorizado de lo que falta antes de conversaciones comerciales exigentes.

## 2. Foco comercial relacionado

Este registro se interpreta contra el MVP comercial actual:

- `research intelligence`

No intenta cubrir todos los futuros verticales. Prioriza lo que hoy importa para vender de forma responsable ese wedge inicial.

## 3. Gaps priorizados

| Prioridad | Gap | Estado actual | Impacto | Recomendacion |
|---|---|---|---|---|
| P0 | Tenant isolation duro | Parcial | Riesgo alto para clientes que exigen segregacion contractual o legal de datos | Priorizar `EPIC-012` con `org_id`, enforcement real de queries y revision de exports/jobs |
| P0 | Retention, export y deletion controls | Gap | Bloquea conversaciones tipo GDPR y genera ambiguedad contractual | Definir politica de ciclo de vida y flujo administrado para exportacion/eliminacion |
| P0 | Rotacion de secretos y credenciales | Parcial | Debilita postura de seguridad y respuesta a incidentes | Crear runbooks, ownership y soporte de rollover por etapas |
| P1 | Auditability como evidence pack | Parcial | Hace lenta y manual la due diligence tecnica | Agregar export de evidencia, ownership de controles y retencion asociada |
| P1 | Data residency | Gap | Limita ventas con instituciones que exigen region o boundary de datos | Documentar topologias soportadas y condiciones antes de hacer claims |
| P1 | Privacy/legal pack | Gap | Frena procurement y legal review aunque el producto encaje tecnicamente | Preparar baseline de DPA, subprocessors, responsabilidades y supuestos de privacidad |
| P1 | Background jobs separados del proceso web | Parcial | Preocupa por confiabilidad y recuperacion operativa | Avanzar `US-042` y externalizar imports/reportes programados |
| P2 | Identity lifecycle enterprise | Parcial | Genera administracion manual en clientes grandes | Completar governance de sesiones, offboarding y provisioning |

## 4. Hooks de roadmap

Este registro alimenta especialmente:

- `EPIC-012` para tenant isolation y access control
- `US-042` para externalizacion de background jobs
- futuros bloques de privacy, retention y legal readiness

## 5. Artefactos tecnicos relacionados

- `backend/enterprise_readiness.py`
- `GET /ops/enterprise-readiness`
- `docs/product/COMMERCIAL_MVP.md`
- `docs/product/epics/EPIC-013-commercial-readiness-and-credibility.md`
- `docs/product/stories/US-048-compliance-gap-register.md`
