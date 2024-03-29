import bpy
import bmesh
import mathutils
import struct
import os
import json
import random
import importlib
from pprint import pprint
# ExporterHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator
# ----------------------------
from .Entities.flatbuffers.builder import Builder
from .Entities.ModelSkeleton import ModelSkeleton, StartBodyVector, ModelSkeletonStart, ModelSkeletonAddMagic, ModelSkeletonAddBody, ModelSkeletonEnd
from .Entities.Bone import Bone, BoneStart, BoneAddA1, BoneAddParentId, BoneAddName, BoneAddPosition, BoneAddQuat, BoneAddScale, BoneEnd
from .Entities.BoneInfo import BoneInfo, CreateBoneInfo
from .Entities.Vec3 import Vec3, CreateVec3
from .Entities.Quaternion import Quaternion, CreateQuaternion
from .Entities import MInfo_Converter
from .utils import *

def write_some_data(context, filepath, export_scale):
	#Init mmesh and json file variables
	f = None ; j = None
	# Init file paths
	minfo_path = os.path.splitext(filepath)[0] + ".minfo"
	mmesh_path = os.path.splitext(filepath)[0] + ".mmesh"
	json_path = os.path.splitext(filepath)[0] + ".json"

	try:
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
		f = open(mmesh_path, 'wb')
		
		selected_obj = context.object # Get selected object

		print (selected_obj.type)
		# If the armature is selected, select its mesh
		if selected_obj.type == 'ARMATURE':
			for child_obj in selected_obj.children:
				if child_obj.type == 'MESH':
					bpy.context.view_layer.objects.active = child_obj
					break
		
		# Get mesh data
		obj = context.object
		mesh = obj.data

		obj.hide_set(False) # ensure mesh object isnt hidden

		utils_set_mode('EDIT')
		bpy.ops.mesh.reveal() # Unhide all vertices
		split_faces_by_edge_seams(obj) # Do this before anything else or BLENDER FUCKS UP THE NORMALS :)))))))))))
		utils_set_mode('OBJECT')

		# Get the model's armature
		armature = obj.find_armature()
		if armature == None or obj.parent.type != 'ARMATURE': # No armature attached to mesh, abort
			raise TypeError(
				format_exception("ERROR: The selected mesh has no armature.\n" + 
				"Your model needs to have an armature.\nMake sure:" +
				"1. You have the correct model selected.\n" +
				"2. The mesh is parented to the armature.\n" +
				"3. The mesh has an Armature Modifier set to the correct armature.")
			)
		armature.hide_set(False) # ensure armature object isnt hidden

		
		print(f"armature.name {armature.name}")

		#================================
		# Apply Mesh and Armature Fixes
		#================================

		obj.select_set(True) # Select mesh object
		armature.select_set(True) # Select armature
		bpy.ops.object.transform_apply(location=True, rotation=True, scale=True) #Apply all transforms
		armature.rotation_euler = (-1.5707963705062866,0,0) #Rotate back 90 to Y up
		bpy.context.view_layer.objects.active = armature # Set armature as active object
		bpy.context.object.scale = (export_scale, export_scale, export_scale) # Scale the armature
		bpy.ops.object.transform_apply(location=True, rotation=True, scale=True) #Apply all transforms again
		armature.select_set(False) # Deselect Armature

		bpy.context.view_layer.objects.active = obj # Set mesh as active object

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
		mesh.calc_tangents() # mesh.calc_tangents(uvmap='Float2')

		for vg in obj.vertex_groups: # Limit and normalize weights
			bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4) # limit total weights to 4
			bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False) # normalize all weights

		# Re-encode and rename all the bone groups back to ints
		if bpy.app.version >= (4, 0, 0): # Blender 4
			for bone_collection in armature.data.collections:
				encode_coll_name = bone_collection.name[0:2] + '\x00\x00'
				try:
					bone_collection.name = str(int.from_bytes(encode_coll_name.encode('ASCII'), 'big'))
				except:
					raise(
						format_exception(f"Bone group name '{bone_collection.name}' is invalid.\n" 
						+ "When exporting to GBFR, Bone group names can only:\n"
						+ "1. be 2 characters long\n"
						+ "2. consist only of alphanumeric characters, no unicode (i.e. japanese symbols).")
						)
				print("Renamed bone group:", bone_collection.name)
		else: # Blender 3
			for bone_group in armature.pose.bone_groups:
				encode_group_name = bone_group.name[0:2] + '\x00\x00'
				try:
					bone_group.name = str(int.from_bytes(encode_group_name.encode('ASCII'), 'big'))
				except:
					raise(
						format_exception(f"Bone group name '{bone_group.name}' is invalid.\n" 
						+ "When exporting to GBFR, Bone group names can only:\n"
						+ "1. be 2 characters long\n"
						+ "2. consist only of alphanumeric characters, no unicode (i.e. japanese symbols).")
						)
				print("Renamed bone group to:", bone_group.name)

		# Check that mesh only has 1 UV map
		if len(mesh.uv_layers) > 1:
			raise Exception(
				format_exception(f"Mesh has {len(mesh.uv_layers)} UV maps. GBFR Models can only have 1 UV map.")
			)

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
		section_length_table = []
		
		vert_count = 0
		face_count = 0
		
		for face in mesh.polygons:
			for vert_id, loop_id in zip(face.vertices, face.loop_indices):
				if vert_id in vert_table:
					continue
				v = mesh.vertices[vert_id]
				loop = mesh.loops[loop_id]
				vert_buffer = []
				vert_buffer.append(struct.pack('<fff', v.undeformed_co[0], v.undeformed_co[1], v.undeformed_co[2]))
				vert_buffer.append(struct.pack('<eee', -loop.normal[0], -loop.normal[1], -loop.normal[2]))
				vert_buffer.append(b'\x00')
				vert_buffer.append(b'\x00')
				vert_buffer.append(struct.pack('<eee', loop.tangent[0], loop.tangent[1], loop.tangent[2]))
				vert_buffer.append(struct.pack('<e', -loop.bitangent_sign))
				uv = obj.data.uv_layers.active.data[loop_id].uv
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
				f.write(elm)
		
		section_length_table.append({'offset': 0, 'size': f.tell()})

		DeformJointsTable = []

		weight_id_table = []
		weight_table = []

		BoneTable = []

		if armature is not None:
			builder = Builder(0)

			# Build Skeleton
			# ================================================
			for n, bone in enumerate(armature.data.bones):
				DeformJointsTable.append(n)
				
				parent = bone.parent
				if parent is None:
					parent = 65535
				else:
					parent = armature.pose.bones.find(parent.name)
				name = builder.CreateString(bone.name)
				mat = bone.matrix_local
				if bone.parent:
					mat = bone.parent.matrix_local.inverted() @ bone.matrix_local
				
				# Get bone's bonegroup
				a1 = None
				if n != 0:
					try:
						if bpy.app.version >= (4, 0, 0):
							for bone_collection in armature.data.collections:
								if bone.name in bone_collection.bones:
									a1  = CreateBoneInfo(builder, n, int(bone_collection.name))
						else:
							pbone = armature.pose.bones[n]
							if pbone.bone_group:
								bone_group = pbone.bone_group
								a1  = CreateBoneInfo(builder, n, int(bone_group.name))
					except:
						a1 = CreateBoneInfo(builder, n, random.randint(0, 4294967294))
					
				BoneStart(builder)
				if a1 is not None:
					BoneAddA1(builder, a1)
				BoneAddParentId(builder, parent)
				BoneAddName(builder, name)
				pos = CreateVec3(builder, mat.translation[0], mat.translation[1], mat.translation[2])
				BoneAddPosition(builder, pos)
				quat = mat.to_quaternion()
				quat = CreateQuaternion(builder, quat[1], quat[2], quat[3], quat[0])           
				BoneAddQuat(builder, quat)
				scale = CreateVec3(builder, 1.0, 1.0, 1.0)
				BoneAddScale(builder, scale)
				bone = BoneEnd(builder)
				
				BoneTable.append(bone)

			StartBodyVector(builder, len(BoneTable))
			for b in reversed(BoneTable):
				builder.PrependUOffsetTRelative(b)
			body = builder.EndVector()

			ModelSkeletonStart(builder)
			ModelSkeletonAddMagic(builder, 20230729)
			ModelSkeletonAddBody(builder, body)
			body = ModelSkeletonEnd(builder)
			builder.Finish(body)

			buf = builder.Output()
			skel = open(os.path.splitext(filepath)[0] + ".skeleton", 'wb')
			skel.write(buf)
			skel.close()
			del skel


			# Build mesh vertex groups
			# ================================================
			  
			for v in mesh.vertices:
				if v.index not in vert_table:
					continue # Make sure we're only processing verts we're exporting
				if len(v.groups) > 4:
					fix_normals(obj)
					raise UserWarning(
						format_exception("Your model has one or more vertices with more than 4 vertex weights.\n"
						+"To export successfully, make sure to use Limit Total on your model."
						)
					)
				for n in range(4):
					if n >= len(v.groups):
						weight_id_table.append(struct.pack('<H', 0))
						weight_table.append(struct.pack('<H', 0))
						if n == 3:
							total_weight_float = 0
							total_weight = 0
							for i in range(len(v.groups)):
								total_weight += int(v.groups[i].weight * 65535)
								total_weight_float += v.groups[i].weight
							if total_weight_float <= 0.99:
								fix_normals(obj)
								raise UserWarning(
									format_exception(
									"Your model has non-normalized weights.\n"
									+"To export successfully, make sure to use Normalize All on your model.\n\n"
									+"You may also be missing weights on some vertices, you cannot have geometry with 0 weights."
									)
								)
							if total_weight != 65535:
								index_max = max(range(4), key=weight_table[-4:].__getitem__)
								weight_table[-4 + index_max] = struct.pack('<H', int(v.groups[index_max].weight * 65535) + (65535 - total_weight))
						continue
						
					group_name = obj.vertex_groups[v.groups[n].group].name

					for i, bone in enumerate(armature.data.bones):
						if group_name == bone.name:
							break

					weight_id_table.append(struct.pack('<H', i))
					weight_table.append(struct.pack('<H', int(v.groups[n].weight * 65535)))
					
					if n == 3:
						total_weight_float = 0
						total_weight = 0
						for i in range(4):
							total_weight += int(v.groups[i].weight * 65535)
							total_weight_float += v.groups[i].weight
						if total_weight_float <= 0.99:
							fix_normals(obj)
							raise UserWarning(
								format_exception("Your model has non-normalized weights.\n"
								+ "To export successfully, make sure to use Normalize All on your model.\n\n"
								+ "You may also be missing weights on some vertices, you cannot have geometry with 0 weights."
								)
							)
						if total_weight != 65535: #TODO: Should be less than 65535? Investigate
							index_max = max(range(4), key=weight_table[-4:].__getitem__)
							print(f"total_weight: {total_weight} | index_max:{index_max}")
							try:
								weight_table[-4 + index_max] = struct.pack('<H', int(v.groups[index_max].weight * 65535) + (65535 - total_weight))
							except:
								raise UserWarning(
									format_exception("Your model probably has way too many bones, merge bones together until you have a reasonable amount.\n"
									+ "Make sure you're merging the vertex groups as well, don't just delete bones.")
								)
			
			# Assign weights		
			weight_id_start = f.tell()
					
			for id in weight_id_table:
				f.write(id)

			section_length_table.append({'offset': weight_id_start, 'size': f.tell() - weight_id_start})
			
			weight_start = f.tell()
			
			for weight in weight_table:
				f.write(weight)
			
			section_length_table.append({'offset': weight_start, 'size': f.tell() - weight_start})        


		# Build  faces
		face_start = f.tell()

		for face in mesh.polygons:
			skip_face = False
			for vert in face.vertices:
				if vert not in vert_table:
					skip_face = True
					break
			if skip_face: continue

			f.write(struct.pack('<I', face.vertices[0]))
			f.write(struct.pack('<I', face.vertices[1]))
			f.write(struct.pack('<I', face.vertices[2]))       
			face_count += 3

		# for face in bm.faces:
		# 	print(f"\nface.index: {face.index}")
		# 	print(f"face.verts[0].index: {face.verts[0].index}")
		# 	print(f"face.verts[1].index: {face.verts[1].index}")
		# 	print(f"face.verts[2].index: {face.verts[2].index}")
		# 	f.write(struct.pack('<III', face.verts[0].index, face.verts[1].index, face.verts[2].index))
		# 	face_count += 3

		section_length_table.append({'offset': face_start, 'size': f.tell() - face_start})     

		f.close() # Close mmesh
		# bm.free() # Free bmesh
		

		# Build minfo json

		# j = open(os.path.splitext(filepath)[0] + ".json", 'w')
		j = open(json_path, 'w')
		
		
		#------------------------------------------
		# Construct chunks and sub meshes list from materials
		sub_meshes_table = []
		sub_mesh_list = []
		chunk_table = []
		sub_mesh_ids = {}
		chunk_bounds = {}
		sub_mesh_count = -1
		for i, material in enumerate(mesh.materials): 
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
			
			chunk_start = -1
			chunk_end = -1
			for face in mesh.polygons:
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
					vert_co = mesh.vertices[vert_index].co
					chunk_bounds[chunk_name]['min']['x'] = min(chunk_bounds[chunk_name]['min']['x'], vert_co.x)
					chunk_bounds[chunk_name]['min']['y'] = min(chunk_bounds[chunk_name]['min']['y'], vert_co.y)
					chunk_bounds[chunk_name]['min']['z'] = min(chunk_bounds[chunk_name]['min']['z'], vert_co.z)
					chunk_bounds[chunk_name]['max']['x'] = max(chunk_bounds[chunk_name]['max']['x'], vert_co.x)
					chunk_bounds[chunk_name]['max']['y'] = max(chunk_bounds[chunk_name]['max']['y'], vert_co.y)
					chunk_bounds[chunk_name]['max']['z'] = max(chunk_bounds[chunk_name]['max']['z'], vert_co.z)

			if i == len(mesh.materials) - 1:
				chunk_end += 3
			chunk_table.append({'offset': chunk_start, 'count': chunk_end - chunk_start, 'sub_mesh_id': sub_mesh_id, 'material_id': int(chunk), 'a5': 0, 'a6': 0})
			
		# Construct and append sub mesh to sub meshes table
		for chunk_name in sub_mesh_list:
			sub_mesh_dict = {}
			sub_mesh_dict['name'] = chunk_name
			sub_mesh_dict['bbox'] = {'min': chunk_bounds[chunk_name]['min'], 'max': chunk_bounds[chunk_name]['max']}
			sub_meshes_table.append(sub_mesh_dict)

		pprint(sub_meshes_table)

		jobj = {'mesh_buffers': section_length_table, 'chunks': chunk_table, 'vertex_count': vert_count, 'poly_count_x3': face_count, 'buffer_types': 11, 'sub_meshes': sub_meshes_table, 'bones_to_weight_indices': DeformJointsTable}
		
		j.write(json.dumps(jobj, indent=2))
		j.close()
		
		fix_normals(obj)

		# minfo_fbs_path = os.path.join(os.path.dirname(flatc_file_path),"MInfo_ModelInfo.fbs")
		magic = armature.get("Magic", utils_get_magic()) # Get model's magic number
		# Run the MInfo_Converter here
		importlib.reload(MInfo_Converter) # RELOAD THE SCRIPT WHY ARE YOU SO BAD AT THIS BLENDER?????!!!!!
		MInfo_Converter.convert_minfo(flatc_file_path, minfo_path, json_path, magic)
		return {'FINISHED'}
	except Exception as err:
		raise #Exception(err)
	finally:
		# Ensure that all created files are closed (released by file system)
		try: 
			f.close()
			del f
			os.remove(mmesh_path)
		except: pass # If file was not defined, disregard
		try: 
			j.close()
			del j
			os.remove(json_path)
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
						format_exception("ERROR: Selected Mesh has no armature as parent!\nMake sure:" +
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
			try: bpy.data.scenes.remove(export_scene) # Make sure export scene gets deleted
			except: pass

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
