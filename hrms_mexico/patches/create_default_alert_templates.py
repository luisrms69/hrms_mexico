# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

"""Crea las plantillas por defecto (Email Template) de las alertas F01 — SOLO si no existen.

Se usa un patch (create-if-absent), **no** fixtures, para que las **migraciones futuras no
sobrescriban** las ediciones que RR. HH. haga sobre estas plantillas. El patch se ejecuta una sola vez
(queda registrado en patches.txt); si la plantilla ya existe, no la toca.
"""

import frappe

AVISO = "MX Aviso Jornada Abierta"
ESCALAMIENTO = "MX Escalamiento Jornada Abierta"

_AVISO_HTML = """<p>Estimado/a <b>{{ employee_name }}</b> ({{ employee_number or "sin número" }}),</p>
<p>Se registró una <b>entrada sin la salida correspondiente</b> en su jornada:</p>
<ul>
  <li><b>Empresa:</b> {{ company }}</li>
  <li><b>Entrada (IN):</b> {{ in_time }}</li>
  <li><b>Turno:</b> {{ shift or "—" }} &mdash; salida esperada: <b>{{ shift_end }}</b></li>
  <li><b>Motivo:</b> {{ motivo }}</li>
</ul>
<p>{{ instruccion }}</p>"""

_ESCALAMIENTO_HTML = """<p><b>Escalamiento</b> — jornada con entrada sin salida sin atender.</p>
<ul>
  <li><b>Empleado:</b> {{ employee_name }} ({{ employee_number or "sin número" }})</li>
  <li><b>Empresa:</b> {{ company }}</li>
  <li><b>Entrada (IN):</b> {{ in_time }}</li>
  <li><b>Turno:</b> {{ shift or "—" }} &mdash; salida esperada: <b>{{ shift_end }}</b></li>
  <li><b>Motivo:</b> {{ motivo }}</li>
</ul>
<p>La incidencia no ha sido atendida ni regularizada. {{ instruccion }}</p>"""


def execute():
	_ensure(AVISO, "Jornada sin salida registrada — {{ employee_name }}", _AVISO_HTML)
	_ensure(
		ESCALAMIENTO,
		"Escalamiento: jornada sin salida sin atender — {{ employee_name }}",
		_ESCALAMIENTO_HTML,
	)


def _ensure(name, subject, response_html):
	if frappe.db.exists("Email Template", name):
		return  # ya existe (posiblemente editada por RR. HH.) — no se sobrescribe
	frappe.get_doc(
		{
			"doctype": "Email Template",
			"name": name,
			"subject": subject,
			"use_html": 1,
			"response_html": response_html,
		}
	).insert(ignore_permissions=True)
