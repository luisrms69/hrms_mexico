# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

"""Etapa 2 / ADR-0004 — tests de consolidación de `MX Attendance Summary`.

Tests autocontenidos (Company/Employee propios, sin importar suites de ERPNext/HRMS). Cubren:
jornada normal, múltiples pares, jornada abierta vs cerrada-incompleta, cruce de medianoche,
idempotencia, no-mutación del `Employee Checkin`, regla de sustitución (ADR-0005) y snapshot
congelado tras *submit*.

Nota sobre medianoche: el cruce se prueba inyectando `shift_start`/`shift_end` en el `Employee
Checkin` (lo que HRMS calcula vía `fetch_shift`), de modo que el test sea determinista y valide que
**nuestra** consolidación agrupa por `shift_start`. La asignación real de turno (Shift Assignment) se
ejercita en la demostración funcional en vivo.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from hrms_mexico.hrms_mexico.doctype.mx_attendance_summary import mx_attendance_summary as mxas_module

DAY = "2026-03-02"  # lunes; sin turno asignado no dependemos de holiday list
NEXT = "2026-03-03"


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


class TestMXAttendanceSummary(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = _ensure_company()
		frappe.db.commit()  # nosemgrep -- datos base del test, fuera de la transacción por-test

	def setUp(self):
		# Empleado único por test: aísla los marcajes (el chequeo de duplicados es por empleado) y
		# evita fugas entre casos sin renunciar a fechas deterministas.
		self.employee = _ensure_employee(f"MXS {frappe.generate_hash(length=8)}", self.company)

	# ----------------------------------------------------------------- helpers
	def _checkin(self, dt, log_type, shift_start=None, shift_end=None):
		doc = frappe.get_doc(
			{
				"doctype": "Employee Checkin",
				"employee": self.employee,
				"time": dt,
				"log_type": log_type,
				"skip_auto_attendance": 1,
			}
		)
		if shift_start:
			doc.shift_start = shift_start
			doc.shift_end = shift_end
		return doc.insert().name

	def _summary(self, start=DAY, end=DAY, as_of=None):
		doc = frappe.get_doc(
			{
				"doctype": "MX Attendance Summary",
				"employee": self.employee,
				"period_start": start,
				"period_end": end,
			}
		)
		if as_of:
			doc.flags.as_of = as_of
		return doc.insert()

	# ----------------------------------------------------------------- casos
	def test_normal_day_in_out(self):
		self._checkin(f"{DAY} 09:00:00", "IN")
		self._checkin(f"{DAY} 17:00:00", "OUT")
		s = self._summary(as_of=f"{NEXT} 08:00:00")
		self.assertEqual(len(s.days), 1)
		row = s.days[0]
		self.assertEqual(getdate(row.date), getdate(DAY))
		self.assertEqual(row.checkin_count, 2)
		self.assertEqual(row.day_status, "Completa")
		self.assertEqual(row.native_working_hours, 8.0)
		self.assertEqual(row.computed_hours, 8.0)
		self.assertEqual(s.total_computed_hours, 8.0)
		self.assertEqual(s.days_complete, 1)

	def test_multiple_pairs(self):
		for t, lt in [("09:00:00", "IN"), ("13:00:00", "OUT"), ("14:00:00", "IN"), ("18:00:00", "OUT")]:
			self._checkin(f"{DAY} {t}", lt)
		s = self._summary(as_of=f"{NEXT} 08:00:00")
		self.assertEqual(len(s.days), 1)
		row = s.days[0]
		self.assertEqual(row.checkin_count, 4)
		self.assertEqual(row.day_status, "Completa")
		self.assertEqual(row.native_working_hours, 8.0)  # (09-13) + (14-18)

	def test_open_shift_same_day(self):
		# Entrada sin salida y el turno todavía no cierra (as_of el mismo día, temprano) -> Abierta.
		self._checkin(f"{DAY} 09:00:00", "IN")
		s = self._summary(as_of=f"{DAY} 10:00:00")
		row = s.days[0]
		self.assertEqual(row.day_status, "Abierta")
		self.assertEqual(row.checkin_count, 1)
		self.assertEqual(row.native_working_hours, 0.0)
		self.assertEqual(s.days_open, 1)

	def test_closed_incomplete(self):
		# Entrada sin salida y el turno ya cerró (as_of días después) -> Incompleta (falta evidencia).
		self._checkin(f"{DAY} 09:00:00", "IN")
		s = self._summary(as_of="2026-03-05 08:00:00")
		row = s.days[0]
		self.assertEqual(row.day_status, "Incompleta")
		self.assertEqual(s.days_incomplete, 1)

	def test_midnight_cross_attributed_to_shift_start_day(self):
		# Turno 22:00->06:00: IN 22:00 (DAY) y OUT 02:00 (NEXT) con shift_start en DAY -> ambos a DAY.
		self._checkin(f"{DAY} 22:00:00", "IN", shift_start=f"{DAY} 22:00:00", shift_end=f"{NEXT} 06:00:00")
		self._checkin(f"{NEXT} 02:00:00", "OUT", shift_start=f"{DAY} 22:00:00", shift_end=f"{NEXT} 06:00:00")
		s = self._summary(start=DAY, end=DAY, as_of="2026-03-05 08:00:00")
		self.assertEqual(len(s.days), 1)
		row = s.days[0]
		self.assertEqual(getdate(row.date), getdate(DAY))
		self.assertEqual(row.checkin_count, 2)
		self.assertEqual(row.day_status, "Completa")
		self.assertEqual(row.native_working_hours, 4.0)  # 22:00 -> 02:00

	def test_idempotent_rebuild(self):
		self._checkin(f"{DAY} 09:00:00", "IN")
		self._checkin(f"{DAY} 17:00:00", "OUT")
		s = self._summary(as_of=f"{NEXT} 08:00:00")
		snapshot = [(getdate(d.date), d.checkin_count, d.native_working_hours, d.day_status) for d in s.days]
		total1 = s.total_computed_hours
		s.flags.as_of = f"{NEXT} 08:00:00"
		s.build()
		snapshot2 = [(getdate(d.date), d.checkin_count, d.native_working_hours, d.day_status) for d in s.days]
		self.assertEqual(snapshot, snapshot2)
		self.assertEqual(total1, s.total_computed_hours)

	def test_does_not_mutate_checkins(self):
		c_in = self._checkin(f"{DAY} 09:00:00", "IN")
		c_out = self._checkin(f"{DAY} 17:00:00", "OUT")
		before = frappe.db.get_value("Employee Checkin", c_in, ["time", "log_type", "employee"], as_dict=True)
		self._summary(as_of=f"{NEXT} 08:00:00")
		after = frappe.db.get_value("Employee Checkin", c_in, ["time", "log_type", "employee"], as_dict=True)
		self.assertEqual(before, after)
		# El OUT sigue existiendo y sin cambios de evidencia.
		self.assertTrue(frappe.db.exists("Employee Checkin", c_out))
		self.assertEqual(frappe.db.get_value("Employee Checkin", c_out, "log_type"), "OUT")

	def test_substitution_rule_replaces_not_adds(self):
		# Jornada nativa de 4h (09-13). Con 480 min reconocidos -> 8h (sustituye, no suma).
		self._checkin(f"{DAY} 09:00:00", "IN")
		self._checkin(f"{DAY} 13:00:00", "OUT")
		original = mxas_module.recognition.recognized_minutes_for
		try:
			mxas_module.recognition.recognized_minutes_for = lambda employee, date: 480
			s = self._summary(as_of=f"{NEXT} 08:00:00")
		finally:
			mxas_module.recognition.recognized_minutes_for = original
		row = s.days[0]
		self.assertEqual(row.native_working_hours, 4.0)
		self.assertEqual(row.recognized_minutes, 480)
		self.assertEqual(row.computed_hours, 8.0)  # sustituido, no 4+8
		self.assertEqual(s.total_native_hours, 4.0)
		self.assertEqual(s.total_computed_hours, 8.0)

	def test_frozen_snapshot_after_submit(self):
		self._checkin(f"{DAY} 09:00:00", "IN")
		self._checkin(f"{DAY} 17:00:00", "OUT")
		s = self._summary(as_of=f"{NEXT} 08:00:00")
		s.submit()
		self.assertEqual(s.docstatus, 1)
		# Un resumen confirmado no se recalcula.
		self.assertRaises(frappe.ValidationError, s.rebuild)

	def test_invalid_period_rejected(self):
		doc = frappe.get_doc(
			{
				"doctype": "MX Attendance Summary",
				"employee": self.employee,
				"period_start": DAY,
				"period_end": "2026-03-01",
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)
