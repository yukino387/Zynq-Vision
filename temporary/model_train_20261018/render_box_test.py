import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw
import trimesh, pyrender
from trimesh.visual.texture import TextureVisuals
ROOT = Path(r"C:/00_workplace/fpga/cnn_accelerator")
OUT = ROOT / "temporary/model_train_20261018"
FRONT = Path(r"C:\Users\YUKINO\Downloads\IMG20261018111348.jpg")
BOX = (635, 502, 2313, 2580)
front = Image.open(FRONT).convert("RGB").crop(BOX)
# atlas 2x3 cells; front cell top-left, back top-middle, sides/bottom/top filled with front for now
cell = 512
atlas = Image.new("RGB", (cell*3, cell*2), (245, 225, 230))
img = front.resize((cell, cell), Image.LANCZOS)
atlas.paste(img, (0, 0)); atlas.paste(img.transpose(Image.FLIP_LEFT_RIGHT), (cell, 0))
atlas.paste(img, (cell*2, 0)); atlas.paste(img.rotate(90, expand=True), (0, cell))
atlas.paste(img, (cell, cell)); atlas.paste(img.rotate(-90, expand=True), (cell*2, cell))
# box 0.6 x 0.456 x 1.0, bottom at z=0
w,d,h = 0.6, 0.456, 1.0
V = np.array([[-w/2,-d/2,0],[w/2,-d/2,0],[w/2,d/2,0],[-w/2,d/2,0],
              [-w/2,-d/2,h],[w/2,-d/2,h],[w/2,d/2,h],[-w/2,d/2,h]], float)
F = np.array([[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],[1,5,6],[1,6,2],[2,6,7],[2,7,3],[3,7,4],[3,4,0]])
# per-face UV cells (3x2 grid); front(-y), back(+y), left(-x), right(+x), top(+z), bottom(-z)
cells = [(0,0),(1,0),(2,0),(0,1),(1,1),(2,1)]
uv = np.zeros((len(V),2))
# assign UVs per face by rewriting faces with per-face vertices
verts=[]; faces=[]; uvs=[]
for fi, cellxy in enumerate(cells):
    a,b,c = F[fi*2]; a2,b2,c2 = F[fi*2+1]
    quad = [V[a],V[b],V[c],V[a2]]  # not always order; use the two triangles' unique corners
    # simpler: build the four corners of the face from the cell
# rebuild with a standard box per-face quads
px, nx = w/2, -w/2; py, ny = d/2, -d/2; pz, nz = h, 0.0
quads = [
    [(nx,ny,nz),(px,ny,nz),(px,ny,pz),(nx,ny,pz)],  # front -y
    [(px,py,nz),(nx,py,nz),(nx,py,pz),(px,py,pz)],  # back +y
    [(nx,py,nz),(nx,ny,nz),(nx,ny,pz),(nx,py,pz)],  # left -x
    [(px,ny,nz),(px,py,nz),(px,py,pz),(px,ny,pz)],  # right +x
    [(nx,ny,pz),(px,ny,pz),(px,py,pz),(nx,py,pz)],  # top +z
    [(nx,py,nz),(px,py,nz),(px,ny,nz),(nx,ny,nz)],  # bottom -z
]
verts=[]; faces=[]; uvs=[]
for qi,q in enumerate(quads):
    cx,cy = cells[qi]; u0,v0 = cx/3, cy/2; u1,v1 = (cx+1)/3, (cy+1)/2
    base=len(verts); verts += q
    uvs += [(u0,v0),(u1,v0),(u1,v1),(u0,v1)]
    faces += [[base,base+1,base+2],[base,base+2,base+3]]
mesh = trimesh.Trimesh(np.array(verts,float), np.array(faces,int), process=False,
                       visual=TextureVisuals(uv=np.array(uvs,float), image=atlas))
# straw cylinder on the front face, diagonal
straw = trimesh.creation.cylinder(radius=0.016, height=0.82, sections=20)
# cylinder axis z; rotate to lie in x-z plane, then diagonal
rot = trimesh.transformations.rotation_matrix(np.deg2rad(28), [0,1,0])
straw.apply_transform(rot)
straw.apply_translation([0.02, -d/2-0.025, h/2])
def look_at(eye, target, up=(0,0,1)):
    eye=np.asarray(eye,float); target=np.asarray(target,float); up=np.asarray(up,float)
    z=eye-target; z/=np.linalg.norm(z); x=np.cross(up,z); x/=np.linalg.norm(x); y=np.cross(z,x)
    M=np.eye(4); M[:3,0]=x; M[:3,1]=y; M[:3,2]=z; M[:3,3]=eye; return M
scene = pyrender.Scene(bg_color=[0,0,0,0])
scene.add(pyrender.Mesh.from_trimesh(mesh, smooth=False))
straw_mat = pyrender.MetallicRoughnessMaterial(baseColorFactor=[0.96,0.96,0.97,1], metallicFactor=0.0, roughnessFactor=0.35)
scene.add(pyrender.Mesh.from_trimesh(straw, smooth=True, material=straw_mat))
eye = np.array([0.15, -2.2, 0.65]); target = np.array([0,0,0.5])
scene.add(pyrender.PerspectiveCamera(yfov=np.deg2rad(40)), pose=look_at(eye,target))
scene.add(pyrender.DirectionalLight(color=np.ones(3), intensity=4.0), pose=look_at(eye+np.array([0.5,0.6,1.2]), target))
r = pyrender.OffscreenRenderer(416,416)
color, depth = r.render(scene, flags=pyrender.RenderFlags.RGBA)
r.delete()
rgba = Image.fromarray(color, "RGBA")
table = Image.open(OUT/"table_bg.png").convert("RGB").resize((416,416))
table = Image.blend(table, Image.new("RGB",(416,416),(180,150,120)), 0.05)
table.paste(rgba, (0,0), rgba)
table.save(OUT/"box_test.png")
print("saved box_test.png")
