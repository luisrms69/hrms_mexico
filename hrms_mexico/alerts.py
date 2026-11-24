# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

"""F01 — Alertas por jornada abierta (salida olvidada).

Detecta jornadas con **IN sin OUT** cuyo turno ya terminó más una **tolerancia** configurable, avisa al
empleado y al responsable de RR. HH. de su empresa (y opcionalmente a supervisor/usuario adicional), con
**escalamiento** si no se atiende. **No** crea OUT ficticios, **no** modifica `Employee Checkin`, **no**
presume ausencias y **no** toca la PWA.

Dedup/escalamiento: control estructurado **`MX Attendance Alert`** (una fila por marcaje, `employee_checkin`
único). La unicidad a nivel BD + un bloqueo `for_update` serializan corridas concurrentes; el **envío y el
sello van en la MISMA transacción del job**, así que una interrupción antes del commit revierte ambos
(Notification Log y sello) y el siguiente ciclo reintenta sin duplicar. `Notification Log` se usa **solo**
para entregar. Configuración y plantillas: `MX Attendance Settings`, **una por empresa**.

Respeta turnos nocturnos (usa el `shift_end` real), descansos / jornadas sin turno (sin `shift_end` → no
se evalúan) y jornadas aún dentro de turno (todavía no vence la tolerancia).
"""

from datetime import timedelta

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

from hrms_mexico.hrms_mexico.doctype.mx_attendance_summary.mx_attendance_summary import MXAttendanceSummary

_LOOKBACK_DAYS = 3  # ventana de búsqueda de jornadas abiertas recientes
_DEFAULT_TEMPLATES = {
	"aviso": "MX Aviso Jornada Abierta",
	"escalamiento": "MX Escalamiento Jornada Abierta",
}


def check_open_journeys(as_of=None):
	"""Entrada del scheduler (hourly). Procesa avisos y escalamientos **por empresa**.

	La configuración es una por empresa (`MX Attendance Settings` con `company`), resuelta por
	`Employee.company`. Nunca se usan destinatarios de otra empresa; si falta la configuración de una
	empresa, se registra y se omite (sin detener el scheduler)."""
	as_of = get_datetime(as_of or now_datetime())

	# Regularizada (Attendance Request MX aprobado) → deja de considerarse abierta (no se alerta).
	unresolved = [j for j in _find_open_journeys(as_of) if not _is_regularized(j["employee"], j["date"])]

	cache: dict = {}
	for j in unresolved:
		settings = _settings_for(j["company"], cache)
		if settings is None:
			frappe.logger("hrms_mexico").warning(
				f"MX Attendance Settings: falta configuración para la empresa {j['company']}; se omite la alerta."
			)
			continue
		if not settings.alerta_activa:
			continue
		# Precaución: sin responsable de RR. HH. no se envía (ni se falla); la config lo exige en el form.
		if not settings.responsable_rrhh:
			frappe.logger("hrms_mexico").warning(
				f"MX Attendance Settings ({j['company']}): sin 'Responsable de RR. HH.'; se omite el envío."
			)
			continue
		# Aviso/escalamiento solo tras fin de turno + tolerancia de ESA empresa (antes, jornada abierta
		# legítima). El umbral de escalamiento (mayor) lo evalúa `_process_journey`.
		cutoff = get_datetime(j["shift_end"]) + timedelta(minutes=int(settings.tolerancia_minutos or 0))
		if as_of < cutoff:
			continue
		_process_journey(settings, j, as_of)


def _settings_for(company, cache):
	"""Configuración de alertas de la empresa (una por empresa) o ``None`` si no existe."""
	if company not in cache:
		name = frappe.db.exists("MX Attendance Settings", {"company": company})
		cache[company] = frappe.get_cached_doc("MX Attendance Settings", name) if name else None
	return cache[company]


