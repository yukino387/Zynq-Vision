import numpy as np
from pathlib import Path
import trimesh
GLB = Path(r"C:\Users\YUKINO\Downloads\a2f2e182611c7076e5d5b6742e03b9ef.glb")
scene = trimesh.load(GLB, force="scene")
mesh = list(scene.geometry.values())[0]
print("mesh", mesh.vertices.shape, mesh.faces.shape)
parts = mesh.split(only_watertight=False)
print("components", len(parts))
parts = sorted(parts, key=lambda m: len(m.faces), reverse=True)
for i, p in enumerate(parts[:10]):
    print(i, "faces", len(p.faces), "bounds", np.round(p.bounds,3), "extents", np.round(p.extents,3))
# face normals of the largest (carton) and UV bbox by dominant normal
carton = parts[0]
fn = carton.face_normals; uv = carton.visual.uv
print("carton uv", uv.shape, "uv range", np.round(uv.min(0),3), np.round(uv.max(0),3))
# group faces by dominant normal axis/sign, print UV bbox and area
for axis in range(3):
    for sign in (-1, 1):
        mask = (np.abs(fn[:, axis]) > 0.8) & (np.sign(fn[:, axis]) == sign)
        if mask.sum() == 0: continue
        fidx = np.where(mask)[0]
        fu = uv[carton.faces[fidx]].reshape(-1, 2)
        print("normal", "xyz"[axis], sign, "faces", len(fidx), "uv bbox", np.round(fu.min(0),3), np.round(fu.max(0),3))
