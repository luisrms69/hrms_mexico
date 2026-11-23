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
		// Rectificar un resumen confirmado: crea un documento NUEVO e independiente (no cancela ni
		// enmienda este). El original permanece confirmado e intacto.
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Rectificar"), () => {
				frm.call("create_rectification").then((r) => {
					if (r.message) frappe.set_route("Form", "MX Attendance Summary", r.message);
				});
			});
		}
	},
});
