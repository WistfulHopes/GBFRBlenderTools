import bpy
import difflib # For bone tranlations

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
	"_900": ["Root"],
	"_000": ["Hips", "Waist", "Pelvis"],
	"_001": ["Spine_1", "Spine"],
	"_002": ["Spine_2"],
	"_003": ["Chest", "Upper Chest"],
	"_004": ["Neck"],
	"_a04": ["Neck Deform", "Neck Twist"],
	"_005": ["Head"],
	"_00a": ["Shoulder_L", "Shoulder_Left", "Clavicle_L", "Clavicle_Left", "Left Shoulder"],
	"_006": ["Shoulder_R", "Shoulder_Right", "Clavicle_R", "Clavicle_Right", "Right Shoulder"],
	"_00b": ["Upper Arm_L", "Upper Arm_Left", "Left Arm", "Arm_L", "Arm Left"],
	"_007": ["Upper Arm_R", "Upper Arm_Right", "Right Arm", "Arm_R", "Arm Right"],
	"_a0b": ["Upper Arm Deform_L", "Upper Arm Deform_Left", "Upper Arm Twist_L", "Upper Arm Twist_Left", "Left Arm Deform", "Left Arm Twist", "Arm Deform_L", "Arm Twist_L", "Arm Deform Left", "Arm Twist Left"],
	"_a07": ["Upper Arm Deform_R", "Upper Arm Deform_Right", "Upper Arm Twist_R", "Upper Arm Twist_Right", "Right Arm Deform", "Right Arm Twist", "Arm Deform_R", "Arm Twist_R", "Arm Deform Left", "Arm Twist Right"],
	"_00c": ["Lower Arm_L", "Lower Arm_Left", "Left Lower Arm", "Elbow_L", "Elbow_Left", "Left Elbow"],
	"_008": ["Lower Arm_R", "Lower Arm_Right", "Left Lower Arm", "Elbow_R", "Elbow_Right", "Right Elbow"],
	"_a0c": ["Lower Arm Deform_L", "Lower Arm Deform_Left", "Left Lower Arm Deform", "Elbow Deform_L", "Elbow Deform_Left", "Left Elbow Deform", "Lower Arm Twist_L", "Lower Arm Twist_Left", "Left Lower Arm Twist", "Elbow Twist_L", "Elbow Twist_Left", "Left Elbow Twist"],
	"_a08": ["Lower Arm Deform_R", "Lower Arm Deform_Right", "Left Lower Arm Deform", "Elbow Deform_R", "Elbow Deform_Right", "Right Elbow Deform", "Lower Arm Twist_R", "Lower Arm Twist_Right", "Left Lower Arm Twist", "Elbow Twist_R", "Elbow Twist_Right", "Right Elbow Twist"],
	"_00d": ["Hand_L", "Hand_Left", "Left Hand", "Wrist_L", "Wrist_Left", "Left Wrist"],
	"_009": ["Hand_R", "Hand_Right", "Right Hand", "Wrist_R", "Wrist_Right", "Right Wrist"],
	"_a0d": ["Hand Deform_L", "Hand Deform_Left", "Left Hand Deform", "Wrist Deform_L", "Wrist Deform_Left", "Left Wrist Deform", "Hand Twist_L", "Hand Twist_Left", "Left Hand Twist", "Wrist Twist_L", "Wrist Twist_Left", "Left Wrist Twist"],
	"_a09": ["Hand Deform_R", "Hand Deform_Right", "Right Hand Deform", "Wrist Deform_R", "Wrist Deform_Right", "Right Wrist Deform", "Hand Twist_R", "Hand Twist_Right", "Right Hand Twist", "Wrist Twist_R", "Wrist Twist_Right", "Right Wrist Twist"],
	"_200": ["Thumb Metacarpal_L", "Thumb_01_L"],
	"_201": ["Thumb Proximal_L", "Thumb_02_L"],
	"_202": ["Thumb Distal_L", "Thumb_03_L"],
	"_211": ["Index Proximal_L", "Index_01_L"],
	"_212": ["Index Middle_L", "Index_02_L"],
	"_213": ["Index Distal_L", "Index_03_L"],
	"_221": ["Middle Proximal_L", "Middle_01_L"],
	"_221": ["Middle Middle_L", "Middle_02_L"],
	"_221": ["Middle Distal_L", "Middle_03_L"],
	"_230": ["Ring Metacarpal_L", "Ring_00_L"],
	"_231": ["Ring Proximal_L", "Ring_01_L"],
	"_232": ["Ring Middle_L", "Ring_02_L"],
	"_233": ["Ring Distal_L", "Ring_03_L"],
	"_240": ["Little Metacarpal_L", "Pinky_00_L"],
	"_241": ["Little Proximal_L", "Pinky_01_L"],
	"_242": ["Little Middle_L", "Pinky_02_L"],
	"_243": ["Little Distal_L", "Pinky_03_L"],
	"_100": ["Thumb Metacarpal_R", "Thumb_01_R"],
	"_101": ["Thumb Proximal_R", "Thumb_02_R"],
	"_102": ["Thumb Distal_R", "Thumb_03_R"],
	"_111": ["Index Proximal_R", "Index_01_R"],
	"_112": ["Index Middle_R", "Index_02_R"],
	"_113": ["Index Distal_R", "Index_03_R"],
	"_121": ["Middle Proximal_R", "Middle_01_R"],
	"_121": ["Middle Middle_R", "Middle_02_R"],
	"_121": ["Middle Distal_R", "Middle_03_R"],
	"_130": ["Ring Metacarpal_R", "Ring_00_R"],
	"_131": ["Ring Proximal_R", "Ring_01_R"],
	"_132": ["Ring Middle_R", "Ring_02_R"],
	"_133": ["Ring Distal_R", "Ring_03_R"],
	"_140": ["Little Metacarpal_R", "Pinky_00_R"],
	"_141": ["Little Proximal_R", "Pinky_01_R"],
	"_142": ["Little Middle_R", "Pinky_02_R"],
	"_143": ["Little Distal_R", "Pinky_03_R"],
	"_012": ["Upper Leg_L", "Upper Leg_Left", "Leg_L", "Leg_Left", "Left Leg"],
	"_00e": ["Upper Leg_R", "Upper Leg_Right", "Leg_R", "Leg_Right", "Right Leg"],
	"_a12": ["Upper Leg Deform_L", "Upper Leg Deform_Left", "Leg Deform_L", "Leg Deform_Left", "Left Leg Deform", "Upper Leg Twist_L", "Upper Leg Twist_Left", "Leg Twist_L", "Leg Twist_Left", "Left Leg Twist"],
	"_a0e": ["Upper Leg Deform_R", "Upper Leg Deform_Right", "Leg Deform_R", "Leg Deform_Right", "Right Leg Deform", "Upper Leg Twist_R", "Upper Leg Twist_Right", "Leg Twist_R", "Leg Twist_Right", "Right Leg Twist"],
	"_013": ["Lower Leg_L", "Lower Leg_Left", "Left Lower Leg", "Knee_L", "Knee_Left", "Left Knee"],
	"_00f": ["Lower Leg_R", "Lower Leg_Right", "Right Lower Leg", "Knee_R", "Knee_Right", "Right Knee"],
	"_a13": ["Lower Leg Deform_L"],
	"_a0f": ["Lower Leg Deform_R"],
	"_014": ["Foot_L", "Foot_Left", "Left Foot", "Ankle_L", "Ankle_Left", "Left Ankle"],
	"_010": ["Foot_R", "Foot_Right", "Right Foot", "Ankle_R", "Ankle_Right", "Right Ankle"],
	"_a14": ["Foot Deform_L", "Foot Deform_Left", "Left Foot Deform", "Ankle Deform_L", "Ankle Deform_Left", "Left Ankle Deform", "Foot Twist_L", "Foot Twist_Left", "Left Foot Twist", "Ankle Twist_L", "Ankle Twist_Left", "Left Ankle Twist"],
	"_a10": ["Foot Deform_R", "Foot Deform_Right", "Right Foot Deform", "Ankle Deform_R", "Ankle Deform_Right", "Right Ankle Deform", "Foot Twist_R", "Foot Twist_Right", "Right Foot Twist", "Ankle Twist_R", "Ankle Twist_Right", "Right Ankle Twist"],
	"_015": ["Toes_L", "Toes_Left", "Left Toes"],
	"_011": ["Toes_R", "Toes_Right", "Right Toes"],
	"_8a0": ["Eye_L", "Eye_Left", "Left Eye", "Pupil_L", "Pupil_Left", "Left Pupil"],
	"_8a1": ["Eye_R", "Eye_Right", "Right Eye", "Pupil_R", "Pupil_Right", "Right Pupil"],
}

