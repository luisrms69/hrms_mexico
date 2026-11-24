# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class MXAttendanceAlert(Document):
	# Control de estado de la alerta F01 (una por marcaje, `employee_checkin` único). Lo gestiona
	# el scheduler (`hrms_mexico.alerts`); no es evidencia.
	pass
