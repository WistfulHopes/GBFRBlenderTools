import bpy
import struct
import os
import time
from math import radians
from mathutils import Vector
from collections import defaultdict
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

# ----------------------------

from . import gbfr_minfo_builder
from . import XXHash32Custom
from .Entities.flatbuffers.builder import Builder
from .Entities.ModelSkeleton import ModelSkeleton, StartBodyVector, ModelSkeletonStart, ModelSkeletonAddMagic, ModelSkeletonAddBody, ModelSkeletonEnd
from .Entities.Bone import Bone, BoneStart, BoneAddA1, BoneAddParentId, BoneAddName, BoneAddPosition, BoneAddQuat, BoneAddScale, BoneEnd
from .Entities.BoneInfo import BoneInfo, CreateBoneInfo
from .Entities.Vec3 import Vec3, CreateVec3
from .Entities.Quaternion import Quaternion, CreateQuaternion
from .utils import *

# WRITE DATA TO MMESH FILE
def write_mesh_buffer(mmesh_file, mesh_data_table, mesh_buffers_table):
	offset = mmesh_file.tell() # get current file stream position
	mmesh_file.write(b''.join(mesh_data_table)) # Write bytes
	mesh_buffers_table.append({'offset': offset, 'size': mmesh_file.tell() - offset})

def bools_to_vertex_flags_sum(flags): # Map bools to bitmask
	from .Entities.MInfo_ModelInfo.VertexBufferType import VertexBufferType
	return sum(
		value for name, value in VertexBufferType.__dict__.items()
		if not name.startswith("__") and isinstance(value, int)
		and flags[f"buffer_types.{name}"]
	)

def bool_array_to_byte(bool_array):
    return sum((1 << i) for i, enabled in enumerate(bool_array) if enabled)

def encode_bone_group_name(group_name): # Encode bone group name to 4-byte little-endian ASCII uint
	encoded_group_name = group_name if group_name.startswith("_") else f"_{group_name}"
	encoded_group_name = encoded_group_name[:4].rjust(4, '\x00') # Truncate
	encoded_group_name = str(int.from_bytes(encoded_group_name.encode('ASCII'), 'little'))
	return encoded_group_name

def build_skeleton(armature_obj):
	DeformJointsTable = []
	BoneInfoTablesList = []
	
	skeleton_builder = Builder(0)
	for n, bone in enumerate(armature_obj.data.bones):
		DeformJointsTable.append(n) # TODO: Check that bone is assigned to a vertex group(?) Doesn't seem to matter
		
		parent = bone.parent
		if parent is None:
			parent = 65535
		else:
			parent = armature_obj.pose.bones.find(parent.name)
		name = skeleton_builder.CreateString(bone.name)
		bone_matrix = bone.matrix_local
		if bone.parent:
			bone_matrix = bone.parent.matrix_local.inverted() @ bone.matrix_local
		
		# Get bone's bonegroup
		a1 = None
		if n != 0:
			try:
				if bpy.app.version >= (4, 0, 0): # Blender 4
					for bone_collection in armature_obj.data.collections:
						if bone.name in bone_collection.bones:
							a1  = CreateBoneInfo(skeleton_builder, n, int(bone_collection.name))
				else: # Blender 3
					pbone = armature_obj.pose.bones[n]
					if pbone.bone_group:
						bone_group = pbone.bone_group
						a1  = CreateBoneInfo(skeleton_builder, n, int(bone_group.name))
			except:
				a1 = CreateBoneInfo(skeleton_builder, n, int(encode_bone_group_name("_UNK")))
		
		# Build FB BoneInfo
		BoneStart(skeleton_builder)
		if a1 is not None:
			BoneAddA1(skeleton_builder, a1)
		BoneAddParentId(skeleton_builder, parent)
		BoneAddName(skeleton_builder, name)
		pos = CreateVec3(skeleton_builder, bone_matrix.translation[0], bone_matrix.translation[1], bone_matrix.translation[2])
		BoneAddPosition(skeleton_builder, pos)
		quat = bone_matrix.to_quaternion()
		quat = CreateQuaternion(skeleton_builder, quat[1], quat[2], quat[3], quat[0])           
		BoneAddQuat(skeleton_builder, quat)
		scale = CreateVec3(skeleton_builder, 1.0, 1.0, 1.0)
		BoneAddScale(skeleton_builder, scale)
		bone = BoneEnd(skeleton_builder)
		
		BoneInfoTablesList.append(bone)

	# Build FB ModelSkeleton Body
	StartBodyVector(skeleton_builder, len(BoneInfoTablesList))
	for b in reversed(BoneInfoTablesList):
		skeleton_builder.PrependUOffsetTRelative(b)
	body = skeleton_builder.EndVector()

	# Build FB ModelSkeleton
	ModelSkeletonStart(skeleton_builder)
	ModelSkeletonAddMagic(skeleton_builder, 100000101)
	ModelSkeletonAddBody(skeleton_builder, body)
	model_skeleton = ModelSkeletonEnd(skeleton_builder)
	skeleton_builder.Finish(model_skeleton)

	return skeleton_builder.Output(), DeformJointsTable

