# CLAUDE.md — hrms_mexico

> **Reglas de operación Claude Code** (commits, PRs, base de datos, flujo de trabajo, prohibiciones git):
> Ver `/home/erpnext/Developer/frappe-infrastructure/.claude/CLAUDE.md`

---

## Estado del proyecto

- **App nueva:** creada en frappe-bench-v16
- **Bench activo:** `/home/erpnext/frappe-bench-v16`
- **Branch protegida:** `version-16` (nunca commitear directamente — estándar Frappe)
- **Versión:** 0.0.1 (desarrollo inicial)
- **En producción:** No

---

## Sites de desarrollo y prueba

| Site | Bench | Propósito | Notas |
|---|---|---|---|
| `proposals-acti.dev` | frappe-bench-v16 | Desarrollo activo | Features, migrate, export-fixtures |
| `test-hrms_mexico.localhost` | frappe-bench-v16 | Tests unitarios | Solo para `bench run-tests` — nunca modificar manualmente |

**Reglas de uso:**
- `bench migrate` → siempre con `--site`. Nunca sin site en bench compartido.
- `bench run-tests` → siempre `test-hrms_mexico.localhost` — nunca en el site de desarrollo.
- `bench export-fixtures` → `proposals-acti.dev`

> **Nota:** `proposals-acti.dev` es un site de desarrollo compartido del bench. Otras apps
> instaladas en él **no** son dependencias de `hrms_mexico` (ver sección Dependencias).
> No está registrado en `frappe-multisite` como app propia.

## Entorno
Ver contexto global en `frappe-infrastructure/.claude/CLAUDE.md`.

**Comandos frecuentes (bench v16):**
```bash
bench --site proposals-acti.dev migrate
bench --site proposals-acti.dev export-fixtures --app hrms_mexico
bench --site test-hrms_mexico.localhost run-tests --app hrms_mexico
bench build --app hrms_mexico
```
**NUNCA:** `bench migrate` sin `--site` — afecta todos los sites del bench compartido

---

## Idioma

- **Interfaz y documentación funcional/legal:** español de México (es-MX).
- **Código y documentación técnica:** según convenciones del ecosistema (`frappe-conventions`).
- MkDocs: `language: es`.

---

## Qué hace esta app

Cumplimiento laboral mexicano para Frappe HRMS.

---

## DocTypes principales

*(pendiente de documentar al implementar)*

---

## Fixtures

*(pendiente — declarar en hooks.py al crear Custom Fields, Roles, Workspaces)*

---

## Dependencias

**Apps requeridas:** erpnext, hrms
**Apps en frappe-bench-v16 (dependencias reales):** frappe, erpnext, hrms, hrms_mexico
**Dependencias externas:** Ninguna

> Otras apps presentes en el site de desarrollo están **instaladas** pero **no** son
> dependencias de `hrms_mexico`.

---

## Tests

```bash
bench --site test-hrms_mexico.localhost run-tests --app hrms_mexico
```

**Sin cobertura inicial.** Documentar tests aquí cuando se implementen.
**Site de tests dedicado:** `test-hrms_mexico.localhost` — nunca correr tests en el site de desarrollo.

---

## REGLAS GIT — HRMS_MEXICO

### Antes de cada commit

- Correr linters en archivos modificados:
  ```bash
  ruff format <archivos .py modificados>
  npx prettier@2.7.1 --write <archivos .js modificados>
  ```

### Antes de cada PR

- [ ] Linters pasados
- [ ] Fixtures exportados si hubo cambios de Custom Fields, Roles, Workspaces
- [ ] Patch creado si hay cambios de esquema — **requiere autorización explícita**
- [ ] `bench --site proposals-acti.dev migrate` limpio
- [ ] `/doc-review` corrido (estándar documental del ecosistema)
- [ ] Ver checklist global en `frappe-infrastructure/CONTRIBUTING.md`

### PROHIBICIÓN ABSOLUTA — NUNCA TRABAJAR EN version-16

**`version-16` es la rama protegida de hrms_mexico. Es el estándar Frappe upstream.**

- **Nunca implementar cambios estando en `version-16`.**
- **Nunca crear commits estando en `version-16`.**
- **Nunca hacer push directo a `version-16`.** Todo cambio entra por PR.
- Todo cambio (incluso documental) debe iniciar en una **rama de trabajo** creada desde `version-16`
  limpio y sincronizado. Convención de prefijos: `feat/ fix/ docs/ chore/ refactor/ hotfix/`
  (ver `CONTRIBUTING.md`).
- `/ship commit` y `/ship push` deben **rechazar** si la rama es `version-16`.
- `/ship pr` debe exigir rama distinta de `version-16` (PR hacia `version-16` como base).

**Única excepción de bootstrap:** el primer commit + primer push a `version-16` (Pasos 8–9 del
scaffold) solo para crear el repo remoto vacío. Esa excepción **termina en cuanto se crea y valida
el ruleset** (Paso 9b). Después de eso, ni un cambio documental va directo a `version-16`.

### Reglas específicas del proyecto

- PRs siempre a `version-16`
- Site de desarrollo: `proposals-acti.dev`
- Site de tests: `test-hrms_mexico.localhost`
- Idioma de UI y doc funcional/legal: español de México (es-MX)
