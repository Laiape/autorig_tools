import os
import json

class DataExportBiped:
    """
    Handles export, import, and management of rigging build cache data.
    Each module can append its own data for rig construction purposes.
    """

    def __init__(self):
        """
        Initializes the export path for the build cache.
        Uses the user's home directory to ensure write permissions.
        """
        complete_path = os.path.realpath(__file__)
        relative_path = complete_path.split("\scripts")[0]
        final_path = os.path.join(relative_path, "cache")   
        self.build_path = os.path.join(final_path, "biped.cache")


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
    """
    def __init__(self):

        super().__init__()
        complete_path = os.path.realpath(__file__)
        relative_path = complete_path.split("\scripts")[0]
        final_path = os.path.join(relative_path, "cache")   
        self.build_path = os.path.join(final_path, "quadruped.cache")
