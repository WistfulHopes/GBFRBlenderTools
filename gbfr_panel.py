import bpy
import os
import webbrowser
import urllib.request
from .utils import *

DIR_PATH = os.path.dirname(os.path.abspath(__file__))
ICONS_PATH = os.path.join(DIR_PATH, "icons")
PCOLL = None
preview_collections = {}
curr_game_magic = utils_get_magic()

# Define the panel class
class GBFRToolPanel_Fixes(bpy.types.Panel):
	"""Creates a custom panel in the Object properties editor"""
	bl_label = "Fixes"
	bl_idname = "VIEW3D_PT_GBFR_Tools_Panel_Fixes"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "GBFR"

	def draw(self, context):
		layout = self.layout
		# Add a boolean property with a tooltip
		# layout.label(text="Fixes")
		box = layout.box()

		row = box.row(align=True) ; row.scale_y = 0.5
		row.label(text="Split Vertices:", icon="MESH_DATA")
		row = box.row(align=True) ; row.scale_y = 1.5
		button = row.operator("mesh.split_mesh_along_uvs", icon='UV')
		# row = box.row() ; row.scale_y = 0.5

		# row = box.row() ; row.scale_y = 0.5
		# row.label(text="Recommended to use this before export", icon='ERROR')
		# row = box.row(align=True) ; row.scale_y = 1.5
		# button = row.operator("mesh.sort_materials", icon='MATERIAL')

		# row = box.row() ; row.scale_y = 0.5
		row = box.row() ; row.scale_y = 0.5
		row.label(text="Mesh Clean Up:", icon='MESH_DATA')
		row = box.row() ; row.scale_y = 1.5
		button = row.operator("mesh.limit_and_normalize_weights", icon='MESH_DATA')
		row = box.row() ; row.scale_y = 1.5
		button = row.operator("mesh.delete_loose_edges_and_verts", icon = "MESH_DATA")

		# ----------------------------

class GBFRToolPanel_Utilities(bpy.types.Panel):
	bl_label = "Utilities"
	bl_idname = "VIEW3D_PT_GBFR_Tools_Panel_Utilities"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "GBFR"

	def draw(self, context):
		layout = self.layout
		# layout.label(text="Utilities", icon='MODIFIER')
		box = layout.box()

		# Armature
		box.label(text="Armature:", icon='ARMATURE_DATA')
		row = box.row() ; row.scale_y = 0.5	
		row.label(text="Translate Bones To:", icon="BONE_DATA")
		
		row = box.row(align=True) ; row.scale_y = 1.5
		button = row.operator("armature.translate_bones_to_unity_blender", icon='NONE')
		button = row.operator("armature.translate_bones_to_gbfr", icon='NONE')

		# Mesh
		box.label(text="Mesh:", icon='MESH_DATA')
		
		col = box.column(align=True)
		row = col.row() ; row.scale_y = 1.4
		button = row.operator("mesh.separate_by_material", icon='MESH_DATA')
		
		row = col.row() ; row.scale_y = 1.4
		button = row.operator("mesh.join_all_meshes", icon='MESH_DATA')
		
		row = box.row()
		button = row.operator("mesh.select_0_weight_vertices", icon='MESH_DATA')
		
		row = box.row()
		button = row.operator("mesh.flip_normals", icon='MESH_DATA')
		
		row = box.row()
		button = row.operator("mesh.remove_doubles", text="Remove Doubles", icon='MESH_DATA')
		button.use_unselected = True
		button.threshold = 0.000001 # Use this threshold or all hell breaks loose


class GBFRToolPanel_Materials(bpy.types.Panel):
	bl_label = "Materials"
	bl_idname = "VIEW3D_PT_GBFR_Tools_Panel_Materials"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "GBFR"

	def draw(self, context):
		layout = self.layout
		# layout.label(text="Materials", icon='MATERIAL')
		box = layout.box()
		obj = context.object
		if obj and obj.type == 'MESH':
			mesh = obj.data
			materials = mesh.materials
			col = box.column(align=True)
			row = col.row(align=False)
			row.label(text = "", icon = "INFO")
			row = col.row(align=False) ; row.scale_y = 0.5
			row.label(text = "Used to set the index of materials")
			row = col.row(align=False) ; row.scale_y = 0.5
			row.label(text = "to their equivalents in the .mmat.")
			row = box.row(align=False) ; row.scale_y = 0.5
			row.label(text = "Material Name:")
			row.label(text = "Material Index:")
			col = box.column(align=True)
			for slot_index, material in enumerate(materials):
				if material:
					row = col.row(align=True)
					row.prop(material, "name", text="")
					material_id = material.get("MaterialID", None)
					if material_id != None:
						if material_id < 0 and material_id:
							row.alert = True # Highlight red to alert user
						row.prop(material, '["MaterialID"]', text="")						
					else:
						row.alert = True # Highlight red to alert user
						op = row.operator("material.add_material_index")
						op.material_slot = slot_index
		else:
			row = box.row(align=False)
			row.label(text = "Select a mesh to configure materials.", icon = "ERROR")

