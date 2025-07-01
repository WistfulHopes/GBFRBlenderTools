import bpy
import bmesh
import mathutils
from mathutils import Vector
import struct
import os
import importlib
from pprint import pprint

from .Entities.MInfo_ModelInfo.ModelInfo import ModelInfo
from .Entities.ModelSkeleton import ModelSkeleton
from .Entities.Vec3 import Vec3
from .utils import *

		
def parse_skeleton(filepath, CurCollection, bone_scale_multiplier = 1.0):
	if os.path.isfile(os.path.splitext(filepath)[0] + ".skeleton"):
		buf = open(os.path.splitext(filepath)[0] + ".skeleton", 'rb').read()
		buf = bytearray(buf)
		skeleton = ModelSkeleton.GetRootAs(buf, 0) # Get skeleton info root in byte array
		
		# Create an armature
		armature_data = bpy.data.armatures.new("Armature")
		armature_obj = bpy.data.objects.new("Armature", armature_data)
		CurCollection.objects.link(armature_obj)
		bpy.context.view_layer.objects.active = armature_obj
		utils_set_mode('EDIT')
			
		SkelTable = []
		print("skeleton.BodyLength()", skeleton.BodyLength())
		for n in range(skeleton.BodyLength()): # For bone index in skeleton
			bone = skeleton.Body(n) # Get the bone's information
			# Set bone info
			pos = (bone.Position().X(), bone.Position().Y(), bone.Position().Z())
			quat = (bone.Quat().W(), bone.Quat().X(), bone.Quat().Y(), bone.Quat().Z())
			scale = (max(bone.Scale().X(),0.01), max(bone.Scale().Y(),0.01), max(bone.Scale().Z(),0.01))
			# Make sure min scale value isn't too small, else blender just deletes the bone without warning ¯\_(ツ)_/¯
			
			parent_index = bone.ParentId()
			# Append position and rotation dictionary to SkelTable list
			SkelTable.append({"Pos":pos,"Rot":quat, "Scale":scale})
			
			name = bone.Name().decode('ascii') # Decode the bone's name

			# Set up blender bone
			edit_bone = armature_obj.data.edit_bones.new(name) # Add bone to armature
			edit_bone.use_connect = False # Don't connect to parent
			edit_bone.use_inherit_rotation = True
			edit_bone.inherit_scale = 'FULL'
			edit_bone.use_local_location = True
			edit_bone.head = (0, 0, 0)
			edit_bone.tail = (0, 0.05 * bone_scale_multiplier, 0)
			
			if parent_index != 65535: # Parent the bone to its parent if it has a parent
				edit_bone.parent = armature_obj.data.edit_bones[parent_index]

			# Set up blender bone collection (Import Only) # Credit to bujyu-uo
			bone_coll_str = None
			if bone.A1() is not None:
				bone_coll_str = bone.A1().Unk() # A1().Unk() is the bone's bone group
			if bone_coll_str is not None:
				try:
					bone_coll_name = bone_coll_str.to_bytes(4, "little").decode("ASCII").lstrip('\x00')
				except:
					bone_coll_name = "_z"

				if bpy.app.version >= (4, 0, 0):
					if bone_coll_name not in armature_obj.data.collections:
						bone_coll = armature_obj.data.collections.new(bone_coll_name)
					else:
						bone_coll = armature_obj.data.collections[bone_coll_name]

					bone_coll.assign(edit_bone)
				else: # Blender 3 uses bone groups
					SkelTable[n]["BoneGroup"] = bone_coll_name
					print(f"SkelTable[n]['BoneGroup']: {SkelTable[n]['BoneGroup']}")

		# Pose bones based on the position and rotation stored in .skeleton
		utils_set_mode('POSE')
		for x in range(skeleton.BodyLength()):
			pbone = armature_obj.pose.bones[x]
			ebone = armature_obj.data.bones[x]			
			pbone.rotation_mode = 'QUATERNION'
			pbone.rotation_quaternion = SkelTable[x]["Rot"]
			pbone.location = SkelTable[x]["Pos"]
			pbone.scale = SkelTable[x]["Scale"]

			if bpy.app.version < (4, 0, 0): # Blender 3 assign bones to bone groups instead
				if "BoneGroup" not in SkelTable[x]: continue
				bone_group_name = SkelTable[x]["BoneGroup"]
				if bone_group_name not in armature_obj.pose.bone_groups:
					bone_group = armature_obj.pose.bone_groups.new(name=bone_group_name)
					armature_obj.data.layers[-1] = True
				else:
					bone_group = armature_obj.pose.bone_groups[bone_group_name]
				pbone.bone_group = bone_group
				bone_in_layers = [False]*32
				bone_in_layers[pbone.bone_group_index] = True
				ebone.layers = bone_in_layers

		bpy.ops.pose.armature_apply()
		utils_set_mode('OBJECT')
		return armature_obj # Return the armature
	# else: raise FileNotFoundError("ERROR: Make sure you've extracted the model's .skeleton file too.")


   
