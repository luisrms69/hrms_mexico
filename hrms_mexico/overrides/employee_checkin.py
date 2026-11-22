# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

"""Protección de inmutabilidad del marcaje original (Employee Checkin).

ADR-0002: los campos de evidencia (`employee`, `time`, `log_type`) son inmutables desde su creación
y el documento no puede eliminarse por los flujos operativos — ni por un rol de RR. HH. Los campos
técnicos de HRMS (`attendance`, `skip_auto_attendance`, turno, ...) siguen siendo actualizables.

La garantía es a nivel de aplicación (validaciones de documento); rutas privilegiadas
(`db_set`/`qb.update`/SQL directo) quedan fuera de alcance de esta etapa (ver ADR-0002/ADR-0008).
"""

import frappe
from frappe import _

# Campos de evidencia del marcaje original — inmutables tras su creación.
EVIDENCE_FIELDS = ("employee", "time", "log_type")


def protect_evidence(doc, method=None):
	"""Impide modificar los campos de evidencia de un `Employee Checkin` ya existente.

	Permite cambios en campos técnicos que HRMS necesita actualizar (p. ej. `attendance`,
	`skip_auto_attendance`, asignación de turno), ya que no forman parte de la evidencia.
	"""
	if doc.is_new():
		return

	changed = [field for field in EVIDENCE_FIELDS if doc.has_value_changed(field)]
	if changed:
		etiquetas = ", ".join(_(doc.meta.get_label(field)) for field in changed)
		frappe.throw(
			_(
				"El marcaje original (Employee Checkin) es evidencia inmutable: no se pueden"
				" modificar los campos {0}. Registre una corrección por separado mediante"
				" Attendance Request."
			).format(etiquetas),
			title=_("Marcaje inmutable"),
		)


def block_delete(doc, method=None):
	"""Bloquea la eliminación del marcaje original (evidencia), para todos los roles."""
	frappe.throw(
		_(
			"El marcaje original (Employee Checkin) no puede eliminarse: es evidencia. Registre"
			" una corrección por separado mediante Attendance Request."
		),
		title=_("Marcaje inmutable"),
	)


# Roles con operación técnica legítima sobre el marcaje (no son el empleado operativo).
# A estos NO los restringe este `has_permission`; la evidencia igualmente la protegen los hooks.
_PRIVILEGED_ROLES = {"HR Manager", "HR User", "System Manager", "Administrator"}


def has_permission(doc, ptype=None, user=None):
	"""Capa de permisos (no destructiva): el rol Employee no puede `write` ni `delete`
	marcajes originales; sí conserva `create` (captura por PWA `/hrms`).

	Devuelve ``False`` para denegar; ``None`` para no interferir con el flujo de permisos
	nativo (lo que mantiene intactos HR/System y el procesamiento de asistencia, que corren
	con roles privilegiados o ignorando permisos).
	"""
	if ptype not in ("write", "delete"):
		return None

	user = user or frappe.session.user
	if user == "Administrator":
		return None
	if _PRIVILEGED_ROLES & set(frappe.get_roles(user)):
		return None

	# Usuario operativo (p. ej. solo rol Employee): no puede modificar ni eliminar su marcaje.
	return False
