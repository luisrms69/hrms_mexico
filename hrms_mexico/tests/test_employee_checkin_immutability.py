# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

"""Etapa 1 / ADR-0002 — inmutabilidad de la evidencia del marcaje original (Employee Checkin).

Tests autocontenidos: crean su propia Company/Employee con `frappe`, sin depender de las suites
de ERPNext/HRMS (evita el bootstrap acoplado a los datos de prueba de ERPNext).

Verifica que:
- `employee`, `time` y `log_type` no pueden modificarse tras crear el marcaje (ningún rol).
- el marcaje original no puede eliminarse.
- las actualizaciones técnicas legítimas de HRMS (p. ej. `skip_auto_attendance`) SÍ se permiten.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime


def _ensure_gender(gender="Male"):
	if not frappe.db.exists("Gender", gender):
		frappe.get_doc({"doctype": "Gender", "gender": gender}).insert(ignore_permissions=True)
	return gender


def _ensure_company():
	existing = frappe.db.get_value("Company", {}, "name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": "MX Test Co",
			"abbr": "MXTC",
			"default_currency": "MXN",
			"country": "Mexico",
		}
	).insert(ignore_permissions=True)
	return doc.name


def _ensure_employee(first_name, company):
	existing = frappe.db.get_value("Employee", {"employee_name": first_name, "company": company}, "name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": first_name,
			"company": company,
			"status": "Active",
			"gender": _ensure_gender(),
			"date_of_birth": "1990-01-01",
			"date_of_joining": "2020-01-01",
		}
	).insert(ignore_permissions=True)
	return doc.name


def _ensure_employee_user(email):
	"""Usuario operativo con solo el rol Employee (simula el empleado que marca por PWA)."""
	if frappe.db.exists("User", email):
		return email
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "MX Empleado",
			"send_welcome_email": 0,
			"roles": [{"role": "Employee"}],
		}
	).insert(ignore_permissions=True)
	return email


class TestEmployeeCheckinImmutability(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _ensure_company()
		cls.employee = _ensure_employee("MX Immut One", cls.company)
		cls.other_employee = _ensure_employee("MX Immut Two", cls.company)
		cls.employee_user = _ensure_employee_user("mx_checkin_employee@example.com")
		frappe.db.commit()  # nosemgrep -- datos base del test, fuera de la transacción por-test

	_seq = 0

	def _make_checkin(self, log_type="IN"):
		# Timestamp único por checkin (evita la validación nativa de "mismo timestamp").
		type(self)._seq += 1
		marca = add_to_date(now_datetime(), seconds=-90 * type(self)._seq)
		return frappe.get_doc(
			{
				"doctype": "Employee Checkin",
				"employee": self.employee,
				"time": marca,
				"log_type": log_type,
			}
		).insert()

	def test_cannot_edit_time(self):
		checkin = self._make_checkin()
		checkin.time = add_to_date(checkin.time, hours=1)
		self.assertRaises(frappe.ValidationError, checkin.save)

	def test_cannot_edit_log_type(self):
		checkin = self._make_checkin(log_type="IN")
		checkin.log_type = "OUT"
		self.assertRaises(frappe.ValidationError, checkin.save)

	def test_cannot_edit_employee(self):
		checkin = self._make_checkin()
		checkin.employee = self.other_employee
		self.assertRaises(frappe.ValidationError, checkin.save)

	def test_cannot_delete_original_checkin(self):
		checkin = self._make_checkin()
		self.assertRaises(frappe.ValidationError, checkin.delete)
		self.assertTrue(frappe.db.exists("Employee Checkin", checkin.name))

	def test_allows_legitimate_technical_update(self):
		"""Un campo técnico de HRMS (no evidencia) debe poder actualizarse sin bloqueo."""
		checkin = self._make_checkin()
		checkin.skip_auto_attendance = 1
		checkin.save()  # no debe lanzar
		self.assertEqual(frappe.db.get_value("Employee Checkin", checkin.name, "skip_auto_attendance"), 1)

	def test_unchanged_resave_is_allowed(self):
		"""Reguardar sin cambiar la evidencia no debe bloquearse."""
		checkin = self._make_checkin()
		checkin.save()  # no debe lanzar
		self.assertTrue(frappe.db.exists("Employee Checkin", checkin.name))

	# --- Capa nativa: set_only_once (Property Setters, aplicados por migrate) ---

	def test_set_only_once_applied_on_evidence_fields(self):
		meta = frappe.get_meta("Employee Checkin")
		for field in ("employee", "time", "log_type"):
			self.assertTrue(
				meta.get_field(field).set_only_once,
				msg=f"set_only_once debería estar activo en {field}",
			)

	# --- Capa nativa: permisos del rol Employee (has_permission hook) ---

	def test_employee_role_cannot_write_or_delete(self):
		checkin = self._make_checkin()
		self.assertFalse(
			frappe.has_permission("Employee Checkin", "write", doc=checkin, user=self.employee_user)
		)
		self.assertFalse(
			frappe.has_permission("Employee Checkin", "delete", doc=checkin, user=self.employee_user)
		)

	def test_has_permission_hook_does_not_block_create_or_read(self):
		# La captura normal (PWA /hrms) depende de que nuestro hook NO interfiera con `create`.
		# Verificamos la contribución de hrms_mexico (devuelve None = no opina) para create/read,
		# de modo que el permiso nativo del rol Employee (create=1) se conserve intacto.
		from hrms_mexico.overrides.employee_checkin import has_permission as ec_has_permission

		self.assertIsNone(ec_has_permission(None, "create", self.employee_user))
		self.assertIsNone(ec_has_permission(None, "read", self.employee_user))

	def test_hr_role_not_restricted_by_has_permission(self):
		# HR Manager no es restringido por el hook de permisos (la evidencia la protegen los doc_events).
		hr_user = "Administrator"
		checkin = self._make_checkin()
		self.assertTrue(frappe.has_permission("Employee Checkin", "read", doc=checkin, user=hr_user))
