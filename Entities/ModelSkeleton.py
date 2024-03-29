# automatically generated by the FlatBuffers compiler, do not modify

# namespace: Entities

from .flatbuffers import *
from .flatbuffers.compat import import_numpy
np = import_numpy()

class ModelSkeleton(object):
    __slots__ = ['_tab']

    @classmethod
    def GetRootAs(cls, buf, offset=0):
        n = encode.Get(packer.uoffset, buf, offset)
        x = ModelSkeleton()
        x.Init(buf, n + offset)
        # print(f"n = {n}, offset = {offset}")
        return x

    @classmethod
    def GetRootAsModelSkeleton(cls, buf, offset=0):
        """This method is deprecated. Please switch to GetRootAs."""
        return cls.GetRootAs(buf, offset)
    # ModelSkeleton
    def Init(self, buf, pos):
        self._tab = table.Table(buf, pos)

    # ModelSkeleton
    def Magic(self):
        o = number_types.UOffsetTFlags.py_type(self._tab.Offset(4))
        if o != 0:
            return self._tab.Get(number_types.Uint32Flags, o + self._tab.Pos)
        return 0

    # ModelSkeleton
    def Body(self, j):
        o = number_types.UOffsetTFlags.py_type(self._tab.Offset(6))
        if o != 0:
            x = self._tab.Vector(o)
            x += number_types.UOffsetTFlags.py_type(j) * 4
            x = self._tab.Indirect(x)
            from .Bone import Bone
            obj = Bone()
            obj.Init(self._tab.Bytes, x)
            return obj
        return None

    # ModelSkeleton
    # Returns the number of bones in the skeleton
    def BodyLength(self):
        o = number_types.UOffsetTFlags.py_type(self._tab.Offset(6)) #Get body length offset 6 from self._tab
        # print(f"BodyLength offset = {o}")
        if o != 0:
            # print(f"BodyLength = {self._tab.VectorLen(o)}")
            return self._tab.VectorLen(o) # Return vector length retrieved from offset
        return 0

    # ModelSkeleton
    def BodyIsNone(self):
        o = number_types.UOffsetTFlags.py_type(self._tab.Offset(6))
        return o == 0

def ModelSkeletonStart(builder):
    builder.StartObject(2)

def Start(builder):
    ModelSkeletonStart(builder)

def ModelSkeletonAddMagic(builder, magic):
    builder.PrependUint32Slot(0, magic, 0)

def AddMagic(builder, magic):
    ModelSkeletonAddMagic(builder, magic)

def ModelSkeletonAddBody(builder, body):
    builder.PrependUOffsetTRelativeSlot(1, number_types.UOffsetTFlags.py_type(body), 0)

def AddBody(builder, body):
    ModelSkeletonAddBody(builder, body)

def ModelSkeletonStartBodyVector(builder, numElems):
    return builder.StartVector(4, numElems, 4)

def StartBodyVector(builder, numElems: int) -> int:
    return ModelSkeletonStartBodyVector(builder, numElems)

def ModelSkeletonEnd(builder):
    return builder.EndObject()

def End(builder):
    return ModelSkeletonEnd(builder)
