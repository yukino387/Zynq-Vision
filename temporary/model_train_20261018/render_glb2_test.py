import numpy as np
from pathlib import Path
import trimesh, pyrender
from PIL import Image
GLB = Path(r"C:\Users\YUKINO\Downloads\335ba5ca50a5917448e171289046b19c.glb")
OUT = Path(r"C:/00_workplace/fpga/cnn_accelerator/temporary/model_train_20261018")
def look_at(eye, target, up=(0,0,1)):
    eye=np.asarray(eye,float);target=np.asarray(target,float);up=np.asarray(up,float)
    z=eye-target;z/=np.linalg.norm(z);x=np.cross(up,z);x/=np.linalg.norm(x);y=np.cross(z,x)
    M=np.eye(4);M[:3,0]=x;M[:3,1]=y;M[:3,2]=z;M[:3,3]=eye;return M
mesh=list(trimesh.load(GLB, force="scene").geometry.values())[0]
center=mesh.bounds.mean(0); size=float(np.linalg.norm(mesh.extents))
print("mesh",mesh.vertices.shape,mesh.faces.shape,"bounds",np.round(mesh.bounds,3),"size",round(size,3))
for tag,eye in [("front",center+np.array([0,-1.8*size,0])),("back",center+np.array([0,1.8*size,0])),("left",center+np.array([-1.8*size,0,0])),("right",center+np.array([1.8*size,0,0]))]:
    sc=pyrender.Scene(bg_color=[45,45,45,255]); sc.add(pyrender.Mesh.from_trimesh(mesh,smooth=False))
    cam=pyrender.PerspectiveCamera(yfov=np.deg2rad(40),aspectRatio=1.0); sc.add(cam,pose=look_at(eye,center))
    sc.add(pyrender.DirectionalLight(color=np.ones(3),intensity=4.0),pose=look_at(eye+np.array([0.5,0.5,1.0])*size,center))
    r=pyrender.OffscreenRenderer(416,416); c,_=r.render(sc); r.delete(); Image.fromarray(c).save(OUT/f"glb2_{tag}.png")
print("done")
