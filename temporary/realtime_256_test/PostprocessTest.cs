using System.Buffers.Binary;
using CNNStudio;

byte[] out0 = new byte[75*8*8*2], out1 = new byte[75*16*16*2];
foreach (var tensor in new[] {out0,out1})
    for (int i=0;i<tensor.Length;i+=2) BinaryPrimitives.WriteInt16LittleEndian(tensor.AsSpan(i),-8192);
int cell=4*8+3;
void Set(int channel,short value) => BinaryPrimitives.WriteInt16LittleEndian(out0.AsSpan((channel*64+cell)*2),value);
for (int i=0;i<4;i++) Set(i,0);
Set(4,5120); Set(5,5120);
var detections=Postprocess.Detect(out0,out1,.5,.3);
if(detections.Count!=1 || detections[0].ClassId!=0) throw new Exception("Detection count/class mismatch");
var result=detections[0];
if(Math.Abs((result.X1+result.X2)/2-182)>1e-9 || Math.Abs((result.Y1+result.Y2)/2-234)>1e-9 ||
   Math.Abs(result.X2-result.X1-2.5312*52)>1e-9) throw new Exception("256 input to 416 preview mapping mismatch");
Console.WriteLine("256 grids and anchor mapping: PASS");
