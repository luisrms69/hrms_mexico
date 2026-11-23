# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

"""Etapa 3 / F01 — alertas por jornada abierta (salida olvidada).

Tests autocontenidos. Verifican detección tras fin de turno + tolerancia, aviso único (dedupe por
ToDo), respeto de tolerancia/turno completo/sin turno, escalamiento configurable, y cese al aparecer
OUT o una regularización aprobada. Las entregas de notificación (`_send_alert`) se interceptan.
"""

import frappe
from frappe.tests import IntegrationTestCase

from hrms_mexico import alerts

D = "2026-03-16"
SHIFT_START = f"{D} 08:00:00"
SHIFT_END = f"{D} 17:00:00"
AFTER = f"{D} 17:30:00"  # tras fin de turno
ESCALATE_AFTER = f"{D} 21:30:00"  # fin de turno + 4 h


def _ensure_company():
	existing = frappe.db.get_value("Company", {}, "name")
	if existing:
		return existing
	return (
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "MX Test Co",
				"abbr": "MXTC",
				"default_currency": "MXN",
				"country": "Mexico",
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def _ensure_gender(gender="Male"):
	if not frappe.db.exists("Gender", gender):
		frappe.get_doc({"doctype": "Gender", "gender": gender}).insert(ignore_permissions=True)
	return gender


def _ensure_employee(first_name, company):
	existing = frappe.db.get_value("Employee", {"employee_name": first_name, "company": company}, "name")
	if existing:
		return existing
	return (
		frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": first_name,
				"company": company,
				"status": "Active",
				"gender": _ensure_gender(),
				"date_of_birth": "1990-01-01",
				"date_of_joining": "2020-01-01",
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


class TestOpenJourneyAlerts(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _ensure_company()
		frappe.db.commit()  # nosemgrep -- datos base del test

	def setUp(self):
		self.employee = _ensure_employee(f"MXA {frappe.generate_hash(length=8)}", self.company)
		# Interceptar la entrega de notificaciones (no crear Notification Log en tests).
		self._alert_calls = []
		original = alerts._send_alert
		alerts._send_alert = lambda recipients, subject, message, checkin: self._alert_calls.append(checkin)
		self.addCleanup(lambda: setattr(alerts, "_send_alert", original))

	def _set_settings(self, **kw):
		s = frappe.get_doc("MX Attendance Settings")
		base = dict(
			alerta_activa=1,
			tolerancia_minutos=0,
			destinatario_adicional="Ninguno",
			escalamiento_activo=0,
			horas_escalamiento=4,
			escalar_a="Supervisor (Reports To)",
		)
		base.update(kw)
		for k, v in base.items():
			setattr(s, k, v)
		s.save(ignore_permissions=True)

	def _checkin(self, dt, log_type, with_shift=True):
		doc = frappe.get_doc(
			{
				"doctype": "Employee Checkin",
				"employee": self.employee,
				"time": dt,
				"log_type": log_type,
				"skip_auto_attendance": 1,
			}
		)
		if with_shift:
			doc.shift_start = SHIFT_START
			doc.shift_end = SHIFT_END
		return doc.insert().name

	def _alerts_for(self, checkin):
		return [c for c in self._alert_calls if c == checkin]

	def _open_todo(self, checkin):
		return frappe.db.exists(
			"ToDo",
			{
				"reference_type": "Employee Checkin",
				"reference_name": checkin,
				"status": "Open",
				"description": ("like", "%MX-ALERTA-JORNADA%"),
			},
		)

	# ---------------------------------------------------------------- casos
	def test_alert_after_shift_end(self):
		self._set_settings()
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		self.assertEqual(len(self._alerts_for(c)), 1)
		self.assertTrue(self._open_todo(c))

	def test_dedup_no_duplicate(self):
		self._set_settings()
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		alerts.check_open_journeys(as_of=AFTER)  # segunda corrida: no re-avisa
		self.assertEqual(len(self._alerts_for(c)), 1)

	def test_within_tolerance_no_alert(self):
		self._set_settings(tolerancia_minutos=120)  # cutoff 19:00
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)  # 17:30 < 19:00
		self.assertEqual(len(self._alerts_for(c)), 0)
		self.assertFalse(self._open_todo(c))

	def test_complete_journey_no_alert(self):
		self._set_settings()
		c_in = self._checkin(f"{D} 09:00:00", "IN")
		c_out = self._checkin(f"{D} 17:05:00", "OUT")
		alerts.check_open_journeys(as_of=AFTER)
		self.assertEqual(len(self._alerts_for(c_in)), 0)
		self.assertEqual(len(self._alerts_for(c_out)), 0)
		self.assertFalse(self._open_todo(c_in))

	def test_no_shift_no_alert(self):
		self._set_settings()
		c = self._checkin(f"{D} 09:00:00", "IN", with_shift=False)
		alerts.check_open_journeys(as_of=AFTER)
		self.assertEqual(len(self._alerts_for(c)), 0)

	def test_alerts_off(self):
		self._set_settings(alerta_activa=0)
		self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		self.assertEqual(self._alert_calls, [])

	def test_escalation(self):
		self._set_settings(escalamiento_activo=1, horas_escalamiento=4)
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)  # N0
		self.assertEqual(len(self._alerts_for(c)), 1)
		alerts.check_open_journeys(as_of=ESCALATE_AFTER)  # N2
		self.assertEqual(len(self._alerts_for(c)), 2)
		todo = frappe.get_doc("ToDo", self._open_todo(c))
		self.assertEqual(todo.priority, "High")
		# Tercera corrida: no re-escala.
		alerts.check_open_journeys(as_of=ESCALATE_AFTER)
		self.assertEqual(len(self._alerts_for(c)), 2)

	def test_cese_on_out(self):
		self._set_settings()
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		self.assertTrue(self._open_todo(c))
		# Aparece la salida -> jornada completa -> cese (ToDo cerrado).
		self._checkin(f"{D} 18:00:00", "OUT")
		alerts.check_open_journeys(as_of=f"{D} 19:00:00")
		self.assertFalse(self._open_todo(c))

	def test_cese_on_regularization(self):
		self._set_settings()
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		self.assertTrue(self._open_todo(c))
		# Regularización aprobada -> cese y sin nuevo aviso.
		frappe.get_doc(
			{
				"doctype": "Attendance Request",
				"employee": self.employee,
				"company": self.company,
				"from_date": D,
				"to_date": D,
				"reason": "On Duty",
				"include_holidays": 1,
				"custom_mx_categoria": "Salida olvidada",
				"custom_mx_minutos_reconocidos": 480,
			}
		).insert(ignore_permissions=True).submit()
		before = len(self._alerts_for(c))
		alerts.check_open_journeys(as_of=f"{D} 20:00:00")
		self.assertFalse(self._open_todo(c))
		self.assertEqual(len(self._alerts_for(c)), before)  # no nuevo aviso