def build_mesh_vert_dictionary(mesh_data):
	uv_data = mesh_data.uv_layers.active.data
	mesh_vert_table = {}
	
	for face in mesh_data.polygons:
		for vert_id, loop_id in zip(face.vertices, face.loop_indices):
			if vert_id in mesh_vert_table:
				continue
			v = mesh_data.vertices[vert_id]
			loop = mesh_data.loops[loop_id]
			vert_buffer = []
			vert_buffer.append(struct.pack('<fff', v.undeformed_co[0], v.undeformed_co[1], v.undeformed_co[2]))
			vert_buffer.append(struct.pack('<eee', -loop.normal[0], -loop.normal[1], -loop.normal[2]))
			vert_buffer.append(b'\x00')
			vert_buffer.append(b'\x00')
			vert_buffer.append(struct.pack('<eee', loop.tangent[0], loop.tangent[1], loop.tangent[2]))
			vert_buffer.append(struct.pack('<e', -loop.bitangent_sign))
			uv = uv_data[loop_id].uv
			vert_buffer.append(struct.pack('<ee', uv[0], uv[1]))
			
			mesh_vert_table[vert_id] = vert_buffer

	# Sort the vert_table	
	keys = list(mesh_vert_table.keys())
	keys.sort()
	mesh_vert_table = {i: mesh_vert_table[i] for i in keys}

	return mesh_vert_table


