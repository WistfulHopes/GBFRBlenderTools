import bpy
import struct
import os
import time
from math import radians
from mathutils import Vector
from collections import defaultdict
from pprint import pprint
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

def byte_to_bool_array(byte_value):
    return [bool(byte_value & (1 << i)) for i in range(8)]

def bool_array_to_byte(bool_array):
    return sum((1 << i) for i, enabled in enumerate(bool_array) if enabled)

def encode_bone_group_name(group_name): # Encode bone group name to 4-byte little-endian ASCII uint
	encoded_group_name = group_name if group_name.startswith("_") else f"_{group_name}"
	encoded_group_name = encoded_group_name[:4].rjust(4, '\x00') # Truncate
	encoded_group_name = str(int.from_bytes(encoded_group_name.encode('ASCII'), 'little'))
	return encoded_group_name

def build_vert_table(mesh_obj, mesh_data):
	vert_table = {}
	vert_count = 0
	
	for face in mesh_data.polygons:
		for vert_id, loop_id in zip(face.vertices, face.loop_indices):
			if vert_id in vert_table:
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
			uv = mesh_obj.data.uv_layers.active.data[loop_id].uv
			vert_buffer.append(struct.pack('<ee', uv[0], uv[1]))
			vert_count += 1
			
			vert_table[vert_id] = vert_buffer

	# Sort the vert_table	
	keys = list(vert_table.keys())
	keys.sort()
	vert_table = {i: vert_table[i] for i in keys}

	return vert_table, vert_count

def build_skeleton(armature_obj):
	DeformJointsTable = []
	BoneInfoTablesList = []
	
	skeleton_builder = Builder(0)
	for n, bone in enumerate(armature_obj.data.bones):
		DeformJointsTable.append(n) # TODO: Check that bone is assigned to a vertex group(?)
		
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

