# ADR-0004: Resumen de jornada — `MX Attendance Summary`

**Fecha:** 2026-11-19
**Status:** Propuesto

## Contexto

El marcaje nativo (`Employee Checkin`) y la `Attendance` nativa no ofrecen un consolidado de jornada orientado a cumplimiento MX (pares entrada/salida, horas trabajadas, incidencias) que sirva de base para consulta, acuse y reportes.

## Decisión

Crear el DocType propio **`MX Attendance Summary`** que **consolida** la jornada por empleado/día/periodo a partir de los `Employee Checkin` (y `Attendance`/correcciones aprobadas), **sin alterar** los registros originales. El cálculo es **idempotente** (mismo insumo → mismo resultado).

Es **submittable**: al hacer *submit* se **congela el snapshot** del periodo (filas diarias, referencias a marcajes, horas nativas, minutos reconocidos, extras, incidencias y parámetros aplicados) y se adjunta el PDF. **Resumen primero, respuesta después:** el acuse (ADR-0006) ocurre sobre el resumen ya *submitted*.

**Regla de sustitución (ver ADR-0005):** cuando una jornada tiene minutos reconocidos por un `Attendance Request` aprobado, esos minutos **sustituyen** (no suman) a `Attendance.working_hours` en el resumen; en caso contrario se usa `working_hours` nativo.

## Consecuencias

- Es una capa derivada/solo-consolidación; nunca modifica checkins ni evidencia.
- Refleja las correcciones aprobadas (ver ADR-0005) y alimenta consulta/acuse (ADR-0006) y reportes (Etapa 5).
- **Rectificación histórica:** una revisión posterior al cierre genera un **documento NUEVO e independiente** (`MX Attendance Summary`) que **referencia** al anterior mediante `rectifica_a`. El resumen original **conserva `docstatus=1`**, su contenido y su evidencia **intactos**; no se toca.
- La granularidad exacta (día/periodo) y los campos se cierran al diseñar el DocType.

### Prohibición — sin `cancel`/`amend` sobre el resumen confirmado (decisión definitiva)

El `MX Attendance Summary` confirmado es **evidencia**. Para corregirlo **está PROHIBIDO**: `Document.cancel()`,
el mecanismo nativo **Amend**/`amended_from`, cualquier modificación posterior al *submit* (incluidos campos
`allow_on_submit`), y cambios directos de `docstatus` para cancelar/sustituir el documento. La **única** vía de
corrección es la **rectificación**: un **documento nuevo e independiente** con referencia (`rectifica_a`) al
original, que permanece confirmado. Protección por metadata (permisos `cancel`/`amend`/`delete` deshabilitados)
y por guard de controlador (`before_cancel`), **sin** modificar el núcleo de Frappe/HRMS. Esta prohibición
aplica igualmente a `MX Attendance Acknowledgement` (ADR-0006).

## Notas

v0.3 contemplaba el acuse como campos `allow_on_submit` **dentro** de este DocType (un único DocType). La decisión posterior lo separa en **`MX Attendance Acknowledgement`** (ADR-0006); este resumen se mantiene submittable como snapshot congelado.

## Notas

Desarrollada en la Etapa 2. Es uno de los **dos** únicos DocTypes propios previstos (junto con `MX Attendance Acknowledgement`).
