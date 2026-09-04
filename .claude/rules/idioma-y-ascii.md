# Idioma y ASCII

Este fichero es la unica politica de idioma y acentos. No la repitas en otras
reglas, docs ni skills.

## Idioma
- Castellano en chat, docs, reglas, comentarios, docstrings, mensajes al
  usuario en Maya y mensajes de commit.
- Identificadores tecnicos en ingles, como ya estan: nombres de nodo,
  atributos, claves del `.build`, funciones (`make`, `corrective_setup`), sufijos.
- No traducir texto existente en ingles (barra de progreso, docstrings viejos)
  solo por unificar.

## ASCII por defecto
- Sin acentos, enes ni simbolos fuera de ASCII en codigo, comentarios, logs,
  prints, commits, `como_funciona.md`, `criterios_*.md` y reglas. Sin emojis.
- Motivo: Maya en Windows y PowerShell (`charmap`) fallan con no-ASCII. El
  historial de commits ya lo cumple.
- Sustituciones: `->` en vez de flecha, `-` en vez de guion largo, "seccion 4"
  en vez del simbolo de seccion.

## Excepciones
| Ambito | No-ASCII |
|---|---|
| `.claude/skills/**` ya escritas | se dejan como estan; no reescribir por acentos |
| Texto nuevo dentro de una skill existente | ASCII, aunque el resto tenga acentos |
| UIs PySide con simbolos (flechas, iconos de texto) | permitido en el `.py` de la UI si ya lo usa |
