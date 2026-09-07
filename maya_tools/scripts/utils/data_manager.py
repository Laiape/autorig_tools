import os
import json
import pathlib

class DataExportBiped:
    """
    Handles export, import, and management of rigging build cache data.
    Each module can append its own data for rig construction purposes.
    """

    CACHE_FILE = "biped.cache"

    def __init__(self):
        """
        Ruta del cache del build: maya_tools/cache/<CACHE_FILE>, resuelta con
        pathlib desde este fichero (utils -> scripts -> maya_tools) para que
        funcione igual en Windows y Linux. Crea la carpeta cache si falta.
        """
        cache_dir = pathlib.Path(__file__).resolve().parents[2] / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.build_path = str(cache_dir / self.CACHE_FILE)


    def new_build(self):
        """
        Initializes an empty build cache file, clearing previous data.
        """
        with open(self.build_path, "w") as f:
            json.dump({}, f, indent=4)
        

    def clear_build(self):
        """
        Deletes the build cache file if it exists.
        """
        if os.path.exists(self.build_path):
            os.remove(self.build_path)

    def append_data(self, module_name, data):

        """
        Appends or updates data for a given module in the build cache.

        Args:
            module_name (str): Name of the rigging module.
            data_dict (dict): Data to store for the module.
            
        """

        if os.path.exists(self.build_path):
            with open(self.build_path, "r") as f:
                try:
                    current_data = json.load(f)
                except json.JSONDecodeError:
                    current_data = {}
        else:
            current_data = {}

        if module_name not in current_data:
            current_data[module_name] = {}
        current_data[module_name].update(data)

        with open(self.build_path, "w") as f:
            json.dump(current_data, f, indent=4)


    def get_data(self, module_name, attribute_name):

        """
        Retrieves a specific attribute for a given module.

        Args:
            module_name (str): Module to look under.
            attribute_name (str): Attribute key to retrieve.

        Returns:
            The value if found, otherwise None.
        """
        if not os.path.exists(self.build_path):
            return None

        with open(self.build_path, "r") as f:
            try:
                current_data = json.load(f)
            except json.JSONDecodeError:
                return None

        return current_data.get(module_name, {}).get(attribute_name)

class DataExportQuadruped(DataExportBiped):
    
    """
    Inherits from DataExportBiped to handle quadruped-specific data management.
    Hoy no la usa nadie: el build de cuadrupedo escribe en biped.cache.
    """
    CACHE_FILE = "quadruped.cache"