class GBFRToolPanel_Advanced(bpy.types.Panel):
	bl_label = "Advanced"
	bl_idname = "VIEW3D_PT_GBFR_Tools_Panel_Advanced"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "GBFR"
	bl_options = {"DEFAULT_CLOSED"}

	def draw(self, context):
		layout = self.layout
		box = layout.box()
		col = box.column(align=True)
		obj = context.object
		if obj and obj.type != 'ARMATURE':
			if obj.parent.type == 'ARMATURE':
				obj = obj.parent
		armature = obj
		if armature and armature.type == 'ARMATURE':
			row = col.row(align=False)
			row.label(text = f".minfo Magic Number:", icon="SHADERFX")
			row = col.row(align=False)
			row.label(text = f"Only edit this if game's Magic Number has changed!", icon="ERROR")
			row = col.row(align=False)
			magic = armature.get("Magic", None)
			
			if magic != None:
				if curr_game_magic > magic: row.alert = True # Highlight if model's version is older
				row.prop(armature, '["Magic"]', text="")
			else:
				row.alert = True
				row.operator("armature.add_magic_number")
			row = col.row(align=False) ; row.scale_y = 0.75
			row.label(text = f"Game's current .minfo magic: {curr_game_magic}", icon="INFO")
			


class GBFRToolPanel_Credits(bpy.types.Panel):
	global PCOLL
	bl_label = "Credits"
	bl_idname = "VIEW3D_PT_GBFR_Tools_Panel_Credits"
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "GBFR"
	bl_options = {"DEFAULT_CLOSED"}

	def draw(self, context):
		layout = self.layout
		box = layout.box()
		col = box.column(align=True)
		row = col.row(align=False)
		row.label(text = f"GBFR Blender Tools", icon_value=preview_collections["icons"]["GBFR_Modding"].icon_id)
		col.separator()
		row = col.row(align=False) ; row.scale_y = 0.75
		row.label(text = "Created by:")
		row = col.row(align=False) ; row.scale_y = 0.75
		row.label(text = "WistfulHopes & AlphaSatanOmega")
		col.separator()
		row = col.row(align=False) ; row.scale_y = 0.75
		row.label(text = "Special thanks:")
		row = col.row(align=False) ; row.scale_y = 0.75
		row.label(text = "WolfieBeat, bujyu-uo, rurires")
		#TODO: Add discord and github button
		col.separator()
		row = col.row() ; row.scale_y = 1.4
		button = row.operator("gbfr.discord", icon_value=preview_collections["icons"]["discord"].icon_id)
		row = col.row() ; row.scale_y = 1.4
		button = row.operator("gbfr.website", icon_value=preview_collections["icons"]["GBFR_Modding"].icon_id)
		row = col.row() ; row.scale_y = 1.4
		button = row.operator("gbfr.github", icon_value=preview_collections["icons"]["github"].icon_id)

		col.separator()
		row = col.row(align=False) ; row.scale_y = 0.75
		row.label(text = "KEEP IT CLEAN!", icon_value=preview_collections["icons"]["KEEPITCLEAN"].icon_id)



#=======================
# Operator Classes
#=======================

class ButtonAddMaterialIndex(bpy.types.Operator):
	bl_idname = "material.add_material_index"
	bl_label = "Add Material Index"
	bl_description = "Add a Material Index to this Material"
	bl_options = {'REGISTER', 'UNDO'}

	# material = bpy.props.PointerProperty(type=bpy.types.Material)
	material_slot: bpy.props.IntProperty(default=-1)

	@classmethod
	def poll(cls, context):
		return (context.active_object is not None and
				context.active_object.type == 'MESH')

	def execute(self, context):
		try:
			mesh = context.object.data
			materials = mesh.materials
			for slot_index, material in enumerate(materials):
				if slot_index == self.material_slot:
					material["MaterialID"] = -1
					# self.report({'INFO'}, f"{material.name}")
		except Exception as err:
			raise Exception(f"{err}")
		return {'FINISHED'}

class ButtonAddMagicNumber(bpy.types.Operator):
	bl_idname = "armature.add_magic_number"
	bl_label = "Add Magic Number"
	bl_description = "Add GBFR's Magic file number to the model"
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		return (context.active_object is not None)

	def execute(self, context):
		try:
			obj = context.object
			if obj.type != 'ARMATURE':
				if obj.parent.type == 'ARMATURE': obj = obj.parent
			if obj.type == 'ARMATURE':
				magic = utils_get_magic()
				obj["Magic"] = magic
				# Set up property
				obj.id_properties_ensure() # ensure manager is updated
				prop_manager = obj.id_properties_ui("Magic")
				prop_manager.update(min=0, max=100000000, default = magic)
		except Exception as err:
			raise Exception(f"{err}")
		return {'FINISHED'}


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
			self.report({'INFO'}, f"Mesh(es) successfully split along UVs!")
			split_faces_by_edge_seams(context.active_object)
		except Exception as err:
			print(f"{err}")
			pass
		return {'FINISHED'}

