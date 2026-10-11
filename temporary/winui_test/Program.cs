using CNNStudio;
using System.Diagnostics;
using System.Text.Json;
using Windows.Storage;
var root = Environment.CurrentDirectory;
var detected = Postprocess.Detect(File.ReadAllBytes(Path.Combine(root,"detect_0.bin")), File.ReadAllBytes(Path.Combine(root,"detect_1.bin")), .5,.3);
File.WriteAllText("native_detections.json",JsonSerializer.Serialize(detected));
using var board = new BoardClient();
var connected = new TaskCompletionSource();
var frames = new System.Collections.Concurrent.ConcurrentQueue<ReceivedFrame>();
board.ConnectionChanged += text => { Console.WriteLine(text); if(text=="已连接") connected.TrySetResult(); };
board.FrameReceived += frame => frames.Enqueue(frame);
board.Start(); await connected.Task.WaitAsync(TimeSpan.FromSeconds(10));
await board.Command(3,1);
while(frames.TryDequeue(out _)){}
var clock = Stopwatch.StartNew();
while(frames.IsEmpty && clock.Elapsed.TotalSeconds<5) await Task.Delay(20);
if(!frames.TryDequeue(out var first)) throw new Exception("No camera frame");
byte[] Convert(byte[] rgb){ byte[] b=new byte[416*416*4];for(int i=0;i<416*416;i++){int v=rgb[i*2]|rgb[i*2+1]<<8;b[i*4]=(byte)(((v&31)<<3)|((v&31)>>2));b[i*4+1]=(byte)((((v>>5)&63)<<2)|(((v>>5)&63)>>4));b[i*4+2]=(byte)((((v>>11)&31)<<3)|(((v>>11)&31)>>2));b[i*4+3]=255;}return b;}
var path=Path.Combine(root,"native_recording.mp4");if(File.Exists(path))File.Delete(path);
var video=new VideoRecorder(path);await video.Start(Convert(first.Pixels));int count=1;clock.Restart();
while(clock.Elapsed.TotalSeconds<5){if(frames.TryDequeue(out var frame)){video.Push(Convert(frame.Pixels));count++;}else await Task.Delay(10);}
await video.Stop();
var properties=new {Duration=video.Elapsed,Width=416,Height=416};
if(properties.Duration.TotalSeconds<4 || properties.Width!=416 || properties.Height!=416) throw new Exception("Invalid video");
var paused=await board.Command(2,0);if(paused.Running)throw new Exception("Pause failed");
while(frames.TryDequeue(out _)){} await Task.Delay(800);while(frames.TryDequeue(out _)){}await Task.Delay(800);if(!frames.IsEmpty)throw new Exception("Frames while paused");
await board.Command(2,1);await board.Command(3,0);
var result=new{Frames=count,Duration=properties.Duration.TotalSeconds,properties.Width,properties.Height,Size=new FileInfo(path).Length,Status=board.Status};
File.WriteAllText("native_results.json",JsonSerializer.Serialize(result,new JsonSerializerOptions{WriteIndented=true}));Console.WriteLine(JsonSerializer.Serialize(result));
