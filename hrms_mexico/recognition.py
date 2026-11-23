# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

"""Seam de "minutos reconocidos" (ADR-0004 / ADR-0005).

La **regla de sustitución** (ADR-0005): cuando una jornada tiene minutos reconocidos por una
regularización **aprobada**, esos minutos **sustituyen** (no suman) a las horas calculadas por HRMS en
el resumen de jornada (`MX Attendance Summary`).

**Fuente (Etapa 3):** un `Attendance Request` **aprobado** (`docstatus == 1`) con **categoría MX**
(`custom_mx_categoria`) que cubra la fecha; sus `custom_mx_minutos_reconocidos` son los minutos
reconocidos. Una solicitud sin categoría MX (p. ej. WFH/On Duty nativo) **no** aplica sustitución.

El consumidor (`MX Attendance Summary`) no cambia: solo llama a `recognized_minutes_for`.
"""

import frappe


def recognized_minutes_for(employee: str, date) -> int | None:
	"""Minutos de jornada reconocidos para `employee` en `date`, o ``None`` si no hay.

	Contrato:
	- ``None``  → no hay regularización MX; el resumen usa las horas nativas de HRMS.
	- ``int``   → minutos reconocidos por una regularización MX aprobada; **sustituyen** (no suman).
	"""
	rows = frappe.get_all(
		"Attendance Request",
		filters={
			"employee": employee,
			"docstatus": 1,
			"from_date": ("<=", date),
			"to_date": (">=", date),
		},
		fields=["custom_mx_categoria", "custom_mx_minutos_reconocidos"],
		order_by="modified desc",
	)
	for r in rows:
		# Solo las regularizaciones MX (con categoría) aplican sustitución; el valor puede ser 0
		# (p. ej. jornada reconocida sin tiempo computable), lo cual también sustituye.
		if r.get("custom_mx_categoria"):
			return int(r.get("custom_mx_minutos_reconocidos") or 0)
	return None
