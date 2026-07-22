import bpy
import sys
import struct
import os

from .Entities.flatbuffers.builder import Builder
from .Entities.MInfo_ModelInfo import (ModelInfo as MInfo, 
									   StreamLOD, BufferLocator, LODChunk, 
									   MeshInfo, 
									   BoundaryBox,
									   MaterialInfo,
									   BgReactionData, BgReactionParticleType,
									   Vec3, Vec4
)

# =============================================================

# /////////////////////////////////////////////////////////////

# ======================= LOD Functions =======================
def create_lod_chunk(builder:Builder, chunk_data:dict):
	return LODChunk.CreateLODChunk(
		builder,
		offset=chunk_data["offset"],
		count=chunk_data["count"],
		meshId=chunk_data["mesh_id"],
		materialId=chunk_data["material_id"],
		a5=chunk_data["a5"],
		a6=chunk_data["a6"]
	)

def create_buffer_locator(builder:Builder, buffer_data:dict):
	#1. Add offset and size ulong
	return BufferLocator.CreateBufferLocator(
		builder,
		offset=buffer_data["offset"],
		size=buffer_data["size"]
	)

def build_stream_lod_table(builder:Builder, lod_data:dict):
	# Build vectors first, then add
	#1. Build buffers vector
	StreamLOD.StartBuffersVector(builder, numElems=len(lod_data["buffers"]))
	for buffer_data in reversed(lod_data["buffers"]):
		create_buffer_locator(builder, buffer_data)
	buffers_vector = builder.EndVector()
	
	#2. Build chunks vector
	StreamLOD.StartChunksVector(builder, numElems=len(lod_data["chunks"]))
	for chunk_data in reversed(lod_data["chunks"]):
		create_lod_chunk(builder, chunk_data)
	chunks_vector = builder.EndVector()

	#3. Build StreamLOD table
	StreamLOD.Start(builder)
	StreamLOD.AddBuffers(builder, buffers_vector)
	StreamLOD.AddChunks(builder, chunks_vector)
	StreamLOD.AddVertexCount(builder, lod_data["vertex_count"])
	StreamLOD.AddIndexCount(builder, lod_data["index_count"])
	StreamLOD.AddBufferTypes(builder, lod_data["buffer_types"])
	StreamLOD.AddA6(builder,lod_data["a6"])
	stream_lod_offset = StreamLOD.End(builder)

	return stream_lod_offset

def build_lods_list(builder:Builder, lods_data:list):
	#1. Build data for each LOD first
	lods_offsets = []
	for lod_data in lods_data:
		lods_offsets.append(build_stream_lod_table(builder, lod_data))
	
	#2. Build LODS vector
	MInfo.StartLodsVector(builder, numElems=len(lods_offsets))
	for lod_offset in reversed(lods_offsets):
		builder.PrependUOffsetTRelative(lod_offset)
	lods_vector = builder.EndVector()

	return lods_vector
# =======================================================================

# ///////////////////////////////////////////////////////////////////////

# ======================= Sub Mesh/BBox Functions =======================
def create_boundary_box(builder:Builder, bounding_box_data:dict):
	# print("bounding_box_data", bounding_box_data)
	boundary_box = BoundaryBox.CreateBoundaryBox(builder,
							   min_x=bounding_box_data["min"]["x"],
							   min_y=bounding_box_data["min"]["y"],
							   min_z=bounding_box_data["min"]["z"],
							   max_x=bounding_box_data["max"]["x"],
							   max_y=bounding_box_data["max"]["y"],
							   max_z=bounding_box_data["max"]["z"]
							   )
	return boundary_box
	

def build_submesh_info_table(builder:Builder, mesh_data:dict):
	#1. Serialize Name string
	name = builder.CreateString(mesh_data["name"])

	#2. Build Mesh Info table
	MeshInfo.Start(builder)
	MeshInfo.AddName(builder, name)
	MeshInfo.AddBbox(builder, create_boundary_box(builder, mesh_data["bbox"]))
	submesh_info_offset = MeshInfo.End(builder)

	return submesh_info_offset

def build_meshes_list(builder:Builder, meshes_data:list):
	#1. Build data for each mesh first
	submesh_info_offsets = []
	for mesh_data in meshes_data:
		submesh_info_offsets.append(build_submesh_info_table(builder, mesh_data))

	#2. Build meshes vector
	MInfo.StartMeshesVector(builder, numElems=len(submesh_info_offsets))
	for mesh_info_offset in reversed(submesh_info_offsets):
		builder.PrependUOffsetTRelative(mesh_info_offset)
	meshes_vector = builder.EndVector()

	return meshes_vector


