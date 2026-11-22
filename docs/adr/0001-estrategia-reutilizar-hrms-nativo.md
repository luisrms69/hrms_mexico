# ADR-0001: Estrategia general — reutilizar HRMS nativo con mínima alteración

**Fecha:** 2026-11-19
**Status:** Propuesto

## Contexto

`hrms_mexico` implementa el registro electrónico de jornada laboral para México sobre Frappe HRMS v16, que ya provee marcaje (`Employee Checkin`), asistencia (`Attendance`, `Shift Type` con auto-attendance), regularización (`Attendance Request`), horas extra (`Overtime Slip`) y ausencias (`Leave Application`).

## Decisión

Construir sobre las capacidades **nativas** de HRMS con la **mínima alteración** de la operación habitual: el empleado sigue marcando con `Employee Checkin` nativo. `hrms_mexico` agrega **encima** protección, consolidación y acuse, sin reemplazar flujos nativos ni crear una pantalla de marcaje paralela.

## Consecuencias

- No se desarrolla captura de marcaje propia salvo necesidad funcional demostrada.
- Los DocTypes propios se limitan a lo que el nativo no cubre (`MX Attendance Summary`, `MX Attendance Acknowledgement`).
- Prohibido modificar el núcleo de Frappe/ERPNext/HRMS; la extensión es por Custom Fields, hooks y DocTypes propios (portabilidad del ecosistema).

## Notas

Transversal; fundamenta las Etapas 1–6 del plan de implementación.

**Antecedente arquitectónico:** *Arquitectura HRMS México 2027 — v0.3* (dictamen técnico previo),
copiada como referencia en `working_docs/archive/arquitectura-hrms-mexico-2027-v0.3.md`. Los ADR 0001–0008
toman v0.3 como antecedente, **respetando las decisiones posteriores** (p. ej. **dos** DocTypes propios en
vez de uno; ver ADR-0004 y ADR-0006).
