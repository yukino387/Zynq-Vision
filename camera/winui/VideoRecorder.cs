using System.Runtime.InteropServices.WindowsRuntime;
using System.Threading.Channels;
using Windows.Media.Core;
using Windows.Media.MediaProperties;
using Windows.Media.Transcoding;
using Windows.Storage;
using Windows.Storage.Streams;

namespace CNNStudio;

public sealed class VideoRecorder
{
    private readonly Channel<(byte[] Bytes, TimeSpan Time)> frames = Channel.CreateBounded<(byte[], TimeSpan)>(
        new BoundedChannelOptions(60) { FullMode = BoundedChannelFullMode.Wait, SingleReader = true });
    private Task? encoding;
    private IRandomAccessStream? stream;
    private FileStream? fileStream;
    private byte[]? last;
    private readonly System.Diagnostics.Stopwatch clock = new();
    public TimeSpan Elapsed => clock.Elapsed;
    public string Path { get; }
    public VideoRecorder(string path) => Path = path;
    public async Task Start(byte[] firstFrame)
    {
        fileStream = new FileStream(Path, FileMode.CreateNew, FileAccess.ReadWrite, FileShare.Read);
        stream = fileStream.AsRandomAccessStream();
        var format = VideoEncodingProperties.CreateUncompressed(MediaEncodingSubtypes.Bgra8, 416, 416);
        format.FrameRate.Numerator = 30;
        format.FrameRate.Denominator = 1;
        var source = new MediaStreamSource(new VideoStreamDescriptor(format)) { BufferTime = TimeSpan.Zero, IsLive = true };
        source.Starting += (_, args) => args.Request.SetActualStartPosition(TimeSpan.Zero);
        source.SampleRequested += async (_, args) =>
        {
            var deferral = args.Request.GetDeferral();
            try
            {
                if (await frames.Reader.WaitToReadAsync() && frames.Reader.TryRead(out var frame))
                {
                    args.Request.Sample = MediaStreamSample.CreateFromBuffer(frame.Bytes.AsBuffer(), frame.Time);
                    args.Request.Sample.Duration = TimeSpan.FromMilliseconds(33.333);
                }
                else args.Request.Sample = null;
            }
            finally { deferral.Complete(); }
        };
        var profile = MediaEncodingProfile.CreateMp4(VideoEncodingQuality.HD720p);
        profile.Audio = null;
        profile.Video.Width = profile.Video.Height = 416;
        profile.Video.FrameRate.Numerator = 30;
        profile.Video.FrameRate.Denominator = 1;
        profile.Video.Bitrate = 2_000_000;
        frames.Writer.TryWrite((firstFrame, TimeSpan.Zero));
        var prepared = await new MediaTranscoder().PrepareMediaStreamSourceTranscodeAsync(source, stream, profile);
        if (!prepared.CanTranscode) { stream.Dispose(); fileStream.Dispose(); throw new InvalidOperationException("无法启动视频录制"); }
        last = firstFrame;
        clock.Start();
        encoding = prepared.TranscodeAsync().AsTask();
    }
    public void Push(byte[] pixels)
    {
        if (encoding?.IsFaulted == true) throw new IOException("视频录制中断", encoding.Exception);
        if (!frames.Writer.TryWrite((pixels, clock.Elapsed))) throw new IOException("录制速度不足，请停止录制");
        last = pixels;
    }
    public async Task Stop()
    {
        try
        {
            if (encoding?.IsFaulted != true && last != null)
                await frames.Writer.WriteAsync((last, clock.Elapsed)).AsTask().WaitAsync(TimeSpan.FromSeconds(3));
            frames.Writer.TryComplete();
            if (encoding != null) await encoding;
        }
        finally { frames.Writer.TryComplete(); clock.Stop(); stream?.Dispose(); fileStream?.Dispose(); }
    }
}
