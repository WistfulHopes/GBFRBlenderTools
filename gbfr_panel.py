import bpy
from .utils import *

# Define the panel class
class GBFRToolPanel(bpy.types.Panel):
	"""Creates a custom panel in the Object properties editor"""
	bl_label = "GBFR Blender Tools"
	bl_idname = "VIEW3D_PT_GBFR_Tools_Panel"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "GBFR"

	def draw(self, context):
		layout = self.layout
		# Add a boolean property with a tooltip
		layout.label(text="Fixes")
		box = layout.box()
		box.label(text="USE THESE BEFORE EXPORTING!!!", icon='ERROR')
		row = box.row(align=True) ;row.scale_y = 1.0
		row.label(text="Split Mesh:", icon="MESH_DATA")
		row = box.row(align=True) ; row.scale_y = 1.5
		button = row.operator("mesh.split_mesh_along_uvs", icon='UV')
		row = box.row() ; row.scale_y = 0.5
		row.label(text="Materials:", icon="MATERIAL")
		row = box.row(align=True) ; row.scale_y = 1.5
		button = row.operator("mesh.sort_materials", icon='SORTALPHA')
		
		# ----------------------------
		layout.label(text="Utilities", icon='MODIFIER')
		box = layout.box()
		box.label(text="Armature:", icon='ARMATURE_DATA')
		row = box.row() ; row.scale_y = 0.5	
		row.label(text="Translate Bones To:", icon="BONE_DATA")
		row = box.row(align=True) ; row.scale_y = 1.5
		button = row.operator("armature.translate_bones_to_unity_blender", icon='NONE')
		button = row.operator("armature.translate_bones_to_gbfr", icon='NONE')
		box.label(text="Mesh:", icon='MESH_DATA')
		row = box.row()
		button = row.operator("mesh.flip_normals", icon='MESH_DATA')
		row = box.row()
		button = row.operator("mesh.remove_doubles", icon='MESH_DATA')
		row = box.row()
		button = row.operator("mesh.separate_by_material", icon='MESH_DATA')
		row = box.row()
		button = row.operator("mesh.join_all_meshes", icon='MESH_DATA')
		row = box.row()
		button = row.operator("mesh.select_0_weight_vertices", icon='MESH_DATA')



class ButtonSplitMeshAlongUVs(bpy.types.Operator):
	bl_idname = "mesh.split_mesh_along_uvs"
	bl_label = "Along UV Islands"
	bl_description = "Splits the edges along UV Islands to prevent UVs from joining on export."
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		return (context.active_object is not None and
				context.active_object.type == 'MESH')

	def execute(self, context):
		try:
			print(f"Button {bl_label} clicked!")
			self.report({'INFO'}, f"Mesh(es) successfully split along UVs!")
		except Exception as err:
			print(f"{err}")
			pass
		return {'FINISHED'}

class ButtonTranslateBonesToUnityBlender(bpy.types.Operator):
	bl_idname = "armature.translate_bones_to_unity_blender"
	bl_label = "Unity/Blender"
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = "Translates general humanoid bones in the GBFR naming scheme to a Unity/Blender naming scheme."

	@classmethod
	def poll(cls, context):
		return (context.active_object is not None and
				context.active_object.type == 'ARMATURE')

	def execute(self, context):
		try:
			armature = context.active_object
			armature_data = armature.data
			utils_rename_bones(armature_data, name_to_index = False)
			self.report({'INFO'}, f"Bone names translated to Unity/Blender Format!")
		except Exception as err:
			print(f"{err}")
			pass
		return {'FINISHED'}

class ButtonTranslateBonesToGBFR(bpy.types.Operator):
	bl_idname = "armature.translate_bones_to_gbfr"
	bl_label = "GBFR"
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = "Translates general humanoid bones in the Unity/Blender naming scheme to the GBFR naming scheme."


	@classmethod
	def poll(cls, context):
		return (context.active_object is not None and
				context.active_object.type == 'ARMATURE')

	def execute(self, context):
		try:
			armature = context.active_object
			armature_data = armature.data
			utils_rename_bones(armature_data, name_to_index = True)
			self.report({'INFO'}, f"Bone names translated to GBFR Format!")
		except Exception as err:
			print(f"{err}")
			pass
		return {'FINISHED'}

