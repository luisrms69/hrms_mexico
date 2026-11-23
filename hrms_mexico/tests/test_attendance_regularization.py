# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

"""Etapa 3 / ADR-0005 — regularización vía `Attendance Request` MX.

Tests autocontenidos. Verifican: una fecha por solicitud, reconocimiento desde la solicitud aprobada,
sustitución (no suma) en el resumen, evidencia original intacta, autorizador registrado al aprobar,
y rectificación de un resumen confirmado mediante nueva versión (amend) conservando la anterior.
"""

import frappe
from frappe.tests import IntegrationTestCase

from hrms_mexico import recognition

DAY = "2026-03-09"  # lunes, pasado


def _ensure_gender(gender="Male"):
	if not frappe.db.exists("Gender", gender):
		frappe.get_doc({"doctype": "Gender", "gender": gender}).insert(ignore_permissions=True)
	return gender


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


class TestAttendanceRegularization(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _ensure_company()
		frappe.db.commit()  # nosemgrep -- datos base del test

	def setUp(self):
		self.employee = _ensure_employee(f"MXR {frappe.generate_hash(length=8)}", self.company)

	# ---------------------------------------------------------------- helpers
	def _checkin(self, dt, log_type):
		return (
			frappe.get_doc(
				{
					"doctype": "Employee Checkin",
					"employee": self.employee,
					"time": dt,
					"log_type": log_type,
					"skip_auto_attendance": 1,
				}
			)
			.insert()
			.name
		)

	def _attendance_request(
		self, categoria="Salida olvidada", minutos=480, from_date=DAY, to_date=DAY, submit=True
	):
		doc = frappe.get_doc(
			{
				"doctype": "Attendance Request",
				"employee": self.employee,
				"company": self.company,
				"from_date": from_date,
				"to_date": to_date,
				"reason": "On Duty",
				"include_holidays": 1,
				"explanation": "Prueba de regularización",
				"custom_mx_categoria": categoria,
				"custom_mx_minutos_reconocidos": minutos,
			}
		)
		doc.insert(ignore_permissions=True)
		if submit:
			doc.submit()
		return doc

	def _summary(self, start=DAY, end=DAY, as_of="2026-03-12 08:00:00"):
		doc = frappe.get_doc(
			{
				"doctype": "MX Attendance Summary",
				"employee": self.employee,
				"period_start": start,
				"period_end": end,
			}
		)
		doc.flags.as_of = as_of
		return doc.insert()

	# ---------------------------------------------------------------- casos
	def test_one_date_per_request(self):
		doc = frappe.get_doc(
			{
				"doctype": "Attendance Request",
				"employee": self.employee,
				"company": self.company,
				"from_date": DAY,
				"to_date": "2026-03-10",
				"reason": "On Duty",
				"include_holidays": 1,
				"custom_mx_categoria": "Salida olvidada",
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_non_mx_request_allows_range(self):
		# Un Attendance Request nativo (sin categoría MX) no queda limitado a una fecha por nuestra regla.
		doc = frappe.get_doc(
			{
				"doctype": "Attendance Request",
				"employee": self.employee,
				"company": self.company,
				"from_date": DAY,
				"to_date": "2026-03-10",
				"reason": "Work From Home",
				"include_holidays": 1,
			}
		)
		doc.insert(ignore_permissions=True)  # no debe lanzar por nuestra regla MX
		self.assertTrue(frappe.db.exists("Attendance Request", doc.name))

	def test_recognized_minutes_from_approved_request(self):
		self._attendance_request(minutos=480)
		self.assertEqual(recognition.recognized_minutes_for(self.employee, DAY), 480)

	def test_non_mx_request_is_not_recognized(self):
		self._attendance_request(categoria="", minutos=0)  # sin categoría MX
		self.assertIsNone(recognition.recognized_minutes_for(self.employee, DAY))

	def test_authorizer_recorded_on_approval(self):
		doc = self._attendance_request()
		self.assertEqual(doc.custom_mx_autorizador, frappe.session.user)

	def test_substitution_in_summary_replaces_not_adds(self):
		# Jornada de 4h (09-13) + regularización de 480 min -> 8h (sustituye, no 12).
		self._checkin(f"{DAY} 09:00:00", "IN")
		self._checkin(f"{DAY} 13:00:00", "OUT")
		self._attendance_request(minutos=480)
		s = self._summary()
		row = next(d for d in s.days if str(d.date) == DAY)
		self.assertEqual(row.recognized_minutes, 480)
		self.assertEqual(row.computed_hours, 8.0)
		self.assertEqual(s.total_computed_hours, 8.0)

	def test_original_checkin_preserved(self):
		c_in = self._checkin(f"{DAY} 09:00:00", "IN")
		before = frappe.db.get_value("Employee Checkin", c_in, ["time", "log_type"], as_dict=True)
		self._attendance_request(minutos=480)
		after = frappe.db.get_value("Employee Checkin", c_in, ["time", "log_type"], as_dict=True)
		self.assertEqual(before, after)

	# --- Prohibición de cancel/amend sobre el resumen confirmado (evidencia) ---

	def _confirmed_summary(self):
		self._checkin(f"{DAY} 09:00:00", "IN")
		self._checkin(f"{DAY} 13:00:00", "OUT")
		v1 = self._summary()
		v1.submit()
		return v1

	def test_confirmed_summary_cannot_be_cancelled(self):
		v1 = self._confirmed_summary()
		self.assertRaises(frappe.ValidationError, v1.cancel)
		self.assertEqual(frappe.db.get_value("MX Attendance Summary", v1.name, "docstatus"), 1)

	def test_confirmed_summary_cannot_be_modified(self):
		v1 = self._confirmed_summary()
		v1.period_end = "2026-03-31"
		self.assertRaises(frappe.exceptions.UpdateAfterSubmitError, v1.save)

	def test_confirmed_summary_cannot_be_deleted(self):
		v1 = self._confirmed_summary()
		self.assertRaises(frappe.exceptions.ValidationError, v1.delete)
		self.assertTrue(frappe.db.exists("MX Attendance Summary", v1.name))

	def test_amend_mechanism_disabled(self):
		# El DocType ya no tiene `amended_from` ni permiso de amend/cancel para ningún rol.
		meta = frappe.get_meta("MX Attendance Summary")
		self.assertIsNone(meta.get_field("amended_from"))
		for perm in meta.permissions:
			self.assertFalse(perm.amend, msg=f"amend debería estar deshabilitado para {perm.role}")
			self.assertFalse(perm.cancel, msg=f"cancel debería estar deshabilitado para {perm.role}")

	def test_rectification_reference_integrity(self):
		# rectifica_a debe apuntar a un resumen confirmado existente (referencia inequívoca).
		doc = frappe.get_doc(
			{
				"doctype": "MX Attendance Summary",
				"employee": self.employee,
				"period_start": DAY,
				"period_end": DAY,
				"rectifica_a": "MXAS-INEXISTENTE-000",
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_rectification_is_independent_document(self):
		v1 = self._confirmed_summary()
		# Regularización aprobada después del cierre.
		self._attendance_request(minutos=480)
		# Rectificación = documento NUEVO e independiente; el original no se toca.
		v2_name = v1.create_rectification()
		v2 = frappe.get_doc("MX Attendance Summary", v2_name)
		v2.flags.as_of = "2026-03-12 08:00:00"
		v2.save()  # reconstruye con la regularización vigente
		v2.submit()

		# Original intacto y confirmado.
		self.assertEqual(frappe.db.get_value("MX Attendance Summary", v1.name, "docstatus"), 1)
		self.assertNotEqual(v2.name, v1.name)
		self.assertEqual(v2.rectifica_a, v1.name)
		# Ambas versiones conservan su detalle/evidencia.
		self.assertTrue(len(frappe.get_doc("MX Attendance Summary", v1.name).days) >= 1)
		row2 = next(d for d in v2.days if str(d.date) == DAY)
		self.assertEqual(row2.computed_hours, 8.0)  # la rectificación refleja la regularización
