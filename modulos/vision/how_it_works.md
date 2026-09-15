# Autorig Tools - product vision (source of truth)

Parent: `modulos/how_it_works.md`.
UI map: `maya_tools/criterios-ui.md`.
Where a source lands: `modulos/vision/mapa_datos.md`.
Parked for delivery: `modulos/vision/pendiente_final.md`.
Maya: `maya_tools/how_it_works.md`.
Unreal: `ue_tools/how_it_works.md`.

This file is the operating model. Do not invent a different product story.

---

## Why this repo exists

Autorig Tools lets a rigger **build and maintain a character rig in Maya**
from guides, then skin, correctives, and related helpers, without a
separate web product.

It is not a DCC. It is not an engine. It is not Factory Hub or a Weelko
service stack.

---

## Audiences

### Rigger (Maya)

- Works inside Autodesk Maya after the module is loaded.
- Uses the **AutoRig Tools** menu and the **AutoRig** shelf.
- Sees the current Maya scene and files the Character Manager lists
  (`.ma`, `.mb`, `.guides`, `.curves`, `.json`, `.skc`).

### Rigger (Unreal)

- Reads production notes under `ue_tools/docs/`.
- No Unreal editor plugin ships in this repo yet. Do not invent one.

There is no multi-tenant web login. Do not add company filters or an
external-vs-internal web home.

---

## Product areas

Fixed order (Maya menu groups first; Unreal last):

| Order | Label | Where | Child doc |
|---|---|---|---|
| 1 | Maya tools | `maya_tools/` | `maya_tools/how_it_works.md` |
| 2 | Unreal tools | `ue_tools/` | `ue_tools/how_it_works.md` |

Maya is the working product. Unreal is notes plus an empty `scripts/`
folder. Keep that split. Do not merge Unreal notes into the Maya menu.

---

## Hard rules

- Do not invent a Maya window. Use `modulos/vision/mapa_datos.md`.
- Do not invent a parallel menu. Use `maya_tools/criterios-ui.md`.
- Do not add `backend/`, `frontend/`, or Docker because another kit
  used those names.
- Docs guide; live Maya scripts and `self_module.mod` are the source of truth.