def utils_rename_bones(armature, name_to_index = False):
	all_dictionary_names = [] # Put all english translation names into one list
	[all_dictionary_names.extend(names) for names in bone_names_mapping.values()]
	all_dictionary_names = [name.lower().replace(' ','_').strip(" _.") for name in all_dictionary_names]
	# Iterate over the armature's bones and apply translations
	for bone in armature.bones:
		if not name_to_index: # Bone Index to Name
			try: #Rename the bone
				bone.name = bone_names_mapping[bone.name][0]
			except: # Bone name doesn't exist in bone name list
				pass
		if name_to_index: # Bone Name to Index
			try: #Rename the bone
				#Get the closest matching bone name
				name_matches = difflib.get_close_matches(bone.name.lower().replace(' ','_').strip(" _."), all_dictionary_names, 1, 0.8)
				if len(name_matches) == 0: continue
				# print(f"bone.name:{bone.name}\t|\tname_matches:{name_matches}")
				closest_name = name_matches[0]
				for index, names in bone_names_mapping.items():
					names = [name.lower().replace(' ','_').strip(" _.") for name in names]
					if closest_name in names:
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
	armature = context.active_object.find_armature()

	if "material_order" in armature:
		material_order = armature["material_order"]
	else:
		raise UserWarning(
			format_exception("No imported material order stored for this model, unable to sort.")
		)
	

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
	utils_set_mode('OBJECT')
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
def utils_limit_and_normalize_weights(mesh):
	for vg in mesh.vertex_groups:
		# limit total weights to 4
		bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
		# normalize all weights
		bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)