def parse_mesh_info(filepath):
	# Read .minfo file in as byte array
	buf = open(filepath, 'rb').read()
	buf = bytearray(buf)    
	model_info = ModelInfo.GetRootAs(buf, 0) # Get model info root in byte array
	
	return model_info   

	
def read_some_data(context, minfo_filepath, mmesh_filepath, import_scale): 
	model_name = os.path.splitext(os.path.basename(minfo_filepath))[0] # Get model name from filename

	CurCollection = bpy.data.collections.new(f"GBFR Model Collection_{model_name}") # Create new collection
	bpy.context.scene.collection.children.link(CurCollection)

	utils_set_mode('OBJECT')
	for mesh_obj in bpy.context.selected_objects:
		mesh_obj.select_set(False) #Deselect everything
	
	mesh_info = parse_mesh_info(minfo_filepath) # Parse the mesh info
	armature = parse_skeleton(minfo_filepath, CurCollection) # Parse the skeleton
	
	DeformJointsTable = []
	# Get bone weights indices (which bones have weight)
	for n in range(mesh_info.BonesToWeightIndicesLength()):
		DeformJointsTable.append(mesh_info.BonesToWeightIndices(n))
	
	lod_index = 0
	LOD = mesh_info.Lods(lod_index) # Get mesh LOD info of LOD0 
	# TODO: Load other LODs too - each stored in model_steaming/lod# - figure out 
	# TODO: Figure out way to attempt loading each LOD. 
	# 1. Try Except For Loop on each LOD index? 
	# 2. Find model's mmeshs automatically by user providing model_streaming folder?
	print("mesh_info.LodsLength()", mesh_info.LodsLength())
	
	try: 
		mmesh_file = open(mmesh_filepath, 'rb')
	except Exception as err: 
		raise FileNotFoundError("ERROR: Put the model's .mmesh file in the same folder as the .minfo.\n" 
			+ "The model's original .mmesh can be found under: data/model_streaming/lod0/<modelID>.mmesh")
	
	vert_count = LOD.VertexCount()
	face_count = LOD.PolyCountX3() // 3
	print(f"vert_count = {vert_count} \n face_count = {face_count} \n LOD.PolyCountX3() = {LOD.PolyCountX3()}")
	
	def vertex_flags_to_bools(bitmask): # Map flags to bools
		from .Entities.MInfo_ModelInfo.VertexBufferType import VertexBufferType
		return {
			name: bool(bitmask & value)
			for name, value in VertexBufferType.__dict__.items()
			if not name.startswith("__") and isinstance(value, int) # Skip built-ins
		}
	buffer_type_flags = vertex_flags_to_bools(LOD.BufferTypes()) # Map buffer_types bitmask to bools

	mesh_data = bpy.data.meshes.new("Mesh") # Create mesh data
	if bpy.app.version < (4, 1, 0): mesh_data.use_auto_smooth = True
	mesh_obj = bpy.data.objects.new(f"{model_name}_lod{lod_index}_Mesh", mesh_data) # Create mesh object with model name
	CurCollection.objects.link(mesh_obj)
	utils_select_active(mesh_obj)
	mesh_obj.select_set(True)

	# Store extra LOD parameters in mesh object
	# Unpack to individual bools
	mesh_obj["buffer_types.POS_NOR_TAN_UV0"]  = buffer_type_flags['POS_NOR_TAN_UV0']
	mesh_obj["buffer_types.BLENDINDICES"]     = buffer_type_flags['BLENDINDICES']
	mesh_obj["buffer_types.BLENDINDICES_2"]   = buffer_type_flags['BLENDINDICES_2']
	mesh_obj["buffer_types.BLENDWEIGHT"]      = buffer_type_flags['BLENDWEIGHT']
	mesh_obj["buffer_types.BLENDWEIGHT_2"]    = buffer_type_flags['BLENDWEIGHT_2']
	mesh_obj["buffer_types.COLOR"]            = buffer_type_flags['COLOR']
	mesh_obj["buffer_types.TEXCOORD"]         = buffer_type_flags['TEXCOORD']
	mesh_obj["a6"] = LOD.A6()

	# Assign verts and faces
	mesh = bpy.context.object.data
	bm = bmesh.new()

	VertTable = []
	NormalTable = []
	TangentTable = []
	UVTable = []
	for n in range(vert_count):
		# Vertex
		vBuffer = struct.unpack('<fff', mmesh_file.read(4*3))
		vBuffer = (vBuffer[0], vBuffer[1], vBuffer[2])
		VertTable.append(vBuffer)
		bm.verts.new(vBuffer) # Assign to mesh
		# Normal
		normal = struct.unpack('<eee', mmesh_file.read(2*3))
		normal = (normal[0], normal[1], normal[2])
		NormalTable.append(normal)
		# Tangent
		mmesh_file.seek(2,1)
		tangent = struct.unpack('<eee', mmesh_file.read(2*3))
		tangent = (tangent[0], tangent[2], tangent[1])
		TangentTable.append(tangent)
		# UV
		mmesh_file.seek(2,1)
		UVTable.append(struct.unpack('<ee', mmesh_file.read(2*2)))
	print(f"len(VertTable) = {len(VertTable)}")

	# Build Faces
	FaceTable = []
	vlist = [v for v in bm.verts]
	print(f"len(vlist) = {len(vlist)}")
	duplicate_face_indices = [] # Models can have duplicate faces, blender can't
	mmesh_file.seek(LOD.Buffers(LOD.BuffersLength() - 1).Offset())
	for n in range(face_count):
		face = struct.unpack('<III', mmesh_file.read(4*3))
		face = (face[2], face[1], face[0]) # Faces are built counter-clockwise
		FaceTable.append(face)
		try:
			bm.faces.new((vlist[face[0]],vlist[face[1]],vlist[face[2]]))
		except Exception as err:
			print(f"{n}: {err}")
			duplicate_face_indices.append(n)
			continue
	print(f"len(FaceTable) = {len(FaceTable)}")
	bm.to_mesh(mesh) # Update mesh

	# Apply normals and uvs to faces
	uv_layer = bm.loops.layers.uv.verify()
	Normals = []
	for face in bm.faces:
		face.smooth=True
		for loop in face.loops:
			if NormalTable:
				Normals.append(NormalTable[loop.vert.index])
			try:
				loop[uv_layer].uv = UVTable[loop.vert.index]
			except:
				continue
	bm.to_mesh(mesh) # Update mesh again
	if Normals: mesh_data.normals_split_custom_set(Normals)

	# ========================================================================================
	# Weights
	# ========================================================================================

	WeightIndicesTable = [] ; WeightIndicesTable_2 = []
	WeightTable = [] ; WeightIndicesTable_2 = []
	# Assign vertices to their respective Vertex Groups
	if armature is not None: 
		# TODO: Properly handle buffer types
		lod_buffers_index = 0
		print(f"LOD.BufferTypes() {LOD.BufferTypes()}")
		
		vertex_weights_sets = 0
		if buffer_type_flags['BLENDINDICES'] and buffer_type_flags['BLENDWEIGHT']:
			vertex_weights_sets += 1
		if buffer_type_flags['BLENDINDICES_2'] and buffer_type_flags['BLENDWEIGHT_2']:
			vertex_weights_sets += 1

		# Get vertex to bone indices for each vertex weight
		for set in range(vertex_weights_sets): # For each set of vertex weights
			lod_buffers_index += 1
			mmesh_file.seek(LOD.Buffers(lod_buffers_index).Offset())
			# print("LOD.Buffers(lod_buffers_index).Offset()", LOD.Buffers(lod_buffers_index).Offset())
			# print("LOD.Buffers(lod_buffers_index).Size()", LOD.Buffers(lod_buffers_index).Size())
			for n in range(LOD.Buffers(lod_buffers_index).Size()//8): # Same as -> for n in range(vert_count):
				i0, i1, i2, i3 = struct.unpack('<HHHH', mmesh_file.read(2*4)) # -> int.from_bytes(f.read(2),byteorder='little')
				try:
					weight_indices = [DeformJointsTable[i0],DeformJointsTable[i1],DeformJointsTable[i2],DeformJointsTable[i3]]
					if len(WeightIndicesTable) <= n: WeightIndicesTable.append(weight_indices) # 1st set
					else: WeightIndicesTable[n].extend(weight_indices) # 2nd set
					# print(f"WeightIndicesTable[{n}]:", WeightIndicesTable[n])
				except Exception as err:
					print(i0, i1, i2, i3) ; print (weight_indices)
					# pass
					raise err
		
		# Get weight values for each vertex
		for set in range(vertex_weights_sets): # For each weight set
			lod_buffers_index += 1
			mmesh_file.seek(LOD.Buffers(lod_buffers_index).Offset())
			for n in range(LOD.Buffers(lod_buffers_index).Size()//8): # Same as -> for n in range(vert_count):
				weight_values = list(struct.unpack('<HHHH', mmesh_file.read(2*4)))
				try:
					if len(WeightTable) <= n: WeightTable.append(weight_values) # 1st set
					else: WeightTable[n].extend(weight_values) # 2nd set
				except Exception as err:
					print(weight_values)
					raise err
		
		print("len(armature.data.bones)", len(armature.data.bones))
		for v in range(len(WeightIndicesTable)):
			for n in range(len(WeightIndicesTable[v])): # for n in range(4):
				try:
					# Uses the WeightsIndicesTable to find the names of vertex groups.
					# print(WeightIndicesTable[v][n])
					group_name = armature.data.bones[WeightIndicesTable[v][n]].name

					# See if a vertex group of that name exists on the mesh or not, add one if not
					if mesh_obj.vertex_groups.find(group_name) == -1:
						vertex_group = mesh_obj.vertex_groups.new(name = group_name)
					else:
						vertex_group = mesh_obj.vertex_groups[mesh_obj.vertex_groups.find(group_name)]
					# Take the vertex group and add the vertices with their respective weights to it.
					weight = float(WeightTable[v][n]) / 65535
					if weight > 0:
						vertex_group.add([v], weight, 'ADD')
				except Exception as err:
					# print(err)
					print(WeightIndicesTable[v][n])
					raise err
					pass
		
		# pprint(index_counter)

	dupe_face_start = -1
	dupe_face_count = -1
	if len(duplicate_face_indices) > 0:
		dupe_face_start = duplicate_face_indices[0]
		dupe_face_count = len(duplicate_face_indices)
	print(f"len(bm.faces) = {len(bm.faces)}")

	# ========================================================================================
	# Materials
	# ========================================================================================
	mat_counter = 0
	for i in range(mesh_info.MeshesLength()):
		sub_mesh = mesh_info.Meshes(i)
		for j in range(LOD.ChunksLength()):
			chunk = LOD.Chunks(j)
			if chunk.MeshId() != i:
				continue
			mat_name = sub_mesh.Name().decode() + "#" + str(chunk.MaterialId())
			mat = bpy.data.materials.new(name=mat_name)
			mesh_obj.data.materials.append(mat)
			mat["MaterialID"] = chunk.MaterialId() # Add material ID as custom property

			chunk_offset = chunk.Offset() // 3
			chunk_count = chunk.Count() // 3
			chunk_end = chunk_offset + chunk_count
			if dupe_face_start != -1:
				if chunk_offset > dupe_face_start:
					chunk_offset = chunk_offset - dupe_face_count
				if chunk_end > dupe_face_start:
					chunk_end = chunk_end - dupe_face_count

			print(f"chunk.Offset() // 3: {chunk.Offset() // 3}\t chunk.Count() // 3: {chunk.Count() // 3}\t sum: {chunk.Offset() // 3 + chunk.Count() // 3}")
			# print(f"chunk.Offset() // 3 + chunk.Count() // 3: {chunk.Offset() // 3 + chunk.Count() // 3}")
			for p in range(chunk_offset, chunk_end):
				try:
					mesh_obj.data.polygons[p].material_index = mat_counter
				except Exception as err:
					raise Exception(format_exception("ERROR: This model's mesh probably has duplicate faces. The model's materials will not be assigned correctly."))
					pass
			
			mat_counter += 1
		
	mmesh_file.close()
	del mmesh_file

	# ========================================================================================
	# Root/Armature Misc
	# ========================================================================================
	if armature is not None:
		armature.name = f"{model_name}" # Set armature name
		
		# Store extra parameters in armature object
		# =====================
		armature["magic"] = mesh_info.Magic() # Add minfo magic number
		armature["a4"] = mesh_info.A4AsNumpy() # LOD Distance parameters list
		"""
		armature["DeformBoneBoundaryBox"] = [{"min": (0.0,0.0,0.0), "max":(0.0,0.0,0.0)}] * mesh_info.DeformBoneBoundaryBoxLength()
		# for i in range(mesh_info.DeformBoneBoundaryBoxLength()):
		# 	d_min = Vec3()
		# 	d_max = Vec3()
		# 	mesh_info.DeformBoneBoundaryBox(i).Min(d_min)
		# 	mesh_info.DeformBoneBoundaryBox(i).Max(d_max)
		# 	armature["DeformBoneBoundaryBox"][i] = {
		# 		"min": (d_min.X(),d_min.Y(),d_min.Z()), 
		# 		"max":(d_max.X(),d_max.Y(),d_max.Z())
		# 		}
		# 	print(armature["DeformBoneBoundaryBox"][i]["min"][0])
		# 	print(armature.data.bones[DeformJointsTable[i]].name, i, ":", (d_min.X(),d_min.Y(),d_min.Z()), "\t", (d_max.X(),d_max.Y(),d_max.Z()))
		"""
		armature["vec3_9"] = (mesh_info.Vec39().X(), mesh_info.Vec39().Y(), mesh_info.Vec39().Z())
		if mesh_info.BgReactionData():
			armature["bg_reaction_data"] = {
				"hit_height": mesh_info.BgReactionData().HitHeight(0.0),
				"hit_radius": mesh_info.BgReactionData().HitRadius(0.0),
				"particle_type": mesh_info.BgReactionData().ParticleType(),
				"play_sound": mesh_info.BgReactionData().PlaySound()
				}
		armature["vec3_11"] = (mesh_info.Vec311().X(), mesh_info.Vec311().Y(), mesh_info.Vec311().Z())
		for i in [12, 13, 15, 16, 17, 18, 19]: # F12 - F20 attributes
			if getattr(mesh_info, f"F{i}")():
				armature[f"f{i}"] = getattr(mesh_info, f"F{i}")() # armature["F12"] = mesh_info.F12()
		armature["fade_out_distance"] = mesh_info.FadeOutDistance()
		if mesh_info.U20(): 	armature["u20"] = mesh_info.U20()
		if mesh_info.Byte21(): 	armature["byte21"] = mesh_info.Byte21()
		if mesh_info.Byte22(): 	armature["byte22"] = mesh_info.Byte22()
		for i in [23, 24, 26, 27, 28, 29, 30, 31, 32, 33]:
			if getattr(mesh_info, f"Bool{i}")():
				armature[f"bool{i}"] = getattr(mesh_info, f"Bool{i}")() # armature["Bool23"] = mesh_info.Bool23()
		if mesh_info.IsShip(): 	armature["is_ship"] = mesh_info.IsShip()
		if mesh_info.Float34(): armature["float34"] = mesh_info.Float34()
		# ======================

		# Set up magic property
		armature.id_properties_ensure() # ensure manager is updated
		prop_manager = armature.id_properties_ui("magic")
		prop_manager.update(min=0, max=100000101, default = 100000101)

		# Clean Up
		# ==================================================
		armature_modifier = mesh_obj.modifiers.new("Armature","ARMATURE")
		armature_modifier.object = armature
		mesh_obj.parent = armature

		bpy.ops.object.vertex_group_sort(sort_type='BONE_HIERARCHY') # Sort Vertex Groups by Bone Hierarchy
		mesh_obj.vertex_groups.active_index = 0 # Set selected vertex group back to 0
		
		armature.rotation_euler = (1.5707963705062866,0,0) # Rotate 90 degrees from Y up to Z up
		armature.select_set(True) # Select the armature
		armature.display_type = 'WIRE'
		armature.show_in_front = True # X-Ray view for armature

		utils_select_active(armature)
	
	bpy.context.object.scale = (import_scale, import_scale, import_scale) # Scale the model
	bpy.ops.object.transform_apply(location=True, rotation=True, scale=True) # Apply Transforms to model

	return {'FINISHED'}


# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

# Save where the user selected each file so when the user imports a model it jumps to the same folders
minfo_directory = ""
mmesh_directory = ""

class SelectMInfo(Operator, ImportHelper):
	"""Importer for Granblue Fantasy Relink models"""
	bl_idname = "gbfr.import_mesh"  # important since its how bpy.ops.import_test.some_data is constructed
	bl_label = "Select .minfo"

	# ImportHelper mix-in class uses this.
	filename_ext = ".minfo"
	filter_glob: StringProperty(
		default="*.minfo",
		options={'HIDDEN'},
		maxlen=255,  # Max internal buffer length, longer would be clamped.
	)
	import_scale: bpy.props.FloatProperty(name="Scale", default=1.0)

	def execute(self, context): # On import button pressed
		global minfo_directory
		minfo_directory = self.filepath # Remember for next import
		bpy.ops.gbfr.select_mmesh('INVOKE_DEFAULT', minfo_path = self.filepath, import_scale = self.import_scale)
		return {'FINISHED'}

	def invoke(self, context, event): # On dialog open
		global minfo_directory
		if minfo_directory:
			self.filepath = minfo_directory # Go to remembered filepath
		context.window_manager.fileselect_add(self)
		return {'RUNNING_MODAL'}


class SelectMMesh(Operator, ImportHelper):
	"""Importer for Granblue Fantasy Relink models"""
	bl_idname = "gbfr.select_mmesh"  # important since its how bpy.ops.import_test.some_data is constructed
	bl_label = "Select .mmesh & Import Model"

	# ImportHelper mix-in class uses this.
	filename_ext = ".mmesh"
	filter_glob: StringProperty(
		default="*.mmesh",
		options={'HIDDEN'},
		maxlen=255,  # Max internal buffer length, longer would be clamped.
	)
	import_scale: bpy.props.FloatProperty()
	minfo_path: bpy.props.StringProperty()

	def execute(self, context): # On import button pressed
		global mmesh_directory
		mmesh_directory = self.filepath # Remember for next import
		return read_some_data(context, self.minfo_path, self.filepath, self.import_scale) # Run import process

	def invoke(self, context, event): # On dialog open
		global mmesh_directory
		if mmesh_directory:
			self.filepath = mmesh_directory # Go to remembered filepath
		else:
			self.filepath = self.minfo_path.replace(".minfo", ".mmesh") # Navigate to same folder as .minfo
		context.window_manager.fileselect_add(self)
		return {'RUNNING_MODAL'}


# Only needed if you want to add into a dynamic menu.
def menu_func_import(self, context):
	self.layout.operator(SelectMInfo.bl_idname, text="Granblue Fantasy Relink (.minfo)")


# Register and add to the "file selector" menu (required to use F3 search "Text Import Operator" for quick access).
def register():
	bpy.utils.register_class(SelectMInfo)
	bpy.utils.register_class(SelectMMesh)
	bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
	bpy.utils.unregister_class(SelectMInfo)
	bpy.utils.unregister_class(SelectMMesh)
	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)