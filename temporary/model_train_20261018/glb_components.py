import numpy as np
from pathlib import Path
import trimesh, scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
GLB = Path(r"C:\Users\YUKINO\Downloads\a2f2e182611c7076e5d5b6742e03b9ef.glb")
mesh = list(trimesh.load(GLB, force="scene").geometry.values())[0]
V, F = mesh.vertices, mesh.faces
e = np.concatenate([F[:, [0,1]], F[:, [1,2]], F[:, [2,0]]], 0)
e = np.sort(e, axis=1); e = np.unique(e, axis=0)
print("edges", e.shape)
g = sp.coo_matrix((np.ones(len(e), np.int8), (e[:,0], e[:,1])), shape=(len(V), len(V)))
n, lab = connected_components(g, directed=False)
print("components", n)
face_lab = lab[F[:,0]]
for c in range(n):
    idx = np.where(face_lab == c)[0]
    if len(idx) < 100: continue
    b = V[np.unique(F[idx])].min(0), V[np.unique(F[idx])].max(0)
    print("comp", c, "faces", len(idx), "verts", len(np.unique(F[idx])), "bbox", np.round(b[0],3), np.round(b[1],3))
np.save(Path(r"C:/00_workplace/fpga/cnn_accelerator/temporary/model_train_20261018/glb_face_labels.npy"), face_lab)
