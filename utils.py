import bpy

def format_exception(exception_string): # raise_noob_readable_exception
	# Prints a much more noticable exception for people to read.
	return f"\n\n==============================\n!!!HEY YOU, READ THIS!!!\n==============================\n{exception_string}"

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


bone_names_mapping = {
	"_900": "Root",
	"_000": "Hips",
	"_001": "Spine",
	"_002": "Chest",
	"_003": "Upper Chest",
	"_004": "Neck",
	"_a04": "Neck Deform",
	"_005": "Head",
	"_00a": "Shoulder_L",
	"_006": "Shoulder_R",
	"_00b": "Upper Arm_L",
	"_007": "Upper Arm_R",
	"_a0b": "Upper Arm Deform_L",
	"_a07": "Upper Arm Deform_R",
	"_00c": "Lower Arm_L",
	"_008": "Lower Arm_R",
	"_a0c": "Lower Arm Deform_L",
	"_a08": "Lower Arm Deform_R",
	"_00d": "Hand_L",
	"_009": "Hand_R",
	"_a0d": "Hand Deform_L",
	"_a09": "Hand Deform_R",
	"_200": "Thumb Metacarpal_L",
	"_201": "Thumb Proximal_L",
	"_202": "Thumb Distal_L",
	"_211": "Index Proximal_L",
	"_212": "Index Middle_L",
	"_213": "Index Distal_L",
	"_221": "Middle Proximal_L",
	"_221": "Middle Middle_L",
	"_221": "Middle Distal_L",
	"_230": "Ring Metacarpal_L",
	"_231": "Ring Proximal_L",
	"_232": "Ring Middle_L",
	"_233": "Ring Distal_L",
	"_240": "Little Metacarpal_L",
	"_241": "Little Proximal_L",
	"_242": "Little Middle_L",
	"_243": "Little Distal_L",
	"_100": "Thumb Metacarpal_R",
	"_101": "Thumb Proximal_R",
	"_102": "Thumb Distal_R",
	"_111": "Index Proximal_R",
	"_112": "Index Middle_R",
	"_113": "Index Distal_R",
	"_121": "Middle Proximal_R",
	"_121": "Middle Middle_R",
	"_121": "Middle Distal_R",
	"_130": "Ring Metacarpal_R",
	"_131": "Ring Proximal_R",
	"_132": "Ring Middle_R",
	"_133": "Ring Distal_R",
	"_140": "Little Metacarpal_R",
	"_141": "Little Proximal_R",
	"_142": "Little Middle_R",
	"_143": "Little Distal_R",
	"_012": "Upper Leg_L",
	"_00e": "Upper Leg_R",
	"_a12": "Upper Leg Deform_L",
	"_a0e": "Upper Leg Deform_R",
	"_013": "Lower Leg_L",
	"_00f": "Lower Leg_R",
	"_a13": "Lower Leg Deform_L",
	"_a0f": "Lower Leg Deform_R",
	"_014": "Foot_L",
	"_010": "Foot_R",
	"_a14": "Foot Deform_L",
	"_a10": "Foot Deform_R",
	"_015": "Toes_L",
	"_011": "Toes_R",
	"_8a0": "Eye_L",
	"_8a1": "Eye_R",
}

def utils_rename_bones(armature, name_to_index = False):
	# Iterate over the armature's bones and apply translations
	for bone in armature.bones:
		if not name_to_index: # Bone Index to Name
			try: #Rename the bone
				bone.name = bone_names_mapping[bone.name]
			except: # Bone name doesn't exist in bone name list
				pass
		if name_to_index: # Bone Name to Index
			try: #Rename the bone
				for index, name in bone_names_mapping.items():
					if bone.name in name:
						bone.name = index
						break
			except:
				pass


def utils_separate_by_materials(context):
	utils_set_mode('EDIT')
	bpy.ops.mesh.select_all(action='SELECT')
	bpy.ops.mesh.separate(type='MATERIAL')
	utils_set_mode('OBJECT')
	# Rename objects based on material names
	for obj in context.selected_objects:
		if obj.type == 'MESH':
			material_name = obj.active_material.name if obj.active_material else obj.name
			obj.name = material_name

# Re-Orders the mesh's materials based on alphabetic order of the first character
# then by reverse numberically of the next 2 characters, then lastly by .# index at the end
def utils_reorder_materials(context):
	mesh_name = context.active_object.name
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


def utils_join_meshes(context, selected_only = False):
	active_object = context.active_object
	if active_object.type == "MESH":
		utils_select_active(active_object.parent)
		active_object = active_object.parent
	if active_object.type == 'ARMATURE':
		armature = active_object
		meshes = [obj for obj in armature.children if obj.type == 'MESH']
		bpy.ops.object.select_all(action='DESELECT') #Clear selections
		if meshes: # Join the meshes
			utils_select_active(meshes[0]) # set first as active
			for mesh in meshes: mesh.select_set(True)
			bpy.ops.object.join()
			context.active_object.name = armature.name + "_Mesh"
		else:
			print("No meshes found under the selected armature.")
	pass

# Select all 0 weight vertices on mesh
def utils_select_0_weight_vertices(mesh):
	utils_set_mode('EDIT')
	bpy.ops.mesh.select_mode(type="VERT")
	bpy.ops.mesh.select_all(action='DESELECT')
	bpy.ops.mesh.select_ungrouped()