# =======================================================================================================================
# MAIN EXPORT FUNCTION
# =======================================================================================================================
def write_some_data(context, filepath, export_scale:float, create_model_subfolders:bool):
	total_export_timer_start = time.perf_counter()
	export_section_timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
	
	root_obj = context.object # Get selected object
	armature_obj = root_obj if root_obj.type == 'ARMATURE' else None # Get the model's armature if it has one
	model_name = os.path.splitext(os.path.basename(filepath))[0]

	# Create model folder
	model_path = os.path.join(
		os.path.dirname(filepath), 
		fr"model\{model_name[:2]}\{model_name}" if create_model_subfolders else "")
	os.makedirs(model_path, exist_ok=True)
	
	lod_objects = root_obj.children
	mesh_objects = []
	for lod in lod_objects:
		mesh_objects.extend(list(lod.children))
	# print(mesh_objects)
	
	print(f"Exporting Model: {root_obj.name}")

	#================================
	# Apply Mesh and Armature Fixes
	#================================

	for mesh_obj in mesh_objects:
		if len(mesh_obj.data.vertices) == 0: continue # Empty mesh
		mesh_obj.select_set(True) # Select mesh object
		utils_select_active(mesh_obj)
		if mesh_obj.vertex_groups:
			bpy.ops.object.vertex_group_sort(sort_type='BONE_HIERARCHY') # Sort Vertex Groups by Bone Hierarchy
		utils_set_mode('EDIT')
		bpy.ops.mesh.reveal() # Unhide all vertices
		split_faces_by_edge_seams(mesh_obj) # Do this before anything else or BLENDER FUCKS UP THE NORMALS :)))))))))))
		utils_set_mode('OBJECT')
		mesh_obj.select_set(False)
	
	# Select all objects
	for mesh_obj in mesh_objects: mesh_obj.select_set(True)
	for lod_obj in lod_objects: lod_obj.select_set(True)
	root_obj.select_set(True)

	bpy.ops.object.transform_apply(location=True, rotation=True, scale=True) # Apply all transforms
	root_obj.rotation_euler = (radians(-90),0,0) # Rotate back 90 to Y up
	utils_select_active(root_obj) # Set root_obj as active object
	bpy.context.object.scale = (export_scale, export_scale, export_scale) # Scale the root_obj
	bpy.ops.object.transform_apply(location=True, rotation=True, scale=True) # Apply all transforms again
	
	# Deselect all objects
	root_obj.select_set(False)
	for lod_obj in lod_objects: lod_obj.select_set(False)
	for mesh_obj in mesh_objects: mesh_obj.select_set(False)

	print(f"1. Elapsed time: {time.perf_counter() - export_section_timer_start:.6f} seconds | Mesh and Armature Fixes")
	export_section_timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

	for mesh_obj in mesh_objects:
		if len(mesh_obj.data.vertices) == 0: continue # Empty mesh
		mesh_obj.select_set(True)
		utils_select_active(mesh_obj) # Set mesh as active object
		mesh_data = mesh_obj.data

		utils_set_mode('EDIT')
		bpy.ops.mesh.select_all(action='SELECT')
		bpy.ops.mesh.quads_convert_to_tris(quad_method='FIXED') # Triangulate the mesh
		bpy.ops.mesh.delete_loose(use_verts=True, use_edges=True, use_faces=False) # DELETE LOOSE EDGES SO MESH DOESNT EXPLODE
		bpy.ops.mesh.select_all(action='SELECT') # After delete_loose, all vertices will be deselected, so reselect them
		bpy.ops.mesh.flip_normals()
		
		# Before sorting by materials, we need to switch to face select mode
		mesh_select_mode_backup=tuple(bpy.context.scene.tool_settings.mesh_select_mode)
		bpy.ops.mesh.select_mode(type='FACE')
		bpy.ops.mesh.sort_elements(type='MATERIAL', elements={'FACE'}) # Sort faces by material
		bpy.context.scene.tool_settings.mesh_select_mode=mesh_select_mode_backup # Restore the mesh select mode

		utils_set_mode('OBJECT')
		mesh_data.calc_tangents() # mesh.calc_tangents(uvmap='Float2')

		# Limit and normalize weights
		if mesh_obj.vertex_groups:
			bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=8) # limit total weights to 8
			bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False) # normalize all weights

		# Check that mesh only has 2 UV maps
		if len(mesh_data.uv_layers) > 2:
			raise Exception(format_exception(
				f"Mesh {mesh_obj.name.split('.')[0]} has {len(mesh_data.uv_layers)} UV maps."\
				"GBFR Models can only have 2 UV maps."
				)
			)
		mesh_obj.select_set(False)

	print(f"2. Elapsed time: {time.perf_counter() - export_section_timer_start:.6f} seconds | Mesh Fixes part 2")
	export_section_timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

	# ================================================
	# Prepare and Build Skeleton file
	# ================================================
	deform_bones_table = []
	if armature_obj:
		bone_name_to_index_dict = {bone.name: i for i, bone in enumerate(armature_obj.data.bones)}
		# Re-encode and rename all the bone groups back to 4-byte little-endian ASCII uints
		# ================================================
		bone_groups = armature_obj.data.collections if bpy.app.version >= (4, 0, 0) else armature_obj.pose.bone_groups
		for bone_group in bone_groups:
			try:
				bone_group.name = encode_bone_group_name(bone_group.name)
				print("Renamed bone group to:", bone_group.name)
			except:
				raise ValueError(
					format_exception(f"Bone group name '{bone_group.name}' is invalid.\n" 
					+ "When exporting to GBFR, Bone group names can only\n"
					+ "consist only of alphanumeric characters, no unicode (i.e. japanese symbols).\n"
					+ "Group names will also be truncated to 4 bytes, starting with an '_'.")
					)

		# Save skeleton_buffer output to .skeleton file
		# ================================================
		skeleton_buffer, deform_bones_table = build_skeleton(armature_obj)
		try:
			# skeleton_file = open(os.path.splitext(filepath)[0] + ".skeleton", 'wb')
			skeleton_file = open(os.path.join(model_path, model_name + ".skeleton"), 'wb')
			skeleton_file.write(skeleton_buffer)
		except Exception as err:
			raise
		finally:
			try: # Ensure skeleton file is closed (released by file system)
				skeleton_file.close()
				del skeleton_file
			except: pass # If file was not defined, disregard

	print(f"3. Elapsed time: {time.perf_counter() - export_section_timer_start:.6f} seconds | Build Skeleton")
	export_section_timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

	#================================
	# Build mmesh files
	#================================
	lods_data = []
	shadowlods_data = []
	mesh_names_list = []
	mesh_bounds = {}
	unique_materials_dict = {}
	vertex_group_boundary_boxes = []

	# For bounding sphere
	model_bounding_sphere = []
	model_bounds_min = Vector((float('inf'),) * 3)
	model_bounds_max = Vector((float('-inf'),) * 3)

	for lod_obj_index, lod_obj in enumerate(lod_objects):
		try:
			lod_id = next((i for i in range(5) if f"lod{i}" in lod_obj.name.lower()), None)
			shadowlod_id = next((i for i in range(3) if f"shadowlod{i}" in lod_obj.name.lower()), None)
			is_shadowlod = shadowlod_id != None
			if lod_id == None and shadowlod_id == None:
				raise ValueError(format_exception(
					"Model hierarchy be structured `Root object -> LOD# object -> Mesh(es)`\n" \
					"LOD object names must contain 'lod#' where '#' is a number between 0-4.\n" \
					"For Shadow LODs, name must contain 'shadowlod#' with a number between 0-2"
					))

			# Create folder and file
			# lod# or shadowlod#
			mmesh_folder_name = f"{'shadow' if is_shadowlod else ''}lod{shadowlod_id if is_shadowlod else lod_id}"
			mmesh_path = os.path.join(
				os.path.dirname(filepath), 
				"model_streaming" if create_model_subfolders else "", 
				mmesh_folder_name, 
				model_name + ".mmesh")
			os.makedirs(os.path.dirname(mmesh_path), exist_ok=True)
			mmesh_file = open(mmesh_path, 'wb')

			# Init LOD Data variables
			mesh_buffers_table = []
			chunks_table = []
			chunks_dict = {}

			vert_table = []
			weight_id_table = [] ; weight_id_table_2 = []
			weight_table = [] ; weight_table_2 = []
			vertex_colors_table = []
			tex_coords_table = []
			face_table = []
			face_table_offset = 0 # Updates after each mesh
			chunks_face_offset = 0 # Updates after each mesh

			vertex_group_verts = defaultdict(list)
			mesh_objects = lod_obj.children
			for mesh_obj_index, mesh_obj in enumerate(mesh_objects):
				mesh_data = mesh_obj.data
				mesh_name = mesh_obj.name.split('.')[0]
				
				# Build the Vertex Table
				mesh_vert_dict = build_mesh_vert_dictionary(mesh_data)
				vert_table.extend(list(mesh_vert_dict.values()))

				print(f"4a. Elapsed time: {time.perf_counter() - export_section_timer_start:.6f} seconds | LOD{lod_obj_index}_{mesh_obj.name} - Build Vertex Table")
				export_section_timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

				# ======== Start of Armature related stuff ========
				if armature_obj is not None:
					if not len(mesh_obj.vertex_groups) > 0:
						raise UserWarning(
							format_exception(f"Mesh '{mesh_name}' has no vertex groups on it! Add at least one."
							)
						)
					# Build vertex groups
					# ================================================
					max_num_weights = max([len(v.groups) for v in mesh_data.vertices])
					weights_count = 4 if max_num_weights <= 4 else 8 # sets of 4 or 8
					if max_num_weights > 8:
						raise UserWarning(
							format_exception(f"Mesh '{mesh_name}' has one or more vertices with more than 8 vertex weights.\n"
							+"To export successfully, make sure to use Limit Total on your model."
							)
						)

					mesh_world_matrix =  mesh_obj.matrix_world
					vertex_groups_length = len(mesh_obj.vertex_groups)
					padding_value = struct.pack('<H', 0)
					for v_index, v in enumerate(mesh_data.vertices):
						# if v.index not in mesh_vert_dict:
						# 	continue # Make sure we're only processing verts we're exporting

						for n in range(weights_count): # Vertex Groups compiled as sets of 4 or 8
							if n < len(v.groups): # Existing Groups
								vgroup_index = v.groups[n].group
								if vgroup_index > vertex_groups_length: continue # Skip invalid group index
								group_name = mesh_obj.vertex_groups[vgroup_index].name
								bone_index = bone_name_to_index_dict.get(group_name, None)
								if bone_index is None:
									raise UserWarning(format_exception(
										f"Missing bone for Vertex Group '{group_name}' on '{mesh_name}\n"\
										"Either create the bone or remove the Vertex Group."
									))
								
								weight_group_index = struct.pack('<H', bone_index)
								weight_group_value = struct.pack('<H', int(v.groups[n].weight * 65535))
								if n<4:
									weight_id_table.append(weight_group_index)
									weight_table.append(weight_group_value)
								else:
									weight_id_table_2.append(weight_group_index)
									weight_table_2.append(weight_group_value)
								
								# Get Vertex group vertices for bounding boxes
								if lod_obj_index > 0: continue # Only calculate for first LOD processed.
								vertex_group_verts[vgroup_index].append(mesh_world_matrix @ v.co)
							else:
								# Pad vertex's weight group list out to full 4 slots with 0's
								if n<4:
									weight_id_table.append(padding_value)
									weight_table.append(padding_value)
								else:
									weight_id_table_2.append(padding_value)
									weight_table_2.append(padding_value)

					# Calculate Boundary Boxes for each Vertex Group
					if lod_obj_index == 0: # Only calculate for first LOD processed.
						for vg_index, vg_coords in sorted(vertex_group_verts.items()):
							vertex_group_boundary_boxes.append(
								{
									"min": {
										'x': min(v.x for v in vg_coords), 
										'y': min(v.y for v in vg_coords), 
										'z': min(v.z for v in vg_coords)
										},
									"max": {
										'x': max(v.x for v in vg_coords), 
										'y': max(v.y for v in vg_coords), 
										'z': max(v.z for v in vg_coords)
										}
								}
							)
				# ======== End of Armature related stuff ========

				print(f"4b. Elapsed time: {time.perf_counter() - export_section_timer_start:.6f} seconds | LOD{lod_obj_index}_{mesh_obj.name} - Build Weights")
				export_section_timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
				
				# Build Vertex Colors and UV1 Coordinates
				# TODO: account for funny meshes that don't have Vertex Colors and UV1 coordinates, but others do (?) Does this matter?
				color_layer = mesh_data.color_attributes.get("COLOR")

				uv1_coords = []
				if len(mesh_data.uv_layers)>1:
					uv1_coords = [() for v in mesh_data.vertices]
					for loop in mesh_data.loops:
						uv1_coords[loop.vertex_index] = mesh_data.uv_layers[1].data[loop.index].uv

				for v in mesh_data.vertices:
					# VERTEX COLORS
					if color_layer:
						r = int(color_layer.data[v.index].color[0] * 255)
						g = int(color_layer.data[v.index].color[1] * 255)
						b = int(color_layer.data[v.index].color[2] * 255)
						a = int(color_layer.data[v.index].color[3] * 255)
						vertex_colors_table.append(struct.pack('<BBBB', r, g, b, a))

					# TEXTURE COORDINATES
					if uv1_coords:
						tex_coords_table.append(struct.pack('<ee', uv1_coords[v.index][0], uv1_coords[v.index][1]))

					# CALCULATE BOUNDING SPHERE
					if lod_obj_index > 0: continue # Only calculate for first LOD
					model_bounds_min.x = min(model_bounds_min.x, v.co.x)
					model_bounds_min.y = min(model_bounds_min.y, v.co.y)
					model_bounds_min.z = min(model_bounds_min.z, v.co.z)
					model_bounds_max.x = max(model_bounds_max.x, v.co.x)
					model_bounds_max.y = max(model_bounds_max.y, v.co.y)
					model_bounds_max.z = max(model_bounds_max.z, v.co.z)

				# Implementation doesn't match GBFR, but still works
				if lod_obj_index == 0: # Only calculate for first LOD
					model_bounds_center = (model_bounds_min + model_bounds_max)/2
					model_bounds_radius = max((v.co - model_bounds_center).length for v in mesh_data.vertices)
					model_bounding_sphere = [
						model_bounds_center.x, model_bounds_center.y, model_bounds_center.z, model_bounds_radius
					]
					# print("model_bounding_sphere", model_bounding_sphere)
				
				print(f"4c. Elapsed time: {time.perf_counter() - export_section_timer_start:.6f} seconds | LOD{lod_obj_index}_{mesh_obj.name} - Build UV1 and Vertex Colors, Bounding Sphere")
				export_section_timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@


				# Build lod data
				# ================================================
				# Build materials list
				for material in mesh_data.materials:
					# Check material index exists and is valid
					if not material: continue # Empty material slot, skip
					if "MaterialID" not in material:
						raise UserWarning(
							format_exception(f"Material '{material.name}' has no Material Index assigned!\n"\
							"Please select the mesh and use the GBFR Tool Shelf Panel in the 3D view to assign"\
							"one and set it to a non-negative number.\n"\
							"(Press N to open the tool shelf while your cursor is in the 3D view)")
						)
					material_id = material['MaterialID']
					if material_id < 0:
						raise UserWarning(
							format_exception(f"Material Index '{material_id}' on {material.name} is invalid.\n"\
							"Please select the mesh and set it to a non-negative number in the GBFR Tool shelf panel.\n"\
							"(Press N to open the tool shelf while your cursor is in the 3D view)")
						)
					
					if material_id not in unique_materials_dict:
						unique_materials_dict[material_id] = material

				# ================================================
				# Construct faces, chunks, and meshes list
				if mesh_name not in mesh_names_list:
					mesh_names_list.append(mesh_name)
				# mesh_id = mesh_names_list.index(mesh_name)

				for face in mesh_data.polygons:
					# Build face table, offset vertex indices with the length of the vert_table
					face_table.append(
						struct.pack(
							'<III', 
							face.vertices[0] + face_table_offset, 
							face.vertices[1] + face_table_offset, 
							face.vertices[2] + face_table_offset
							)
						)

					mat_index = face.material_index
					material = mesh_data.materials[mat_index]
					material_id = material["MaterialID"]
					
					chunk_id = f"{mesh_obj_index}_{material_id}"
					if chunk_id not in chunks_dict: # Init Chunk
						chunks_dict[chunk_id] = {
							'offset': chunks_face_offset + (face.index * 3),
							'count': 0,
							'mesh_id': mesh_obj_index,
							'material_id': material["MaterialID"],
							'a5': 0,
							'a6': 0
						}

						if lod_obj_index == 0: # Only calculate for first LOD object
							mesh_bounds[mesh_name] = { #Initialize chunk bounds at infinity
								'min': {'x': float('inf'), 'y': float('inf'), 'z': float('inf')},
								'max': {'x': float('-inf'), 'y': float('-inf'), 'z': float('-inf')}
							}

					chunks_dict[chunk_id]['count'] += 3

					if lod_obj_index > 0: continue # Only calculate for first LOD object
					for vert_index in face.vertices: #Calculate and update bounds
						vert_co = mesh_data.vertices[vert_index].co
						mesh_bounds[mesh_name]['min']['x'] = min(mesh_bounds[mesh_name]['min']['x'], vert_co.x)
						mesh_bounds[mesh_name]['min']['y'] = min(mesh_bounds[mesh_name]['min']['y'], vert_co.y)
						mesh_bounds[mesh_name]['min']['z'] = min(mesh_bounds[mesh_name]['min']['z'], vert_co.z)
						mesh_bounds[mesh_name]['max']['x'] = max(mesh_bounds[mesh_name]['max']['x'], vert_co.x)
						mesh_bounds[mesh_name]['max']['y'] = max(mesh_bounds[mesh_name]['max']['y'], vert_co.y)
						mesh_bounds[mesh_name]['max']['z'] = max(mesh_bounds[mesh_name]['max']['z'], vert_co.z)

				face_table_offset = len(vert_table) # Update face table offset for next mesh in LOD
				chunks_face_offset = len(face_table) * 3

				print(f"4d. Elapsed time: {time.perf_counter() - export_section_timer_start:.6f} seconds | LOD{lod_obj_index}_{mesh_obj.name} - Build Faces, Chunks and Mesh Bounds")
				export_section_timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

				print(f"LOD{lod_obj_index} - {mesh_obj.name} done processing!")

			# Write .mmesh Buffers
			# ================================================
			# Write Vertex Table to Mesh Buffer
			for vert in vert_table:
				for elm in vert:
					mmesh_file.write(elm)
			mesh_buffers_table.append({'offset': 0, 'size': mmesh_file.tell()})

			# Assign weights
			if weight_id_table 	: write_mesh_buffer(mmesh_file, weight_id_table, mesh_buffers_table)
			if weight_id_table_2: write_mesh_buffer(mmesh_file, weight_id_table_2, mesh_buffers_table)
			if weight_table		: write_mesh_buffer(mmesh_file, weight_table, mesh_buffers_table)
			if weight_table_2	: write_mesh_buffer(mmesh_file, weight_table_2, mesh_buffers_table)

			# Assign Vertex Colors
			if vertex_colors_table	: write_mesh_buffer(mmesh_file, vertex_colors_table, mesh_buffers_table)
			# Assign texture coordinates
			if tex_coords_table 	: write_mesh_buffer(mmesh_file, tex_coords_table, mesh_buffers_table)
			
			# Write faces to .mmesh - always written last in mmesh, face data is placed at end of mmesh file
			write_mesh_buffer(mmesh_file, face_table, mesh_buffers_table)
			# Done with .mmesh file
			mmesh_file.close() # Close mmesh
			del mmesh_file # Delete Reference

			# Create lod data table
			# ================================================
			
			buffer_types_bool_flags = {
				"buffer_types.POS_NOR_TAN_UV0": True, # Always true, not sure if could ever be false?
				"buffer_types.BLENDINDICES": True if weight_id_table else False,
				"buffer_types.BLENDINDICES_2": True if weight_id_table_2 else False,
				"buffer_types.BLENDWEIGHT": True if weight_table else False,
				"buffer_types.BLENDWEIGHT_2": True if weight_table_2 else False,
				"buffer_types.COLOR": True if vertex_colors_table else False,
				"buffer_types.TEXCOORD": True if tex_coords_table else False
			}
			buffer_types = bools_to_vertex_flags_sum(buffer_types_bool_flags)

			chunks_table = list(chunks_dict.values())

			lod_data_table = {
				'buffers': mesh_buffers_table, 
				'chunks': chunks_table,
				'vertex_count': len(vert_table),
				'index_count': len(face_table) * 3, # index_count is stored as 3 X Face Count
				'buffer_types': buffer_types, # mesh_obj.get("buffer_types", 11),
				'a6': bool_array_to_byte(lod_obj.get("a6", [False * 8]))
				}
			if not is_shadowlod:
				lods_data.append(lod_data_table)
			else:
				shadowlods_data.append(lod_data_table)

			print(f"4e. Elapsed time: {time.perf_counter() - export_section_timer_start:.6f} seconds | LOD{lod_obj_index} - Write mmesh Buffers")
			export_section_timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

		except Exception as err:
			raise
		finally:
			try: # Ensure mmesh file is closed (released by file system)
				mmesh_file.close()
				del mmesh_file
			except: pass # If file was not defined, disregard

	# Build minfo Data Table
	# ================================================

	# Construct and append mesh to meshes table
	meshes_table = [
		{
			'name': mesh_name,
			'bbox': {'min': mesh_bounds[mesh_name]['min'], 'max': mesh_bounds[mesh_name]['max']}
		}
		for mesh_name in mesh_names_list
	]

	# Real name hash is based on prefix of texture names found in .mmat for each material
	# e.g texture name:
	# pl1400_body01_1_lod0_msk3 => prefix: pl1400_body01_1_lod0 => Hash: 9CE82257 => unique_name_hash in minfo materials: 2632458839
	# TODO: Find elegant way to get texture name from .mmat
	# Note: .mmat also have some hash, maybe for names, but are not the same as hash in .minfo
	unique_materials_dict = dict(sorted(unique_materials_dict.items())) # Sort by material_ids
	materials_table = [
		{
			"unique_name_hash": int(material.name) 
							if int(material.name) 
							else XXHash32Custom.Hash_string(material.name), # Hash the material name
			"material_flags": bool_array_to_byte(material['material_flags']) 
							if 'material_flags' in material 
							else bool_array_to_byte([False*8]) # Unknown ubyte material flags
		}
		for material in unique_materials_dict.values()
	]
	
	minfo_data = {
		'magic': 100000101, # Game only checks if it's at least some date, so set to 10000_01_01
		'lods': lods_data,
		'shadow_lods': shadowlods_data,
		'lod_screen_size_thresholds': root_obj.get("lod_screen_size_thresholds", [1.0, 0.6, 0.15, 0.07]),
		'meshes': meshes_table,
		'materials': materials_table,
		'deform_bone_to_bone_index_table': deform_bones_table,
		'deform_bone_boundary_box': vertex_group_boundary_boxes,
		'bounding_sphere': model_bounding_sphere, # root_obj.get("bounding_sphere", [0.0, 0.0, 0.0, 0.0]),
		# bg_reaction_data,
		'vec3_11': root_obj.get("vec3_11", [0.0, 0.0, 0.0]),
		'near_camera_bound_radius': root_obj.get("near_camera_bound_radius", 0.0),
		'near_camera_detection_scale': root_obj.get("near_camera_detection_scale", 0.0),
		'fade_out_distance': root_obj.get("fade_out_distance", 3.0),
		# f15,
		'f16': root_obj.get("render_mesh_screen_size_threshold", 0.0),
		'f17': root_obj.get("render_shadow_screen_size_threshold", 0.0),
		'f18': root_obj.get("render_outline_screen_size_threshold", 0.0),
		'f19': root_obj.get("f19", 0.0),
		# u20,
		'byte21': bool_array_to_byte(root_obj.get("byte21", [False*8])),
		#scene_graph_mode,
		#use_scene_graph_cache, bool24, is_ship,
		'bool26': root_obj.get("fade_between_lods", False),
		'use_bone_bounds_for_fade': root_obj.get("use_bone_bounds_for_fade", False),
		#bool28, bool29, force_near_fade_evaluation, bool31, use_mesh_aabb_for_fade,
		#render_flags,
		#camera_near_fade_aabb_radius,
		}
	# Optional parameters (model context dependent, some models have these, some dont)
	optional_minfo_params = ['bg_reaction_data','f15','u20','scene_graph_mode','use_scene_graph_cache',
					   'bool24','is_ship','bool28','bool29','force_near_fade_evaluation','bool31',
					   'use_mesh_aabb_for_fade','render_flags','camera_near_fade_aabb_radius']
	byte_params = ['scene_graph_mode','bool31','render_flags']
	for param in optional_minfo_params: # Try to get these params from the model
		param_value = root_obj.get(param, None)
		if param_value:
			minfo_data[param] = param_value if param not in byte_params else bool_array_to_byte(param_value)

	# Create and Build .minfo file
	try:
		# minfo_path = os.path.splitext(filepath)[0] + ".minfo"
		minfo_path = os.path.join(model_path, model_name + ".minfo")
		gbfr_minfo_builder.build_minfo(minfo_data, minfo_path)
	except Exception as err:
		raise err

	print(f"5. Elapsed time: {time.perf_counter() - export_section_timer_start:.6f} seconds - Create and Build .minfo file")
	export_section_timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

	print(f"{root_obj.name} Exported! Model took {time.perf_counter() - total_export_timer_start:.6f} seconds to export!")

	return {'FINISHED'}


