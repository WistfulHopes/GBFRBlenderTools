# automatically generated by the FlatBuffers compiler, do not modify

# namespace: Entities

from .flatbuffers import *
from .flatbuffers.compat import import_numpy
np = import_numpy()

class LODChunk(object):
    __slots__ = ['_tab']

    @classmethod
    def SizeOf(cls):
        return 12

    # LODChunk
    def Init(self, buf, pos):
        self._tab = table.Table(buf, pos)

    # LODChunk
    def Offset(self): return self._tab.Get(number_types.Int32Flags, self._tab.Pos + number_types.UOffsetTFlags.py_type(0))
    # LODChunk
    def Count(self): return self._tab.Get(number_types.Int32Flags, self._tab.Pos + number_types.UOffsetTFlags.py_type(4))
    # LODChunk
    def SubMesh(self): return self._tab.Get(number_types.Int8Flags, self._tab.Pos + number_types.UOffsetTFlags.py_type(8))
    # LODChunk
    def Material(self): return self._tab.Get(number_types.Int8Flags, self._tab.Pos + number_types.UOffsetTFlags.py_type(9))
    # LODChunk
    def Unk1(self): return self._tab.Get(number_types.Int8Flags, self._tab.Pos + number_types.UOffsetTFlags.py_type(10))
    # LODChunk
    def Unk2(self): return self._tab.Get(number_types.Int8Flags, self._tab.Pos + number_types.UOffsetTFlags.py_type(11))

def CreateLODChunk(builder, offset, count, subMesh, material, unk1, unk2):
    builder.Prep(4, 12)
    builder.PrependInt8(unk2)
    builder.PrependInt8(unk1)
    builder.PrependInt8(material)
    builder.PrependInt8(subMesh)
    builder.PrependInt32(count)
    builder.PrependInt32(offset)
    return builder.Offset()
