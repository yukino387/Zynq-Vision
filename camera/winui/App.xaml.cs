using Microsoft.UI.Xaml;
namespace CNNStudio;
public partial class App : Application
{
    private Window? window;
    public App() { InitializeComponent(); UnhandledException += (_, e) => System.IO.File.AppendAllText(System.IO.Path.Combine(AppContext.BaseDirectory,"errors.log"),$"{DateTime.Now:o} {e.Exception}\n"); }
    protected override void OnLaunched(LaunchActivatedEventArgs args) { window = new MainWindow(); window.Activate(); }
}
