using System.Diagnostics;
using System.Runtime.InteropServices.WindowsRuntime;
using Microsoft.UI;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Controls.Primitives;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using Microsoft.UI.Xaml.Shapes;
using Windows.Graphics;
using Windows.Graphics.Imaging;
using Windows.Storage;
using Windows.Storage.Streams;

namespace CNNStudio;
public sealed partial class MainWindow : Window
{
    private BoardClient? client;
    private ReceivedFrame? pending;
    private VideoRecorder? recorder;
    private readonly DispatcherTimer timer = new() { Interval = TimeSpan.FromMilliseconds(33) };
    private readonly DispatcherTimer brightnessTimer = new() { Interval = TimeSpan.FromMilliseconds(250) };
    private double confidence = .5, overlap = .3, pcMs;
    private long previousFrame;
    private int count, rotation;
    private bool displaying, closing, fullScreen, recordBusy;
    private readonly string saveFolder = System.IO.Path.Combine(AppContext.BaseDirectory, "Recordings");
    public MainWindow()
    {
        InitializeComponent();
        System.IO.Directory.CreateDirectory(saveFolder);

        SystemBackdrop = new MicaBackdrop();
        ExtendsContentIntoTitleBar = true;
        SetTitleBar(TitleArea);
        AppWindow.SetIcon(System.IO.Path.Combine(AppContext.BaseDirectory, "Assets", "App.ico"));
        AppWindow.Resize(new SizeInt32(1400, 900));

        Root.SizeChanged += (_, args) => { bool show = args.NewSize.Width >= 900; ResultsPanel.Visibility = show ? Visibility.Visible : Visibility.Collapsed; ResultsColumn.Width = new GridLength(show ? 280 : 0); };
        timer.Tick += async (_, _) => await Display();
        brightnessTimer.Tick += async (_, _) => { brightnessTimer.Stop(); await Control(4, (int)Brightness.Value); };
        AppWindow.Closing += WindowClosing;
    }
    private void PageLoaded(object sender, RoutedEventArgs e)
    {
        try
        {
            client = new BoardClient();
            client.FrameReceived += frame => Interlocked.Exchange(ref pending, frame);
            client.ConnectionChanged += text => DispatcherQueue.TryEnqueue(async () => {
                ConnectionText.Text = text;
                if (text != "已连接") FpsText.Text = "— fps";
                ConnectionDot.Fill = new SolidColorBrush(text == "已连接" ? Windows.UI.Color.FromArgb(255, 22, 163, 106) : Windows.UI.Color.FromArgb(255, 138, 138, 138));
                if (text == "已连接") await Control(3, Mode.SelectedIndex);
            });
            client.StatusReceived += status => DispatcherQueue.TryEnqueue(() => { PauseIcon.Glyph = status.Running ? "\uE769" : "\uE768"; if (status.Errors != 0) ActionHint.Text = "设备运行中断"; });
            client.Start(); timer.Start();
        }
        catch (Exception error) { ActionHint.Text = "无法连接，请关闭其他接收程序"; Log(error); }
    }
    private static void Log(Exception error) => System.IO.File.AppendAllText(System.IO.Path.Combine(AppContext.BaseDirectory, "errors.log"), $"{DateTime.Now:o} {error}\n");
    private async Task Control(uint command, int value)
    {
        if (client?.Status == null) return;
        try { await client.Command(command, value); ActionHint.Text = ""; }
        catch (Exception error) { ActionHint.Text = "设备未响应"; Log(error); }
    }
    private async void ModeChanged(object sender, SelectionChangedEventArgs e) { if (client != null) { if (recorder != null) await StopRecording(); await Control(3, Mode.SelectedIndex); } }
    private async void PauseClicked(object sender, RoutedEventArgs e) { if (recorder != null) await StopRecording(); await Control(2, client?.Status?.Running == true ? 0 : 1); }
    private void BrightnessChanged(object sender, RangeBaseValueChangedEventArgs e) { if (client == null) return; brightnessTimer.Stop(); brightnessTimer.Start(); }
    private void ThresholdChanged(object sender, RangeBaseValueChangedEventArgs e) { if (Confidence == null || Overlap == null) return; confidence = Confidence.Value; overlap = Overlap.Value; }
    private async Task Display()
    {
        if (displaying) return;
        var frame = Interlocked.Exchange(ref pending, null);
        if (frame == null) { if (recorder != null) RecordingTime.Text = $"REC {recorder.Elapsed:mm\\:ss}"; return; }
        displaying = true;
        try
        {
            var clock = Stopwatch.StartNew();
            var detections = frame.Out0 != null && frame.Out1 != null ? Postprocess.Detect(frame.Out0, frame.Out1, confidence, overlap) : [];
            byte[] pixels = new byte[416 * 416 * 4];
            for (int y = 0; y < 416; y++) for (int x = 0; x < 416; x++)
            {
                int input = (y * 416 + x) * 2;
                int raw = frame.Pixels[input] | frame.Pixels[input + 1] << 8;
                var (rx, ry) = Rotate(x, y);
                int output = ((int)ry * 416 + (int)rx) * 4;
                pixels[output] = (byte)(((raw & 31) << 3) | ((raw & 31) >> 2));
                pixels[output+1] = (byte)((((raw >> 5) & 63) << 2) | (((raw >> 5) & 63) >> 4));
                pixels[output+2] = (byte)((((raw >> 11) & 31) << 3) | (((raw >> 11) & 31) >> 2));
                pixels[output+3] = 255;
            }
            var bitmap = new WriteableBitmap(416, 416);
            using (var buffer = bitmap.PixelBuffer.AsStream()) buffer.Write(pixels);
            PreviewImage.Source = bitmap;
            EmptyState.Visibility = Visibility.Collapsed;
            Overlay.Children.Clear();
            if (Boxes.IsOn) foreach (var detection in detections) Draw(detection);
            Results.ItemsSource = detections;
            DetectionCount.Text = detections.Count.ToString();
            ResultHint.Text = frame.Out0 == null ? "预览模式" : detections.Count == 0 ? "暂无目标" : "识别结果";
            SessionText.Text = $"本次接收 {++count:N0} 帧";
            if (previousFrame != 0) FpsText.Text = $"{1 / Stopwatch.GetElapsedTime(previousFrame, frame.Timestamp).TotalSeconds:F1} fps";
            previousFrame = frame.Timestamp;
            RecordButton.IsEnabled = !recordBusy;
            SnapshotButton.IsEnabled = true;
            pcMs = clock.Elapsed.TotalMilliseconds;
            if (recorder != null) { recorder.Push(await Capture()); RecordingTime.Text = $"REC {recorder.Elapsed:mm\\:ss}"; }
        }
        catch (Exception error) { Log(error); ActionHint.Text = "画面处理失败"; if (recorder != null) await StopRecording(); }
        finally { displaying = false; }
    }
    private (double X, double Y) Rotate(double x, double y) => rotation switch { 1 => (415-y,x), 2 => (415-x,415-y), 3 => (y,415-x), _ => (x,y) };
    private void Draw(Detection d)
    {
        var a = Rotate(d.X1, d.Y1); var b = Rotate(d.X2, d.Y2);
        double x = Math.Max(0, Math.Min(a.X,b.X)), y = Math.Max(0, Math.Min(a.Y,b.Y));
        var brush = new SolidColorBrush(Windows.UI.Color.FromArgb(255, 67, 222, 183));
        var box = new Rectangle { Width = Math.Abs(a.X-b.X), Height = Math.Abs(a.Y-b.Y), Stroke = brush, StrokeThickness = 2 };
        Canvas.SetLeft(box,x); Canvas.SetTop(box,y); Overlay.Children.Add(box);
        var label = new Border { Background = brush, CornerRadius = new CornerRadius(3), Padding = new Thickness(5,2,5,2), Child = new TextBlock { Text = $"{d.Label} {d.Confidence}", FontSize = 11, Foreground = new SolidColorBrush(Colors.Black) } };
        Canvas.SetLeft(label,x); Canvas.SetTop(label,Math.Max(0,y-22)); Overlay.Children.Add(label);
    }
    private async Task<byte[]> Capture()
    {
        var image = new RenderTargetBitmap();
        await image.RenderAsync(PreviewSurface,416,416);
        return (await image.GetPixelsAsync()).ToArray();
    }
    private async void RecordClicked(object sender, RoutedEventArgs e)
    {
        if (recordBusy) return;
        recordBusy = true;
        RecordButton.IsEnabled = false;
        try
        {
            if (recorder != null) await StopRecording();
            else
            {
                var recording = new VideoRecorder(System.IO.Path.Combine(saveFolder,$"视频_{DateTime.Now:yyyyMMdd_HHmmss_fff}.mp4"));
                await recording.Start(await Capture()); recorder = recording;
                RecordingBadge.Visibility = Visibility.Visible; RecordLabel.Text = "停止录制"; ActionHint.Text = "";
            }
        }
        catch (Exception error) { Log(error); ActionHint.Text = "无法开始录制"; }
        finally { recordBusy = false; RecordButton.IsEnabled = true; }
    }
    private async Task StopRecording()
    {
        var recording = recorder; recorder = null;
        if (recording == null) return;
        try { await recording.Stop(); ActionHint.Text = "视频已保存"; }
        catch (Exception error) { Log(error); ActionHint.Text = "视频保存失败"; }
        RecordingBadge.Visibility = Visibility.Collapsed; RecordLabel.Text = "录制";
    }
    private async void SnapshotClicked(object sender, RoutedEventArgs e)
    {
        try
        {
            using var file = new System.IO.FileStream(System.IO.Path.Combine(saveFolder,$"画面_{DateTime.Now:yyyyMMdd_HHmmss_fff}.png"),System.IO.FileMode.CreateNew);
            using var stream = file.AsRandomAccessStream();
            var encoder = await BitmapEncoder.CreateAsync(BitmapEncoder.PngEncoderId,stream);
            encoder.SetPixelData(BitmapPixelFormat.Bgra8,BitmapAlphaMode.Premultiplied,416,416,96,96,await Capture()); await encoder.FlushAsync(); ActionHint.Text = "画面已保存";
        }
        catch (Exception error) { Log(error); ActionHint.Text = "画面保存失败"; }
    }
    private async void OpenFolderClicked(object sender, RoutedEventArgs e)
    {
        try
        {
            System.IO.Directory.CreateDirectory(saveFolder);
            var folder = await StorageFolder.GetFolderFromPathAsync(saveFolder);
            if (!await Windows.System.Launcher.LaunchFolderAsync(folder)) ActionHint.Text = "无法打开保存位置";
        }
        catch (Exception error) { Log(error); ActionHint.Text = "无法打开保存位置"; }
    }
    private void RotateClicked(object sender, RoutedEventArgs e) => rotation = (rotation + 1) % 4;
    private void FullScreenClicked(object sender, RoutedEventArgs e) { fullScreen = !fullScreen; AppWindow.SetPresenter(fullScreen ? AppWindowPresenterKind.FullScreen : AppWindowPresenterKind.Overlapped); }
    private async void DiagnosticsClicked(object sender, RoutedEventArgs e)
    {
        var s = client?.Status;
        var dialog = new ContentDialog { XamlRoot = Root.XamlRoot, Title = "运行状态", CloseButtonText = "关闭", Content = s == null ? "设备未连接" : $"采集等待 {s.CaptureUs/1000.0:F1} ms\n输入准备 {s.ConvertUs/1000.0:F1} ms\n板端推理 {(s.PreviewOnly ? 0 : s.InferenceUs)/1000.0:F1} ms\n传输 {s.TransferUs/1000.0:F1} ms\n电脑处理 {pcMs:F1} ms\n完整周期 {s.CycleUs/1000.0:F1} ms\n设备错误 {s.Errors}" };
        await dialog.ShowAsync();
    }
    private async void WindowClosing(AppWindow sender, AppWindowClosingEventArgs args)
    {
        if (closing) return;
        args.Cancel = true; closing = true; timer.Stop(); brightnessTimer.Stop();
        await StopRecording(); await Control(2,0); client?.Dispose(); Close();
    }
}
