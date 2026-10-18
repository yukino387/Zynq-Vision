import numpy as np
from pathlib import Path
import trimesh, pyrender
from PIL import Image, ImageDraw, ImageFilter
OLD = Path(r"C:\Users\YUKINO\Downloads\a2f2e182611c7076e5d5b6742e03b9ef.glb")
NEW = Path(r"C:\Users\YUKINO\Downloads\335ba5ca50a5917448e171289046b19c.glb")
OUT = Path(r"C:/00_workplace/fpga/cnn_accelerator/temporary/model_train_20261018")
def look_at(eye,target,up=(0,0,1)):
    eye=np.asarray(eye,float);target=np.asarray(target,float);up=np.asarray(up,float)
    z=eye-target;z/=np.linalg.norm(z);x=np.cross(up,z);x/=np.linalg.norm(x);y=np.cross(z,x)
    M=np.eye(4);M[:3,0]=x;M[:3,1]=y;M[:3,2]=z;M[:3,3]=eye;return M
def render(mesh, az_deg, tag):
    center=mesh.bounds.mean(0); size=float(np.linalg.norm(mesh.extents)); rad=np.deg2rad(az_deg)
    eye=center+np.array([np.sin(rad),-np.cos(rad),0])*1.7*size+np.array([0,0,0.55*size])
    sc=pyrender.Scene(bg_color=[0,0,0,0]); sc.add(pyrender.Mesh.from_trimesh(mesh,smooth=False))
    cam=pyrender.PerspectiveCamera(yfov=np.deg2rad(40),aspectRatio=1.0); pose=look_at(eye,center); sc.add(cam,pose=pose)
    sc.add(pyrender.DirectionalLight(color=np.ones(3),intensity=4.0),pose=look_at(eye+np.array([0.5,0.4,1.0])*size,center))
    r=pyrender.OffscreenRenderer(416,416); color,_=r.render(sc,flags=pyrender.RenderFlags.RGBA); r.delete()
    rgba=Image.fromarray(color,'RGBA'); table=Image.open(OUT/'table_bg.png').convert('RGB').resize((416,416))
    table.paste(rgba,(0,0),rgba); table.save(OUT/f'glb_pair_{tag}.png'); print(tag,'saved')
old=list(trimesh.load(OLD,force='scene').geometry.values())[0]
new=list(trimesh.load(NEW,force='scene').geometry.values())[0]
render(old, 90, 'old_straw_side')
render(new, 0, 'new_nostraw_front')
render(old, 0, 'old_straw_front')
render(new, 90, 'new_nostraw_side')
