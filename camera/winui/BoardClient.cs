using System.Buffers.Binary;
using System.Diagnostics;
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;

namespace CNNStudio;

public record BoardStatus(uint Request, uint Flags, uint Frame, uint CaptureUs, uint ConvertUs,
    uint InferenceUs, uint TransferUs, uint CycleUs, uint Errors, int Brightness)
{
    public bool Running => (Flags & 1) != 0;
    public bool PreviewOnly => (Flags & 2) != 0;
}
public record ReceivedFrame(uint Id, byte[] Pixels, byte[]? Out0, byte[]? Out1, long Timestamp);

public sealed class BoardClient : IDisposable
{
    private readonly UdpClient udp = new(new IPEndPoint(IPAddress.Any, 5002));
    private readonly CancellationTokenSource stop = new();
    private readonly Dictionary<uint, Dictionary<uint, PartialStream>> frames = new();
    private readonly Dictionary<uint, TaskCompletionSource<BoardStatus>> requests = new();
    private readonly object requestLock = new();
    private IPEndPoint? board;
    private int requestId;
    private long lastSeen;
    public BoardStatus? Status { get; private set; }
    public event Action<ReceivedFrame>? FrameReceived;
    public event Action<BoardStatus>? StatusReceived;
    public event Action<string>? ConnectionChanged;
    private sealed class PartialStream(int length)
    {
        public readonly byte[] Bytes = new byte[length];
        public readonly HashSet<uint> Offsets = [];
    }
    public BoardClient()
    {
        udp.Client.ReceiveBufferSize = 4 * 1024 * 1024;
        udp.EnableBroadcast = true;
        udp.Client.IOControl((IOControlCode)(-1744830452), new byte[4], null);
    }
    public void Start()
    {
        _ = ReceiveLoop();
        _ = DiscoverLoop();
    }
    private static IEnumerable<IPAddress> Broadcasts()
    {
        foreach (var adapter in NetworkInterface.GetAllNetworkInterfaces())
        {
            if (adapter.OperationalStatus != OperationalStatus.Up ||
                adapter.NetworkInterfaceType != NetworkInterfaceType.Ethernet) continue;
            foreach (var address in adapter.GetIPProperties().UnicastAddresses)
            {
                if (address.Address.AddressFamily != AddressFamily.InterNetwork) continue;
                var ip = address.Address.GetAddressBytes();
                var mask = address.IPv4Mask.GetAddressBytes();
                yield return new IPAddress(ip.Zip(mask, (a, b) => (byte)(a | ~b)).ToArray());
            }
        }
    }
    private async Task DiscoverLoop()
    {
        try
        {
            while (!stop.IsCancellationRequested)
            {
                if (board != null && Stopwatch.GetElapsedTime(lastSeen).TotalSeconds > 4)
                {
                    board = null;
                    Status = null;
                    ConnectionChanged?.Invoke("正在寻找设备");
                }
                try
                {
                    if (board == null)
                    {
                        foreach (var ip in Broadcasts().Append(IPAddress.Parse("169.254.140.110")).Distinct())
                            await Send(0, 0, 0, new IPEndPoint(ip, 5001));
                    }
                    else await Send(0, 0, 0, board);
                }
                catch (SocketException) { board = null; Status = null; ConnectionChanged?.Invoke("正在寻找设备"); }
                await Task.Delay(1000, stop.Token);
            }
        }
        catch (OperationCanceledException) { }
        catch (ObjectDisposedException) { }
        catch (SocketException error) { ConnectionChanged?.Invoke($"连接中断：{error.Message}"); }
    }
    private Task Send(uint id, uint command, int value, IPEndPoint endpoint)
    {
        byte[] packet = new byte[16];
        BinaryPrimitives.WriteUInt32LittleEndian(packet, 0x31434e43);
        BinaryPrimitives.WriteUInt32LittleEndian(packet.AsSpan(4), id);
        BinaryPrimitives.WriteUInt32LittleEndian(packet.AsSpan(8), command);
        BinaryPrimitives.WriteInt32LittleEndian(packet.AsSpan(12), value);
        return udp.SendAsync(packet, endpoint, stop.Token).AsTask();
    }
    public async Task<BoardStatus> Command(uint command, int value)
    {
        var endpoint = board ?? throw new InvalidOperationException("设备未连接");
        uint id = (uint)Interlocked.Increment(ref requestId);
        var completion = new TaskCompletionSource<BoardStatus>(TaskCreationOptions.RunContinuationsAsynchronously);
        lock (requestLock) requests[id] = completion;
        try
        {
            await Send(id, command, value, endpoint);
            return await completion.Task.WaitAsync(TimeSpan.FromSeconds(3), stop.Token);
        }
        finally { lock (requestLock) requests.Remove(id); }
    }
    private async Task ReceiveLoop()
    {
        try
        {
            while (!stop.IsCancellationRequested)
            {
                UdpReceiveResult message;
                try { message = await udp.ReceiveAsync(stop.Token); }
                catch (SocketException) when (!stop.IsCancellationRequested) { continue; }
                var packet = message.Buffer;
                if (packet.Length == 48 && Read(packet, 0) == 0x31545343 && Read(packet, 8) == 0x7020)
                {
                    if (message.RemoteEndPoint.Port != 5001) continue;
                    if (board != null && !board.Equals(message.RemoteEndPoint)) continue;
                    bool found = board == null;
                    board = message.RemoteEndPoint;
                    lastSeen = Stopwatch.GetTimestamp();
                    var status = new BoardStatus(Read(packet, 4), Read(packet, 12), Read(packet, 16),
                        Read(packet, 20), Read(packet, 24), Read(packet, 28), Read(packet, 32),
                        Read(packet, 36), Read(packet, 40), (int)Read(packet, 44));
                    if (Status?.PreviewOnly != status.PreviewOnly) frames.Clear();
                    Status = status;
                    lock (requestLock)
                        if (requests.TryGetValue(status.Request, out var completion)) completion.TrySetResult(status);
                    StatusReceived?.Invoke(status);
                    if (found)
                    {
                        _ = Connect();
                    }
                    continue;
                }
                if (board == null || !board.Equals(message.RemoteEndPoint) || packet.Length <= 20 ||
                    Read(packet, 0) != 0x314f4c59) continue;
                Assemble(packet);
            }
        }
        catch (OperationCanceledException) { }
        catch (ObjectDisposedException) { }
        catch (SocketException error) { ConnectionChanged?.Invoke($"连接中断：{error.Message}"); }
    }
    private async Task Connect()
    {
        try { await Command(1, 0); ConnectionChanged?.Invoke("已连接"); }
        catch (Exception error) when (error is TimeoutException or OperationCanceledException or SocketException)
        { board = null; Status = null; ConnectionChanged?.Invoke("正在寻找设备"); }
    }
    private static uint Read(byte[] packet, int offset) => BinaryPrimitives.ReadUInt32LittleEndian(packet.AsSpan(offset));
    private void Assemble(byte[] packet)
    {
        uint frame = Read(packet, 4), kind = Read(packet, 8), length = Read(packet, 12), offset = Read(packet, 16);
        int expected = kind switch { 0 => 9600, 1 => 38400, 2 => 346112, _ => 0 };
        if (expected == 0 || length != expected || offset >= length || offset % 1400 != 0 ||
            packet.Length - 20 != Math.Min(1400, length - offset)) return;
        if (!frames.TryGetValue(frame, out var streams))
        {
            frames[frame] = streams = new();
            while (frames.Count > 3) frames.Remove(frames.Keys.Min());
            if (!frames.ContainsKey(frame)) return;
        }
        if (!streams.TryGetValue(kind, out var stream)) streams[kind] = stream = new(expected);
        packet.AsSpan(20).CopyTo(stream.Bytes.AsSpan((int)offset));
        stream.Offsets.Add(offset);
        uint[] required = Status?.PreviewOnly == true ? [2] : [0, 1, 2];
        if (!required.All(k => streams.TryGetValue(k, out var s) && s.Offsets.Count == (s.Bytes.Length + 1399) / 1400)) return;
        FrameReceived?.Invoke(new(frame, streams[2].Bytes, streams.GetValueOrDefault(0u)?.Bytes,
            streams.GetValueOrDefault(1u)?.Bytes, Stopwatch.GetTimestamp()));
        foreach (var key in frames.Keys.Where(k => k <= frame).ToArray()) frames.Remove(key);
    }
    public void Dispose()
    {
        stop.Cancel();
        udp.Dispose();
    }
}
