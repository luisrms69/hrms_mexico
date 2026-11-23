# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

"""Seam de "minutos reconocidos" (ADR-0004 / ADR-0005).

La **regla de sustitución** (ADR-0005) dice que, cuando una jornada tiene minutos reconocidos por una
corrección aprobada, esos minutos **sustituyen** (no suman) a las horas calculadas por HRMS en el
resumen de jornada (`MX Attendance Summary`).

En la **Etapa 2** aquí vive únicamente el *punto de extensión* (seam): `recognized_minutes_for`
devuelve ``None`` (no hay minutos reconocidos). La **fuente real** —Custom Fields en `Attendance
Request` aprobado— se cablea en la **Etapa 3** reemplazando el cuerpo de esta función, sin tocar el
consumidor (`MX Attendance Summary`).

No se persisten datos simulados: los tests inyectan minutos reconocidos monkeypatcheando esta función.
"""

import frappe


def recognized_minutes_for(employee: str, date) -> int | None:
	"""Minutos de jornada reconocidos para `employee` en `date`, o ``None`` si no hay.

	Contrato (estable para la Etapa 3):
	- ``None``  → no hay reconocimiento; el resumen usa las horas nativas de HRMS.
	- ``int``   → minutos reconocidos; **sustituyen** (no suman) a las horas nativas.

	Etapa 2: siempre ``None`` (la fuente `Attendance Request` llega en la Etapa 3).
	"""
	# Etapa 3 (ADR-0005): consultar aquí el/los `Attendance Request` aprobado(s) de ese empleado/fecha
	# y devolver los minutos reconocidos. Hasta entonces, no hay reconocimiento.
	del employee, date  # sin uso en la Etapa 2; se documentan para la firma estable
	return None
