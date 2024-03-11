import bpy
import bmesh
import mathutils
import struct
import os
import importlib
from .Entities.ModelInfo import ModelInfo
from .Entities.ModelSkeleton import ModelSkeleton
from .utils import *
		
def parse_skeleton(filepath, CurCollection):
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
		for n in range(skeleton.BodyLength()): # For bone index in skeleton
			bone = skeleton.Body(n) # Get the bone's information
			# Set bone info
			pos = (bone.Position().X(), bone.Position().Y(), bone.Position().Z())
			quat = (bone.Quat().W(), bone.Quat().X(), bone.Quat().Y(), bone.Quat().Z())
			scale = (bone.Scale().X(), bone.Scale().Y(), bone.Scale().Z())


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
			edit_bone.head = (0,0,0)
			edit_bone.tail = (0,0.05,0)
			
			if parent_index != 65535: # Parent the bone to its parent if it has a parent
				edit_bone.parent = armature_obj.data.edit_bones[parent_index]

			# Set up blender bone collection (Import Only) # Credit to bujyu-uo
			Unk = None
			if bone.A1() is not None:
				Unk = bone.A1().Unk()
			if Unk is not None:
				try:
					bone_coll_name = Unk.to_bytes(4, "big").decode("ASCII").rstrip('\x00')
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

	
def read_some_data(context, filepath, import_scale): 
	model_name = os.path.splitext(os.path.basename(filepath))[0] # Get model name from filename

	CurCollection = bpy.data.collections.new(f"GBFR Model Collection_{model_name}") # Create new collection
	bpy.context.scene.collection.children.link(CurCollection)

	utils_set_mode('OBJECT')
	for obj in bpy.context.selected_objects:
		obj.select_set(False) #Deselect everything
	
	mesh_info = parse_mesh_info(filepath) # Parse the mesh info
	armature = parse_skeleton(filepath, CurCollection) # Parse the skeleton
	
	DeformJointsTable = []
	# Get bone weights indices (which bones have weight)
	for n in range(mesh_info.BonesToWeightIndicesLength()):
		DeformJointsTable.append(mesh_info.BonesToWeightIndices(n))
	
	LOD = mesh_info.Lodinfos(0) # Get mesh LOD info of LOD0
	
	try: 
		f = open(os.path.splitext(filepath)[0] + ".mmesh", 'rb')
	except Exception as err: 
		raise FileNotFoundError("ERROR: Put the model's .mmesh file in the same folder as the .minfo.\n" 
			+ "The model's original .mmesh can be found under: data/model_streaming/lod0/<modelID>.mmesh")
	
	vert_count = LOD.VertCount()
	face_count = LOD.PolyCountX3() // 3
	print(f"vert_count = {vert_count} \n face_count = {face_count} \n LOD.PolyCountX3() = {LOD.PolyCountX3()}")
	
	VertTable = []
	NormalTable = []
	TangentTable = []
	UVTable = []
	WeightIndicesTable = []
	WeightTable = []
	FaceTable = []
	
	for n in range(vert_count):
		VertTable.append(struct.unpack('<fff', f.read(4*3)))
		normal = struct.unpack('<eee', f.read(2*3))
		normal = (-normal[0], -normal[1], -normal[2])
		NormalTable.append(normal)
		f.seek(2,1)
		TangentTable.append(struct.unpack('<eee', f.read(2*3)))
		f.seek(2,1)
		UVTable.append(struct.unpack('<ee', f.read(2*2)))
	print(f"len(VertTable) = {len(VertTable)}")
	
	if armature is not None:
		armature.name = f"{model_name}" # Set armature name
		print(f"LOD.BufferTypes() {LOD.BufferTypes()}")
		if LOD.BufferTypes() & 2:
			f.seek(LOD.MeshBuffers(1).Offset())
			for n in range(vert_count):
				i0 = int.from_bytes(f.read(2),byteorder='little')
				i1 = int.from_bytes(f.read(2),byteorder='little')
				i2 = int.from_bytes(f.read(2),byteorder='little')
				i3 = int.from_bytes(f.read(2),byteorder='little')
				
				weight_indices = [DeformJointsTable[i0],DeformJointsTable[i1],DeformJointsTable[i2],DeformJointsTable[i3]]
				WeightIndicesTable.append(weight_indices)

		print(f"LOD.BufferTypes() {LOD.BufferTypes()}")
		print(f"LOD.BufferTypes() & 2 = {LOD.BufferTypes() & 2}")
		print(f"LOD.BufferTypes() & 8 = {LOD.BufferTypes() & 8}")
		print(f"LOD.BufferTypes() & 4 = {LOD.BufferTypes() & 4}")
		if LOD.BufferTypes() & 8:
			if LOD.BufferTypes() & 4:
				f.seek(LOD.MeshBuffers(3).Offset())
			else:
				f.seek(LOD.MeshBuffers(2).Offset())
			for n in range(vert_count):
				WeightTable.append(struct.unpack('<HHHH', f.read(2*4)))
	
	f.seek(LOD.MeshBuffers(LOD.MeshBuffersLength() - 1).Offset())
	for n in range(face_count):
		FaceTable.append(struct.unpack('<III', f.read(4*3)))
	print(f"len(FaceTable) = {len(FaceTable)}")
		
	f.close()
	del f
	
	mesh1 = bpy.data.meshes.new("Mesh") # Create mesh data
	mesh1.use_auto_smooth = True
	obj = bpy.data.objects.new(f"{model_name}_Mesh",mesh1) # Create mesh object with model name
	CurCollection.objects.link(obj)
	utils_select_active(obj)
	obj.select_set(True)
	mesh = bpy.context.object.data
	bm = bmesh.new()
	for v in VertTable:
		bm.verts.new((v[0],v[1],v[2]))
	list = [v for v in bm.verts]
	print(f"len(list) = {len(list)}")
	duplicate_face_indices = [] # Models can have duplicate faces
	for idx, f in enumerate(FaceTable): # Convert verts to faces
		try:
			# if idx < 35000: print(f"{idx}: {(f[0],f[1],f[2])}")
			bm.faces.new((list[f[0]],list[f[1]],list[f[2]]))
		except Exception as err:
			print(f"{idx}: {err}")
			duplicate_face_indices.append(idx)
			pass
	bm.to_mesh(mesh)

	dupe_face_start = -1
	dupe_face_count = -1
	if len(duplicate_face_indices) > 0:
		dupe_face_start = duplicate_face_indices[0]
		dupe_face_count = len(duplicate_face_indices)
	print(f"len(bm.faces) = {len(bm.faces)}")

	uv_layer = bm.loops.layers.uv.verify()
	Normals = []
	for f in bm.faces:
		f.smooth=True
		for l in f.loops:
			if NormalTable != []:
				Normals.append(NormalTable[l.vert.index])
			luv = l[uv_layer]
			try:
				luv.uv = UVTable[l.vert.index]
			except:
				continue
	bm.to_mesh(mesh)
		
	if NormalTable != []:
		mesh1.normals_split_custom_set(Normals)

	if armature is not None:
		for v in range(vert_count):
			for n in range(4):
				group_name = armature.data.bones[WeightIndicesTable[v][n]].name
				if obj.vertex_groups.find(group_name) == -1:
					TempVG = obj.vertex_groups.new(name = group_name)
				else:
					TempVG = obj.vertex_groups[obj.vertex_groups.find(group_name)]
				
				TempVG.add([v], float(WeightTable[v][n]) / 65535, 'ADD')
	
	mat_counter = 0
	
	for i in range(mesh_info.SubMeshesLength()):
		sub_mesh = mesh_info.SubMeshes(i)
		for j in range(LOD.ChunksLength()):
			chunk = LOD.Chunks(j)
			if chunk.SubMesh() != i:
				continue
			mat_name = sub_mesh.Name().decode() + "#" + str(chunk.Material())
			mat = bpy.data.materials.new(name=mat_name)
			obj.data.materials.append(mat)
			mat["MaterialID"] = chunk.Material() # Add material ID as custom property

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
					obj.data.polygons[p].material_index = mat_counter
				except Exception as err:
					raise Exception(format_exception("ERROR: This model's mesh probably has duplicate faces. The model's materials will not be assigned correctly."))
					pass
			
			mat_counter += 1

	# Store mat order in custom property on armature
	mat_order = [mat.name for mat in obj.data.materials]
	armature["material_order"] = mat_order
		
	if armature is not None:
		ArmMod = obj.modifiers.new("Armature","ARMATURE")
		ArmMod.object = armature
		obj.parent = armature
		armature.rotation_euler = (1.5707963705062866,0,0) # Rotate 90 degrees from Y up to Z up
	
	obj.select_set(True)
	utils_set_mode('EDIT')
	bpy.ops.mesh.select_all(action='SELECT')
	bpy.ops.mesh.flip_normals()
	utils_set_mode('OBJECT')

	if armature is not None:
		armature.select_set(True) # Select the armature
		armature.display_type = 'WIRE'
		armature.show_in_front = True # X-Ray view for armature
		utils_select_active(armature)
		bpy.context.object.scale = (import_scale, import_scale, import_scale) # Scale the armature
		bpy.ops.object.transform_apply(location=True, rotation=True, scale=True) # Apply Transforms to armature

	return {'FINISHED'}


# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator


class ImportSomeData(Operator, ImportHelper):
	"""Importer for Granblue Fantasy Relink models"""
	bl_idname = "gbfr.import_mesh"  # important since its how bpy.ops.import_test.some_data is constructed
	bl_label = "Import"

	# ImportHelper mix-in class uses this.
	filename_ext = ".minfo"

	filter_glob: StringProperty(
		default="*.minfo",
		options={'HIDDEN'},
		maxlen=255,  # Max internal buffer length, longer would be clamped.
	)
	import_scale: bpy.props.FloatProperty(name="Scale", default=1.0)

	def execute(self, context):
		return read_some_data(context, self.filepath, self.import_scale)


# Only needed if you want to add into a dynamic menu.
def menu_func_import(self, context):
	self.layout.operator(ImportSomeData.bl_idname, text="Granblue Fantasy Relink (.minfo)")


# Register and add to the "file selector" menu (required to use F3 search "Text Import Operator" for quick access).
def register():
	bpy.utils.register_class(ImportSomeData)
	bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
	bpy.utils.unregister_class(ImportSomeData)
	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)