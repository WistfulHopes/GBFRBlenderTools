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

from .Entities.ModelInfo import ModelInfo
import bpy
import bmesh
import mathutils
import struct
import os
import json

def utils_set_mode(mode):
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=mode, toggle=False)
        
   
def parse_mesh_info(filepath):
    buf = open(filepath, 'rb').read()
    buf = bytearray(buf)    
    model_info = ModelInfo.GetRootAs(buf, 0)
    
    return model_info   


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
            vert_buffer.append(struct.pack('<e', loop.bitangent_sign))
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

    mesh_info = parse_mesh_info(filepath)

    DeformJointsTable = []
    for n in range(mesh_info.BonesToWeightIndicesLength()):
        DeformJointsTable.append(mesh_info.BonesToWeightIndices(n))

    weight_id_table = []
    weight_table = []

    vgroup_names = {vgroup.index: vgroup.name for vgroup in obj.vertex_groups}

    if armature is not None:
        for v in mesh.vertices:
            for n in range(4):
                if n >= len(v.groups):
                    weight_id_table.append(struct.pack('<H', 0))
                    weight_table.append(struct.pack('<H', 0))
                    continue
                
                group_name = obj.vertex_groups[v.groups[n].group].name     

                deform_id = -1
                
                for i, bone in enumerate(armature.data.bones):
                    if group_name == bone.name:
                        deform_id = i
                        break
                
                weight_id_table.append(struct.pack('<H', DeformJointsTable.index(i)))
                weight_table.append(struct.pack('<H', int(v.groups[n].weight * 65535)))
                
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
    
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
    
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
        chunk_table.append({'Offset': chunk_start, 'Count': chunk_end - chunk_start, 'SubMeshID': sub_mesh_count, 'MaterialID': int(chunk[1]), 'Unk1': 0, 'Unk2': 0})
    
    jobj = {'MeshBuffers': section_length_table, 'Chunks': chunk_table, 'VertCount': vert_count, 'PolyCountX3': face_count, 'BufferTypes': 11, 'SubMeshes': sub_mesh_table}
    
    j.write(json.dumps(jobj, indent=2))
    j.close()
    
    return {'FINISHED'}


# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator


class ExportSomeData(Operator, ImportHelper):
    """Importer for Granblue Fantasy Relink meshes"""
    bl_idname = "gbfr.export_mesh"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import"

    # ImportHelper mix-in class uses this.
    filename_ext = ".minfo"

    filter_glob: StringProperty(
        default="*.minfo",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return write_some_data(context, self.filepath)


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(ExportSomeData.bl_idname, text="Granblue Fantasy Relink .minfo")


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