# ===================================================================

# ///////////////////////////////////////////////////////////////////

# ======================= Materials Functions =======================
def build_material_info(builder:Builder, material_data:dict):
	# Build Material info table
	MaterialInfo.Start(builder)
	MaterialInfo.AddUniqueNameHash(builder, material_data["unique_name_hash"])
	MaterialInfo.AddMaterialFlags(builder, material_data["material_flags"])
	material_info_offset = MaterialInfo.End(builder)
	
	return material_info_offset
	
def build_materials_list(builder:Builder, materials_data:list):
	#1. Build data for each material first
	material_info_offsets = []
	for material_data in materials_data:
		material_info_offsets.append(build_material_info(builder, material_data))

	#2. Build materials vector
	MInfo.StartMaterialsVector(builder, numElems=len(material_info_offsets))
	for material_info_offset in reversed(material_info_offsets):
		builder.PrependUOffsetTRelative(material_info_offset)
	materials_vector = builder.EndVector()

	return materials_vector


# =============================================================

# /////////////////////////////////////////////////////////////

# ======================= Util Function =======================
def build_vector(builder:Builder, builder_function_name:str, vector_name:str, list_data:list):
	vector_offsets = []
	for item_data in list_data:
		vector_offsets.append(getattr(sys.modules[__name__], f"{builder_function_name}")(builder, item_data))

	getattr(MInfo, f"Start{vector_name.capitalize()}Vector")(builder, numElems=len(vector_offsets))
	for vector_offset in reversed(vector_offsets):
		builder.PrependUOffsetTRelative(vector_offset)
	vector = builder.EndVector()
	
	return vector

# =============================================================

# /////////////////////////////////////////////////////////////

# ======================= Save Function =======================
def save_minfo_file(builder:Builder, filepath:str):
	buffer = builder.Output()
	minfo_file = open(os.path.splitext(filepath)[0] + ".minfo", 'wb')
	minfo_file.write(buffer)
	minfo_file.close()
	del minfo_file # Delete File reference


# =============================================================

# /////////////////////////////////////////////////////////////

