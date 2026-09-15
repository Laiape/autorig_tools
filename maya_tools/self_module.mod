# First existing module root wins. Maya skips a + block whose path is missing.
# Add another clone by copying a block; do not delete the others.

+ self_module 1.0 C:\proyectos_laia\autorig_tools\maya_tools
PYTHONPATH += C:\proyectos_laia\autorig_tools
XBMLANGPATH +:= icons

+ self_module 1.0 C:\GIT\autorig_tools\maya_tools
PYTHONPATH += C:\GIT\autorig_tools
XBMLANGPATH +:= icons
