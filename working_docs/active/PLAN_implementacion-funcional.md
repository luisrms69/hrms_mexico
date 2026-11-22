# PLAN de implementación funcional — hrms_mexico

**Fecha:** 2026-11-19
**Estado:** Activo (planificación)
**Alcance:** Registro electrónico de jornada laboral (México) sobre Frappe HRMS v16, reutilizando al máximo las capacidades nativas.

> Documento de trabajo (no publicable). Las **decisiones** viven en `docs/adr/`; aquí viven las **etapas y tareas**.
> Convenciones: `frappe-infrastructure/docs/documentation-standard.md`.
> **Antecedente arquitectónico:** `working_docs/archive/arquitectura-hrms-mexico-2027-v0.3.md` (dictamen técnico v0.3).
> Este plan toma v0.3 como antecedente, respetando las decisiones posteriores (p. ej. **dos** DocTypes propios).

---

## Principios establecidos (insumo de negocio)

1. **Mínima alteración de la operación habitual** — el empleado marca entrada/salida con los mecanismos nativos de HRMS (`Employee Checkin`). No se desarrolla otra pantalla de marcaje.
2. **Inmutabilidad del marcaje original** — el `Employee Checkin` original **no se edita ni se elimina** por procedimientos normales **ni por rol de RR. HH.** (inmutabilidad absoluta a nivel aplicación).
3. **Correcciones documentadas** — se registran **por separado**, conservando el original.
4. **Trazabilidad** — evidencia de marcajes, correcciones, autorizaciones y responsables.
5. **Participación del empleado** — consulta de registros, estadísticas y acuse.
6. **Casos excepcionales** — omisiones, errores, ausencias, horas extraordinarias.
7. **Cumplimiento normativo** — preparar para obligaciones legales MX sin asumir disposiciones STPS definitivas.
8. **Criptografía** — fuera del alcance inicial.

## DocTypes propios previstos (únicos)

- `MX Attendance Summary` — resumen/consolidación de jornada.
- `MX Attendance Acknowledgement` — acuse/aceptación del empleado.

> **No** se crea `MX Attendance Correction`. Las correcciones usan `Attendance Request` **nativo** + Custom Fields, **limitado a una fecha por solicitud**.

## Nativo de HRMS v16 reutilizado

`Employee Checkin` (marcaje IN/OUT; no submittable), `Shift Type` (auto-attendance), `Attendance`, `Attendance Request` (regularización/omisiones — una fecha por solicitud), `Overtime Slip`/`Overtime Type` (horas extra), `Leave Application` (ausencias), roles HR y portal del empleado.

---

## Etapas

### Etapa 1 — Fundamentos y controles
- **Objetivo:** configuración, roles/permisos, **protección del marcaje original** y trazabilidad base.
- **Nativo:** roles HR, `Employee Checkin`, `Shift Type`, permisos Frappe.
- **Propio:** `MX Attendance Settings` (Single) para parámetros; Custom Fields de origen/trazabilidad en `Employee Checkin`; **guard de inmutabilidad de la evidencia** (`set_only_once` en `employee`/`time`/`log_type` + `validate`/`on_trash` + retiro de `delete`/`write`/`import` a roles operativos, conservando `create` para la PWA); rol MX de operación. **Importante:** la inmutabilidad protege la **evidencia** (`employee`, `time`, `log_type`) y el borrado, **no** los campos técnicos que HRMS actualiza (`attendance`, `skip_auto_attendance`, turno). Ver ADR-0002.
- **Depende de:** —
- **Criterios de aceptación:**
  - Los campos de evidencia (`employee`, `time`, `log_type`) de un `Employee Checkin` creado **no** pueden modificarse por UI/API, **ni** por HR Manager/System Manager; el documento **no** puede eliminarse por flujos operativos.
  - Los campos técnicos de HRMS (`attendance`, `skip_auto_attendance`, turno) **siguen** actualizándose (auto-attendance, scheduler, `bulk_fetch_shift`).
  - El intento de edición/borrado de evidencia queda bloqueado con mensaje claro y trazado.
  - Roles/permisos aplicados; `bench --site <dev-site> migrate` limpio; fixtures (roles, custom fields, property setters) exportables.
- **Pruebas:** crear checkin y verificar que editar `time`/`log_type` o borrarlo falla para todos los roles; verificar que auto-attendance/scheduler sí pueden actualizar campos técnicos; verificar que cancelar `Attendance` no habilita editar el checkin.

