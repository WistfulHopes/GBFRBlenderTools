import bpy
# import bmesh
# import mathutils
import struct
import os
import time
# import json
# import random
# import importlib
from collections import defaultdict
from pprint import pprint
# ExporterHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
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

def write_some_data(context, filepath, export_scale):
	#Init mmesh and json file variables
	mmesh_file = None ; minfo_json_file = None
	# Init file paths
	minfo_path = os.path.splitext(filepath)[0] + ".minfo"
	mmesh_path = os.path.splitext(filepath)[0] + ".mmesh"
	json_path = os.path.splitext(filepath)[0] + ".json"

	try:
		timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
		# Get the path to flatc specified by user
		flatc_file_path = bpy.context.preferences.addons[__package__].preferences.flatc_file_path
		if os.path.exists(flatc_file_path) == False:
			raise FileNotFoundError(format_exception("ERROR: Please put in the correct path to FlatBuffers/flatc.exe " + 
			"in the preferences for the GBFR Exporter addon settings under: Preferences > Addons"))
		
		# Check that a .minfo is present
		if os.path.exists(minfo_path) == False:
			raise FileNotFoundError(
				format_exception("ERROR: No .minfo of same name found in export folder.\nMake sure the " + 
				"model's original .minfo is in the folder you're exporting to, and that your export name matches.\n" + 
				"Example: If exporting with 'pl1400.minfo', export name must be 'pl1400.mmesh' \n" + 
				f"\nTried to find .minfo at: {minfo_path}")
			)
		
		# f = open(os.path.splitext(filepath)[0] + ".mmesh", 'wb')
		mmesh_file = open(mmesh_path, 'wb')
		
		selected_obj = context.object # Get selected object

		# print (selected_obj.type)
		# If the armature is selected, select its mesh
		if selected_obj.type == 'ARMATURE':
			for child_obj in selected_obj.children:
				if child_obj.type == 'MESH':
					bpy.context.view_layer.objects.active = child_obj
					break
		
		# Get mesh data
		mesh_obj = context.object
		mesh_data = mesh_obj.data

		mesh_obj.hide_set(False) # ensure mesh object isnt hidden

		bpy.ops.object.vertex_group_sort(sort_type='BONE_HIERARCHY') # Sort Vertex Groups by Bone Hierarchy
		utils_set_mode('EDIT')
		bpy.ops.mesh.reveal() # Unhide all vertices
		split_faces_by_edge_seams(mesh_obj) # Do this before anything else or BLENDER FUCKS UP THE NORMALS :)))))))))))
		utils_set_mode('OBJECT')

		# Get the model's armature
		armature = mesh_obj.find_armature()
		if armature == None or mesh_obj.parent.type != 'ARMATURE': # No armature attached to mesh, abort
			print(f"armature: {armature}, obj {mesh_obj}, obj.parent: {mesh_obj.parent.type}")
			raise TypeError(
				format_exception("ERROR: The selected mesh has no armature.\n" + 
				"Your model needs to have an armature.\nMake sure:\n" +
				"1. You have the correct model selected.\n" +
				"2. The mesh is parented to the armature.\n" +
				"3. The mesh has an Armature Modifier set to the correct armature.")
			)
		armature.hide_set(False) # ensure armature object isnt hidden

		
		print(f"Exporting Model: {armature.name}")

		print(f"1. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
		timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
		#================================
		# Apply Mesh and Armature Fixes
		#================================

		mesh_obj.select_set(True) # Select mesh object
		armature.select_set(True) # Select armature
		bpy.ops.object.transform_apply(location=True, rotation=True, scale=True) #Apply all transforms
		armature.rotation_euler = (-1.5707963705062866,0,0) #Rotate back 90 to Y up
		bpy.context.view_layer.objects.active = armature # Set armature as active object
		bpy.context.object.scale = (export_scale, export_scale, export_scale) # Scale the armature
		bpy.ops.object.transform_apply(location=True, rotation=True, scale=True) #Apply all transforms again
		armature.select_set(False) # Deselect Armature

		bpy.context.view_layer.objects.active = mesh_obj # Set mesh as active object

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
		# for vg in mesh_obj.vertex_groups: # <- Unnecessary
		bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=8) # limit total weights to 8
		bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False) # normalize all weights
		
		print(f"2b. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
		timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

		def encode_bone_group_name(group_name): # Encode bone group name to 4-byte little-endian ASCII uint
			encoded_group_name = group_name if group_name.startswith("_") else f"_{group_name}"
			encoded_group_name = encoded_group_name[:4].rjust(4, '\x00') # Truncate
			encoded_group_name = str(int.from_bytes(encoded_group_name.encode('ASCII'), 'little'))
			return encoded_group_name

		# Re-encode and rename all the bone groups back to 4-byte little-endian ASCII uints
		if bpy.app.version >= (4, 0, 0): # Blender 4
			bone_groups = armature.data.collections
		else: # Blender 3
			bone_groups = armature.pose.bone_groups
		for bone_group in bone_groups:
			# encode_group_name = bone_group.name[0:2] + '\x00\x00'
			try:
				bone_group.name = encode_bone_group_name(bone_group.name)
				print("Renamed bone group to:", bone_group.name)
			except:
				raise(
					format_exception(f"Bone group name '{bone_group.name}' is invalid.\n" 
					+ "When exporting to GBFR, Bone group names can only\n"
					+ "consist only of alphanumeric characters, no unicode (i.e. japanese symbols).\n"
					+ "Group names will also be truncated to 4 bytes, starting with an '_'.")
					)

		# Check that mesh only has 1 UV map
		if len(mesh_data.uv_layers) > 1:
			raise Exception(
				format_exception(f"Mesh has {len(mesh_data.uv_layers)} UV maps. GBFR Models can only have 1 UV map.")
			)

		print(f"2. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
		timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
		#================================
		# Build file
		#================================

		#Get BMesh from mesh
		# bm = bmesh.new()
		# bm.from_mesh(mesh)
		# bm.verts.ensure_lookup_table() # Ensure that the lookup tables are initialized
		# bm.edges.ensure_lookup_table()
		# bm.faces.ensure_lookup_table()

		vert_table = {}
		mesh_buffers_table = []
		
		vert_count = 0
		face_count = 0
		
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

		# for face in bm.faces:
		# 	for vert, loop in zip(face.verts, face.loops):
		# 		vert_id = vert.index				
		# 		if vert_id in vert_table:
		# 			continue
		# 		# v = mesh.vertices[vert_id]
		# 		# loop = mesh.loops[loop_id]
		# 		normal = -loop.calc_normal() # Get Normal
		# 		tangent = loop.calc_tangent() # Get Tangent
		# 		bitangent_sign = -1.0 #-loop.calc_tangent_edge_sign() # Get bitangent sign

		# 		vert_buffer = []
		# 		vert_buffer.append(struct.pack('<fff', vert.co[0], vert.co[1], vert.co[2]))
		# 		vert_buffer.append(struct.pack('<eee', normal[0], normal[1], normal[2]))
		# 		vert_buffer.append(b'\x00')
		# 		vert_buffer.append(b'\x00')
		# 		vert_buffer.append(struct.pack('<eee', tangent[0], tangent[1], tangent[2]))
		# 		vert_buffer.append(struct.pack('<e', bitangent_sign))
		# 		uv_layer = bm.loops.layers.uv.active
		# 		uv = loop[uv_layer].uv
		# 		vert_buffer.append(struct.pack('<ee', uv[0], uv[1]))
		# 		vert_count += 1
				
		# 		vert_table[vert_id] = vert_buffer
				
		keys = list(vert_table.keys())
		keys.sort()
		vert_table = {i: vert_table[i] for i in keys}
		
		for vert in vert_table.items():
			for elm in vert[1]:
				mmesh_file.write(elm)
		
		mesh_buffers_table.append({'offset': 0, 'size': mmesh_file.tell()})

		print(f"3. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
		timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

		
		if armature is not None:
			
			# Build Skeleton
			# ================================================
			DeformJointsTable = []
			BoneInfoTablesList = []
			
			skeleton_builder = Builder(0)
			for n, bone in enumerate(armature.data.bones):
				DeformJointsTable.append(n) # TODO: Check that bone is assigned to a vertex group
				
				parent = bone.parent
				if parent is None:
					parent = 65535
				else:
					parent = armature.pose.bones.find(parent.name)
				name = skeleton_builder.CreateString(bone.name)
				bone_matrix = bone.matrix_local
				if bone.parent:
					bone_matrix = bone.parent.matrix_local.inverted() @ bone.matrix_local
				
				# Get bone's bonegroup
				a1 = None
				if n != 0:
					try:
						if bpy.app.version >= (4, 0, 0): # Blender 4
							for bone_collection in armature.data.collections:
								if bone.name in bone_collection.bones:
									a1  = CreateBoneInfo(skeleton_builder, n, int(bone_collection.name))
						else: # Blender 3
							pbone = armature.pose.bones[n]
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

			# Save output to .skeleton file
			buf = skeleton_builder.Output()
			skel = open(os.path.splitext(filepath)[0] + ".skeleton", 'wb')
			skel.write(buf)
			skel.close()
			del skel

			print(f"4. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
			timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

			# Build mesh vertex groups
			# ================================================
			weight_id_table = [] ; weight_id_table_2 = []
			weight_table = [] ; weight_table_2 = []
			vertex_group_verts = defaultdict(list)
			bone_name_to_index_dict = {bone.name: i for i, bone in enumerate(armature.data.bones)}

			max_num_weights = max([len(v.groups) for v in mesh_data.vertices])
			if max_num_weights > 8: 
				raise UserWarning(
					format_exception("Your model has one or more vertices with more than 8 vertex weights.\n"
					+"To export successfully, make sure to use Limit Total on your model."
					)
				)
			# print("max_num_weights", max_num_weights)

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
				
				# Get Vertex group verts
				# for g in v.groups:
				# 	# if g.weight > 0:
				# 	vertex_group_verts[g.group].append(mesh_obj.matrix_world @ v.co)
			
			# Get Boundary Boxes for each Vertex Group
			vertex_group_boundary_boxes = []
			for vg_index, vg_coords in sorted(vertex_group_verts.items()):
				vertex_group_boundary_boxes.append(
					{
						"min": {'x': min(v.x for v in vg_coords), 'y': min(v.y for v in vg_coords), 'z': min(v.z for v in vg_coords)},
						"max": {'x': max(v.x for v in vg_coords), 'y': max(v.y for v in vg_coords), 'z': max(v.z for v in vg_coords)}
					}
				)
			
			# Assign weights		
			weight_id_start = mmesh_file.tell() # get current file stream position
			mmesh_file.write(b''.join(weight_id_table))
			mesh_buffers_table.append({'offset': weight_id_start, 'size': mmesh_file.tell() - weight_id_start})
			
			if weight_id_table_2:
				weight_id_start = mmesh_file.tell() # get current file stream position
				mmesh_file.write(b''.join(weight_id_table_2))
				mesh_buffers_table.append({'offset': weight_id_start, 'size': mmesh_file.tell() - weight_id_start})
			
			weight_start = mmesh_file.tell()
			mmesh_file.write(b''.join(weight_table))
			mesh_buffers_table.append({'offset': weight_start, 'size': mmesh_file.tell() - weight_start})    

			if weight_table_2:
				weight_start = mmesh_file.tell()
				mmesh_file.write(b''.join(weight_table_2))
				mesh_buffers_table.append({'offset': weight_start, 'size': mmesh_file.tell() - weight_start})    

		print(f"5. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
		timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

		# Build  faces
		face_start = mmesh_file.tell()
		for face in mesh_data.polygons:
			skip_face = False
			for vert in face.vertices:
				if vert not in vert_table:
					skip_face = True
					break
			if skip_face: continue

			mmesh_file.write(struct.pack('<III', face.vertices[0], face.vertices[1], face.vertices[2]))
			face_count += 3

		# for face in bm.faces:
		# 	print(f"\nface.index: {face.index}")
		# 	print(f"face.verts[0].index: {face.verts[0].index}")
		# 	print(f"face.verts[1].index: {face.verts[1].index}")
		# 	print(f"face.verts[2].index: {face.verts[2].index}")
		# 	f.write(struct.pack('<III', face.verts[0].index, face.verts[1].index, face.verts[2].index))
		# 	face_count += 3

		mesh_buffers_table.append({'offset': face_start, 'size': mmesh_file.tell() - face_start})     

		mmesh_file.close() # Close mmesh
		del mmesh_file # Delete Reference
		# bm.free() # Free bmesh
		
		print(f"6. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
		timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

		# Build minfo json
		# ================================================
		# minfo_json_file = open(json_path, 'w')
		# Construct chunks and sub meshes list from materials
		sub_meshes_table = []
		sub_mesh_list = []
		chunks_table = []
		sub_mesh_ids = {}
		material_ids = []
		chunk_bounds = {}
		sub_mesh_count = -1
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

			# Add material name to submesh table
			chunk_name = material.name.split("#")[0]
			if chunk_name not in sub_mesh_list:
				sub_mesh_list.append(chunk_name)
				sub_mesh_count += 1
				sub_mesh_ids[chunk_name] = sub_mesh_count
				sub_mesh_id = sub_mesh_count
			else:
				sub_mesh_id = sub_mesh_ids[chunk_name]
				
			# print(f"\nsub_mesh_ids[chunk_name]: {sub_mesh_ids[chunk_name]}")
			# print(f"sub_mesh_list: {sub_mesh_list}")
			# print(f"sub_mesh_id: {sub_mesh_id}")

			# Get material index
			chunk = material['MaterialID']
			if int(chunk) not in material_ids:
				material_ids.append(chunk)
			chunk_start = -1
			chunk_end = -1
			for face in mesh_data.polygons:
				chunk_end = face.index * 3
				if chunk_start == -1 and face.material_index == i:
					chunk_start = face.index * 3
				elif chunk_start != -1 and face.material_index != i:
					break

				# Get chunk's bounds
				face_mat_index = face.material_index
				if chunk_name not in chunk_bounds:
					chunk_bounds[chunk_name] = { #Initialize chunk bounds at infinity
						'min': {'x': float('inf'), 'y': float('inf'), 'z': float('inf')},
						'max': {'x': float('-inf'), 'y': float('-inf'), 'z': float('-inf')}
					}
				for vert_index in face.vertices: #Calculate bounds
					vert_co = mesh_data.vertices[vert_index].co
					chunk_bounds[chunk_name]['min']['x'] = min(chunk_bounds[chunk_name]['min']['x'], vert_co.x)
					chunk_bounds[chunk_name]['min']['y'] = min(chunk_bounds[chunk_name]['min']['y'], vert_co.y)
					chunk_bounds[chunk_name]['min']['z'] = min(chunk_bounds[chunk_name]['min']['z'], vert_co.z)
					chunk_bounds[chunk_name]['max']['x'] = max(chunk_bounds[chunk_name]['max']['x'], vert_co.x)
					chunk_bounds[chunk_name]['max']['y'] = max(chunk_bounds[chunk_name]['max']['y'], vert_co.y)
					chunk_bounds[chunk_name]['max']['z'] = max(chunk_bounds[chunk_name]['max']['z'], vert_co.z)

			if i == len(mesh_data.materials) - 1:
				chunk_end += 3
			chunks_table.append({'offset': chunk_start, 'count': chunk_end - chunk_start, 'mesh_id': sub_mesh_id, 'material_id': int(chunk), 'a5': 0, 'a6': 0})

		print(f"7. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
		timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

		# Prepare minfo data
		# ================================================

		# Construct and append sub mesh to sub meshes table
		for chunk_name in sub_mesh_list:
			sub_mesh_dict = {}
			sub_mesh_dict['name'] = chunk_name
			sub_mesh_dict['bbox'] = {'min': chunk_bounds[chunk_name]['min'], 'max': chunk_bounds[chunk_name]['max']}
			sub_meshes_table.append(sub_mesh_dict)

		# pprint(sub_meshes_table)
		def bools_to_vertex_flags_sum(flags): # Map bools to bitmask
			from .Entities.MInfo_ModelInfo.VertexBufferType import VertexBufferType
			return sum(
				value for name, value in VertexBufferType.__dict__.items()
				if not name.startswith("__") and isinstance(value, int)
				and flags[f"buffer_types.{name}"]
			)
		buffer_types_bool_flags = [
			"buffer_types.POS_NOR_TAN_UV0",
			"buffer_types.BLENDINDICES",
			"buffer_types.BLENDINDICES_2",
			"buffer_types.BLENDWEIGHT",
			"buffer_types.BLENDWEIGHT_2",
			"buffer_types.COLOR",
			"buffer_types.TEXCOORD"
		]
		buffer_types_bools = {bool_flag:mesh_obj.get(bool_flag, False) for bool_flag in buffer_types_bool_flags}
		buffer_types = bools_to_vertex_flags_sum(buffer_types_bools)


		lods_data = [ # TODO: Support multiple LODs
			{
			'buffers': mesh_buffers_table, 
			'chunks': chunks_table, 
			'vertex_count': vert_count,
			'poly_count_x3': face_count,
			'buffer_types': buffer_types, # mesh_obj.get("buffer_types", 11),
			'a6': mesh_obj.get("a6", 0) # TODO
			}
		]

		# Real name hash is based on prefix of texture names found in .mmat for each material
		# e.g texture name: pl1400_body01_1_lod0_msk3 => prefix: pl1400_body01_1_lod0 => Hash: 9CE82257 => unique_name_hash in minfo materials: 2632458839
		# TODO: Find elegant way to get texture name from .mmat
		# Note: .mmat also have some hash, maybe for names, but are not the same as hash in .minfo
		materials_data = [
			{
				"unique_name_hash": XXHash32Custom.Hash_string(str(material_id)), # Hash the material ID # TODO: figure out proper way.
				"unk_flags": 11 # Unknown ubyte flags # TODO: Investigate whether important or not. Set up flag bool controls if necessary
			}
			for material_id in material_ids
		]
		
		minfo_data = {
			'magic': 100000101, # Game only checks if it's at least some date, so set to 10000_01_01	#OLD: armature.get("magic", utils_get_magic())
			'lods': lods_data,
			'shadow_lods': [], # TODO: Empty for characters? Used for bgs?
			'a4': armature.get("a4", [1.0, 0.6, 0.15, 0.07]), # TODO: LOD level distances
			'meshes': sub_meshes_table,
			'materials': materials_data,
			'bones_to_weight_indices': DeformJointsTable,
			'deform_bone_boundary_box': vertex_group_boundary_boxes, # TODO
			'vec3_9': armature.get("vec3_9", [0.0, 0.0, 0.0]),
			# bg_reaction_data,
			'vec3_11': armature.get("vec3_11", [0.0, 0.0, 0.0]),
			'f12': armature.get("f12", 0.0),
			'f13': armature.get("f13", 0.0),
			'fade_out_distance': armature.get("fade_out_distance", 3.0),
			# f15,
			'f16': armature.get("f16", 0.0),
			'f17': armature.get("f17", 0.0),
			'f18': armature.get("f18", 0.0),
			'f19': armature.get("f19", 0.0),
			# u20,
			'byte21': armature.get("byte21", 0),
			'byte22': armature.get("byte22", 0),
			#bool23, bool24, is_ship
			'bool26': armature.get("bool26", False),
			'bool27': armature.get("bool27", False),
			#bool28, bool29, bool30, bool31, bool32
			#bool33, (actually byte not bool)
			#float34
			}
		# Extra params (model context dependent, some models have these, some dont)
		extra_minfo_params = ['bg_reaction_data','f15','u20','bool23','bool24','is_ship','bool28','bool29','bool30','bool31','bool32','bool33','float34']
		for param in extra_minfo_params: # Try to get these params from the model
			param_value = armature.get(param, None)
			if param_value: 
				minfo_data[param] = param_value
		
		print(f"8. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
		timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

		# Build the .minfo file
		try:
			gbfr_minfo_builder.build_minfo(minfo_data, minfo_path)
		except Exception as err:
			raise err

		print(f"9. Elapsed time: {time.perf_counter() - timer_start:.6f} seconds")
		timer_start = time.perf_counter() # @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

		# minfo_data = {
		# 	'mesh_buffers': section_length_table, 
		# 	'chunks': chunk_table, 
		# 	'vertex_count': vert_count, 
		# 	'poly_count_x3': face_count, 
		# 	'buffer_types': 11, 
		# 	'sub_meshes': sub_meshes_table, 
		# 	'bones_to_weight_indices': DeformJointsTable
		# 	}
		# minfo_json_file.write(json.dumps(minfo_data, indent=2))
		# minfo_json_file.close()
		
		# minfo_fbs_path = os.path.join(os.path.dirname(flatc_file_path),"MInfo_ModelInfo.fbs")
		# magic = armature.get("magic", utils_get_magic()) # Get model's magic number
		# Run the MInfo_Converter here
		# importlib.reload(MInfo_Converter) # RELOAD THE SCRIPT WHY ARE YOU SO BAD AT THIS BLENDER?????!!!!!
		# MInfo_Converter.convert_minfo(flatc_file_path, minfo_path, json_path, magic)
		print("HOORAY!!!!!")
		return {'FINISHED'}
	except Exception as err:
		raise #Exception(err)
	finally:
		# Ensure that all created files are closed (released by file system)
		try: 
			mmesh_file.close()
			del mmesh_file
			# os.remove(mmesh_path)
		except: pass # If file was not defined, disregard
		try: 
			minfo_json_file.close()
			del minfo_json_file
			os.remove(json_path)
		except: pass
		try: fix_normals(mesh_obj) # Flip model's normals
		except: pass

		# return {'ERROR'}


class ExportSomeData(Operator, ExportHelper):
	"""Exporter for Granblue Fantasy Relink meshes"""
	bl_idname = "gbfr.export_mesh"  # important since its how bpy.ops.import_test.some_data is constructed
	bl_label = "Export"
	
	# ImportHelper mix-in class uses this.
	filename_ext = ".mmesh"

	filter_glob: StringProperty(
		default="*.mmesh;*.minfo", #Show .minfo files in selector, but always set the extension to mmesh
		options={'HIDDEN'},
		maxlen=255,  # Max internal buffer length, longer would be clamped.
	)
	export_scale: bpy.props.FloatProperty(name="Scale", default=1.0)

	def execute(self, context):
		# if mesh_count > 1:
			# bpy.ops.gbfr.display_error('INVOKE_DEFAULT')
			# return {'FINISHED'}

		original_scene = bpy.context.scene # Store the current scene to revert later

		export_scene = bpy.data.scenes.new(name="Export_Scene") # Create a new scene for export
		export_collection = bpy.data.collections.new(name="Collection")
		export_scene.collection.children.link(export_collection)

		try:
			utils_set_mode('OBJECT') # Set Object Mode

			# Get model's armature and mesh
			selected_obj = context.object # Get active object
			if selected_obj == None: raise UserWarning(
				format_exception("ERROR: Select the model before exporting.")
				)

			if selected_obj.type == 'MESH':
				#---------------------------------
				if selected_obj.parent.type == 'ARMATURE':
					selected_obj = selected_obj.parent # Set armature as selected
				else: raise UserWarning(
						format_exception("ERROR: Selected Mesh has no armature as parent!\nMake sure:\n" +
						"1. You have the correct mesh selected.\n" +
						"2. The mesh is parented to the armature.\n"
						)
					)

			if selected_obj.type == 'ARMATURE':
				# Duplicate object and link to export scene
				arm_copy = selected_obj.copy()
				arm_copy.data = selected_obj.data.copy() 
				arm_copy.name = selected_obj.name + "_export"
				export_collection.objects.link(arm_copy)

				mesh_count = 0
				for child in selected_obj.children:
					if child.type == 'MESH':
						mesh_count += 1
						print(f"mesh_count {mesh_count}")
						# Well apparently blender can't fucking count to save its life so this is getting commented out
						# Let's just hope nobody actually tries to export with more than 1 mesh
						# if mesh_count > 1:
						#     raise UserWarning("ERROR: Models can only have 1 mesh. No more or less.")
						mesh_copy = child.copy()
						mesh_copy.data = child.data.copy()
						export_collection.objects.link(mesh_copy)
						# Parent the duplicated mesh to the duplicated armature
						mesh_copy.parent = arm_copy
						for modifier in mesh_copy.modifiers: # Set armature modifier to arm_copy
							if modifier.type == 'ARMATURE':
								modifier.object = arm_copy
								break

				bpy.context.window.scene = export_scene # Set export scene as active scene                
				bpy.context.view_layer.objects.active = arm_copy # Set copied armature as active object in the export scene

				selected_obj = context.object
				print(f"selected_obj.name {selected_obj.name}")

				write_some_data(context, self.filepath, self.export_scale) # Export the model

			else: raise UserWarning(
				format_exception("ERROR: No model selected, select the model's armature or mesh before export.")
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


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
	self.layout.operator(ExportSomeData.bl_idname, text="Granblue Fantasy Relink (.mmesh)")


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
