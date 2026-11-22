# ADR-0005: Correcciones vía `Attendance Request` (una fecha por solicitud)

**Fecha:** 2026-11-19
**Status:** Propuesto

## Contexto

Las omisiones, errores y regularizaciones deben documentarse **sin alterar** el marcaje original (ver ADR-0002). HRMS ya provee `Attendance Request` con flujo de aprobación.

## Decisión

Las correcciones se registran con el **`Attendance Request` nativo + Custom Fields** (motivo/categoría MX, `hora_salida_declarada` cuando aplique, `minutos_reconocidos_mx`, referencia a jornada/turno, resolución del aprobador), **limitado a una fecha por solicitud**. **No** se crea un DocType `MX Attendance Correction`. Las ausencias usan `Leave Application` y las horas extra `Overtime Slip`, ambos nativos.

**Sin OUT no se inserta un OUT ficticio (R2):** el empleado declara hora y motivo; el supervisor/RR. HH. valida y **reconoce minutos**. Sin resolución, la jornada queda **pendiente**; no se presume una hora de salida.

## Consecuencias

- La corrección aprobada se **refleja** en el `MX Attendance Summary` pero el `Employee Checkin` original queda intacto.
- **Regla de sustitución (R3):** los minutos reconocidos **sustituyen** a `Attendance.working_hours` en el resumen, **no se suman**.
- Una solicitud = una fecha (se valida). *Motivo:* v0.3 §5.1 exige asignar minutos inequívocamente a cada jornada; si la estructura no soporta multifecha con seguridad, se limita a **una fecha por solicitud** sin crear otro DocType.
- Una modificación tardía no debe alterar una resolución ya formalizada (definir tratamiento de rechazadas/canceladas/reemplazadas).
- **Horas extra — brecha funcional pendiente (R4):** `Overtime Slip` usa campos de `Attendance` (`actual_overtime_duration`); los minutos reconocidos **no** alimentan automáticamente el proceso de extras. El pago de extras derivadas de una **salida omitida** requiere un `cancel`/`amend` documentado de `Attendance` (sin tocar el Checkin), **probado** antes de declararlo integrado.
- Los únicos DocTypes propios del dominio siguen siendo `MX Attendance Summary` y `MX Attendance Acknowledgement`.

## Notas

Desarrollada en la Etapa 3. Relacionada con [[0002-inmutabilidad-marcaje-original]] y [[0004-resumen-jornada-mx-attendance-summary]].
