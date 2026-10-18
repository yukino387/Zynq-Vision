import numpy as np
from pathlib import Path
import trimesh, pyrender
from PIL import Image, ImageDraw, ImageFilter
GLB = Path(r"C:\Users\YUKINO\Downloads\a2f2e182611c7076e5d5b6742e03b9ef.glb")
OUT = Path(r"C:/00_workplace/fpga/cnn_accelerator/temporary/model_train_20261018")
def look_at(eye, target, up=(0,0,1)):
    eye=np.asarray(eye,float); target=np.asarray(target,float); up=np.asarray(up,float)
    z=eye-target; z/=np.linalg.norm(z); x=np.cross(up,z); x/=np.linalg.norm(x); y=np.cross(z,x)
    M=np.eye(4); M[:3,0]=x; M[:3,1]=y; M[:3,2]=z; M[:3,3]=eye; return M
mesh = list(trimesh.load(GLB, force="scene").geometry.values())[0]
center = mesh.bounds.mean(0); size=float(np.linalg.norm(mesh.extents))
eye = center + np.array([0.15*size, -1.7*size, 0.55*size]); target = center
cam = pyrender.PerspectiveCamera(yfov=np.deg2rad(40), aspectRatio=1.0); cam_pose = look_at(eye,target)
scene = pyrender.Scene(bg_color=[0,0,0,0])
scene.add(pyrender.Mesh.from_trimesh(mesh, smooth=False))
scene.add(cam, pose=cam_pose)
scene.add(pyrender.DirectionalLight(color=np.ones(3), intensity=4.0), pose=look_at(eye+np.array([0.5,0.4,1.0])*size,target))
r = pyrender.OffscreenRenderer(416,416); color, depth = r.render(scene, flags=pyrender.RenderFlags.RGBA); r.delete()
rgba = Image.fromarray(color,"RGBA")
table = Image.open(OUT/"table_bg.png").convert("RGB").resize((416,416)); table = Image.blend(table, Image.new("RGB",(416,416),(190,160,125)),0.06)
# project bbox corners for box + shadow
proj = cam.get_projection_matrix(1.0); view = np.linalg.inv(cam_pose)
pts=[]
for x in (mesh.bounds[0][0],mesh.bounds[1][0]):
    for y in (mesh.bounds[0][1],mesh.bounds[1][1]):
        for z in (mesh.bounds[0][2],mesh.bounds[1][2]):
            p=np.array([x,y,z,1.0]); q=proj@view@p; q=q[:3]/q[3]
            pts.append(((q[0]+1)/2*416,(1-q[1])/2*416))
xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
print("bbox px",round(min(xs)),round(min(ys)),round(max(xs)),round(max(ys)))
# shadow ellipse at bottom
sh=Image.new("RGBA",(416,416),(0,0,0,0)); d=ImageDraw.Draw(sh)
bh=max(ys); bw=max(xs)-min(xs)
d.ellipse([min(xs)+0.1*bw, bh-0.06*bw, max(xs)-0.1*bw, bh+0.06*bw], fill=(0,0,0,110))
sh=sh.filter(ImageFilter.GaussianBlur(8))
table=Image.alpha_composite(table.convert("RGBA"),sh).convert("RGB")
table.paste(rgba,(0,0),rgba)
table.save(OUT/"glb_table_test.png"); print("saved")
