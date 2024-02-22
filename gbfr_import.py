import bpy
import bmesh
import mathutils
import struct
import os
from .Entities.ModelInfo import ModelInfo
from .Entities.ModelSkeleton import ModelSkeleton
from .utils import raise_noob_readable_exception

def utils_set_mode(mode):
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=mode, toggle=False)
        
        
def parse_skeleton(filepath, CurCollection):
    if os.path.isfile(os.path.splitext(filepath)[0] + ".skeleton"):
        buf = open(os.path.splitext(filepath)[0] + ".skeleton", 'rb').read()
        buf = bytearray(buf)    
        skeleton = ModelSkeleton.GetRootAs(buf, 0)
        
        armature_data = bpy.data.armatures.new("Armature")
        armature_obj = bpy.data.objects.new("Armature", armature_data)
        CurCollection.objects.link(armature_obj)
        bpy.context.view_layer.objects.active = armature_obj
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            
        SkelTable = []
        for n in range(skeleton.BodyLength()):
            bone = skeleton.Body(n)
            pos = (bone.Position().X(), bone.Position().Y(), bone.Position().Z())
            quat = (bone.Quat().W(), bone.Quat().X(), bone.Quat().Y(), bone.Quat().Z())
            parent_index = bone.ParentId()
            
            SkelTable.append({"Pos":pos,"Rot":quat})
            
            name = bone.Name().decode('ascii')
            
            edit_bone = armature_obj.data.edit_bones.new(name)
            edit_bone.use_connect = False
            edit_bone.use_inherit_rotation = True
            edit_bone.inherit_scale = 'FULL'
            edit_bone.use_local_location = True
            edit_bone.head = (0,0,0)
            edit_bone.tail = (0,0.05,0)
            
            if parent_index != 65535:
                edit_bone.parent = armature_obj.data.edit_bones[parent_index]

        utils_set_mode('POSE')
        for x in range(skeleton.BodyLength()):
            pbone = armature_obj.pose.bones[x]
            pbone.rotation_mode = 'QUATERNION'
            pbone.rotation_quaternion = SkelTable[x]["Rot"]
            pbone.location = SkelTable[x]["Pos"]
        bpy.ops.pose.armature_apply()
        utils_set_mode('OBJECT')

        bpy.ops.object.mode_set(mode='OBJECT')
        
        return armature_obj


   
def parse_mesh_info(filepath):
    buf = open(filepath, 'rb').read()
    buf = bytearray(buf)    
    model_info = ModelInfo.GetRootAs(buf, 0)
    
    return model_info   

    
def read_some_data(context, filepath, import_scale):    
    CurCollection = bpy.data.collections.new("Mesh Collection")
    bpy.context.scene.collection.children.link(CurCollection)

    model_name = os.path.splitext(os.path.basename(filepath))[0] # Get model name from filename
    
    mesh_info = parse_mesh_info(filepath)
    armature = parse_skeleton(filepath, CurCollection)
    armature.name = f"{model_name}" # Set armature name
    
    DeformJointsTable = []
    for n in range(mesh_info.BonesToWeightIndicesLength()):
        DeformJointsTable.append(mesh_info.BonesToWeightIndices(n))
    
    LOD = mesh_info.Lodinfos(0)
    
    try: 
        f = open(os.path.splitext(filepath)[0] + ".mmesh", 'rb')
    except Exception as err: 
        raise_noob_readable_exception("ERROR: Put the model's .mmesh file in the same folder as the .minfo.\n" 
            + "The model's original .mmesh can be found under: data/model_streaming/lod0/<modelID>.mmesh")
    
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
    obj = bpy.data.objects.new(f"{model_name}_Mesh",mesh1) # Create mesh object with model name
    CurCollection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    mesh = bpy.context.object.data
    bm = bmesh.new()
    for v in VertTable:
        bm.verts.new((v[0],v[1],v[2]))
    list = [v for v in bm.verts]
    for f in FaceTable:
        try:
            bm.faces.new((list[f[0]],list[f[1]],list[f[2]]))
        except:
            pass
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
    
    mat_counter = 0
    
    for i in range(mesh_info.SubMeshesLength()):
        sub_mesh = mesh_info.SubMeshes(i)
        for j in range(LOD.ChunksLength()):
            chunk = LOD.Chunks(j)
            if chunk.SubMesh() != i:
                continue
            mat = bpy.data.materials.new(name=sub_mesh.Name().decode() + "." + str(chunk.Material()))
            obj.data.materials.append(mat)

            for p in range(chunk.Offset() // 3, chunk.Offset() // 3 + chunk.Count() // 3):
                obj.data.polygons[p].material_index = mat_counter
            
            mat_counter += 1
        
    if armature is not None:
        ArmMod = obj.modifiers.new("Armature","ARMATURE")
        ArmMod.object = armature
        obj.parent = armature
        armature.rotation_euler = (1.5707963705062866,0,0) # Rotate 90 degrees from Y up to Z up
    
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT', toggle=False)
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

    armature.select_set(True) # Select the armature
    bpy.context.view_layer.objects.active = armature
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