class ExportSomeData(Operator, ExportHelper):
	"""Exporter for Granblue Fantasy Relink meshes"""
	bl_idname = "gbfr.export_mesh"  # important since its how bpy.ops.import_test.some_data is constructed
	bl_label = "Export"
	
	# ImportHelper mix-in class uses this.
	filename_ext = ".minfo"

	filter_glob: StringProperty(
		default="*.mmesh;*.minfo", #Show .minfo and .mmesh files in selector
		options={'HIDDEN'},
	)
	export_scale: bpy.props.FloatProperty(name="Model Export Scale", default=1.0)
	create_model_subfolders: bpy.props.BoolProperty(name="Create model/model_streaming Folders", default=False)

	def draw(self, context):
		layout = self.layout
		# layout.use_property_split = True

		box = layout.box()
		row = box.row()
		row.label(text="Model Export Scale")
		row.prop(self, "export_scale", text="")
		box = layout.box()
		row = box.row() ; row.split(factor = 0.1)
		row.prop(self, "create_model_subfolders", text="")
		row.label(text="Create model/model_streaming Folders")

	def invoke(self, context, event):
		try:
			selected_obj = context.object # Get active object
			if selected_obj == None: 
				show_message_box("Select the model before exporting!", "ERROR!", icon="ERROR")
				return {'CANCELLED'}
			
			# Select Root and ensure model hierarchy is correct
			# =================================================

			# Mesh Object
			if selected_obj.type == 'MESH':
				if selected_obj.parent and selected_obj.parent.type in ('EMPTY'):
					lod_obj = selected_obj.parent # Set lod_obj as selected
					utils_select_active(lod_obj)
					selected_obj = lod_obj
					if lod_obj.parent and lod_obj.parent.type in ('ARMATURE','EMPTY'):
						root_obj = selected_obj.parent # Set root as selected
						utils_select_active(root_obj)
						selected_obj = root_obj
					else: raise UserWarning(
							format_exception("ERROR: Selected object has no root object or armature as parent!\nMake sure:\n"\
							"1. You have the correct model selected.\n"\
							"2. The lod object is parented to an armature or an empty root.\n"\
							"Example Model Hierarchy:\n" \
							"\t\t->Root\n" \
							"\t\t\t\t->LOD0\n" \
							"\t\t\t\t\t\t->Mesh\n"
							)
						)
				else: raise UserWarning(
						format_exception("ERROR: Selected Mesh has no empty object named 'lod#' as parent!\nMake sure:\n" \
						"1. You have the correct mesh selected.\n" \
						"2. The mesh is parented to an empty named 'lod#' which is parented to an armature or an empty root.\n" \
						"Example Model Hierarchy:\n" \
						"\t\t->Root\n" \
						"\t\t\t\t->LOD0\n" \
						"\t\t\t\t\t\t->Mesh\n"
						)
					)
			
			# LOD Object
			if selected_obj.type == 'EMPTY':
				root_obj = selected_obj.parent
				if root_obj and root_obj.type in ('ARMATURE','EMPTY'):
					selected_obj = root_obj
					utils_select_active(selected_obj)

			if(selected_obj.type) not in ('ARMATURE','EMPTY'):
				raise UserWarning(format_exception("Model Root object must be an Armature or an Empty!"))
			
			# Root Object
			if len(selected_obj.children) < 1:
				raise UserWarning(format_exception(f"ERROR: Selected Model {selected_obj.name} has no LODs!"))
			lods = [lod_child for lod_child in selected_obj.children if 'lod' in lod_child.name.lower()]
			if not lods: raise UserWarning(format_exception(f"ERROR: Selected Model {selected_obj.name} has no LODs!"))
			for lod_child in lods:
				if len(lod_child.children) < 1:
					raise UserWarning(format_exception(f"ERROR: {lod_child.name} has no Meshes!"))
				else:
					meshes = [mesh_child for mesh_child in lod_child.children if mesh_child.type == "MESH"]
					if not meshes:
						raise UserWarning(format_exception(f"ERROR: {lod_child.name} has no Meshes!"))
			
			# ===============================
			
			# self.filepath = selected_obj.name + self.filename_ext
			self.filepath = os.path.join(
				os.path.dirname(self.filepath),
				f"{selected_obj.name}{self.filename_ext}"
			)

			return ExportHelper.invoke(self, context, event)
		except Exception as err:
			raise err

	def execute(self, context):
		export_collection = bpy.data.collections.new(name="Export_Collection")
		context.window.scene.collection.children.link(export_collection)

		try:
			utils_set_mode('OBJECT') # Set Object Mode

			# Get model's armature and mesh
			selected_obj = context.object # Get active object

			if selected_obj.type in ('ARMATURE', 'EMPTY'):
				# Duplicate object and link to export scene
				root_obj_copy = selected_obj.copy()
				root_obj_copy.data = selected_obj.data.copy()  if selected_obj.data else None
				root_obj_copy.name = selected_obj.name + "_export"
				root_obj_copy.hide_set(False) # ensure root object isnt hidden
				export_collection.objects.link(root_obj_copy)

				for lod_obj in selected_obj.children:
					if lod_obj.type != 'EMPTY' or 'lod' not in lod_obj.name.lower(): continue
					lod_obj_copy = lod_obj.copy()
					lod_obj_copy.data = lod_obj.data.copy() if lod_obj.data else None
					lod_obj_copy.hide_set(False)
					export_collection.objects.link(lod_obj_copy)
					# Parent the duplicated lod object root to the duplicated root
					lod_obj_copy.parent = root_obj_copy

					for child in lod_obj.children:
						if child.type != 'MESH': continue
						
						mesh_obj_copy = child.copy()
						mesh_obj_copy.data = child.data.copy()
						mesh_obj_copy.hide_set(False) # ensure mesh object isnt hidden
						export_collection.objects.link(mesh_obj_copy)
						# Parent the duplicated mesh to the duplicated lod object root
						mesh_obj_copy.parent = lod_obj_copy
						for modifier in mesh_obj_copy.modifiers: # Set armature modifier to root_obj_copy
							if modifier.type == 'ARMATURE':
								modifier.object = root_obj_copy
								break
				
				utils_select_active(root_obj_copy) # Set copied root as active object

				selected_obj = context.object
				print(f"selected_obj.name {selected_obj.name}")

				write_some_data(context, self.filepath, self.export_scale, self.create_model_subfolders) # Export the model
				show_message_box("Model Exported!", "GBFR Blender Tools")
				self.report({'INFO'}, f"Model Exported!")

			else: raise UserWarning(
				format_exception("ERROR: No model selected, select the model's root/armature or mesh before export.")
				)

		except Exception as err:
			raise
		finally:
			try:
				# Clean up data
				for obj in export_collection.objects:
					bpy.data.objects.remove(obj)
				bpy.data.collections.remove(export_collection)
			except Exception as err: 
				raise err
				pass
			try:
				# Clean Orphan Data to avoid memory leaks
				bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
			except Exception as err: 
				raise err
				pass

		return {'FINISHED'}


def menu_func_export(self, context):
	self.layout.operator(ExportSomeData.bl_idname, text="Granblue Fantasy Relink (.minfo)")


# Register and add to the "file selector" menu (required to use F3 search "Text Export Operator" for quick access).
def register():
	bpy.utils.register_class(ExportSomeData)
	bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
	bpy.utils.unregister_class(ExportSomeData)
	bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
