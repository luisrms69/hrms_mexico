# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

"""`MX Attendance Summary` — resumen/consolidación de jornada (ADR-0004).

Consolida, por empleado y periodo, los `Employee Checkin` (y la `Attendance` nativa cuando existe) en
filas diarias, **sin alterar** los registros originales. El cálculo es **idempotente**: reconstruir el
resumen desde el mismo insumo produce el mismo resultado. Al hacer *submit* el documento queda como
**snapshot congelado** (no se recalcula).

Decisiones de diseño (ver investigación del nativo y ADRs):
- **Medianoche (C):** la jornada se atribuye a `Employee Checkin.shift_start.date()` cuando hay turno
  asignado (lo calcula HRMS), con *fallback* a `time.date()` si la jornada no tiene turno. No se impone
  arbitrariamente el día de entrada.
- **Horas:** se reutiliza `hrms...employee_checkin.calculate_working_hours` (no se reimplementa). Si
  existe `Attendance` nativa del día, su `working_hours` es la fuente.
- **Sustitución (ADR-0005):** los minutos reconocidos (seam `hrms_mexico.recognition`) **sustituyen**
  (no suman) a las horas nativas. En la Etapa 2 no hay reconocimiento (siempre nativo); la fuente real
  llega en la Etapa 3.
- **Incompletos (B):** una jornada con entrada sin salida se marca **Abierta** si el turno todavía no
  cierra (el empleado aún puede marcar salida) o **Incompleta** si el turno ya cerró (falta evidencia).
  Nunca se inventa una salida ficticia ni se presume ausencia.
"""

from datetime import datetime, time, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, getdate, now_datetime
from hrms.hr.doctype.employee_checkin.employee_checkin import calculate_working_hours

from hrms_mexico import recognition

# Configuración de emparejamiento/cálculo por defecto (jornadas sin turno asignado).
_DEFAULT_CHECK_IN_OUT_TYPE = "Alternating entries as IN and OUT during the same shift"
_DEFAULT_CALC_TYPE = "Every Valid Check-in and Check-out"