# ------------------------------------------------------------------ detección
def _find_open_journeys(as_of):
	"""Jornadas con entrada sin salida que tienen turno (`shift_end`). Agrupa como el resumen. Incluye
	empresa (`Employee.company`), hora de entrada y turno para la plantilla."""
	start = add_to_date(as_of, days=-_LOOKBACK_DAYS)
	checkins = frappe.get_all(
		"Employee Checkin",
		filters={"time": ("between", [start, as_of])},
		fields=["name", "employee", "time", "log_type", "shift", "shift_start", "shift_end"],
		order_by="employee asc, time asc",
	)

	groups: dict[tuple, list] = {}
	for c in checkins:
		day = c.shift_start.date() if c.shift_start else get_datetime(c.time).date()
		groups.setdefault((c.employee, day, c.shift or None), []).append(frappe._dict(c))

	company_of: dict = {}
	open_journeys = []
	for (employee, day, shift), logs in groups.items():
		if MXAttendanceSummary._is_complete(logs):
			continue  # jornada cerrada (todos sus pares) → no es olvido de salida
		shift_ends = [l.shift_end for l in logs if l.shift_end]
		if not shift_ends:
			continue  # sin turno (descanso / sin asignación) → no se evalúa
		if employee not in company_of:
			company_of[employee] = frappe.db.get_value("Employee", employee, "company")
		open_journeys.append(
			{
				"employee": employee,
				"company": company_of[employee],
				"date": day,
				"checkin": logs[-1].name,
				"in_time": logs[0].time,
				"shift": shift,
				"shift_end": max(shift_ends),
			}
		)
	return open_journeys


def _is_regularized(employee, date):
	"""¿Existe un Attendance Request MX aprobado que cubra la fecha?"""
	return bool(
		frappe.db.exists(
			"Attendance Request",
			{
				"employee": employee,
				"docstatus": 1,
				"from_date": ("<=", date),
				"to_date": (">=", date),
				"custom_mx_categoria": ("is", "set"),
			},
		)
	)


# ------------------------------------------------------------------ proceso por jornada (idempotente)
def _process_journey(settings, journey, as_of):
	alert = _get_or_create_alert(journey["checkin"])
	# Bloqueo de fila: serializa corridas concurrentes sobre ESTA incidencia (el segundo job espera
	# al commit del primero y luego ve el sello).
	state = frappe.db.get_value(
		"MX Attendance Alert",
		alert.name,
		["aviso_enviado_el", "escalamiento_enviado_el"],
		as_dict=True,
		for_update=True,
	)

	if not state.aviso_enviado_el:
		# Enviar y SELLAR en la misma transacción del job: si se interrumpe antes del commit, ambos se
		# revierten (sin duplicar, sin perder). El sello va DESPUÉS del envío (si el envío falla, no sella).
		_send(settings, journey, kind="aviso")
		frappe.db.set_value("MX Attendance Alert", alert.name, "aviso_enviado_el", as_of)
		return  # N0 en esta corrida; el escalamiento, en una posterior

	if not settings.escalamiento_activo or state.escalamiento_enviado_el:
		return
	escalate_at = (
		get_datetime(journey["shift_end"])
		+ timedelta(minutes=int(settings.tolerancia_minutos or 0))
		+ timedelta(hours=int(settings.horas_escalamiento or 0))
	)
	if as_of < escalate_at:
		return
	_send(settings, journey, kind="escalamiento")
	frappe.db.set_value("MX Attendance Alert", alert.name, "escalamiento_enviado_el", as_of)


def _get_or_create_alert(checkin):
	"""Devuelve (creando si hace falta) el control de la incidencia. El índice único por `employee_checkin`
	garantiza una sola fila incluso con corridas concurrentes."""
	name = frappe.db.exists("MX Attendance Alert", {"employee_checkin": checkin})
	if name:
		return frappe.get_doc("MX Attendance Alert", name)
	try:
		return frappe.get_doc({"doctype": "MX Attendance Alert", "employee_checkin": checkin}).insert(
			ignore_permissions=True
		)
	except frappe.exceptions.DuplicateEntryError:
		# Otra corrida concurrente la creó primero: reusar esa fila.
		return frappe.get_doc("MX Attendance Alert", {"employee_checkin": checkin})


