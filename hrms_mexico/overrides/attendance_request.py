# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

"""Regularización de asistencia (Etapa 3, ADR-0005) sobre `Attendance Request` nativo.

Se reutiliza el DocType nativo `Attendance Request` (submittable; el *submit* nativo es la aprobación
de RR. HH.). `hrms_mexico` añade, vía Custom Fields, la categoría MX, los **minutos reconocidos**, la
evidencia y el autorizador, y aplica dos reglas por hooks, **sin** modificar el core ni los
`Employee Checkin`:

- **Una fecha por solicitud** cuando es una regularización MX (categoría MX presente).
- Registrar el **autorizador** al aprobar (submit).

Los minutos reconocidos **sustituyen** (no suman) las horas calculadas; esa sustitución la aplica
`MX Attendance Summary` leyendo esta solicitud aprobada (ver `hrms_mexico.recognition`).
"""

import frappe
from frappe import _
from frappe.utils import getdate


def _is_mx_regularization(doc) -> bool:
	return bool(doc.get("custom_mx_categoria"))


def validate(doc, method=None):
	"""Regla de una sola fecha para las regularizaciones MX (no afecta al Attendance Request nativo)."""
	if not _is_mx_regularization(doc):
		return
	if getdate(doc.from_date) != getdate(doc.to_date):
		frappe.throw(
			_(
				"Una regularización de asistencia (México) abarca una sola fecha: «desde» y «hasta» deben coincidir."
			),
			title=_("Una fecha por solicitud"),
		)


def before_submit(doc, method=None):
	"""Deja constancia de quién aprueba la regularización MX (autorizador)."""
	if _is_mx_regularization(doc) and not doc.get("custom_mx_autorizador"):
		doc.custom_mx_autorizador = frappe.session.user
