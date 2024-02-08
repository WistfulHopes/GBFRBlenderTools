bl_info = {
    "name": "Granblue Fantasy Relink Mesh Importer",
    "author": "WistfulHopes",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "File > Import-Export",
    "description": "A script to import meshes from Granblue Fantasy Relink",
    "warning": "",
    "category": "Import-Export",
}

import bpy
import bmesh
import mathutils
import struct
import os

def utils_set_mode(mode):
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=mode, toggle=False)
        
        
def parse_skeleton(filepath, CurCollection):
    if os.path.isfile(os.path.splitext(filepath)[0] + ".skeleton"):
        f = open(os.path.splitext(filepath)[0] + ".skeleton", 'rb')
        
        armature_data = bpy.data.armatures.new("Armature")
        armature_obj = bpy.data.objects.new("Armature", armature_data)
        CurCollection.objects.link(armature_obj)
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            
        f.seek(0x20)
        
        joint_count = int.from_bytes(f.read(4),byteorder='little')
        joint_offsets = [f.tell() + int.from_bytes(f.read(4),byteorder='little') for _ in range(joint_count)]
        
        SkelTable = []
        for i, offset in enumerate(joint_offsets):
            f.seek(offset + 4)
            scale = struct.unpack('<fff', f.read(4*3))
            quat = struct.unpack('<ffff', f.read(4*4))
            quat = mathutils.Quaternion((quat[3],quat[0],quat[1],quat[2]))
            pos = struct.unpack('<fff', f.read(4*3))
            _, parent_index, _ = f.read(4), int.from_bytes(f.read(2), byteorder='little'), f.read(2)
            
            SkelTable.append({"Pos":pos,"Rot":quat})
                
            length = int.from_bytes(f.read(4),byteorder='little')
            name = f.read(length).decode('ascii')
            
            edit_bone = armature_obj.data.edit_bones.new(name)
            edit_bone.use_connect = False
            edit_bone.use_inherit_rotation = True
            edit_bone.inherit_scale = 'FULL'
            edit_bone.use_local_location = True
            edit_bone.head = (0,0,0)
            edit_bone.tail = (0,0.05,0)
            
            edit_bone["scale"] = scale
            
            if parent_index != 65535:
                edit_bone.parent = armature_obj.data.edit_bones[parent_index]

        utils_set_mode('POSE')
        for x in range(joint_count):
            pbone = armature_obj.pose.bones[x]
            pbone.rotation_mode = 'QUATERNION'
            pbone.rotation_quaternion = SkelTable[x]["Rot"]
            pbone.location = SkelTable[x]["Pos"]
        bpy.ops.pose.armature_apply()
        utils_set_mode('OBJECT')

        bpy.ops.object.mode_set(mode='OBJECT')
        f.close()
        del f
        return armature_obj


class MeshInfo:
    deform_joints = []
    face_count = 0
    vertex_count = 0
    materials = []
    weight_indices_offset = 0
    weight_offset = 0
    face_offset = 0

   
def parse_mesh_info(filepath):
    is_skeletal = os.path.isfile(os.path.splitext(filepath)[0] + ".skeleton")
    f = open(filepath, 'rb')
    
    mesh_info = MeshInfo()
    
    init_offset = int.from_bytes(f.read(4),byteorder='little')
    if init_offset == 0x40:
        f.seek(0x16)
    elif init_offset == 0x48:
        f.seek(0x18)
    elif is_skeletal:
        f.seek(0x1A)
    else:
        f.seek(0x18)
    deform_field_offset = int.from_bytes(f.read(2),byteorder='little')
    if init_offset == 0x40:
        f.seek(0xC)
    elif init_offset == 0x48:
        f.seek(0xE)
    elif is_skeletal:
        f.seek(0x10)
    else:
        f.seek(0xE)
    lod_field_offset = int.from_bytes(f.read(2),byteorder='little')
    
    deform_offset_add = 0
    if init_offset == 0x48:
        deform_offset_add = 4
    f.seek(init_offset + deform_field_offset + deform_offset_add)
    deform_offset = int.from_bytes(f.read(4),byteorder='little')
    f.seek(deform_offset - 4, 1)
    
    deform_joint_count = int.from_bytes(f.read(4),byteorder='little')
    deform_joints = []
    
    for n in range(deform_joint_count):
        deform_joints.append(int.from_bytes(f.read(2),byteorder='little'))
    
    mesh_info.deform_joints = deform_joints

    f.seek(init_offset + lod_field_offset)
    lod_offset = int.from_bytes(f.read(4),byteorder='little')
    lod_offset_take = 4
    if init_offset == 0x48:
        lod_offset_take = 0
    f.seek(lod_offset - lod_offset_take, 1)
    
    lod_count = int.from_bytes(f.read(4),byteorder='little')
    
    f.seek(int.from_bytes(f.read(4),byteorder='little'), 1)
    
    face_count = 0
    vertex_count = 0
    material_count = []
    weight_indices_offset = 0
    weight_offset = 0
    face_offset = 0
    
    f.seek(4, 1)
    face_count = int.from_bytes(f.read(4),byteorder='little') // 3
    vertex_count = int.from_bytes(f.read(4),byteorder='little')

    f.seek(8, 1)
    material_count = int.from_bytes(f.read(4),byteorder='little')
    materials = []
    
    for n in range(material_count):
        start = joint_count = int.from_bytes(f.read(4),byteorder='little')
        end = joint_count = int.from_bytes(f.read(4),byteorder='little') + start
        index = joint_count = int.from_bytes(f.read(4),byteorder='little')
        materials.append((start // 3, end // 3))
    
    section_count = int.from_bytes(f.read(4),byteorder='little')
    f.seek(8, 1)
    if section_count == 3:
        f.seek(24, 1)
        face_offset = int.from_bytes(f.read(8),byteorder='little')
        f.seek(8, 1)
    elif section_count == 4:
        f.seek(8, 1)
        weight_indices_offset = int.from_bytes(f.read(8),byteorder='little')
        f.seek(8, 1)
        weight_offset = int.from_bytes(f.read(8),byteorder='little')
        f.seek(8, 1)
        face_offset = int.from_bytes(f.read(8),byteorder='little')
        f.seek(8, 1)
    elif section_count == 6:
        f.seek(8, 1)
        weight_indices_offset = int.from_bytes(f.read(8),byteorder='little')
        f.seek(24, 1)
        weight_offset = int.from_bytes(f.read(8),byteorder='little')
        f.seek(24, 1)
        face_offset = int.from_bytes(f.read(8),byteorder='little')
        f.seek(8, 1)
    else:
        raise Exception("Unhandled mesh section count " + str(section_count) + " at " + str(f.tell()))
        
    print(face_offset)
    print(face_count)
    
    mesh_info.face_count = face_count
    mesh_info.vertex_count = vertex_count
    mesh_info.materials = materials
    mesh_info.weight_indices_offset = weight_indices_offset
    mesh_info.weight_offset = weight_offset
    mesh_info.face_offset = face_offset
    
    f.close()
    del f
    
    return mesh_info

def get_relative_mmesh_path(filepath):
    filename = os.path.basename(filepath)
    filename = os.path.splitext(filename)[0]
    mesh_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(filepath))))
    additional = ("model_streaming", "lod0", filename + ".mmesh")
    return os.path.join(mesh_path, *additional)
    