# ------------------------------------------------------------------ mensaje (Email Template editable)
def _send(settings, journey, kind):
	if kind == "aviso":
		recipients = _recipients_n0(settings, journey["employee"])
		template = settings.plantilla_aviso or _DEFAULT_TEMPLATES["aviso"]
	else:
		recipients = _recipients_escalation(settings)
		template = settings.plantilla_escalamiento or _DEFAULT_TEMPLATES["escalamiento"]
	subject, message = _render_message(template, journey, kind)
	_send_alert(recipients, subject, message, journey["checkin"])


def _render_message(template_name, journey, kind):
	"""Renderiza asunto y cuerpo desde el Email Template (editable) con los datos de la jornada. Si la
	plantilla no existe, usa un mensaje por defecto embebido (para no fallar)."""
	ctx = _context(journey, kind)
	if template_name and frappe.db.exists("Email Template", template_name):
		et = frappe.get_cached_doc("Email Template", template_name)
		# La plantilla es un Email Template administrado solo por System Manager/HR Manager (no entrada
		# de usuario), el mismo patrón que usa Frappe nativo para Email Templates → no es SSTI explotable.
		subject = frappe.render_template(
			et.subject or "", ctx
		)  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
		body = frappe.render_template(
			et.response_html or et.response or "", ctx
		)  # nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
		if subject or body:
			return subject, body
	return _fallback(ctx, kind)


def _context(journey, kind):
	emp = (
		frappe.db.get_value(
			"Employee", journey["employee"], ["employee_name", "employee_number", "company"], as_dict=True
		)
		or frappe._dict()
	)
	return {
		"employee": journey["employee"],
		"employee_name": emp.get("employee_name"),
		"employee_number": emp.get("employee_number"),
		"company": emp.get("company"),
		"in_time": journey.get("in_time"),
		"shift": journey.get("shift"),
		"shift_end": journey.get("shift_end"),
		"motivo": frappe._("Entrada registrada sin salida tras el fin del turno."),
		"instruccion": frappe._(
			"Verifique su marcaje o solicite una regularización mediante Attendance Request."
		),
		"es_escalamiento": kind == "escalamiento",
	}


def _fallback(ctx, kind):
	titulo = (
		frappe._("Escalamiento: jornada sin salida sin atender")
		if kind == "escalamiento"
		else frappe._("Jornada sin salida registrada")
	)
	subject = f"{titulo} — {ctx.get('employee_name') or ''}"
	message = frappe._(
		"Empleado: {0} ({1}). Empresa: {2}. Entrada: {3}. Turno: {4}, salida esperada: {5}. {6}"
	).format(
		ctx.get("employee_name"),
		ctx.get("employee_number") or "-",
		ctx.get("company"),
		ctx.get("in_time"),
		ctx.get("shift") or "-",
		ctx.get("shift_end"),
		ctx.get("instruccion"),
	)
	return subject, message


# ------------------------------------------------------------------ destinatarios / entrega
def _employee_user(employee):
	return frappe.db.get_value("Employee", employee, "user_id") or None


def _recipients_n0(settings, employee):
	"""Siempre: empleado + responsable de RR. HH. de la empresa. Opcional: supervisor (si se activó y hay
	Reports To) y un usuario adicional. Dedup por usuario (varios roles → una sola notificación)."""
	users = {_employee_user(employee), settings.responsable_rrhh}
	if settings.notificar_supervisor:
		supervisor = frappe.db.get_value("Employee", employee, "reports_to")
		if supervisor:  # sin Reports To -> se omite, no bloquea las demás
			users.add(_employee_user(supervisor))
	if settings.notificar_usuario_adicional:
		users.add(settings.usuario_adicional or None)
	return [u for u in users if u]


def _recipients_escalation(settings):
	"""Escalamiento: responsable de RR. HH. (siempre) + usuario adicional opcional. Dedup."""
	users = {settings.responsable_rrhh}
	if settings.escalar_usuario_adicional:
		users.add(settings.usuario_escalamiento or None)
	return [u for u in users if u]


def _send_alert(recipients, subject, message, checkin):
	"""Entrega la notificación (bell nativo). Punto único de envío — monkeypatcheable en tests."""
	for user in recipients:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"type": "Alert",
				"subject": subject,
				"email_content": message,
				"document_type": "Employee Checkin",
				"document_name": checkin,
			}
		).insert(ignore_permissions=True)
