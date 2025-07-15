import maya.cmds as cmds
import maya.api.OpenMaya as om
import json
import os

TEMPLATE_PATH = "C:/GITHUB/curves"

class CurveTool(object):

    def __init__(self):

        """ Initialize the CurveTool class and set the file path for curves information."""

        global TEMPLATE_PATH

        file_name = "curves_info.json"
        self.final_path = os.path.join(TEMPLATE_PATH, file_name)

    def get_curves_info(self):

        """
        Get all curves in the scene and extract their information such as name, control points, degree, knots, and overrideColor.
        This information is stored in a dictionary with the curve name as the key.
        """

        all_curves = cmds.ls(type="nurbsCurve")

        print(f"Found {all_curves} curves in the scene.")

        # Get the curves info: name, control points, degree, knots, overrideColor.

        self.curves_info = {}

        for curve in all_curves:
            
            side = curve.split("_")[0]
            names = curve.split("_")[1]
            name = f"{side}_{names}"
            override_color = None  

            control_points = cmds.getAttr(f"{curve}.controlPoints")
            degree = cmds.getAttr(f"{curve}.degree")
            form = cmds.getAttr(f"{curve}.form")
            draw_always_on_top = cmds.getAttr(f"{curve}.alwaysDrawOnTop")
            # knots = cmds.getAttr(f"{curve}.knots")
            override_enabled = cmds.getAttr(f"{curve}.overrideEnabled")
            if override_enabled:
                override_color = cmds.getAttr(f"{curve}.overrideColor")

            self.curves_info[curve] = {
                "name": name,
                "controlPoints": control_points,
                "degree": degree,
                # "knots": knots,
                "overrideEnabled": override_enabled,
                "overrideColor": override_color,
                "form": form,
                "alwaysDrawOnTop": draw_always_on_top
        }

                
        om.MGlobal.displayInfo(f"Curves info collected: {len(self.curves_info)} curves found.")

    def write_json(self):

        """ Writes curves information to a JSON file."""

        with open(self.final_path, "w") as file:
            json.dump(self.curves_info, file, indent=4)
        
        om.MGlobal.displayInfo(f"Curves info saved to {self.final_path}")

    def create_controller(self, name, offset=[None]):

        """Creates the controller based on the curves information."""

        # Build the controller offset groups.
        offset_grps = []

        for grp in offset:
            if grp is None:
                grp = cmds.createNode("transform", name=f"{name}_GRP", ss=True)
            else:
                grp = cmds.createNode("transform", name=f"{name}_{grp}", ss=True)
            if offset_grps:
                cmds.parent(grp, offset_grps[-1])
            offset_grps.append(grp)

        
        # Create the controller from the curve information.

        if name in self.curves_info:
            curve_info = self.curves_info[name]
            control_points = curve_info["controlPoints"]
            degree = curve_info["degree"]
            knots = curve_info["knots"]
            override_enabled = curve_info["overrideEnabled"]
            override_color = curve_info["overrideColor"] if "overrideColor" in curve_info else None


            # Create the NURBS curve.
            controller = cmds.curve(d=degree, p=control_points, k=knots, name=name)

            # Set the override color if it exists.
            
            cmds.setAttr(f"{controller}.overrideEnabled", override_enabled)
            if override_color is not 0:
                cmds.setAttr(f"{controller}.overrideColor", override_color)

            # Parent the controller to the last offset group.
            cmds.parent(controller, offset_grps[-1])



    