# ======================= Main Function =======================
def build_minfo(minfo_data:dict, filepath:str):
	minfo_builder = Builder(0)

	#1. Set Magic
	magic = minfo_data["magic"]
	#2. Build lods list
	lods_vector = build_lods_list(minfo_builder, minfo_data["lods"])

	#3. Build shadow lods list
	shadow_lods_vector = build_lods_list(minfo_builder, minfo_data["shadow_lods"])

	#4. Build LOD distance thresholds float list
	MInfo.StartLodScreenSizeThresholdsVector(minfo_builder, len(minfo_data["lod_screen_size_thresholds"]))
	for lod_threshold_float in reversed(minfo_data["lod_screen_size_thresholds"]):
		minfo_builder.PrependFloat32(lod_threshold_float)
	lod_thresholds_vector = minfo_builder.EndVector()

	#5. Build Sub Meshes info List (Geometry separated by Materials)
	meshes_vector = build_meshes_list(minfo_builder, minfo_data["meshes"])

	#6. Build Materials List
	materials_vector = build_materials_list(minfo_builder, minfo_data["materials"])
	# materials_vector = build_vector(minfo_builder, builder_function_name = "build_material_info", vector_name="materials", list_data=minfo_data["materials"])

	#7. Build Bones to Weight Indices list
	MInfo.StartDeformBoneToBoneIndexTableVector(minfo_builder, len(minfo_data["deform_bone_to_bone_index_table"]))
	for index_short in reversed(minfo_data["deform_bone_to_bone_index_table"]):
		minfo_builder.PrependUint16(index_short)
	deform_bone_to_bone_index_table_vector = minfo_builder.EndVector()

	#8. Build Bone Deform Bounding Boxes list (remember to flip y and z, y is negative)
	MInfo.StartDeformBoneBoundaryBoxVector(minfo_builder, len(minfo_data["deform_bone_boundary_box"]))
	for bounding_box_data in reversed(minfo_data["deform_bone_boundary_box"]):
		create_boundary_box(minfo_builder, bounding_box_data)
	deform_bone_boundary_box_vector = minfo_builder.EndVector()	

	#10. Build bg_reaction_data (Only build for bgXXXX files)
	# TODO: Work on BG files and implement them

	#11. Build Model Info Table. Add everything to minfo. Wrap it up!
	# Start Table
	MInfo.ModelInfoStart(minfo_builder)

	# Add Data
	MInfo.AddMagic(minfo_builder, magic)
	MInfo.AddLods(minfo_builder, lods_vector)
	MInfo.AddShadowLods(minfo_builder, shadow_lods_vector)
	MInfo.AddLodScreenSizeThresholds(minfo_builder, lod_thresholds_vector)
	MInfo.AddMeshes(minfo_builder, meshes_vector)
	MInfo.AddMaterials(minfo_builder, materials_vector)
	MInfo.AddDeformBoneToBoneIndexTable(minfo_builder, deform_bone_to_bone_index_table_vector)
	MInfo.AddDeformBoneBoundaryBox(minfo_builder, deform_bone_boundary_box_vector)
	MInfo.AddBoundingSphere(minfo_builder, Vec4.CreateVec4(minfo_builder, 
											   x=minfo_data["bounding_sphere"][0], 
											   y=minfo_data["bounding_sphere"][1], 
											   z=minfo_data["bounding_sphere"][2], 
											   r=minfo_data["bounding_sphere"][3]))
	# TODO: IMPLEMENT
	#if "bg_reaction_data" in minfo_data:
	#  MInfo.AddBgReactionData(minfo_builder, )
	MInfo.AddVec311(minfo_builder, Vec3.CreateVec3(minfo_builder, 
												x=minfo_data["vec3_11"][0], 
												y=minfo_data["vec3_11"][1],
												z=minfo_data["vec3_11"][2]))
	MInfo.AddNearCameraBoundRadius(minfo_builder, minfo_data["near_camera_bound_radius"])
	MInfo.AddNearCameraDetectionScale(minfo_builder, minfo_data["near_camera_detection_scale"])
	MInfo.AddFadeOutDistance(minfo_builder, minfo_data["fade_out_distance"])
	if "f15" in minfo_data: 
		MInfo.AddF15(minfo_builder, minfo_data["f15"])
	MInfo.AddF16(minfo_builder, minfo_data["f16"])
	MInfo.AddF17(minfo_builder, minfo_data["f17"])
	MInfo.AddF18(minfo_builder, minfo_data["f18"])
	MInfo.AddF19(minfo_builder, minfo_data["f19"])
	if "u20" in minfo_data: 
		MInfo.AddU20(minfo_builder, int(minfo_data["u20"]) & 0xFFFFFFFF) # Ensure conversion to uint32
	MInfo.AddByte21(minfo_builder, minfo_data["byte21"])
	if "scene_graph_mode" in minfo_data:
		MInfo.AddSceneGraphMode(minfo_builder, minfo_data["scene_graph_mode"])
	if "use_scene_graph_cache" in minfo_data: 
		MInfo.AddUseSceneGraphCache(minfo_builder, minfo_data["use_scene_graph_cache"])
	if "bool24" in minfo_data: 
		MInfo.AddBool24(minfo_builder, minfo_data["bool24"])
	if "is_ship" in minfo_data: 
		MInfo.AddIsShip(minfo_builder, minfo_data["is_ship"])
	MInfo.AddBool26(minfo_builder, minfo_data["bool26"])
	MInfo.AddUseBoneBoundsForFade(minfo_builder, minfo_data["use_bone_bounds_for_fade"])
	if "bool28" in minfo_data: 
		MInfo.AddBool28(minfo_builder, minfo_data["bool28"])
	if "bool29" in minfo_data: 
		MInfo.AddBool29(minfo_builder, minfo_data["bool29"])
	if "force_near_fade_evaluation" in minfo_data: 
		MInfo.AddForceNearFadeEvaluation(minfo_builder, minfo_data["force_near_fade_evaluation"])
	if "bool31" in minfo_data: 
		MInfo.AddBool31(minfo_builder, minfo_data["bool31"])
	if "use_mesh_aabb_for_fade" in minfo_data: 
		MInfo.AddUseMeshAabbForFade(minfo_builder, minfo_data["use_mesh_aabb_for_fade"])
	if "render_flags" in minfo_data:
		MInfo.AddRenderFlags(minfo_builder, minfo_data["render_flags"])
	if "camera_near_fade_aabb_radius" in minfo_data: 
		MInfo.AddCameraNearFadeAabbRadius(minfo_builder, minfo_data["camera_near_fade_aabb_radius"])
	
	# Finish Table
	minfo_table = MInfo.ModelInfoEnd(minfo_builder)
	minfo_builder.Finish(minfo_table)

	#12. Save Output to file. Done! Keep It Clean! (0 0)b
	save_minfo_file(minfo_builder, filepath)