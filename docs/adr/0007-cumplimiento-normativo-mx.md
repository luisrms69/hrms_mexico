# ADR-0007: Cumplimiento normativo MX — enfoque y supuestos

**Fecha:** 2026-11-19
**Status:** Propuesto

## Contexto

El objetivo es un registro electrónico de jornada orientado a las obligaciones laborales mexicanas. Al momento de este ADR **no se asume** la existencia de disposiciones STPS definitivas que fijen formato/contenido obligatorios.

## Decisión

Diseñar la solución para que quede **preparada** para las obligaciones legales MX (inmutabilidad, trazabilidad, conservación, acuse del empleado) **sin** hardcodear requisitos de una norma aún no definitiva. Los requisitos regulatorios concretos se incorporarán cuando existan disposiciones aplicables.

## Consecuencias

- Es un **riesgo regulatorio** explícito: cambios normativos pueden requerir ajustes (campos, reportes, retención).
- **Parámetros por régimen (R7):** jornada, límites diarios/semanales, descansos y vigencias deben **parametrizarse** (no un valor único para todos los trabajadores) y **conservarse los parámetros usados en cada snapshot**.
- Los reportes y la estructura de conservación (Etapa 5) se construyen de forma adaptable.

## Referencias a validar (no afirmar prueba plena)

DOF 03-03-2026 y 01-05-2026; LFT art. 132 fr. XXXIV, 994 fr. IV Bis y artículos de jornada, descanso, conservación y medios electrónicos. **No** afirmar que un resumen firmado reemplaza el registro electrónico exigido por ley ni que implica prueba plena automática.

## Notas

Transversal; se materializa sobre todo en la Etapa 5. Decisión de negocio/legal: cualquier interpretación normativa requiere **validación humana** (legal).
