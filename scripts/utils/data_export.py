import json
import os
import maya.api.OpenMaya as om

complete_path = os.path.realpath(__file__)
relative_path = complete_path.split("\scripts")[0]
final_path = os.path.join(relative_path, "data")


def write_data(data):

    """Writes data to a JSON file."""

    with open(final_path, 'w') as file:
        new_file = json.dump(data, file, indent=4)

def append_data(data):

    """Appends data to an existing JSON file."""

    if not os.path.exists(final_path):
        write_data(data)
        return

    with open(final_path, 'r') as file:
        existing_data = json.load(file)

    existing_data.update(data)

    with open(final_path, 'w') as file:
        json.dump(existing_data, file, indent=4)


def get_data(data):

    """Retrieves data from a JSON file."""

    if not os.path.exists(final_path):
        om.MGlobal.displayError(f"Data file not found at {final_path}")
        return 

    with open(final_path, 'r') as file:
        returned_data = json.load(file)
        if data in returned_data:
            return returned_data[data]
        else:
            return None
    