class ButtonSeparateByMaterial(bpy.types.Operator):
	bl_idname = "mesh.separate_by_material"
	bl_label = "Separate By Materials"
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = "Separates the actively selected mesh by materials and names them accordingly."

	@classmethod
	def poll(cls, context):
		return (context.active_object is not None and
				context.active_object.type == 'MESH')

	def execute(self, context):
		try:
			utils_separate_by_materials(context)
			self.report({'INFO'}, f"Separated by Materials!")
		except Exception as err:
			print(f"{err}")
			pass
		return {'FINISHED'}

class ButtonSortMaterials(bpy.types.Operator):
	bl_idname = "mesh.sort_materials"
	bl_label = "Sort Materials"
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = "Separates the model's meshes by materials, then sorts and joins them in roughly the same order as GBFR's material sorting order."

	@classmethod
	def poll(cls, context):
		return (context.active_object is not None and
				context.active_object.type == 'MESH')

	def execute(self, context):
		try:
			utils_reorder_materials(context)
			self.report({'INFO'}, f"Sorted all Materials!")
		except Exception as err:
			print(f"{err}")
			# raise Exception(f"{err}")
			pass
		return {'FINISHED'}

class ButtonJoinAllMeshes(bpy.types.Operator):
	bl_idname = "mesh.join_all_meshes"
	bl_label = "Join All Meshes"
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = "Joins all the model's meshes"

	@classmethod
	def poll(cls, context):
		return (context.active_object is not None and
				(context.active_object.type == 'MESH' or context.active_object.type == 'ARMATURE'))

	def execute(self, context):
		try:
			utils_join_meshes(context, selected_only = False)
			self.report({'INFO'}, f"Joined all meshes!")
		except Exception as err:
			print(f"{err}")
			raise Exception(f"{err}")
			pass
		return {'FINISHED'}

class ButtonSelect0WeightVertices(bpy.types.Operator):
	bl_idname = "mesh.select_0_weight_vertices"
	bl_label = "Select Zero Weight Vertices"
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = "Selects all vertices on the active mesh that have no weights."

	@classmethod
	def poll(cls, context):
		return (context.active_object is not None and
				context.active_object.type == 'MESH')

	def execute(self, context):
		try:
			active_object = context.active_object
			utils_select_0_weight_vertices(active_object)
			self.report({'INFO'}, f"Selected !")
		except Exception as err:
			print(f"{err}")
			raise Exception(f"{err}")
			pass
		return {'FINISHED'}

# Register the panel class
def register():
	bpy.utils.register_class(GBFRToolPanel)
	bpy.utils.register_class(ButtonSplitMeshAlongUVs)
	bpy.utils.register_class(ButtonTranslateBonesToGBFR)
	bpy.utils.register_class(ButtonTranslateBonesToUnityBlender)
	bpy.utils.register_class(ButtonSeparateByMaterial)
	bpy.utils.register_class(ButtonSortMaterials)
	bpy.utils.register_class(ButtonJoinAllMeshes)
	bpy.utils.register_class(ButtonSelect0WeightVertices)

# Unregister the panel class
def unregister():
	bpy.utils.unregister_class(GBFRToolPanel)
	bpy.utils.unregister_class(ButtonSplitMeshAlongUVs)
	bpy.utils.unregister_class(ButtonTranslateBonesToGBFR)
	bpy.utils.unregister_class(ButtonTranslateBonesToUnityBlender)
	bpy.utils.unregister_class(ButtonSeparateByMaterial)
	bpy.utils.unregister_class(ButtonSortMaterials)
	bpy.utils.unregister_class(ButtonJoinAllMeshes)
	bpy.utils.unregister_class(ButtonSelect0WeightVertices)

# Test the panel in Blender
# if __name__ == "__main__":
# 	register()
