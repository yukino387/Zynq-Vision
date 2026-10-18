import numpy as np
from pathlib import Path
import trimesh
GLB = Path(r"C:\Users\YUKINO\Downloads\a2f2e182611c7076e5d5b6742e03b9ef.glb")
scene = trimesh.load(GLB, force="scene")
mesh = list(scene.geometry.values())[0]
v = mesh.vertices; f = mesh.faces; uv = mesh.visual.uv
print("verts", v.shape, "faces", f.shape, "uv", uv.shape)
a = v[f[:,0]]; b = v[f[:,1]]; c = v[f[:,2]]
fn = np.cross(b-a, c-a); n = np.linalg.norm(fn, axis=1); ok = n>1e-12; fn[ok] /= n[ok,None]
area = 0.5*n
print("total area", area.sum())
for axis in range(3):
    for sign in (-1,1):
        mask = (np.abs(fn[:,axis]) > 0.85) & (np.sign(fn[:,axis]) == sign)
        if mask.sum()==0: continue
        fu = uv[f[mask]].reshape(-1,2)
        print("normal", "xyz"[axis], sign, "faces", int(mask.sum()), "area", round(float(area[mask].sum()),4),
              "uv", np.round(fu.min(0),3), np.round(fu.max(0),3))
# straw-like faces: remaining area with normals not axis aligned, and their uv bbox
axis_mask = np.zeros(len(f), bool)
for axis in range(3):
    axis_mask |= (np.abs(fn[:,axis]) > 0.85)
print("non-axis faces", int((~axis_mask).sum()), "area", round(float(area[~axis_mask].sum()),4))
fu = uv[f[~axis_mask]].reshape(-1,2)
print("non-axis uv", np.round(fu.min(0),3), np.round(fu.max(0),3))
