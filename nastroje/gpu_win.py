"""Windows: vypíše LUID grafické karty s největší vlastní pamětí ve tvaru „high,low“ pro --use-adapter-luid v Chromiu.

Headless Chromium jinak bere první adaptér, což je na počítači s integrovanou grafikou ta slabší.
LUID se mění po restartu, proto se zjišťuje při každém renderu (render.mjs).
"""
import ctypes as C
import uuid


class GUID(C.Structure):
    _fields_ = [('a', C.c_uint32), ('b', C.c_uint16), ('c', C.c_uint16), ('d', C.c_ubyte * 8)]


class DXGI_ADAPTER_DESC1(C.Structure):
    _fields_ = [('Description', C.c_wchar * 128), ('VendorId', C.c_uint), ('DeviceId', C.c_uint), ('SubSysId', C.c_uint),
                ('Revision', C.c_uint), ('DedicatedVideoMemory', C.c_size_t), ('DedicatedSystemMemory', C.c_size_t),
                ('SharedSystemMemory', C.c_size_t), ('LuidLow', C.c_uint32), ('LuidHigh', C.c_int32), ('Flags', C.c_uint)]


def method(obj, index, *argtypes):
    """metoda COM rozhraní podle pořadí ve vtable"""
    vtable = C.cast(C.cast(obj, C.POINTER(C.c_void_p))[0], C.POINTER(C.c_void_p))
    return C.WINFUNCTYPE(C.c_long, C.c_void_p, *argtypes)(vtable[index])


iid = GUID()
C.memmove(C.byref(iid), uuid.UUID('770aae78-f26f-4dba-a829-253c83d1b387').bytes_le, 16)  # IDXGIFactory1
factory = C.c_void_p()
C.windll.dxgi.CreateDXGIFactory1(C.byref(iid), C.byref(factory))
best, i = None, 0
while True:
    adapter = C.c_void_p()
    if method(factory, 12, C.c_uint, C.POINTER(C.c_void_p))(factory, i, C.byref(adapter)): break  # EnumAdapters1
    d = DXGI_ADAPTER_DESC1()
    method(adapter, 10, C.POINTER(DXGI_ADAPTER_DESC1))(adapter, C.byref(d))  # GetDesc1
    if not d.Flags & 2 and (best is None or d.DedicatedVideoMemory > best.DedicatedVideoMemory): best = d  # 2 = software
    i += 1
if best: print(f'{best.LuidHigh},{best.LuidLow}')
