# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

"""F01 — Alertas por jornada abierta (salida olvidada).

Detecta jornadas con **IN sin OUT** cuyo turno ya terminó más una **tolerancia** configurable, y avisa
al empleado (y, opcionalmente, a un destinatario adicional), con **escalamiento** si no se atiende.
**No** crea OUT ficticios, **no** modifica `Employee Checkin`, **no** presume ausencias y **no** toca la
PWA. Usa el **scheduler** y las notificaciones nativas de Frappe.

Estado e idempotencia se apoyan en un **ToDo** nativo por jornada abierta (referencia al `Employee
Checkin` de entrada): su existencia evita duplicados (N0), su antigüedad dispara el escalamiento (N2),
y se **cierra** cuando la incidencia se resuelve (aparece OUT) o hay una **regularización aprobada**
(`Attendance Request` MX). Parámetros en `MX Attendance Settings` (Single).

Respeta turnos nocturnos (usa el `shift_end` real), descansos y jornadas sin turno (sin `shift_end` →
no se evalúan) y jornadas aún dentro de turno (todavía no vence la tolerancia).
"""

from datetime import timedelta

import frappe
from frappe.utils import add_to_date, get_datetime, getdate, now_datetime

from hrms_mexico.hrms_mexico.doctype.mx_attendance_summary.mx_attendance_summary import MXAttendanceSummary

_ALERT_TAG = "MX-ALERTA-JORNADA"
_LOOKBACK_DAYS = 3  # ventana de búsqueda de jornadas abiertas recientes


def check_open_journeys(as_of=None):
	"""Entrada del scheduler (hourly). Procesa avisos, escalamientos y cese de alertas."""
	settings = frappe.get_cached_doc("MX Attendance Settings")
	if not settings.alerta_activa:
		return

	as_of = get_datetime(as_of or now_datetime())
	tolerancia = int(settings.tolerancia_minutos or 0)

	open_journeys = _find_open_journeys(as_of, tolerancia)
	# Una jornada regularizada (Attendance Request MX aprobado) deja de considerarse abierta: no se
	# alerta y su ToDo se cierra en el cese.
	unresolved = [j for j in open_journeys if not _is_regularized(j["employee"], j["date"])]
	open_keys = {j["checkin"] for j in unresolved}

	# Cese: cerrar ToDos cuya jornada ya se resolvió (apareció OUT) o se regularizó.
	_close_resolved_todos(as_of, open_keys)

	for j in unresolved:
		_process_journey(settings, j, as_of)


# ------------------------------------------------------------------ detección
def _find_open_journeys(as_of, tolerancia):
	"""Jornadas con entrada sin salida cuyo turno terminó + tolerancia. Agrupa como el resumen."""
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

	open_journeys = []
	for (employee, day, _shift), logs in groups.items():
		if MXAttendanceSummary._is_complete(logs):
			continue  # jornada cerrada (todos sus pares) → no es olvido de salida
		shift_ends = [l.shift_end for l in logs if l.shift_end]
		if not shift_ends:
			continue  # sin turno (descanso / sin asignación) → no se evalúa
		cutoff = get_datetime(max(shift_ends)) + timedelta(minutes=tolerancia)
		if cutoff >= as_of:
			continue  # el turno aún no cierra (jornada abierta legítima)
		open_journeys.append(
			{"employee": employee, "date": day, "checkin": logs[-1].name, "shift_end": max(shift_ends)}
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


# ------------------------------------------------------------------ proceso por jornada
def _process_journey(settings, journey, as_of):
	todo = _open_todo_for(journey["checkin"])
	if not todo:
		# N0 — primer aviso al empleado (+ destinatario adicional).
		recipients = _recipients_n0(settings, journey["employee"])
		_send_alert(
			recipients,
			subject=frappe._("Jornada sin salida registrada"),
			message=frappe._(
				"Se registró una entrada sin su salida correspondiente. Verifique su marcaje o solicite"
				" una regularización (Attendance Request)."
			),
			checkin=journey["checkin"],
		)
		_create_todo(journey, settings, as_of)
		return

	# Ya avisado: evaluar escalamiento (N2). El umbral se mide desde el fin de turno (datos), no desde
	# la creación del ToDo, para ser determinista: shift_end + tolerancia + horas_escalamiento.
	if not settings.escalamiento_activo or todo.priority == "High":
		return
	escalate_at = (
		get_datetime(journey["shift_end"])
		+ timedelta(minutes=int(settings.tolerancia_minutos or 0))
		+ timedelta(hours=int(settings.horas_escalamiento or 0))
	)
	if as_of < escalate_at:
		return
	recipient = _recipient_escalation(settings, journey["employee"])
	_send_alert(
		[r for r in [recipient] if r],
		subject=frappe._("Escalamiento: jornada sin salida sin atender"),
		message=frappe._(
			"Una jornada con entrada sin salida sigue sin atenderse ni regularizarse. Requiere revisión."
		),
		checkin=journey["checkin"],
	)
	todo.db_set("priority", "High")  # marca escalado (evita re-escalar)


# ------------------------------------------------------------------ cese
def _close_resolved_todos(as_of, open_keys):
	todos = frappe.get_all(
		"ToDo",
		filters={
			"reference_type": "Employee Checkin",
			"status": "Open",
			"description": ("like", f"%{_ALERT_TAG}%"),
		},
		fields=["name", "reference_name"],
	)
	for t in todos:
		# Resuelta si ya no aparece como jornada abierta (apareció OUT) o hay regularización aprobada.
		if t.reference_name not in open_keys:
			frappe.db.set_value("ToDo", t.name, "status", "Closed")


# ------------------------------------------------------------------ helpers de ToDo / destinatarios
def _open_todo_for(checkin):
	name = frappe.db.exists(
		"ToDo",
		{
			"reference_type": "Employee Checkin",
			"reference_name": checkin,
			"status": "Open",
			"description": ("like", f"%{_ALERT_TAG}%"),
		},
	)
	return frappe.get_doc("ToDo", name) if name else None


def _create_todo(journey, settings, as_of):
	user = _employee_user(journey["employee"])
	frappe.get_doc(
		{
			"doctype": "ToDo",
			"status": "Open",
			"priority": "Medium",
			"date": getdate(as_of),
			"allocated_to": user,
			"reference_type": "Employee Checkin",
			"reference_name": journey["checkin"],
			"description": f"[{_ALERT_TAG}] Jornada con entrada sin salida — requiere salida o regularización.",
		}
	).insert(ignore_permissions=True)


def _employee_user(employee):
	return frappe.db.get_value("Employee", employee, "user_id") or None


def _recipients_n0(settings, employee):
	users = {_employee_user(employee)}
	users.add(_recipient_by_option(settings.destinatario_adicional, settings, employee))
	return [u for u in users if u]


def _recipient_escalation(settings, employee):
	return _recipient_by_option(settings.escalar_a, settings, employee)


def _recipient_by_option(option, settings, employee):
	if option == "Supervisor (Reports To)":
		supervisor = frappe.db.get_value("Employee", employee, "reports_to")
		return _employee_user(supervisor) if supervisor else None
	if option == "Responsable de RR. HH.":
		return settings.responsable_rrhh or None
	if option == "Usuario designado":
		# Usuario de aviso o de escalamiento según el campo configurado.
		return settings.usuario_designado or settings.usuario_escalamiento or None
	return None


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
