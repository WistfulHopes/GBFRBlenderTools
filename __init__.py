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

from .Entities.ModelInfo import ModelInfo
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


   
def parse_mesh_info(filepath):
    buf = open(filepath, 'rb').read()
    buf = bytearray(buf)    
    model_info = ModelInfo.GetRootAs(buf, 0)
    
    return model_info   

    
def read_some_data(context, filepath):    
    CurCollection = bpy.data.collections.new("Mesh Collection")
    bpy.context.scene.collection.children.link(CurCollection)
    
    mesh_info = parse_mesh_info(filepath)
    armature = parse_skeleton(filepath, CurCollection)
    
    DeformJointsTable = []
    for n in range(mesh_info.BonesToWeightIndicesLength()):
        DeformJointsTable.append(mesh_info.BonesToWeightIndices(n))
    
    LOD = mesh_info.Lodinfos(0)
    
    f = open(os.path.splitext(filepath)[0] + ".mmesh", 'rb')
    
    vert_count = LOD.VertCount()
    face_count = LOD.PolyCountX3() // 3
    
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
        if LOD.BufferTypes() & 2:
            f.seek(LOD.MeshBuffers(1).Offset())
            for n in range(vert_count):
                i0 = int.from_bytes(f.read(2),byteorder='little')
                i1 = int.from_bytes(f.read(2),byteorder='little')
                i2 = int.from_bytes(f.read(2),byteorder='little')
                i3 = int.from_bytes(f.read(2),byteorder='little')
                
                weight_indices = [DeformJointsTable[i0],DeformJointsTable[i1],DeformJointsTable[i2],DeformJointsTable[i3]]
                WeightIndicesTable.append(weight_indices)

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
                
    for i in range(mesh_info.SubMeshesLength()):
        sub_mesh = mesh_info.SubMeshes(i)
        for j in range(LOD.ChunksLength()):
            chunk = LOD.Chunks(j)
            if chunk.SubMesh() != i:
                continue
            mat = bpy.data.materials.new(name=sub_mesh.Name().decode())
            obj.data.materials.append(mat)

            for p in range(chunk.Offset() // 3, chunk.Offset() // 3 + chunk.Count() // 3):
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