def write_some_data(context, filepath, export_scale):
	timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
	
	root_obj = context.object # Get selected object
	armature_obj = root_obj if root_obj.type == 'ARMATURE' else None # Get the model's armature if it has one
	
	mesh_objects = root_obj.children
	
	print(f"Exporting Model: {root_obj.name}")

	print(f"1. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
	timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
	#================================
	# Apply Mesh and Armature Fixes
	#================================

	for mesh_obj in mesh_objects:
		mesh_obj.select_set(True) # Select mesh object
		utils_select_active(mesh_obj)
		if mesh_obj.vertex_groups:
			bpy.ops.object.vertex_group_sort(sort_type='BONE_HIERARCHY') # Sort Vertex Groups by Bone Hierarchy
		utils_set_mode('EDIT')
		bpy.ops.mesh.reveal() # Unhide all vertices
		split_faces_by_edge_seams(mesh_obj) # Do this before anything else or BLENDER FUCKS UP THE NORMALS :)))))))))))
		utils_set_mode('OBJECT')
		mesh_obj.select_set(False)
	
	for mesh_obj in mesh_objects: mesh_obj.select_set(True)
	root_obj.select_set(True) # Select root_obj
	bpy.ops.object.transform_apply(location=True, rotation=True, scale=True) #Apply all transforms
	root_obj.rotation_euler = (radians(-90),0,0) #Rotate back 90 to Y up
	utils_select_active(root_obj) # Set root_obj as active object
	bpy.context.object.scale = (export_scale, export_scale, export_scale) # Scale the root_obj
	bpy.ops.object.transform_apply(location=True, rotation=True, scale=True) #Apply all transforms again
	root_obj.select_set(False) # Deselect root_obj
	for mesh_obj in mesh_objects: mesh_obj.select_set(False)

	for mesh_obj in mesh_objects:
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
	
		print(f"2a. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
		timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

		utils_set_mode('OBJECT')
		mesh_data.calc_tangents() # mesh.calc_tangents(uvmap='Float2')

		# Limit and normalize weights
		if mesh_obj.vertex_groups:
			bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=8) # limit total weights to 8
			bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False) # normalize all weights
		
		print(f"2b. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
		timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

		# Check that mesh only has 2 UV maps
		if len(mesh_data.uv_layers) > 2:
			raise Exception(
				format_exception(f"Mesh {mesh_obj.name} has {len(mesh_data.uv_layers)} UV maps. GBFR Models can only have 2 UV maps.")
			)
		mesh_obj.select_set(False)

	# Re-encode and rename all the bone groups back to 4-byte little-endian ASCII uints
	if armature_obj:
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

	print(f"2. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
	timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

	# ================================================
	# Build Skeleton file
	# ================================================
	DeformJointsTable = []
	if armature_obj is not None:
		# Save skeleton_buffer output to .skeleton file
		skeleton_buffer, DeformJointsTable = build_skeleton(armature_obj)
		try:
			skeleton_file = open(os.path.splitext(filepath)[0] + ".skeleton", 'wb')
			skeleton_file.write(skeleton_buffer)
		except Exception as err:
			raise
		finally:
			# Ensure skeleton file is closed (released by file system)
			try: 
				skeleton_file.close()
				del skeleton_file
			except: pass # If file was not defined, disregard
		

	print(f"3. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
	timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

	#================================
	# Build mmesh files
	#================================
	lods_data = []
	shadowlods_data = []
	meshes_table = []
	mesh_list = []
	mesh_ids = {}
	mesh_bounds = {}
	unique_materials_dict = {}

	# For bounding sphere
	model_bounding_sphere = []
	model_bounds_min = Vector((float('inf'),) * 3)
	model_bounds_max = Vector((float('-inf'),) * 3)

	for mesh_obj in mesh_objects:
		try:
			# TODO: Handle shadow_lods
			lod_id = next((i for i in range(5) if f"_lod{i}" in mesh_obj.name.lower()), None)
			shadowlod_id = next((i for i in range(3) if f"_shadowlod{i}" in mesh_obj.name.lower()), None)
			is_shadowlod = shadowlod_id != None
			if lod_id == None and shadowlod_id == None:
				raise ValueError(format_exception("Mesh object names must contain '_lod#' where '#' is a number between 0-4. \n" \
				"For shadow meshes, name must contain '_shadowlod#'"))

			# Create folder and file
			mmesh_folder_name = f"{'shadow' if is_shadowlod else ''}lod{shadowlod_id if is_shadowlod else lod_id}" # lod# or shadowlod#
			mmesh_path = os.path.join(
				os.path.dirname(filepath), mmesh_folder_name, 
				os.path.splitext(os.path.basename(filepath))[0] + ".mmesh") # mmesh_path = os.path.splitext(filepath)[0] + ".mmesh"
			os.makedirs(os.path.dirname(mmesh_path), exist_ok=True)
			mmesh_file = open(mmesh_path, 'wb')

			mesh_data = mesh_obj.data
			mesh_buffers_table = []
			
			# Build the Vertex Table
			vert_table, vert_count = build_vert_table(mesh_obj, mesh_data)
			
			# Write Vertex Table to Mesh Buffer
			for vert in vert_table.items():
				for elm in vert[1]:
					mmesh_file.write(elm)
			mesh_buffers_table.append({'offset': 0, 'size': mmesh_file.tell()})

			print(f"4. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
			timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

			# ======== Start of Armature related stuff ========
			weight_id_table = [] ; weight_id_table_2 = []
			weight_table = [] ; weight_table_2 = []
			vertex_group_boundary_boxes = []
			if armature_obj is not None:
				# Build vertex groups
				# ================================================
				vertex_group_verts = defaultdict(list)
				bone_name_to_index_dict = {bone.name: i for i, bone in enumerate(armature_obj.data.bones)}

				max_num_weights = max([len(v.groups) for v in mesh_data.vertices])
				if max_num_weights > 8: 
					raise UserWarning(
						format_exception("Your model has one or more vertices with more than 8 vertex weights.\n"
						+"To export successfully, make sure to use Limit Total on your model."
						)
					)

				for v in mesh_data.vertices:
					if v.index not in vert_table:
						continue # Make sure we're only processing verts we're exporting

					for n in range(max_num_weights): # Vertex Groups compiled as sets of 4
						if n < len(v.groups): # Existing Groups
							group_name = mesh_obj.vertex_groups[v.groups[n].group].name
							bone_index = bone_name_to_index_dict.get(group_name, None)
							
							weight_group_index = struct.pack('<H', bone_index)
							weight_group_value = struct.pack('<H', int(v.groups[n].weight * 65535))
							if n<4:
								weight_id_table.append(weight_group_index)
								weight_table.append(weight_group_value)
							else:
								weight_id_table_2.append(weight_group_index)
								weight_table_2.append(weight_group_value)
							
							# Get Vertex group vertices for bounding boxes
							vertex_group_verts[v.groups[n].group].append(mesh_obj.matrix_world @ v.co)
						else:
							# Pad vertex's weight group list out to full 4 slots with 0's
							padding_value = struct.pack('<H', 0)
							if n<4:
								weight_id_table.append(padding_value)
								weight_table.append(padding_value)
							else:
								weight_id_table_2.append(padding_value)
								weight_table_2.append(padding_value)

				# Assign weights
				write_mesh_buffer(mmesh_file, weight_id_table, mesh_buffers_table)
				if weight_id_table_2: write_mesh_buffer(mmesh_file, weight_id_table_2, mesh_buffers_table)
				write_mesh_buffer(mmesh_file, weight_table, mesh_buffers_table)
				if weight_table_2: write_mesh_buffer(mmesh_file, weight_table_2, mesh_buffers_table)

				# Calculate Boundary Boxes for each Vertex Group
				for vg_index, vg_coords in sorted(vertex_group_verts.items()):
					vertex_group_boundary_boxes.append(
						{
							"min": {'x': min(v.x for v in vg_coords), 'y': min(v.y for v in vg_coords), 'z': min(v.z for v in vg_coords)},
							"max": {'x': max(v.x for v in vg_coords), 'y': max(v.y for v in vg_coords), 'z': max(v.z for v in vg_coords)}
						}
					)
			# ======== End of Armature related stuff ========

			print(f"5. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
			timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
			

			# Build Vertex Colors and UV1 Coordinates
			vertex_colors_table = []
			color_layer = mesh_data.color_attributes.get("COLOR")

			tex_coords_table = [] ; uv1_coords = []
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
					tex_coords_table.append(struct.pack('<ee', uv1_coords[v][0], uv1_coords[v][1]))

				# CALCULATE BOUNDING SPHERE
				model_bounds_min.x = min(model_bounds_min.x, v.co.x)
				model_bounds_min.y = min(model_bounds_min.y, v.co.y)
				model_bounds_min.z = min(model_bounds_min.z, v.co.z)
				model_bounds_max.x = max(model_bounds_max.x, v.co.x)
				model_bounds_max.y = max(model_bounds_max.y, v.co.y)
				model_bounds_max.z = max(model_bounds_max.z, v.co.z)

			# Implementation doesn't match GBFR, but still works
			model_bounds_center = (model_bounds_min + model_bounds_max)/2
			model_bounds_radius = max((v.co - model_bounds_center).length for v in mesh_data.vertices)
			model_bounding_sphere = [model_bounds_center.x, model_bounds_center.y, model_bounds_center.z, model_bounds_radius]
			print("model_bounding_sphere", model_bounding_sphere)

			# Assign Vertex Colors
			if vertex_colors_table: write_mesh_buffer(mmesh_file, vertex_colors_table, mesh_buffers_table)
			# Assign texture coordinates
			if tex_coords_table: write_mesh_buffer(mmesh_file, tex_coords_table, mesh_buffers_table)

			# Build faces - always built last, face data is placed at end of mmesh file
			# face_table = []
			# face_count = 0
			# for face in mesh_data.polygons:
			# 	skip_face = False
			# 	for vert in face.vertices:
			# 		if vert not in vert_table:
			# 			skip_face = True
			# 			break
			# 	if skip_face: continue

			# 	face_table.append(struct.pack('<III', face.vertices[0], face.vertices[1], face.vertices[2]))
			# 	face_count += 3 # Face count is stored as 3 X Face Count
			# write_mesh_buffer(mmesh_file, face_table, mesh_buffers_table)
			# mmesh_file.close() # Close mmesh
			# del mmesh_file # Delete Reference
			
			
			print(f"6. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
			timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

			# Build lod data
			# ================================================
			# Build materials list
			for material in mesh_data.materials:
				# Check material index exists and is valid
				if "MaterialID" not in material:
					raise UserWarning(
						format_exception(f"Material '{material.name}' has no Material Index assigned!\n"
						+ "Please select the mesh and use the GBFR Tool Shelf Panel in the 3D view to assign one and set it to a non-negative number.\n"
						+ f"(Press N to open the tool shelf while your cursor is in the 3D view)")
					)
				material_id = material['MaterialID']
				if material_id < 0:
					raise UserWarning(
						format_exception(f"Material Index '{material_id}' on {material.name} is invalid.\n"
						+ "Please select the mesh and set it to a non-negative number in the GBFR Tool shelf panel.\n"
						+ f"(Press N to open the tool shelf while your cursor is in the 3D view)")
					)
				
				if material_id not in unique_materials_dict:
					unique_materials_dict[material_id] = material

			# ================================================
			# Construct faces, chunks, and meshes list
			face_table = []
			face_count = 0
			
			chunks_table = []
			chunks = {}
			mesh_count = -1

			for face in mesh_data.polygons:
				# Build face table
				face_table.append(struct.pack('<III', face.vertices[0], face.vertices[1], face.vertices[2]))
				face_count += 3 # Face count is stored as 3 X Face Count

				mat_index = face.material_index
				material = mesh_data.materials[mat_index]
				mesh_name = material.name.split("#")[0]
			
				if mesh_name not in mesh_ids:
					mesh_count += 1
					mesh_ids[mesh_name] = mesh_count
					mesh_list.append(mesh_name)
				
				mesh_id = mesh_ids[mesh_name]


				if material.name not in chunks: # Init Chunk
					chunks[material.name] = {
						'offset': face.index * 3,
						'count': 0,
						'mesh_id': mesh_id,
						'material_id': material["MaterialID"],
						'a5': 0,
						'a6': 0
					}

					mesh_bounds[mesh_name] = { #Initialize chunk bounds at infinity
						'min': {'x': float('inf'), 'y': float('inf'), 'z': float('inf')},
						'max': {'x': float('-inf'), 'y': float('-inf'), 'z': float('-inf')}
					}

				chunk = chunks[material.name]
				chunk['count'] += 3

				for vert_index in face.vertices: #Calculate and update bounds
					vert_co = mesh_data.vertices[vert_index].co
					mesh_bounds[mesh_name]['min']['x'] = min(mesh_bounds[mesh_name]['min']['x'], vert_co.x)
					mesh_bounds[mesh_name]['min']['y'] = min(mesh_bounds[mesh_name]['min']['y'], vert_co.y)
					mesh_bounds[mesh_name]['min']['z'] = min(mesh_bounds[mesh_name]['min']['z'], vert_co.z)
					mesh_bounds[mesh_name]['max']['x'] = max(mesh_bounds[mesh_name]['max']['x'], vert_co.x)
					mesh_bounds[mesh_name]['max']['y'] = max(mesh_bounds[mesh_name]['max']['y'], vert_co.y)
					mesh_bounds[mesh_name]['max']['z'] = max(mesh_bounds[mesh_name]['max']['z'], vert_co.z)

			print("len(chunks.keys())", len(chunks.keys()))
			chunks_table = chunks.values()
			
			# Write faces to .mmesh - always written last in mmesh, face data is placed at end of mmesh file
			write_mesh_buffer(mmesh_file, face_table, mesh_buffers_table)
			# Done with .mmesh file
			mmesh_file.close() # Close mmesh
			del mmesh_file # Delete Reference
			"""
			for i, material in enumerate(mesh_data.materials): 
				# Check material index exists and is valid
				if "MaterialID" not in material:
					raise UserWarning(
						format_exception(f"Material '{material.name}' has no Material Index assigned!\n"
						+ "Please select the mesh and use the GBFR Tool Shelf Panel in the 3D view to assign one and set it to a non-negative number.\n"
						+ f"(Press N to open the tool shelf while your cursor is in the 3D view)")
					)
				if material['MaterialID'] < 0:
					raise UserWarning(
						format_exception(f"Material Index '{material['MaterialID']}' on {material.name} is invalid.\n"
						+ "Please select the mesh and set it to a non-negative number in the GBFR Tool shelf panel.\n"
						+ f"(Press N to open the tool shelf while your cursor is in the 3D view)")
					)
				
				if material['MaterialID'] not in unique_materials_dict:
					unique_materials_dict[material['MaterialID']] = material

				# Add material name to mesh table
				mesh_name = material.name.split("#")[0]
				if mesh_name not in mesh_list:
					mesh_list.append(mesh_name)
					mesh_count += 1
					mesh_ids[mesh_name] = mesh_count
					mesh_id = mesh_count
				else:
					mesh_id = mesh_ids[mesh_name]

				chunk_start = -1 ; chunk_end = -1
				for face in mesh_data.polygons:
					chunk_end = face.index * 3
					if chunk_start == -1 and face.material_index == i:
						chunk_start = face.index * 3
					elif chunk_start != -1 and face.material_index != i:
						break

					# Get chunk's bounds
					if mesh_name not in mesh_bounds:
						mesh_bounds[mesh_name] = { #Initialize chunk bounds at infinity
							'min': {'x': float('inf'), 'y': float('inf'), 'z': float('inf')},
							'max': {'x': float('-inf'), 'y': float('-inf'), 'z': float('-inf')}
						}
					for vert_index in face.vertices: #Calculate and update bounds
						vert_co = mesh_data.vertices[vert_index].co
						mesh_bounds[mesh_name]['min']['x'] = min(mesh_bounds[mesh_name]['min']['x'], vert_co.x)
						mesh_bounds[mesh_name]['min']['y'] = min(mesh_bounds[mesh_name]['min']['y'], vert_co.y)
						mesh_bounds[mesh_name]['min']['z'] = min(mesh_bounds[mesh_name]['min']['z'], vert_co.z)
						mesh_bounds[mesh_name]['max']['x'] = max(mesh_bounds[mesh_name]['max']['x'], vert_co.x)
						mesh_bounds[mesh_name]['max']['y'] = max(mesh_bounds[mesh_name]['max']['y'], vert_co.y)
						mesh_bounds[mesh_name]['max']['z'] = max(mesh_bounds[mesh_name]['max']['z'], vert_co.z)

				if i == len(mesh_data.materials) - 1:
					chunk_end += 3
				chunks_table.append({'offset': chunk_start, 'count': chunk_end - chunk_start, 'mesh_id': mesh_id, 
						'material_id': material["MaterialID"], 'a5': 0, 'a6': 0})
			"""

			print(f"7. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
			timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

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
			# buffer_types_bools = {bool_flag:mesh_obj.get(bool_flag, False) for bool_flag in buffer_types_bool_flags}
			# buffer_types = bools_to_vertex_flags_sum(buffer_types_bools)
			buffer_types = bools_to_vertex_flags_sum(buffer_types_bool_flags)

			lod_data_table = {
				'buffers': mesh_buffers_table, 
				'chunks': chunks_table, 
				'vertex_count': vert_count,
				'index_count': face_count,
				'buffer_types': buffer_types, # mesh_obj.get("buffer_types", 11),
				'a6': bool_array_to_byte(mesh_obj.get("a6", [False * 8])) # TODO
				}
			if not is_shadowlod:
				lods_data.append(lod_data_table)
			else:
				shadowlods_data.append(lod_data_table)
		except Exception as err:
			raise
		finally:
			# Ensure mmesh file is closed (released by file system)
			try: 
				mmesh_file.close()
				del mmesh_file
			except: pass # If file was not defined, disregard

	# Construct and append mesh to meshes table
	for mesh_name in mesh_list:
		mesh_dict = {}
		mesh_dict['name'] = mesh_name
		mesh_dict['bbox'] = {'min': mesh_bounds[mesh_name]['min'], 'max': mesh_bounds[mesh_name]['max']}
		meshes_table.append(mesh_dict)
	# pprint(meshes_table)

	# Real name hash is based on prefix of texture names found in .mmat for each material
	# e.g texture name: pl1400_body01_1_lod0_msk3 => prefix: pl1400_body01_1_lod0 => Hash: 9CE82257 => unique_name_hash in minfo materials: 2632458839
	# TODO: Find elegant way to get texture name from .mmat
	# Note: .mmat also have some hash, maybe for names, but are not the same as hash in .minfo
	unique_materials_dict = dict(sorted(unique_materials_dict.items())) # Sort by material_ids
	materials_data = [
		{
			"unique_name_hash": XXHash32Custom.Hash_string(str(material['MaterialID'])), # Hash the material ID # TODO: figure out proper way.
			"material_flags": bool_array_to_byte(material['material_flags']) # Unknown ubyte material flags
		}
		for material in unique_materials_dict.values()
	]
	
	minfo_data = {
		'magic': 100000101, # Game only checks if it's at least some date, so set to 10000_01_01	#OLD: armature.get("magic", utils_get_magic())
		'lods': lods_data,
		'shadow_lods': shadowlods_data, # TODO: Used for BGs, implement
		'lod_screen_size_thresholds': root_obj.get("lod_screen_size_thresholds", [1.0, 0.6, 0.15, 0.07]), # TODO: Create LOD level distances controls
		'meshes': meshes_table,
		'materials': materials_data,
		'deform_bone_to_bone_index_table': DeformJointsTable,
		'deform_bone_boundary_box': vertex_group_boundary_boxes,
		'bounding_sphere': model_bounding_sphere, # root_obj.get("bounding_sphere", [0.0, 0.0, 0.0, 0.0]),
		# bg_reaction_data,
		'vec3_11': root_obj.get("vec3_11", [0.0, 0.0, 0.0]),
		'near_camera_bound_radius': root_obj.get("near_camera_bound_radius", 0.0),
		'near_camera_detection_scale': root_obj.get("near_camera_detection_scale", 0.0),
		'fade_out_distance': root_obj.get("fade_out_distance", 3.0),
		# f15,
		'f16': root_obj.get("f16", 0.0),
		'f17': root_obj.get("f17", 0.0),
		'f18': root_obj.get("f18", 0.0),
		'f19': root_obj.get("f19", 0.0),
		# u20,
		'byte21': bool_array_to_byte(root_obj.get("byte21", [False*8])),
		#scene_graph_mode,
		#use_scene_graph_cache, bool24, is_ship,
		'bool26': root_obj.get("bool26", False),
		'use_bone_bounds_for_fade': root_obj.get("use_bone_bounds_for_fade", False),
		#bool28, bool29, force_near_fade_evaluation, bool31, use_mesh_aabb_for_fade,
		#render_flags,
		#camera_near_fade_aabb_radius,
		}
	# Extra params (model context dependent, some models have these, some dont)
	# TODO: Convert Bool array parameters back to bytes
	extra_minfo_params = ['bg_reaction_data','f15','u20','scene_graph_mode','use_scene_graph_cache','bool24','is_ship','bool28','bool29','force_near_fade_evaluation','bool31','use_mesh_aabb_for_fade','render_flags','camera_near_fade_aabb_radius']
	byte_params = ['bool31', 'render_flags']
	for param in extra_minfo_params: # Try to get these params from the model
		param_value = root_obj.get(param, None)
		if param_value: 
			minfo_data[param] = param_value if param not in byte_params else bool_array_to_byte(param_value)
	
	print(f"8. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
	timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

	# Build the .minfo file
	try:
		minfo_path = os.path.splitext(filepath)[0] + ".minfo"
		gbfr_minfo_builder.build_minfo(minfo_data, minfo_path)
	except Exception as err:
		raise err

	print(f"9. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
	timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

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
		maxlen=255,  # Max internal buffer length, longer would be clamped.
	)
	export_scale: bpy.props.FloatProperty(name="Scale", default=1.0)

	def invoke(self, context, event):
		try:
			selected_obj = context.object # Get active object
			if selected_obj == None: raise UserWarning(
				format_exception("ERROR: Select the model before exporting.")
				)
			if selected_obj.type == 'MESH':
				#---------------------------------
				print(selected_obj.parent)
				if selected_obj.parent and selected_obj.parent.type in ('ARMATURE','EMPTY'):
					selected_obj = selected_obj.parent # Set root as selected
					utils_select_active(selected_obj)
				else: raise UserWarning(
						format_exception("ERROR: Selected Mesh has no root object or armature as parent!\nMake sure:\n" +
						"1. You have the correct mesh selected.\n" +
						"2. The mesh is parented to an armature or an empty root.\n"
						)
					)
			if len(selected_obj.children) < 1:
				raise UserWarning(format_exception(f"ERROR: Selected Model {selected_obj.name} has no mesh!"))
			
			# self.filepath = selected_obj.name + self.filename_ext
			self.filepath = os.path.join(
				os.path.dirname(self.filepath),
				f"{selected_obj.name}_export{self.filename_ext}"
			)

			return ExportHelper.invoke(self, context, event)
		except Exception as err:
			raise err

	def execute(self, context):

		original_scene = bpy.context.scene # Store the current scene to revert later

		export_scene = bpy.data.scenes.new(name="Export_Scene") # Create a new scene for export
		export_collection = bpy.data.collections.new(name="Collection")
		export_scene.collection.children.link(export_collection)

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

				for child in selected_obj.children:
					if child.type == 'MESH':
						mesh_obj_copy = child.copy()
						mesh_obj_copy.data = child.data.copy()
						mesh_obj_copy.hide_set(False) # ensure mesh object isnt hidden
						export_collection.objects.link(mesh_obj_copy)
						# Parent the duplicated mesh to the duplicated root
						mesh_obj_copy.parent = root_obj_copy
						for modifier in mesh_obj_copy.modifiers: # Set armature modifier to root_obj_copy
							if modifier.type == 'ARMATURE':
								modifier.object = root_obj_copy
								break

				bpy.context.window.scene = export_scene # Set export scene as active scene                
				utils_select_active(root_obj_copy) # Set copied root as active object in the export scene

				selected_obj = context.object
				print(f"selected_obj.name {selected_obj.name}")

				write_some_data(context, self.filepath, self.export_scale) # Export the model

			else: raise UserWarning(
				format_exception("ERROR: No model selected, select the model's root/armature or mesh before export.")
				)

			self.report({'INFO'}, f"Export Finished!")

		except Exception as err:
			raise #Exception(format_exception(str(err))) # Print noob friendly exception
			# raise Exception(str(err))
		finally:
			try:
				bpy.data.scenes.remove(export_scene) # Make sure export scene gets deleted
			except: pass

			# Clean Orphan Data to avoid memory leaks
			bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

		return {'FINISHED'}


class ErrorDisplay(bpy.types.Operator):
	bl_idname = "gbfr.display_error"
	bl_label = "WARNING"
	bl_options = {'INTERNAL'}

	def execute(self, context):
		return {'FINISHED'}

	def invoke(self,context,event):
		return context.window_manager.invoke_props_dialog(self, width = 400)

	def draw(self, context):
		layout = self.layout
		col = layout.column(align=True)

		row = col.row(align=True)
		row.label(text="WARNING: MORE THAN 1 MESH DETECTED ON MODEL!", icon='ERROR')
		row = col.row(align=True)
		row.label(text="You can only have 1 mesh object on the model.")
		row = col.row(align=True)
		row.label(text="Make sure to join all your meshes.")
		row = col.row(align=True)
		row.label(text="Press OK to proceed anyway.")
		col.separator()


def menu_func_export(self, context):
	self.layout.operator(ExportSomeData.bl_idname, text="Granblue Fantasy Relink (.minfo)")


# Register and add to the "file selector" menu (required to use F3 search "Text Export Operator" for quick access).
def register():
	bpy.utils.register_class(ExportSomeData)
	bpy.utils.register_class(ErrorDisplay)
	bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
	bpy.utils.unregister_class(ExportSomeData)
	bpy.utils.unregister_class(ErrorDisplay)
	bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


# if __name__ == "__main__":
#     register()

#     # test call
#     bpy.ops.gbfr.export_mmesh('INVOKE_DEFAULT')
