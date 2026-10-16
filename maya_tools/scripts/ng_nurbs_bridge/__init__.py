"""NURBS authoring for an installed ngSkinTools 2. No AutoRig dependency."""

__version__ = "1.0.0"


def attach():
    """Attach the extension to present and future standalone NG windows."""
    from .ng_host import install
    return install()


def open_ui():
    attach()
    import ngSkinTools2
    ngSkinTools2.open_ui()


def deactivate():
    from . import brush
    brush.stop()
