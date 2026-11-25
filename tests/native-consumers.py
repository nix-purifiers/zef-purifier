import ctypes
import json
from pathlib import Path
import subprocess
import sys

projection, expected = Path(sys.argv[1]), int(sys.argv[2])
sys.path.insert(0, str(projection))
import purifier_native

library = json.loads((projection / "catalog.json").read_text())["libraries"]["answer"]
handle = purifier_native.load("answer")
handle.native_answer.argtypes = [ctypes.c_uint32]
handle.native_answer.restype = ctypes.c_uint32
for value in [*range(100), 0xffffffff]:
    assert handle.native_answer(value) == (value + expected) % (1 << 32)
program = '''from cffi import FFI
f=FFI(); f.cdef("uint32_t native_answer(uint32_t);")
lib=f.dlopen(LIBRARY)
for value in [*range(100),0xffffffff]: assert lib.native_answer(value)==(value+EXPECTED) % (1<<32)
print("Actual Zef resource CFFI100/overflow PASS")
'''
subprocess.run([sys.executable, "-c", "LIBRARY=" + repr(library) + "\nEXPECTED=" + str(expected) + "\n" + program], check=True)
print("Actual Zef Python projection ctypes100/overflow PASS")