class ButtonDeleteLooseGeometry(bpy.types.Operator):
	bl_idname = "mesh.delete_loose_edges_and_verts"
	bl_label = "Delete Loose Verts & Edges"
	bl_description = "Deletes Loose any loose Vertices & Edges on the mesh so the model doesn't explode."
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		return (context.active_object is not None and
				context.active_object.type == 'MESH')

	def execute(self, context):
		try:
			mesh = context.active_object.data
			init_verts = len(mesh.vertices) ; init_edges = len(mesh.edges) ; init_faces = len(mesh.polygons)
			utils_set_mode('EDIT')
			bpy.ops.mesh.select_all(action='SELECT')
			bpy.ops.mesh.delete_loose(use_verts=True, use_edges=True, use_faces=False)
			utils_set_mode('OBJECT')
			removed_verts = init_verts - len(mesh.vertices) ; removed_edges = init_edges - len(mesh.edges) ; removed_faces = init_faces - len(mesh.polygons)
			self.report({'INFO'}, f"Removed: {removed_verts} vertices, {removed_edges} edges, {removed_faces} faces")
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
			raise #print(f"{err}")
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
			zero_weight_vert_count = utils_select_0_weight_vertices(active_object)
			self.report({'INFO'}, f"{zero_weight_vert_count} Vertices Selected")
		except Exception as err:
			print(f"{err}")
			raise Exception(f"{err}")
			pass
		return {'FINISHED'}


class ButtonLimitAndNormalizeAllWeights(bpy.types.Operator):
	bl_idname = "mesh.limit_and_normalize_weights"
	bl_label = "Limit & Normalize Weights"
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = "Limits the weights of all vertices on the mesh to 4 vertex groups, and normalizes them."

	@classmethod
	def poll(cls, context):
		return (context.active_object is not None and
				context.active_object.type == 'MESH')

	def execute(self, context):
		try:
			mesh = context.active_object
			utils_limit_and_normalize_weights(mesh)
			self.report({'INFO'}, f"Weights normalized and limited to 4 groups per vetex.")
		except Exception as err:
			print(f"{err}")
			raise Exception(f"{err}")
			pass
		return {'FINISHED'}

class ButtonDiscord(bpy.types.Operator):
	bl_idname = "gbfr.discord"
	bl_label = "Relink Modding Discord"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		webbrowser.open("https://discord.gg/gbsG4CDsru")
		return {'FINISHED'}

class ButtonWebsite(bpy.types.Operator):
	bl_idname = "gbfr.website"
	bl_label = "Relink Modding Website"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		webbrowser.open("https://nenkai.github.io/relink-modding/")
		return {'FINISHED'}

class ButtonGitHub(bpy.types.Operator):
	bl_idname = "gbfr.github"
	bl_label = "GitHub"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		webbrowser.open("https://github.com/WistfulHopes/GBFRBlenderTools")
		return {'FINISHED'}
	


classes = [GBFRToolPanel_Fixes, GBFRToolPanel_Utilities, GBFRToolPanel_Materials, GBFRToolPanel_Advanced, GBFRToolPanel_Credits,
			ButtonSplitMeshAlongUVs, ButtonTranslateBonesToGBFR, ButtonTranslateBonesToUnityBlender, 
			ButtonSeparateByMaterial, ButtonSortMaterials, ButtonJoinAllMeshes, ButtonSelect0WeightVertices, 
			ButtonLimitAndNormalizeAllWeights, ButtonDeleteLooseGeometry, ButtonAddMaterialIndex, ButtonAddMagicNumber,
			ButtonDiscord, ButtonWebsite, ButtonGitHub
			]

# Register the panel class
def register():
	global preview_collections
	for cls in classes:
		bpy.utils.register_class(cls)
	# Load in custom icons
	icon_names = ["GBFR", "GBFR_Modding", "KEEPITCLEAN", "discord", "github"]
	pcoll = bpy.utils.previews.new()
	for icon_name in icon_names:
		pcoll.load(icon_name, os.path.join(ICONS_PATH, icon_name + ".png"), 'IMAGE')
	# Clear and assign icons to preview collection
	if preview_collections.get('icons'):
		bpy.utils.previews.remove(preview_collections['icons'])
	preview_collections['icons'] = pcoll



# Unregister the panel class
def unregister():
	global preview_collections
	# Remove the image preview collection
	for pcoll in preview_collections.values():
		bpy.utils.previews.remove(pcoll)
	preview_collections.clear()

	for cls in classes:
		bpy.utils.unregister_class(cls)

# Test the panel in Blender
# if __name__ == "__main__":
# 	register()
