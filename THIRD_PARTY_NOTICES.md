# Third-party notices

## puiastre_tools controller shape operations

Source: https://github.com/guidogonzalezc/puiastre_tools
Revision: 36a2acd4f57d8d5f65db9c38c0493dcf07330a5d
Original file: scripts/puiastreTools/utils/curve_tool.py
Original functions: mirror_shapes, replace_shape_colored
License: Apache License, Version 2.0 (see LICENSE).

The adaptation in maya_tools/scripts/utils/controller_shapes.py retains the
world-X shape mirror, side-color mapping and first-source/multiple-target
replacement behavior. It adds undo and failure rollback, namespace handling,
curve-only snapshots without hierarchy duplication, validation of editable
targets, preservation of controller transforms and geometry consumers, and
integration with the existing Autorig menu and tool catalogue.
