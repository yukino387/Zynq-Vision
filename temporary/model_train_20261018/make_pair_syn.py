"""Render old GLB (with straw) = class 0 and new GLB (no straw) = class 1 on the wooden table."""
import argparse, json, math, random
from pathlib import Path
import numpy as np, trimesh, pyrender
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
OLD = Path(r"C:\Users\YUKINO\Downloads\a2f2e182611c7076e5d5b6742e03b9ef.glb")
NEW = Path(r"C:\Users\YUKINO\Downloads\335ba5ca50a5917448e171289046b19c.glb")
ROOT=Path(r"C:/00_workplace/fpga/cnn_accelerator"); OUT=ROOT/"temporary/model_train_20261018/pair_syn"
OUT.mkdir(exist_ok=True); (OUT/"images").mkdir(exist_ok=True)
TABLE=ROOT/"temporary/model_train_20261018/table_bg.png"
def look_at(eye,target,up=(0,0,1)):
    eye=np.asarray(eye,float);target=np.asarray(target,float);up=np.asarray(up,float)
    z=eye-target;z/=np.linalg.norm(z);x=np.cross(up,z);x/=np.linalg.norm(x);y=np.cross(z,x)
    M=np.eye(4);M[:3,0]=x;M[:3,1]=y;M[:3,2]=z;M[:3,3]=eye;return M
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--per-class',type=int,default=100); ap.add_argument('--seed',type=int,default=7020)
    args=ap.parse_args(); random.seed(args.seed); rng=np.random.default_rng(args.seed)
    meshes={0:list(trimesh.load(OLD,force='scene').geometry.values())[0], 1:list(trimesh.load(NEW,force='scene').geometry.values())[0]}
    scenes={}; cams={}; lights={}
    for cls,m in meshes.items():
        sc=pyrender.Scene(bg_color=[0,0,0,0]); sc.add(pyrender.Mesh.from_trimesh(m,smooth=False))
        cam=pyrender.PerspectiveCamera(yfov=np.deg2rad(40),aspectRatio=1.0); cams[cls]=(sc,cam,sc.add(cam,pose=np.eye(4)),sc.add(pyrender.DirectionalLight(color=np.ones(3),intensity=4.0),pose=np.eye(4)))
    r=pyrender.OffscreenRenderer(416,416); table=Image.open(TABLE).convert('RGB'); tw,th=table.size
    metas=[]
    for cls in (0,1):
        m=meshes[cls]; sc,cam,cam_node,light_node=cams[cls]
        center=m.bounds.mean(0); size=float(np.linalg.norm(m.extents))
        for i in range(args.per_class):
            az=math.radians(random.uniform(-115,-65) if cls==0 else random.uniform(-25,25))
            eye=center+np.array([math.sin(az),-math.cos(az),0])*1.7*size+np.array([0,0,random.uniform(0.3,0.75)*size])
            pose=look_at(eye,center); sc.set_pose(cam_node,pose); sc.set_pose(light_node,look_at(eye+np.array([0.5,0.4,1.0])*size,center))
            color,_=r.render(sc,flags=pyrender.RenderFlags.RGBA); rgba=Image.fromarray(color,'RGBA')
            cw=random.randint(320,min(416,tw)); ch=random.randint(320,min(416,th)); x0=random.randint(0,tw-cw); y0=random.randint(0,th-ch)
            bg=table.crop((x0,y0,x0+cw,y0+ch)).resize((416,416),Image.BICUBIC)
            bg=ImageEnhance.Brightness(bg).enhance(random.uniform(0.8,1.15)); bg=ImageEnhance.Contrast(bg).enhance(random.uniform(0.85,1.15))
            if random.random()<0.5: bg=bg.transpose(Image.FLIP_LEFT_RIGHT)
            proj=cam.get_projection_matrix(1.0); view=np.linalg.inv(pose); pts=[]
            for x in (m.bounds[0][0],m.bounds[1][0]):
                for y in (m.bounds[0][1],m.bounds[1][1]):
                    for z in (m.bounds[0][2],m.bounds[1][2]):
                        q=proj@view@np.array([x,y,z,1.0]); q=q[:3]/q[3]; pts.append(((q[0]+1)/2*416,(1-q[1])/2*416))
            xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
            x1=max(0,min(xs)); y1=max(0,min(ys)); x2=min(416,max(xs)); y2=min(416,max(ys))
            if x2-x1<40 or y2-y1<40: continue
            sh=Image.new('RGBA',(416,416),(0,0,0,0)); dd=ImageDraw.Draw(sh); bw=x2-x1
            dd.ellipse([x1+0.1*bw,y2-0.06*bw,x2-0.1*bw,y2+0.06*bw],fill=(0,0,0,95)); sh=sh.filter(ImageFilter.GaussianBlur(8))
            bg=Image.alpha_composite(bg.convert('RGBA'),sh).convert('RGB'); bg.paste(rgba,(0,0),rgba)
            if random.random()<0.4: bg=bg.filter(ImageFilter.GaussianBlur(random.uniform(0.2,0.8)))
            arr=np.asarray(bg).astype(np.int16)+rng.normal(0,random.uniform(0,3),(416,416,3)).astype(np.int16)
            bg=Image.fromarray(np.clip(arr,0,255).astype(np.uint8))
            p=OUT/'images'/f'pair_{cls}_{i:04d}.png'; bg.save(p)
            metas.append({'path':str(p),'boxes':[{'classId':cls,'x1':x1,'y1':y1,'x2':x2,'y2':y2}]})
    r.delete(); (OUT/'meta.json').write_text(json.dumps(metas,ensure_ascii=False,indent=1),encoding='utf-8'); print('generated',len(metas))
if __name__=='__main__': main()
