import numpy as np
from pathlib import Path
import trimesh, pyrender
from trimesh.visual.texture import TextureVisuals
from PIL import Image, ImageDraw, ImageFilter
GLB = Path(r"C:\Users\YUKINO\Downloads\a2f2e182611c7076e5d5b6742e03b9ef.glb")
D = Path(r"C:\Users\YUKINO\Downloads")
OUT = Path(r"C:/00_workplace/fpga/cnn_accelerator/temporary/model_train_20261018")
cell=512
atlas=Image.new('RGB',(cell*3,cell*3),(235,235,235))
def panel(path, box=None):
    im=Image.open(path).convert('RGB')
    if box: im=im.crop(box)
    return im.resize((cell,cell),Image.LANCZOS)
# front/back = pink carton; sides/top/bottom = top-row photos; white cell for straw/non-axis
front=panel(D/"IMG20261018111348.jpg",(635,502,2313,2580))
atlas.paste(front,(0,0)); atlas.paste(front.transpose(Image.FLIP_LEFT_RIGHT),(cell,0))
# manual crops of the carton on the flat top-row photos
def crop_frac(im, fx0,fy0,fx1,fy1):
    w,h=im.size; return im.crop((int(fx0*w),int(fy0*h),int(fx1*w),int(fy1*h)))
for idx,(name,frac) in enumerate([("IMG20261018111410.jpg",(0.14,0.30,0.86,0.70)),
                                  ("IMG20261018111406.jpg",(0.14,0.30,0.86,0.70)),
                                  ("IMG20261018111401.jpg",(0.12,0.28,0.88,0.72)),
                                  ("IMG20261018111357.jpg",(0.12,0.28,0.88,0.72))]):
    im=Image.open(D/name).convert('RGB'); p=crop_frac(im,*frac).resize((cell,cell),Image.LANCZOS)
    cx=(idx+2)%3; cy=0 if idx<1 else 1; atlas.paste(p,(cx*cell,cy*cell))
# white cell at (2,1) for straw/non-axis
ImageDraw.Draw(atlas).rectangle([cell*2,cell,cell*3-1,cell*2-1],fill=(245,245,245))
base=list(trimesh.load(GLB, force="scene").geometry.values())[0]
V,F=base.vertices, base.faces
a=V[F[:,0]]; b=V[F[:,1]]; c=V[F[:,2]]
fn=np.cross(b-a,c-a); n=np.linalg.norm(fn,axis=1); ok=n>1e-12; fn[ok]/=n[ok,None]
lo,hi=base.bounds; span=hi-lo
def uv_for(pos, normal):
    ax=int(np.argmax(np.abs(normal)))
    if np.abs(normal[ax])<0.8: return (2*cell+cell*0.5)/ (cell*3), (cell+cell*0.5)/(cell*3)  # white cell
    u=(pos[0]-lo[0])/span[0]; v=(pos[2]-lo[2])/span[2]
    if ax==0: u=(pos[1]-lo[1])/span[1]
    if ax==2: v=(pos[1]-lo[1])/span[1]
    # choose panel cell by axis/sign
    if ax==1: cx,cy=(0,0) if normal[1]<0 else (1,0)
    elif ax==0: cx,cy=(2,0) if normal[0]<0 else (0,1)
    else: cx,cy=(1,1) if normal[2]>0 else (2,1)
    return (cx+u)/3, (cy+1-v)/3
verts=[]; uvs=[]; faces=[]
for i in range(len(F)):
    for j in range(3):
        verts.append(V[F[i,j]]); uvs.append(uv_for(V[F[i,j]], fn[i]))
    base_i=len(faces)*3; faces.append([base_i,base_i+1,base_i+2])
mesh=trimesh.Trimesh(np.array(verts),np.array(faces),process=False,visual=TextureVisuals(uv=np.array(uvs),image=atlas))
def look_at(eye,target,up=(0,0,1)):
    eye=np.asarray(eye,float);target=np.asarray(target,float);up=np.asarray(up,float)
    z=eye-target;z/=np.linalg.norm(z);x=np.cross(up,z);x/=np.linalg.norm(x);y=np.cross(z,x)
    M=np.eye(4);M[:3,0]=x;M[:3,1]=y;M[:3,2]=z;M[:3,3]=eye;return M
center=base.bounds.mean(0); size=float(np.linalg.norm(base.extents))
for tag,az in (("front",0),("back",180)):
    rad=np.deg2rad(az); eye=center+np.array([np.sin(rad),-np.cos(rad),0])*1.7*size+np.array([0,0,0.55*size])
    sc=pyrender.Scene(bg_color=[0,0,0,0]); sc.add(pyrender.Mesh.from_trimesh(mesh,smooth=False))
    cam=pyrender.PerspectiveCamera(yfov=np.deg2rad(40),aspectRatio=1.0); pose=look_at(eye,center); sc.add(cam,pose=pose)
    sc.add(pyrender.DirectionalLight(color=np.ones(3),intensity=4.0),pose=look_at(eye+np.array([0.5,0.4,1.0])*size,center))
    r=pyrender.OffscreenRenderer(416,416); color,_=r.render(sc,flags=pyrender.RenderFlags.RGBA); r.delete()
    rgba=Image.fromarray(color,'RGBA'); table=Image.open(OUT/"table_bg.png").convert('RGB').resize((416,416))
    table.paste(rgba,(0,0),rgba); table.save(OUT/f"glb_photo_{tag}.png")
print("saved")