def read_some_data(context, filepath):    
    CurCollection = bpy.data.collections.new("Mesh Collection")
    bpy.context.scene.collection.children.link(CurCollection)
    
    mesh_info = parse_mesh_info(filepath)
    armature = parse_skeleton(filepath, CurCollection)
    
    DeformJointsTable = mesh_info.deform_joints
    Materials = mesh_info.materials
    
    relative_mmesh_path = get_relative_mmesh_path(filepath)
    if (os.path.exists(relative_mmesh_path)):
        f = open(relative_mmesh_path, 'rb')
    else:
        f = open(os.path.splitext(filepath)[0] + ".mmesh", 'rb')
    
    vert_count = mesh_info.vertex_count
    face_count = mesh_info.face_count
    
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
    
    if armature is not None:
        f.seek(mesh_info.weight_indices_offset)
        for n in range(vert_count):
            i0 = int.from_bytes(f.read(2),byteorder='little')
            i1 = int.from_bytes(f.read(2),byteorder='little')
            i2 = int.from_bytes(f.read(2),byteorder='little')
            i3 = int.from_bytes(f.read(2),byteorder='little')
            
            weight_indices = [DeformJointsTable[i0],DeformJointsTable[i1],DeformJointsTable[i2],DeformJointsTable[i3]]
            WeightIndicesTable.append(weight_indices)
    
        f.seek(mesh_info.weight_offset)
        for n in range(vert_count):
            WeightTable.append(struct.unpack('<HHHH', f.read(2*4)))
    
    f.seek(mesh_info.face_offset)
    for n in range(face_count):
        FaceTable.append(struct.unpack('<III', f.read(4*3)))
    f.close()
    del f
    
    mesh1 = bpy.data.meshes.new("Mesh")
    mesh1.use_auto_smooth = True
    obj = bpy.data.objects.new("Obj",mesh1)
    CurCollection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    mesh = bpy.context.object.data
    bm = bmesh.new()
    for v in VertTable:
        bm.verts.new((v[0],v[1],v[2]))
    list = [v for v in bm.verts]
    for f in FaceTable:
        bm.faces.new((list[f[0]],list[f[1]],list[f[2]]))
    bm.to_mesh(mesh)

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

    for n, m in enumerate(Materials):
        mat = bpy.data.materials.new(name="Material")
        obj.data.materials.append(mat)
        for p in range(m[0], m[1]):
            obj.data.polygons[p].material_index = n
        
    if armature is not None:
        ArmMod = obj.modifiers.new("Armature","ARMATURE")
        ArmMod.object = armature
        obj.parent = armature
        armature.rotation_euler = (1.5707963705062866,0,0)
    
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

    return {'FINISHED'}


# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator


class ImportSomeData(Operator, ImportHelper):
    """Importer for Granblue Fantasy Relink meshes"""
    bl_idname = "gbfr.mesh"  # important since its how bpy.ops.import_test.some_data is constructed
    bl_label = "Import"

    # ImportHelper mix-in class uses this.
    filename_ext = ".minfo"

    filter_glob: StringProperty(
        default="*.minfo",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return read_some_data(context, self.filepath)


# Only needed if you want to add into a dynamic menu.
def menu_func_import(self, context):
    self.layout.operator(ImportSomeData.bl_idname, text="Granblue Fantasy Relink .minfo")


# Register and add to the "file selector" menu (required to use F3 search "Text Import Operator" for quick access).
def register():
    bpy.utils.register_class(ImportSomeData)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportSomeData)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.gbfr.mesh('INVOKE_DEFAULT')