### Etapa 2 — Registro y consolidación
- **Objetivo:** aprovechar marcajes nativos y **generar resúmenes de jornada**.
- **Nativo:** `Employee Checkin` + `Shift Type` (auto-attendance) → `Attendance`.
- **Propio:** `MX Attendance Summary` (DocType **submittable**): consolida por empleado/día/periodo (pares IN/OUT, horas nativas, minutos reconocidos, extras, incidencias, parámetros) **sin alterar** el original; recálculo **idempotente**; al *submit* **congela el snapshot** + PDF. Aplica la **regla de sustitución** (ADR-0005): los minutos reconocidos **sustituyen** (no suman) a `working_hours`.
- **Depende de:** Etapa 1.
- **Criterios de aceptación:**
  - Dados checkins IN/OUT de un día, el summary refleja pares y horas correctos.
  - El summary **no** modifica checkins; recálculo reproducible (mismo input → mismo output).
  - Al *submit*, el snapshot/PDF quedan congelados.
- **Pruebas:** pares completos, marcaje impar, múltiples pares/día, cruce de medianoche; verificación de que no muta checkins; snapshot congelado tras submit.
- **Decisión pendiente (sincronización / falso Absent):** un IN sin OUT puede generar `Attendance` `Absent` (`working_hours=0`). v0.3 §4 propone control de `last_sync_of_checkin`; se requiere **control de liberación por turno/periodo** para incidencias abiertas (a diseñar/ensayar — ver Riesgos).

### Etapa 3 — Correcciones y excepciones
- **Objetivo:** solicitudes, justificaciones, aprobaciones y **conservación de evidencia**.
- **Nativo:** `Attendance Request` (una fecha por solicitud) para regularización/omisiones; `Leave Application` (ausencias); `Overtime Slip` (horas extra); workflow de aprobación nativo.
- **Propio:** Custom Fields en `Attendance Request` (motivo/categoría MX, evidencia, autorizador); vínculo de la corrección aprobada con el `MX Attendance Summary`. **Sin** DocType de corrección propio.
- **Depende de:** Etapas 1, 2.
- **Criterios de aceptación:**
  - Una omisión/error se corrige vía `Attendance Request` aprobado **sin** modificar el checkin original.
  - **Sin OUT no se inserta OUT ficticio (R2):** el empleado declara hora/motivo, RR. HH. reconoce minutos; sin resolución la jornada queda **pendiente** (no se presume salida).
  - Los minutos reconocidos **sustituyen** (no suman) a `working_hours` en el summary (R3).
  - La corrección (motivo, evidencia, aprobador, fecha) queda trazada y **reflejada** en el summary.
  - Cada `Attendance Request` abarca **una** fecha.
  - Horas extra vía `Overtime Slip`; ausencias vía `Leave Application`.
- **Brecha funcional pendiente (R4):** extras **derivadas de una salida omitida** (minutos reconocidos → `Overtime Slip`) **no** se declaran integradas hasta probar el `cancel`/`amend` documentado de `Attendance` (sin tocar el Checkin).
- **Pruebas:** corrección aprobada que ajusta el summary dejando intacto el checkin; rechazo/pendiente que no altera nada; validación de "una fecha por solicitud"; jornada reconocida que genera extras (resultado correcto o procedimiento explícito probado, sin duplicar horas).

### Etapa 4 — Consulta y acuse del empleado
- **Objetivo:** visualización de jornadas, estadísticas y **reconocimiento**.
- **Nativo:** portal/dashboards del empleado, permisos por empleado (User Permission).
- **Propio:** `MX Attendance Acknowledgement` (DocType): acuse/aceptación del empleado sobre su registro de periodo; vistas/estadísticas de consulta.
- **Depende de:** Etapas 2, 3.
- **Criterios de aceptación:**
  - El empleado consulta sus jornadas y estadísticas de su propio registro.
  - **Resumen primero, respuesta después:** el acuse se emite sobre un `MX Attendance Summary` ya *submitted*.
  - El acuse es de **una sola escritura** (Conforme/Inconforme/Pendiente), atribuido al empleado autenticado (sin suplantación), registrando usuario, fecha, canal y **versión mostrada**.
  - **Silencio = Pendiente** (no aceptación tácita); el acuse **no** altera checkins ni summary.
