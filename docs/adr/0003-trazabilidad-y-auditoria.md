# ADR-0003: Trazabilidad y auditoría

**Fecha:** 2026-11-19
**Status:** Propuesto

## Contexto

El cumplimiento exige conservar evidencia de marcajes, correcciones, autorizaciones y responsables (quién, cuándo, con qué autorización).

## Decisión

Toda operación relevante deja **traza**: marcaje original (con metadatos de origen), correcciones (motivo, evidencia, aprobador, fecha), y acuses del empleado. Se aprovechan los mecanismos nativos de Frappe (campos `owner`/`creation`/`modified`, Version/Document History, Comentarios) y se complementan con Custom Fields específicos donde el nativo no alcanza.

## Consecuencias

- Los DocTypes propios y los Custom Fields incluyen los campos de auditoría necesarios.
- La pista de auditoría es consultable para RR. HH. y auditores (ver Etapa 5).
- **Expediente exportable** por empleado/periodo con: `Employee Checkin`, turnos, `Attendance`
  original/enmendado, `Attendance Request`, `Overtime Slip`, `MX Attendance Summary` y el PDF con su
  respuesta.
- **Conservación** conforme a la legislación/STPS aplicable (definir antes de producción); **no** depender
  solo de `Version`/`Deleted Document` para retención permanente; el respaldo externo debe comprobarse por
  restauración.

## Notas

Desarrollada en Etapas 1 y 5. Relacionada con [[0002-inmutabilidad-marcaje-original]] y
[[0007-cumplimiento-normativo-mx]].
