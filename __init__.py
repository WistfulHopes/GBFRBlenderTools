bl_info = {
    "name": "Granblue Fantasy Relink Blender Tools",
    "author": "WistfulHopes & AlphaSatanOmega",
    "version": (0, 3, 0),
    "blender": (3, 5, 0),
    "location": "File > Import/Export",
    "description": "Tool to import & export models from Granblue Fantasy Relink",
    "warning": "",
    "category": "Import-Export",
}

# Reloads the addons on script reload
# Good for editing script
if "bpy" in locals():
    import importlib
    if "gbfr_import" in locals():
        importlib.reload(gbfr_import)
    if "gbfr_export" in locals():
        importlib.reload(gbfr_export)
    if "utils" in locals():
        importlib.reload(utils)

import bpy
import bmesh
import mathutils
import struct
import os
from . import gbfr_import, gbfr_export, utils
from .Entities.ModelInfo import ModelInfo
# from .Entities.ModelSkeleton import ModelSkeleton

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

# Addon preferences, where users will specify flatc.exe path
class AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__
    
    # Define a custom property for storing the flatc file path
    flatc_file_path: StringProperty(
        name="flatc.exe filepath",
        description="File path to flatc.exe be used for export.",
        subtype='FILE_PATH',
    )
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "flatc_file_path")


# Register importer & exporter
def register():
    gbfr_import.register()
    gbfr_export.register()
    bpy.utils.register_class(AddonPreferences)

def unregister():
    gbfr_import.unregister()
    gbfr_export.unregister()
    bpy.utils.unregister_class(AddonPreferences)

#Run the addon
if __name__ == "__main__":
    register()
    # test call
    # bpy.ops.gbfr.mesh('INVOKE_DEFAULT')