- **Pruebas:** acuse de un periodo; segunda escritura bloqueada; aislamiento por empleado (no ve ni firma registros ajenos); el acuse no modifica evidencia; snapshot intacto tras la respuesta.

### Etapa 5 — Reportes y cumplimiento *(post-MVP)*
- **Objetivo:** reportes RR. HH., evidencias, auditoría y conservación.
- **Nativo:** Report/Query Builder, print formats, roles de auditoría.
- **Propio:** reportes MX (jornada, incidencias, horas extra), export de evidencia, estructura de conservación; **preparación** de requisitos legales MX (sin asumir disposiciones STPS definitivas).
- **Depende de:** Etapas 1–4.
- **Criterios de aceptación:** reportes reproducibles; evidencia exportable; pista de auditoría consultable; checklist de cumplimiento con pendientes normativos marcados.

### Etapa 6 — Pruebas y piloto *(post-MVP)*
- **Objetivo:** pruebas automatizadas, casos operativos y validación con usuarios.
- **Nativo:** framework de tests de Frappe, CI.
- **Propio:** suite de tests (inmutabilidad, summary, correcciones, acuse); casos operativos; piloto con usuarios.
- **Depende de:** Etapas 1–5.
- **Criterios de aceptación:** suite verde en CI; casos operativos cubiertos; feedback de piloto incorporado.

---

## MVP

**MVP = Etapas 1 a 4** (protección del registro · consolidación · correcciones · acuse del empleado).

**Posterior al MVP:** Etapa 5 (reportes y cumplimiento completos) y Etapa 6 (piloto).

## Dependencias entre etapas

```
1 → 2 → 3 → 4   (MVP)
        ↘ 5 → 6 (post-MVP)
```

## Decisiones pendientes / riesgos

- **Regulatorio (principio 7):** no se asume disposición STPS definitiva; el diseño queda "preparado" (ver ADR-0007). Riesgo de cambios normativos. Parámetros por **régimen** (no valor único); conservar los usados en cada snapshot.
- **Inmutabilidad a nivel BD:** la garantía es **a nivel aplicación** (hooks/permisos/`set_only_once`). Escrituras privilegiadas (`db_set`, `qb.update`, SQL) quedan fuera del control de la app → riesgo residual documentado; sello/cripto = etapa 2 (ADR-0008).
- **Liberación de sincronización / falso Absent (v0.3 §4):** definir y ensayar el control por turno/periodo para incidencias abiertas; evitar `Absent` indebido y no bloquear a todos por una omisión.
- **Extras por minutos reconocidos (R4):** brecha funcional pendiente (cancel/amend de `Attendance` probado) antes de declarar integrado el pago de extras por salida omitida.
- **Solicitudes multifecha:** confirmado **una fecha por solicitud** salvo que se valide asignación inequívoca de minutos por jornada (ADR-0005).
- **Persistencia tras `cancel`/`amend`:** validar que el resumen anterior y su acuse se conservan tras rectificación/cancelación y restauración (ADR-0004).
- **Trabajadores sin portal:** definir canal de puesta a disposición y acuse (operativo/legal — pendiente).
- **Alcance de `MX Attendance Summary`:** granularidad (día/periodo) y campos exactos a cerrar al diseñar el DocType (ADR-0004).

## Mapa ADR → etapa

| ADR | Decisión | Etapa |
|---|---|---|
| 0001 | Reutilizar HRMS nativo con mínima alteración | transversal / 1 |
| 0002 | Inmutabilidad absoluta del marcaje original | 1 |
| 0003 | Trazabilidad y auditoría | 1 / 5 |
| 0004 | `MX Attendance Summary` | 2 |
| 0005 | Correcciones vía `Attendance Request` (1 fecha) | 3 |
| 0006 | `MX Attendance Acknowledgement` | 4 |
| 0007 | Cumplimiento normativo MX (supuestos) | 5 / transversal |
| 0008 | Criptografía fuera de alcance inicial | — |

## Primera actividad de desarrollo (tras aprobación)

Etapa 1 — **control de inmutabilidad del marcaje original**: Custom Fields de origen/trazabilidad en `Employee Checkin` + hooks `on_update`/`on_trash` que bloqueen edición/eliminación del original para todos los roles, **con test automatizado primero (TDD)**.
