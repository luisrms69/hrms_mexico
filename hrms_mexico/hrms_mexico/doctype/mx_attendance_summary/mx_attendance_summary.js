// Copyright (c) 2026, Consultoria en Negocios y Aplicaciones and contributors
// For license information, please see license.txt

frappe.ui.form.on("MX Attendance Summary", {
	refresh(frm) {
		// Reconstruir el detalle diario bajo demanda (solo en borrador). El guardado ya reconstruye;
		// este botón permite recalcular tras cargar nuevos marcajes sin re-teclear el periodo.
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.add_custom_button(__("Reconstruir jornada"), () => {
				frm.call("rebuild").then(() => frm.reload_doc());
			});
		}
	},
});
