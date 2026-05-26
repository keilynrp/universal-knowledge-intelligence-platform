# Field Correspondence Governance Runbook

1. Open Admin UI > Settings > Field rules.
2. Load preventive candidates with **Cargar preventivas**.
3. Disable **Solo activas** to review inactive candidates.
4. Use **Calcular evidencia** and review rules in priority order: Alta, Media, Baja, Sin evidencia.
5. Filter by source or destination when reviewing a specific import family.
6. For each candidate, inspect **Previsualizar impacto** and examples.
7. Mark the review decision: Pendiente, Aprobada, Rechazada, or Ajustar.
8. Only approved/active rules should move to production preview.
9. Use **Preview prod** before every apply.
10. Apply only after confirming the explicit affected-record prompt.
11. Check **Ejecuciones de produccion** after apply.
12. Use **Rollback** immediately if a production execution produces an unexpected result.
13. Export CSV when an offline review or governance sign-off is needed.
14. Treat collisions or invalid identifier validation as blockers until the rule is adjusted.
15. Keep preventive rules inactive unless evidence and review status justify activation.