class MXAttendanceSummary(Document):
	def validate(self):
		self._block_amend()
		self._validate_rectification()
		self._validate_period()
		# El snapshot solo se (re)construye mientras el documento está en borrador.
		if self.docstatus == 0:
			self.build()

	def _validate_rectification(self):
		"""La referencia de rectificación debe ser inequívoca: a un resumen confirmado existente, distinto."""
		if not self.rectifica_a:
			return
		if self.rectifica_a == self.name:
			frappe.throw(_("Una rectificación no puede referenciarse a sí misma."), title=_("Rectificación"))
		target = frappe.db.get_value("MX Attendance Summary", self.rectifica_a, "docstatus")
		if target is None:
			frappe.throw(_("El resumen que se rectifica no existe."), title=_("Rectificación"))
		if target != 1:
			frappe.throw(
				_("Solo se rectifica un resumen confirmado (docstatus=1)."), title=_("Rectificación")
			)

	def _block_amend(self):
		"""El resumen confirmado es evidencia: no se enmienda (amend). La rectificación es un documento
		NUEVO e independiente (ver `create_rectification`); el original conserva docstatus=1."""
		if self.get("amended_from"):
			frappe.throw(
				_(
					"El resumen de jornada no admite enmienda (amend). Genere una rectificación: un documento"
					" nuevo e independiente que referencia al anterior, el cual se conserva intacto."
				),
				title=_("Enmienda no permitida"),
			)

	def before_cancel(self):
		"""Prohibido cancelar un resumen confirmado (evidencia). Aplica a todos los roles, incluido
		Administrator (los permisos por rol no bastan porque Administrator los omite)."""
		frappe.throw(
			_(
				"El resumen de jornada confirmado no puede cancelarse: es evidencia. Para corregir, genere"
				" una rectificación (documento nuevo que referencia a este); el original permanece confirmado."
			),
			title=_("Cancelación no permitida"),
		)

	@frappe.whitelist()
	def create_rectification(self):
		"""Crea un resumen NUEVO e independiente (borrador) que rectifica a este, sin tocar el original.

		El nuevo documento referencia al anterior vía `rectifica_a`; reconstruye su detalle con la
		información vigente (p. ej. regularizaciones aprobadas). El original conserva su `docstatus=1`,
		su contenido y su evidencia.
		"""
		if self.docstatus != 1:
			frappe.throw(_("Solo se rectifica un resumen confirmado."), title=_("Rectificación"))
		nuevo = frappe.get_doc(
			{
				"doctype": "MX Attendance Summary",
				"employee": self.employee,
				"period_start": self.period_start,
				"period_end": self.period_end,
				"shift_type": self.shift_type,
				"rectifica_a": self.name,
			}
		)
		nuevo.insert()
		return nuevo.name

	def _validate_period(self):
		if not (self.period_start and self.period_end):
			return
		if getdate(self.period_start) > getdate(self.period_end):
			frappe.throw(
				_("El inicio del periodo no puede ser posterior al fin del periodo."),
				title=_("Periodo inválido"),
			)

	# ----------------------------------------------------------------- construcción idempotente
	@frappe.whitelist()
	def rebuild(self):
		"""Reconstruye el detalle diario (solo en borrador). Expuesto para el botón del formulario."""
		if self.docstatus != 0:
			frappe.throw(_("Un resumen confirmado no se recalcula."), title=_("Snapshot congelado"))
		self.build()
		self.save()

	def build(self, as_of=None):
		"""Reconstruye `days` y los totales desde los marcajes/asistencias. No muta originales."""
		as_of = get_datetime(as_of or getattr(self.flags, "as_of", None) or now_datetime())

		self.applied_check_in_out_type = _DEFAULT_CHECK_IN_OUT_TYPE
		self.applied_calc_type = _DEFAULT_CALC_TYPE

		groups = self._group_checkins_by_day()
		attendances = self._fetch_attendances()

		keys = sorted(set(groups) | set(attendances))
		rows = []
		for day, shift in keys:
			rows.append(
				self._build_day_row(
					day, shift, groups.get((day, shift), []), attendances.get((day, shift)), as_of
				)
			)

		self.set("days", [])
		for row in rows:
			self.append("days", row)

		self._recompute_totals()

	def _group_checkins_by_day(self):
		"""Marcajes del periodo agrupados por (día efectivo, turno). Día efectivo = `shift_start` del
		turno (maneja el cruce de medianoche como HRMS) o `time` si no hay turno."""
		start = datetime.combine(getdate(self.period_start), time.min)
		# Límite superior ampliado un día para captar una salida después de medianoche cuyo turno
		# inició dentro del periodo; luego se descartan los días fuera del periodo.
		end = datetime.combine(getdate(self.period_end) + timedelta(days=1), time.max)

		filters = {"employee": self.employee, "time": ("between", [start, end])}
		if self.shift_type:
			filters["shift"] = self.shift_type

		checkins = frappe.get_all(
			"Employee Checkin",
			filters=filters,
			fields=["name", "time", "log_type", "shift", "shift_start", "shift_end", "attendance"],
			order_by="time asc",
		)

		p_start, p_end = getdate(self.period_start), getdate(self.period_end)
		groups: dict[tuple, list] = {}
		for c in checkins:
			day = c.shift_start.date() if c.shift_start else get_datetime(c.time).date()
			if not (p_start <= day <= p_end):
				continue
			groups.setdefault((day, c.shift or None), []).append(frappe._dict(c))
		return groups

	def _fetch_attendances(self):
		"""Attendance nativa del periodo por (fecha, turno). Excluye canceladas."""
		filters = {
			"employee": self.employee,
			"attendance_date": ("between", [getdate(self.period_start), getdate(self.period_end)]),
			"docstatus": ("<", 2),
		}
		if self.shift_type:
			filters["shift"] = self.shift_type

		rows = frappe.get_all(
			"Attendance",
			filters=filters,
			fields=["name", "attendance_date", "shift", "status", "working_hours", "in_time", "out_time"],
		)
		return {(getdate(a.attendance_date), a.shift or None): frappe._dict(a) for a in rows}

	def _build_day_row(self, day, shift, logs, att, as_of):
		checkin_count = len(logs)

		# Horas nativas: Attendance si existe; si no, cálculo nativo desde los marcajes.
		if att:
			native_hours = flt(att.working_hours)
			native_status = att.status
		elif logs:
			native_hours, _in, _out = calculate_working_hours(
				logs, _DEFAULT_CHECK_IN_OUT_TYPE, _DEFAULT_CALC_TYPE
			)
			native_hours = flt(native_hours)
			native_status = None
		else:
			native_hours = 0.0
			native_status = None

		complete = self._is_complete(logs)
		day_status = self._day_status(day, shift, logs, checkin_count, complete, as_of)

		first_in = logs[0].time if logs else (att.in_time if att else None)
		last_out = (logs[-1].time if (logs and complete) else None) or (att.out_time if att else None)

		# Regla de sustitución (ADR-0005): minutos reconocidos sustituyen (no suman) a las horas nativas.
		rec = recognition.recognized_minutes_for(self.employee, day)
		if rec is not None:
			recognized_minutes = int(rec)
			computed_hours = round(recognized_minutes / 60.0, 2)
			remarks = _("Horas sustituidas por minutos reconocidos (corrección aprobada).")
		else:
			recognized_minutes = 0
			computed_hours = flt(native_hours, 2)
			remarks = None

		return {
			"date": day,
			"shift": shift,
			"attendance": att.name if att else None,
			"native_status": native_status,
			"checkin_count": checkin_count,
			"first_in": first_in,
			"last_out": last_out,
			"day_status": day_status,
			"native_working_hours": flt(native_hours, 2),
			"recognized_minutes": recognized_minutes,
			"computed_hours": computed_hours,
			"checkin_refs": ", ".join(l.name for l in logs) or None,
			"remarks": remarks,
		}

	@staticmethod
	def _is_complete(logs):
		"""¿La jornada tiene todos sus pares IN/OUT? Usa log_type si está presente; si no, paridad."""
		if not logs:
			return False
		has_types = any(l.log_type for l in logs)
		if has_types:
			ins = sum(1 for l in logs if l.log_type == "IN")
			outs = sum(1 for l in logs if l.log_type == "OUT")
			return outs > 0 and ins == outs and logs[-1].log_type == "OUT"
		return len(logs) >= 2 and len(logs) % 2 == 0

	def _day_status(self, day, shift, logs, checkin_count, complete, as_of):
		if checkin_count == 0:
			return "Sin marcajes"
		if complete:
			return "Completa"
		# Entrada sin salida (o paridad impar): ¿el turno ya cerró?
		return "Incompleta" if self._shift_closed(day, shift, logs, as_of) else "Abierta"

	@staticmethod
	def _shift_closed(day, shift, logs, as_of):
		"""Cierre de la jornada: fin del turno (+ margen de salida) o fin del día si no hay turno."""
		shift_ends = [l.shift_end for l in logs if l.shift_end]
		if shift_ends:
			cutoff = max(shift_ends)
			if shift:
				margin = frappe.db.get_value("Shift Type", shift, "allow_check_out_after_shift_end_time")
				cutoff = cutoff + timedelta(minutes=int(margin or 0))
		else:
			cutoff = datetime.combine(getdate(day), time.max)
		return get_datetime(cutoff) < get_datetime(as_of)

	def _recompute_totals(self):
		self.total_native_hours = flt(sum(flt(d.native_working_hours) for d in self.days), 2)
		self.total_computed_hours = flt(sum(flt(d.computed_hours) for d in self.days), 2)
		self.total_recognized_minutes = sum(int(d.recognized_minutes or 0) for d in self.days)
		self.days_complete = sum(1 for d in self.days if d.day_status == "Completa")
		self.days_open = sum(1 for d in self.days if d.day_status == "Abierta")
		self.days_incomplete = sum(1 for d in self.days if d.day_status == "Incompleta")
		self.days_no_checkin = sum(1 for d in self.days if d.day_status == "Sin marcajes")
