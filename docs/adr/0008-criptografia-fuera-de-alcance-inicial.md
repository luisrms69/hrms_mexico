# ADR-0008: Criptografía fuera de alcance inicial

**Fecha:** 2026-11-19
**Status:** Propuesto

## Contexto

Se evaluó incorporar mecanismos criptográficos (p. ej. firma/sellado de registros) para reforzar la evidencia.

## Decisión

La criptografía queda **fuera del alcance inicial**. La integridad del registro se sustenta en la **inmutabilidad a nivel aplicación** (ADR-0002) y la **trazabilidad/auditoría** (ADR-0003).

## Consecuencias

- La primera entrega no incluye firma/sellado criptográfico.
- La **etapa 2** (sujeta a análisis jurídico/riesgo, ver ADR-0007) podría incorporar: **sello de tiempo externo / NOM-151**, **atribución reforzada**, cadena hash/HMAC/anclajes externos y **retención técnica avanzada**. No están en etapa 1.
- Si una obligación legal futura lo exige (ver ADR-0007), se abrirá un ADR específico para evaluarlo e incorporarlo.

## Notas

Decisión de alcance. Relacionada con [[0002-inmutabilidad-marcaje-original]] y [[0007-cumplimiento-normativo-mx]].
