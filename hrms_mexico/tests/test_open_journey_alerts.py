# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

"""Etapa 3 / F01 — alertas por jornada abierta (salida olvidada).

Tests autocontenidos. Verifican detección tras fin de turno + tolerancia, aviso único (dedupe por el
control `MX Attendance Alert`, no por ToDo), respeto de tolerancia/turno completo/sin turno,
escalamiento configurable, resolución (OUT o regularización), destinatarios por empresa, unicidad por
marcaje, reintento ante interrupción y contenido del mensaje (plantilla). Las entregas de notificación
(`_send_alert`) se interceptan.
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


def _ensure_named_company(name, abbr):
	existing = frappe.db.get_value("Company", {"company_name": name}, "name")
	if existing:
		return existing
	return (
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": name,
				"abbr": abbr,
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
		# Registra (checkin, destinatarios) por cada aviso, sin crear Notification Log.
		self._alert_calls = []
		original = alerts._send_alert
		alerts._send_alert = lambda recipients, subject, message, checkin: self._alert_calls.append(
			(checkin, tuple(sorted(recipients)), subject, message)
		)
		self.addCleanup(lambda: setattr(alerts, "_send_alert", original))

	def _set_settings(self, company=None, **kw):
		"""Upsert de la configuración de alertas de UNA empresa (por defecto, la del test)."""
		company = company or self.company
		name = frappe.db.exists("MX Attendance Settings", {"company": company})
		s = (
			frappe.get_doc("MX Attendance Settings", name)
			if name
			else frappe.new_doc("MX Attendance Settings")
		)
		s.company = company
		base = dict(
			alerta_activa=1,
			tolerancia_minutos=0,
			responsable_rrhh="Administrator",  # obligatorio por empresa; siempre recibe
			notificar_supervisor=0,
			notificar_usuario_adicional=0,
			usuario_adicional=None,
			escalamiento_activo=0,
			horas_escalamiento=4,
			escalar_usuario_adicional=0,
			usuario_escalamiento=None,
		)
		base.update(kw)
		for k, v in base.items():
			setattr(s, k, v)
		s.save(ignore_permissions=True)
		return s

	def _ensure_user(self, email=None):
		email = email or f"mxu_{frappe.generate_hash(length=6)}@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "MX Test",
					"send_welcome_email": 0,
					"roles": [{"role": "Employee"}],
				}
			).insert(ignore_permissions=True)
		return email

	def _recipients_for(self, checkin):
		users = set()
		for call in self._alert_calls:
			if call[0] == checkin:
				users.update(call[1])
		return users

	def _messages_for(self, checkin):
		return [(call[2], call[3]) for call in self._alert_calls if call[0] == checkin]

	def _checkin(self, dt, log_type, with_shift=True, employee=None):
		doc = frappe.get_doc(
			{
				"doctype": "Employee Checkin",
				"employee": employee or self.employee,
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
		return [c for c in self._alert_calls if c[0] == checkin]

	def _alert(self, checkin):
		"""Control MX Attendance Alert de la incidencia (o None)."""
		name = frappe.db.exists("MX Attendance Alert", {"employee_checkin": checkin})
		return frappe.get_doc("MX Attendance Alert", name) if name else None

	# ---------------------------------------------------------------- casos
	def test_alert_after_shift_end(self):
		self._set_settings()
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		self.assertEqual(len(self._alerts_for(c)), 1)
		alert = self._alert(c)
		self.assertIsNotNone(alert)
		self.assertTrue(alert.aviso_enviado_el)

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
		self.assertIsNone(self._alert(c))

	def test_complete_journey_no_alert(self):
		self._set_settings()
		c_in = self._checkin(f"{D} 09:00:00", "IN")
		c_out = self._checkin(f"{D} 17:05:00", "OUT")
		alerts.check_open_journeys(as_of=AFTER)
		self.assertEqual(len(self._alerts_for(c_in)), 0)
		self.assertEqual(len(self._alerts_for(c_out)), 0)
		self.assertIsNone(self._alert(c_in))

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
		self.assertTrue(self._alert(c).escalamiento_enviado_el)
		# Tercera corrida: no re-escala.
		alerts.check_open_journeys(as_of=ESCALATE_AFTER)
		self.assertEqual(len(self._alerts_for(c)), 2)

	def test_resolution_on_out(self):
		self._set_settings()
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		self.assertEqual(len(self._alerts_for(c)), 1)
		# Aparece la salida -> jornada completa -> resuelta: no se envían más avisos.
		self._checkin(f"{D} 18:00:00", "OUT")
		alerts.check_open_journeys(as_of=f"{D} 19:00:00")
		self.assertEqual(len(self._alerts_for(c)), 1)

	def test_resolution_on_regularization(self):
		self._set_settings()
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		before = len(self._alerts_for(c))
		# Regularización aprobada -> resuelta: sin nuevo aviso.
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
		alerts.check_open_journeys(as_of=f"{D} 20:00:00")
		self.assertEqual(len(self._alerts_for(c)), before)  # no nuevo aviso

	# ---------------------------------------------------------------- F07-F13: destinatarios y defaults
	def test_defaults_meta(self):
		meta = frappe.get_meta("MX Attendance Settings")
		self.assertFalse(meta.issingle)  # ya no es Single: una configuración por empresa
		self.assertTrue(meta.get_field("company").reqd)
		self.assertTrue(meta.get_field("company").unique)  # sin duplicados por empresa
		self.assertEqual(meta.get_field("alerta_activa").default, "1")  # F07
		self.assertEqual(meta.get_field("tolerancia_minutos").default, "15")  # F08
		self.assertTrue(meta.get_field("responsable_rrhh").reqd)  # RR. HH. obligatorio por empresa
		# Sin selectores excluyentes (F11):
		self.assertIsNone(meta.get_field("destinatario_adicional"))
		self.assertIsNone(meta.get_field("escalar_a"))

	def test_rrhh_always_notified(self):
		self._set_settings(responsable_rrhh="Administrator")
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		self.assertIn("Administrator", self._recipients_for(c))

	def test_employee_always_notified(self):
		email = self._ensure_user()
		frappe.db.set_value("Employee", self.employee, "user_id", email)
		self._set_settings(responsable_rrhh="Administrator")
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		recips = self._recipients_for(c)
		self.assertIn(email, recips)  # empleado
		self.assertIn("Administrator", recips)  # RR. HH.

	def test_supervisor_notified_when_configured(self):
		sup_email = self._ensure_user()
		supervisor = _ensure_employee(f"MXsup {frappe.generate_hash(length=6)}", self.company)
		frappe.db.set_value("Employee", supervisor, "user_id", sup_email)
		frappe.db.set_value("Employee", self.employee, "reports_to", supervisor)
		self._set_settings(notificar_supervisor=1)
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		self.assertIn(sup_email, self._recipients_for(c))

	def test_no_reports_to_does_not_block(self):
		# Supervisor activado pero el empleado no tiene Reports To: no bloquea; RR. HH. sí recibe.
		self._set_settings(notificar_supervisor=1, responsable_rrhh="Administrator")
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		self.assertIn("Administrator", self._recipients_for(c))

	def test_additional_user_notified(self):
		extra = self._ensure_user()
		self._set_settings(notificar_usuario_adicional=1, usuario_adicional=extra)
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		self.assertIn(extra, self._recipients_for(c))

	def test_dedup_same_user_multiple_roles(self):
		# Mismo User como empleado, RR. HH. y usuario adicional -> una sola notificación.
		email = self._ensure_user()
		frappe.db.set_value("Employee", self.employee, "user_id", email)
		self._set_settings(responsable_rrhh=email, notificar_usuario_adicional=1, usuario_adicional=email)
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		self.assertEqual(self._recipients_for(c), {email})  # sin duplicados

	def test_no_rrhh_no_crash_no_alert(self):
		# Alertas activas pero sin responsable de RR. HH. de la empresa: no falla y no envía.
		s = self._set_settings(responsable_rrhh="Administrator")
		frappe.db.set_value("MX Attendance Settings", s.name, "responsable_rrhh", None)
		frappe.clear_document_cache("MX Attendance Settings", s.name)
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)  # no debe lanzar
		self.assertEqual(len(self._alerts_for(c)), 0)

	# ---------------------------------------------------------------- multiempresa
	def test_two_companies_separate_recipients(self):
		# Empresa A (self.company) con responsable A; Empresa B con responsable B.
		rrhh_a = self._ensure_user()
		self._set_settings(company=self.company, responsable_rrhh=rrhh_a)
		company_b = _ensure_named_company("MX Test Co B", "MXB")
		rrhh_b = self._ensure_user()
		self._set_settings(company=company_b, responsable_rrhh=rrhh_b)
		# El empleado del test está en la empresa A: solo debe notificarse al responsable de A.
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		recips = self._recipients_for(c)
		self.assertIn(rrhh_a, recips)
		self.assertNotIn(rrhh_b, recips)  # nunca el responsable de otra empresa

	def test_missing_company_settings_skips(self):
		# Empleado de una empresa SIN configuración: no alerta, no falla, no usa destinatarios de otra.
		self._set_settings(company=self.company, responsable_rrhh="Administrator")  # otra empresa SÍ tiene
		company_c = _ensure_named_company("MX Test Co C", "MXC")
		emp_c = _ensure_employee(f"MXc {frappe.generate_hash(length=6)}", company_c)
		c = self._checkin(f"{D} 09:00:00", "IN", employee=emp_c)
		alerts.check_open_journeys(as_of=AFTER)  # no debe lanzar
		self.assertEqual(len(self._alerts_for(c)), 0)

	def test_escalation_goes_to_rrhh(self):
		self._set_settings(escalamiento_activo=1, horas_escalamiento=4, responsable_rrhh="Administrator")
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)  # N0
		alerts.check_open_journeys(as_of=ESCALATE_AFTER)  # N2
		# El escalamiento (segunda llamada) incluye a RR. HH.
		self.assertIn("Administrator", self._recipients_for(c))
		self.assertEqual(len(self._alerts_for(c)), 2)

	# ---------------------------------------------------------------- control de incidencia (dedup/concurrencia)
	def test_unique_incidence_per_checkin(self):
		# El índice único por marcaje garantiza una sola incidencia (base de la seguridad concurrente).
		c = self._checkin(f"{D} 09:00:00", "IN")
		frappe.get_doc({"doctype": "MX Attendance Alert", "employee_checkin": c}).insert(
			ignore_permissions=True
		)
		dup = frappe.get_doc({"doctype": "MX Attendance Alert", "employee_checkin": c})
		self.assertRaises(frappe.exceptions.DuplicateEntryError, dup.insert)

	def test_interrupted_send_is_retriable(self):
		# Si el envío se interrumpe, el control NO queda sellado -> el siguiente ciclo reintenta sin duplicar.
		self._set_settings()
		c = self._checkin(f"{D} 09:00:00", "IN")

		def _boom(*a, **k):
			raise RuntimeError("interrupción simulada durante el envío")

		original = alerts._send_alert
		alerts._send_alert = _boom
		try:
			self.assertRaises(RuntimeError, alerts.check_open_journeys, as_of=AFTER)
		finally:
			alerts._send_alert = original
		# El control existe pero SIN sello (el sello va después del envío) -> reintetable.
		alert = self._alert(c)
		self.assertIsNotNone(alert)
		self.assertIsNone(alert.aviso_enviado_el)
		# Reintento normal (con el envío restaurado + el monkeypatch de captura de setUp): avisa una vez.
		original2 = alerts._send_alert
		alerts._send_alert = lambda recipients, subject, message, checkin: self._alert_calls.append(
			(checkin, tuple(sorted(recipients)), subject, message)
		)
		try:
			alerts.check_open_journeys(as_of=AFTER)
		finally:
			alerts._send_alert = original2
		self.assertEqual(len(self._alerts_for(c)), 1)
		self.assertTrue(self._alert(c).aviso_enviado_el)

	def test_message_includes_employee_and_journey_data(self):
		# El mensaje (plantilla por defecto) debe identificar empleado, empresa y jornada.
		email = self._ensure_user()
		frappe.db.set_value("Employee", self.employee, "user_id", email)
		emp = frappe.db.get_value(
			"Employee", self.employee, ["employee_name", "employee_number"], as_dict=True
		)
		self._set_settings()
		c = self._checkin(f"{D} 09:00:00", "IN")
		alerts.check_open_journeys(as_of=AFTER)
		msgs = self._messages_for(c)
		self.assertTrue(msgs)
		subject, body = msgs[0]
		blob = f"{subject} {body}"
		self.assertIn(emp.employee_name, blob)
		self.assertIn("17:00", blob)  # hora esperada de salida (shift_end)
