# Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
# For license information, please see license.txt

"""Bootstrap de tests de hrms_mexico.

Garantiza una Company de prueba válida (con su setup: warehouse types, cuentas, etc.) en una base
limpia (p. ej. CI), usando el **setup wizard** estándar — sin importar los módulos de test de
ERPNext/HRMS (que acoplan a datos como `_Test Customer`).
"""

import frappe
from frappe.utils import now_datetime


def before_tests():
	frappe.clear_cache()
	if not frappe.get_list("Company", limit=1):
		from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

		year = now_datetime().year
		setup_complete(
			{
				"currency": "INR",
				"full_name": "Test User",
				"company_name": "_Test Company",
				"timezone": "Asia/Kolkata",
				"company_abbr": "_TC",
				"industry": "Manufacturing",
				"country": "India",
				"fy_start_date": f"{year}-01-01",
				"fy_end_date": f"{year}-12-31",
				"language": "english",
				"company_tagline": "Testing",
				"email": "test@example.com",
				"password": "test",
				"chart_of_accounts": "Standard",
			}
		)
	frappe.db.commit()  # nosemgrep -- setup base del entorno de test
