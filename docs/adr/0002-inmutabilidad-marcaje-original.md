# ADR-0002: Inmutabilidad absoluta del marcaje original

**Fecha:** 2026-11-19
**Status:** Propuesto

## Contexto

`Employee Checkin` (el marcaje nativo) **no es submittable**, por lo que por defecto puede editarse o eliminarse según permisos. El cumplimiento requiere que el marcaje original sea **evidencia inmutable**.

## Decisión

Los **campos de evidencia** del `Employee Checkin` (`employee`, `time`, `log_type`) son **inmutables desde
su creación**, y el documento **no puede eliminarse** por los flujos operativos — **ni** por Employee, HR
User, HR Manager **ni** System Manager. Se implementa con:
- `set_only_once` (Property Setter) en `employee`, `time` y `log_type`;
- retiro de `delete` y de `write`/`import` a los roles operativos en los DocPerm, **conservando `create`**
  para la PWA `/hrms`;
- `validate`/`on_trash` propios **independientes** del vínculo con `Attendance` (cancelar `Attendance`
  desvincula checkins y desactiva la protección condicional nativa de `time`; el blindaje propio no puede
  depender de esa relación).

Las correcciones **no** alteran el original: se registran por separado (ver ADR-0005).

## Consecuencias

- Los **campos técnicos** que HRMS actualiza por su cuenta (`attendance`, `skip_auto_attendance`,
  asignación de turno; vía `qb.update`/scheduler/`bulk_fetch_shift`) **siguen funcionando**: la
  inmutabilidad aplica a la **evidencia**, no a la plomería técnica de HRMS.
- La garantía es **a nivel aplicación**; rutas privilegiadas (`db_set`, `frappe.db.set_value`, `qb.update`,
  SQL directo, `ignore_validate`) pueden evadirla → se documentan como **riesgo residual** y se restringen
  privilegios. **No se promete inviolabilidad ante SQL privilegiado** en etapa 1 (sellado/cripto = ADR-0008).
- Requiere Custom Fields de origen/trazabilidad para distinguir y auditar el marcaje (ver ADR-0003).

## Notas

Desarrollada en la Etapa 1. Relacionada con [[0003-trazabilidad-y-auditoria]] y [[0005-correcciones-via-attendance-request]].
