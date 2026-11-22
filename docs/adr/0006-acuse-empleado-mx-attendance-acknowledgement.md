# ADR-0006: Acuse del empleado — `MX Attendance Acknowledgement`

**Fecha:** 2026-11-19
**Status:** Propuesto

## Contexto

El empleado debe poder consultar su jornada y **reconocer/aceptar** sus registros de un periodo (participación del empleado), dejando evidencia del acuse.

## Decisión

Crear el DocType propio **`MX Attendance Acknowledgement`** para que el empleado emita un **acuse** sobre un `MX Attendance Summary` **ya *submitted*** (snapshot congelado).

**Semántica (R5):** el acuse es de **una sola escritura** (protegido contra segunda escritura), con estado **Conforme / Inconforme / Pendiente**, atribuido al **empleado autenticado** (sin suplantación), registrando **usuario, fecha, canal y versión mostrada** del resumen. **Silencio = Pendiente**, nunca aceptación tácita; la aceptación **no** supone renuncia a derechos.

## Consecuencias

- El empleado consulta sus jornadas/estadísticas (aislado a sus propios registros vía User Permission) y emite acuse.
- El acuse es evidencia adicional; **no** modifica el marcaje ni el summary.
- Un **desacuerdo** (Inconforme) se atiende por `Attendance Request` (ADR-0005) y se emite una **nueva versión** del resumen (ADR-0004), conservando el acuse anterior.

## Notas

Separa el acuse del `MX Attendance Summary` (v0.3 lo resolvía con campos `allow_on_submit` dentro del resumen). Decisión posterior: **dos** DocTypes propios. Relacionada con [[0004-resumen-jornada-mx-attendance-summary]] y [[0005-correcciones-via-attendance-request]].

## Notas

Desarrollada en la Etapa 4. Es el segundo de los **dos** únicos DocTypes propios previstos.
