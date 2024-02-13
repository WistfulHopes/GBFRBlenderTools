bl_info = {
    "name": "Granblue Fantasy Relink Mesh Exporter",
    "author": "WistfulHopes",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "File > Import-Export",
    "description": "A script to export meshes from Granblue Fantasy Relink",
    "warning": "",
    "category": "Import-Export",
}

import bpy
import bmesh
import mathutils
import struct
import os
import json
import random
from .Entities.flatbuffers.builder import Builder
from .Entities.ModelSkeleton import ModelSkeleton, StartBodyVector, ModelSkeletonStart, ModelSkeletonAddMagic, ModelSkeletonAddBody, ModelSkeletonEnd
from .Entities.Bone import Bone, BoneStart, BoneAddA1, BoneAddParentId, BoneAddName, BoneAddPosition, BoneAddQuat, BoneAddScale, BoneEnd
from .Entities.BoneInfo import BoneInfo, CreateBoneInfo
from .Entities.Vec3 import Vec3, CreateVec3
from .Entities.Quaternion import Quaternion, CreateQuaternion

def utils_set_mode(mode):
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=mode, toggle=False)
        
def fix_normals(obj):
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)


def write_some_data(context, filepath):
    f = open(os.path.splitext(filepath)[0] + ".mmesh", 'wb')
    
    obj = context.object
    mesh = obj.data
    
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.flip_normals()
    bpy.ops.mesh.sort_elements(type='MATERIAL')
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

    mesh.calc_tangents()
    
    vert_table = {}
    
    armature = obj.find_armature()
    
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
            
    keys = list(vert_table.keys())
    keys.sort()
    vert_table = {i: vert_table[i] for i in keys}
    
    for vert in vert_table.items():
        for elm in vert[1]:
            f.write(elm)
    
    section_length_table.append({'Offset': 0, 'Size': f.tell()})

    DeformJointsTable = []

    weight_id_table = []
    weight_table = []

    BoneTable = []

    if armature is not None:
        builder = Builder(0)

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
            
            a1 = None
            if n != 0:
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
        
        for vg in obj.vertex_groups:
          # limit total weights to 4
          bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
          # normalize all weights
          bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL')
          
        for v in mesh.vertices:
            if len(v.groups) > 4:
                fix_normals(obj)
                raise Exception("Your model has one or more vertices with more than 4 vertex weights. To export successfully, make sure to use Limit Total on your model.")
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
                            raise Exception("Your model has non-normalized weights. To export successfully, make sure to use Normalize All on your model.")
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
                        raise Exception("Your model has non-normalized weights. To export successfully, make sure to use Normalize All on your model.")
                    if total_weight != 65535:
                        index_max = max(range(4), key=weight_table[-4:].__getitem__)
                        weight_table[-4 + index_max] = struct.pack('<H', int(v.groups[index_max].weight * 65535) + (65535 - total_weight))
                
        weight_id_start = f.tell()
                
        for id in weight_id_table:
            f.write(id)

        section_length_table.append({'Offset': weight_id_start, 'Size': f.tell() - weight_id_start})
        
        weight_start = f.tell()
        
        for weight in weight_table:
            f.write(weight)
        
        section_length_table.append({'Offset': weight_start, 'Size': f.tell() - weight_start})        

    face_start = f.tell()

    for face in mesh.polygons:
        f.write(struct.pack('<I', face.vertices[0]))
        f.write(struct.pack('<I', face.vertices[1]))
        f.write(struct.pack('<I', face.vertices[2]))       
        face_count += 3

    section_length_table.append({'Offset': face_start, 'Size': f.tell() - face_start})     

    f.close()
    
    j = open(os.path.splitext(filepath)[0] + ".json", 'w')
    
    sub_mesh_table = []
    chunk_table = []

    sub_mesh_count = -1

    for i, material in enumerate(mesh.materials):
        chunk = material.name.split(".")
        if chunk[0] not in sub_mesh_table:
            sub_mesh_table.append(chunk[0])
            sub_mesh_count += 1
        
        chunk_start = -1
        chunk_end = -1
        for face in mesh.polygons:
            chunk_end = face.index * 3
            if chunk_start == -1 and face.material_index == i:
                chunk_start = face.index * 3
            elif chunk_start != -1 and face.material_index != i:
                break
        if i == len(mesh.materials) - 1:
            chunk_end += 3
        chunk_table.append({'Offset': chunk_start, 'Count': chunk_end - chunk_start, 'SubMeshID': sub_mesh_count, 'MaterialID': int(chunk[1]), 'Unk1': 0, 'Unk2': 0})
    
    jobj = {'MeshBuffers': section_length_table, 'Chunks': chunk_table, 'VertCount': vert_count, 'PolyCountX3': face_count, 'BufferTypes': 11, 'SubMeshes': sub_mesh_table, 'BonesToWeightIndices': DeformJointsTable}
    
    j.write(json.dumps(jobj, indent=2))
    j.close()
    del j
    
    fix_normals(obj)
    
    return {'FINISHED'}


# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator


class ExportSomeData(Operator, ImportHelper):
    """Importer for Granblue Fantasy Relink meshes"""
    bl_idname = "gbfr.export_mesh"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Export"

    # ImportHelper mix-in class uses this.
    filename_ext = ".mmesh"

    filter_glob: StringProperty(
        default="*.mmesh",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return write_some_data(context, self.filepath)


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(ExportSomeData.bl_idname, text="Granblue Fantasy Relink .mmesh")


# Register and add to the "file selector" menu (required to use F3 search "Text Export Operator" for quick access).
def register():
    bpy.utils.register_class(ExportSomeData)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportSomeData)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.gbfr.export_mmesh('INVOKE_DEFAULT')
