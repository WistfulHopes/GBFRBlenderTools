# automatically generated by the FlatBuffers compiler, do not modify

# namespace: Entities

from .flatbuffers import *
from .flatbuffers.compat import import_numpy
np = import_numpy()

class BoneInfo(object):
    __slots__ = ['_tab']

    @classmethod
    def SizeOf(cls):
        return 8

    # BoneInfo
    def Init(self, buf, pos):
        self._tab = table.Table(buf, pos)

    # BoneInfo
    def BoneId(self): return self._tab.Get(number_types.Uint16Flags, self._tab.Pos + number_types.UOffsetTFlags.py_type(0))
    # BoneInfo
    def Unk(self): return self._tab.Get(number_types.Uint32Flags, self._tab.Pos + number_types.UOffsetTFlags.py_type(4))

def CreateBoneInfo(builder, boneId, unk):
    builder.Prep(4, 8)
    builder.PrependUint32(unk)
    builder.Pad(2)
    builder.PrependUint16(boneId)
    return builder.Offset()
