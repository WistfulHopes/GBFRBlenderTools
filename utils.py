import bpy
import re
import urllib
import difflib # For bone tranlations

from .bone_name_mappings import BONE_NAME_MAPPINGS


def format_exception(exception_string): # raise_noob_readable_exception
	# Prints a much more noticable exception for people to read.
	return f"\n\n==============================\n!!!HEY YOU, READ THIS!!!\n==============================\n{exception_string}"

# Borrowed from NieR2Blender2NieR - https://github.com/WoefulWolf/NieR2Blender2NieR
def show_message_box(message = "", title = "Message Box", icon = 'INFO'):
    def draw(self, context):
        self.layout.label(text = message)
        self.layout.alignment = 'CENTER'
    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

def utils_get_magic():
	magic = 100000101 # Default Hard coded value
	# try: # Get latest magic # from github
	# 	url = "https://raw.githubusercontent.com/WistfulHopes/GBFRBlenderTools/main/magic.txt"
	# 	res = urllib.request.urlopen(url)
	# 	print(f"fetch magic res status: {res.status}")
	# 	if res.status == 200: # OK
	# 		data = res.read()
	# 		print(f"magic res data returned: {data}")
	# 		number = int(data.decode('utf-8').strip())
	# 		if number > magic: # If the fetched number is newer, use it
	# 			magic = number
	# except Exception as err:
	# 	print(f"Error: {str(err)}")
	# 	pass

	return magic

def utils_set_mode(mode):
	if bpy.ops.object.mode_set.poll():
		bpy.ops.object.mode_set(mode=mode, toggle=False)

def utils_select_active(obj):
	bpy.context.view_layer.objects.active = obj

def utils_test():
	print("\n\n!!!NARMAYA IS BEST!!!\n\n")
	raise Exception("!!!NARMAYA IS BEST!!!")

def utils_show_message(message = "", title = "Message", icon = 'INFO'):
	def draw(self, context):
		self.layout.label(text = message)
		self.layout.alignment = 'CENTER'
	bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

def fix_normals(obj):
	obj.select_set(True)
	utils_set_mode('EDIT')
	bpy.ops.mesh.select_all(action='SELECT')
	bpy.ops.mesh.flip_normals()
	utils_set_mode('OBJECT')

def split_faces_by_edge_seams(obj): # Split mesh faces by seams
	utils_set_mode('EDIT')
	bpy.ops.mesh.select_all(action='SELECT')

	bpy.ops.uv.select_all(action='SELECT') # Select all UVs
	bpy.ops.uv.seams_from_islands(mark_seams=True) # Mark boundary edges of UV islands as seams

	bpy.context.tool_settings.mesh_select_mode = (False, True, False) # Set Edge Select
	bpy.ops.mesh.select_all(action = 'DESELECT')
	
	utils_set_mode('OBJECT') # For some reason we can only select edges in object mode ???????? :) Funny Blender
	for edge in obj.data.edges: # Select all edge seams
		if edge.use_seam:
			edge.select = True

	utils_set_mode('EDIT')
	
	bpy.ops.mesh.edge_split(type='EDGE') # Split faces by selected edge seams
	# utils_set_mode('OBJECT')

	# Just split all faces by all edges (like how imported, avoids UV stitching and Normals issues)
	# bpy.ops.mesh.select_all(action = 'SELECT')
	# bpy.ops.mesh.edge_split(type='EDGE')

def utils_rename_bones(armature, name_to_index = False):
	all_dictionary_names = [] # Put all english translation names into one list
	[all_dictionary_names.extend(names) for names in BONE_NAME_MAPPINGS.values()]
	all_dictionary_names = [name.lower().replace(' ','_').strip(" _.") for name in all_dictionary_names]
	# Iterate over the armature's bones and apply translations
	for bone in armature.bones:
		if not name_to_index: # Bone Index to Name
			try: #Rename the bone
				bone.name = BONE_NAME_MAPPINGS[bone.name][0]
			except: # Bone name doesn't exist in bone name list
				pass
		if name_to_index: # Bone Name to Index
			try: #Rename the bone
				if 'original_name' in bone: # If original name variable stored in bone
					bone.name = bone['original_name']
				else: #Get the closest matching bone name
					name_matches = difflib.get_close_matches(bone.name.lower().replace(' ','_').strip(" _."), all_dictionary_names, 1, 0.8)
					if len(name_matches) == 0: continue
					print(f"bone.name:{bone.name}\t|\tname_matches:{name_matches}")
					closest_name = name_matches[0]
					for index, names in BONE_NAME_MAPPINGS.items():
						names = [name.lower().replace(' ','_').strip(" _.") for name in names]
						if closest_name in names:
							bone.name = index
							break
			except:
				pass

