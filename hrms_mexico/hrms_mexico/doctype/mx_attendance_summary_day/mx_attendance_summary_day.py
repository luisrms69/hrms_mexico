# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class MXAttendanceSummaryDay(Document):
	# Fila diaria del resumen de jornada. Snapshot: no recalcula por sí misma; la llena el padre
	# (`MX Attendance Summary`) de forma idempotente. Ver ADR-0004.
	pass
