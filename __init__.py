bl_info = {
    "name": "Granblue Fantasy Relink Blender Tools",
    "author": "AlphaSatanOmega & WistfulHopes",
    "version": (2, 0, 0),
    "blender": (4, 0, 0),
    "location": "File > Import/Export | View 3D > Tool Shelf > GBFR",
    "description": "Tool to import & export models from Granblue Fantasy Relink",
    "warning": "",
    "category": "Import-Export",
    "doc_url": "https://github.com/WistfulHopes/GBFRBlenderTools?tab=readme-ov-file#gbfr-blender-tools"
}

import bpy
import bmesh
import mathutils
import struct
import os
from . import gbfr_import, gbfr_export, gbfr_panel, utils, gbfr_minfo_builder, bone_name_mappings

# Reloads the addons on script reload
# Good for editing script
if "bpy" in locals():
    import importlib
    if "gbfr_import" in locals():
        importlib.reload(gbfr_import)
    if "gbfr_export" in locals():
        importlib.reload(gbfr_export)
    if "gbfr_panel" in locals():
        importlib.reload(gbfr_panel)
    if "utils" in locals():
        importlib.reload(utils)
    if "gbfr_minfo_builder" in locals():
        importlib.reload(gbfr_minfo_builder)
    if "bone_name_mappings" in locals():
        importlib.reload(bone_name_mappings)

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

# Addon preferences
class AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    # Define a custom property for storing the extracted game data folder path
    extracted_game_data_folder_path: StringProperty(
        name="Extracted Game Data Folder Path",
        description="Path to the folder where you extracted the game files with GBFRDataTools.",
        subtype='DIR_PATH'
    )
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "extracted_game_data_folder_path")


# Register importer & exporter
def register():
    gbfr_import.register()
    gbfr_export.register()
    gbfr_panel.register()
    bpy.utils.register_class(AddonPreferences)

def unregister():
    gbfr_import.unregister()
    gbfr_export.unregister()
    gbfr_panel.unregister()
    bpy.utils.unregister_class(AddonPreferences)

#Run the addon
if __name__ == "__main__":
    register()
    # test call
    # bpy.ops.gbfr.mesh('INVOKE_DEFAULT')