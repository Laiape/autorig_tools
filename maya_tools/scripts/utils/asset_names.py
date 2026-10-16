"""Character identity shared by asset readers and writers."""


def normalize_asset_name(name):
    """Use an initial capital without changing the rest of the character name."""
    name = str(name).strip() if name else ""
    return name[:1].upper() + name[1:]
