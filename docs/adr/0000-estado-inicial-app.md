# ADR-0000: Estado inicial — hrms_mexico

**Fecha:** 2026-11-18
**Status:** Activo

## Contexto

App nueva creada como parte del ecosistema Buzola sobre frappe-bench-v16.
Cumplimiento laboral mexicano para Frappe HRMS.

## Decisiones iniciales

- Bench: frappe-bench-v16 (Frappe 16.x, ERPNext 16.x)
- Branch protegida: version-16 (estándar Frappe upstream)
- Site de desarrollo: proposals-acti.dev → localhost:8410
- Site de tests: test-hrms_mexico.localhost
- Apps requeridas: erpnext, hrms
- Idioma: interfaz y documentación funcional/legal en español de México (es-MX); código y documentación técnica según convenciones del ecosistema
- GitHub: https://github.com/luisrms69/hrms_mexico

## Notas

La arquitectura funcional de `hrms_mexico` **sigue en revisión**: no se da por aprobada aquí.
Cada decisión arquitectónica se documentará como un ADR independiente (una decisión por ADR, con
su propio `Status` aprobable/cerrable). Ver `docs/adr/index.md`.