def utils_separate_by_materials(context, obj):
	mesh_name = obj.data.name
	if len(obj.data.materials) <= 1: return
	separated_mesh_root = bpy.data.objects.new(mesh_name, None)
	separated_mesh_root.empty_display_size = 0.25
	obj.users_collection[0].objects.link(separated_mesh_root)
	separated_mesh_root.parent = obj.parent

	utils_set_mode('EDIT')
	bpy.ops.mesh.select_all(action='SELECT')
	bpy.ops.mesh.separate(type='MATERIAL')
	utils_set_mode('OBJECT')
	# Rename objects based on material names

	for obj in context.selected_objects:
		material_name = obj.active_material.name if obj.active_material else obj.data.name
		obj.name = f"{mesh_name}.{material_name}"
		obj.parent = separated_mesh_root
		obj.select_set(False)

# TODO: Rejoin meshes properly.
def utils_join_meshes(context, selected_only = False):
	utils_set_mode('OBJECT')
	active_object = context.active_object
	if active_object.type == "MESH":
		utils_select_active(active_object.parent)
		active_object = active_object.parent
	if active_object.type in ('ARMATURE', 'EMPTY'):
		root_obj = active_object
		meshes = [obj for obj in root_obj.children if obj.type == 'MESH']
		bpy.ops.object.select_all(action='DESELECT') #Clear selections
		if meshes: # Join the meshes
			utils_select_active(meshes[0]) # set first as active
			for mesh in meshes: mesh.select_set(True)
			bpy.ops.object.join()
			active_object = context.active_object
			active_object.name = active_object.name.split('.')[0]
			parent_obj = active_object.parent
			if parent_obj and active_object.parent.name.split('.')[0] == active_object.name.split('.')[0]:
				active_object.parent = parent_obj.parent
				bpy.data.objects.remove(parent_obj)
		else:
			print("No meshes found under the selected armature.")
	


# Re-Orders the mesh's materials based on alphabetic order of the first character
# then by reverse numberically of the next 2 characters, then lastly by .# index at the end
def utils_reorder_materials(context):
	mesh_name = context.active_object.name

	# armature = context.active_object.find_armature()
	# if "material_order" in armature:
	# 	material_order = armature["material_order"]
	# else:
	# 	raise UserWarning(
	# 		format_exception("No imported material order stored for this model, unable to sort.")
	# 	)
	

	utils_separate_by_materials(context) #Separate by materials first to give the neshes their material names

	# Get meshes
	meshes = context.selected_objects
	print(f"{meshes}")

	# Sort selected objects by name
	sorted_meshes = sorted(meshes, key=lambda obj: (
		obj.name[0], # Order by first character alaphabetically
		-int(obj.name[1:3]) if obj.name[1:3].isdigit() else 0, #Then by reverse numerically on 2nd character if it's a number
		int(''.join(filter(str.isdigit, obj.name))) #Then numerically by material .# index number
		)
	)

	bpy.ops.object.select_all(action='DESELECT') #Clear selections
	# Select the first object in the sorted list
	if sorted_meshes:
		utils_select_active(sorted_meshes[0])
		sorted_meshes[0].select_set(True)

	# Join meshes one by one
	for idx, obj in enumerate(sorted_meshes[0:]):
		print(f"Joining: {bpy.context.view_layer.objects.active}\t&\t{obj.name}")
		obj.select_set(True)
		bpy.ops.object.join()

	context.active_object.name = mesh_name # Restore original Name
	bpy.ops.object.select_all(action='DESELECT') # Clear selections

# Select all 0 weight vertices on mesh
# Credit to WolfieBeat
def utils_select_0_weight_vertices(mesh):
	zero_weight_vert_count = 0
	utils_set_mode('EDIT')
	bpy.ops.mesh.select_mode(type="VERT")
	bpy.ops.mesh.reveal(select=False) # Unhide all vertices
	bpy.ops.mesh.select_all(action='DESELECT')
	mesh_data = mesh.data
	utils_set_mode('OBJECT') # Funny blender only allows object mode selection :)
	for vertex in mesh_data.vertices:
		total_vert_weight = 0.0 # keep track of vertex's total weight
		for vertex_group in vertex.groups: # add up total weightr for each vertex group vert belongs to
			total_vert_weight += vertex_group.weight
		if total_vert_weight == 0.0: # if the vertex weights doesn't add up to roughly 1.0, select it
			vertex.select = True
			zero_weight_vert_count += 1
	utils_set_mode('EDIT')
	return zero_weight_vert_count

# Limit and Normalize all vertex weights
def UtilsLimitAndNormalizeWeights(mesh, limit_number=8):
	# for vg in mesh.vertex_groups: # <- Unnecessary
	# limit total weight group assignments per vertex
	bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=limit_number)
	# normalize all weights
	bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)