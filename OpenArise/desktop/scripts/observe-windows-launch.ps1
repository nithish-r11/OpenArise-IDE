param(
  [Parameter(Mandatory=$true)][string]$ExecutablePath,
  [Parameter(Mandatory=$true)][string]$EvidenceDirectory
)
$ErrorActionPreference='Stop'
$phase8Exe=(Resolve-Path -LiteralPath $ExecutablePath).Path
$phase8Evidence=[IO.Path]::GetFullPath($EvidenceDirectory)
$phase8Workspace=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if(-not $phase8Evidence.StartsWith($phase8Workspace+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Evidence must stay inside the desktop workspace'}
New-Item -ItemType Directory -Path $phase8Evidence -Force | Out-Null
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class OpenAriseWindowObservation {
  [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr handle);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr handle, out Rect rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr handle, IntPtr dc, uint flags);
}
"@
$phase8DpiContext=[OpenAriseWindowObservation]::SetThreadDpiAwarenessContext([IntPtr](-4))
$phase8Processes=@(Get-CimInstance Win32_Process | Where-Object {$_.ExecutablePath -eq $phase8Exe})
$phase8Main=@($phase8Processes | Where-Object {$_.CommandLine -notmatch '--type='})
if($phase8Main.Count -ne 1){throw ('Expected exactly one main process; got '+$phase8Main.Count)}
$phase8Visible=@()
for($phase8Attempt=0;$phase8Attempt -lt 60;$phase8Attempt++){
  $phase8Visible=@()
  foreach($phase8Process in $phase8Processes){
    $phase8Native=Get-Process -Id $phase8Process.ProcessId -ErrorAction SilentlyContinue
    if($phase8Native){$phase8Native.Refresh(); if($phase8Native.MainWindowHandle -ne 0 -and [OpenAriseWindowObservation]::IsWindowVisible($phase8Native.MainWindowHandle)){$phase8Visible+=$phase8Native}}
  }
  if($phase8Visible.Count -gt 0){break}
  Start-Sleep -Milliseconds 500
}
if($phase8Visible.Count -ne 1){throw ('Expected exactly one visible native main window; got '+$phase8Visible.Count)}
$phase8Window=$phase8Visible[0]
if($phase8Window.MainWindowTitle -ne 'OpenArise'){throw ('Wrong window title: '+$phase8Window.MainWindowTitle)}
$phase8Rect=New-Object OpenAriseWindowObservation+Rect
if(-not [OpenAriseWindowObservation]::GetWindowRect($phase8Window.MainWindowHandle,[ref]$phase8Rect)){throw 'Window rectangle unavailable'}
$phase8Bitmap=New-Object Drawing.Bitmap (($phase8Rect.Right-$phase8Rect.Left),($phase8Rect.Bottom-$phase8Rect.Top))
$phase8Graphics=[Drawing.Graphics]::FromImage($phase8Bitmap)
$phase8DC=$phase8Graphics.GetHdc()
try{$phase8Captured=[OpenAriseWindowObservation]::PrintWindow($phase8Window.MainWindowHandle,$phase8DC,2)}finally{$phase8Graphics.ReleaseHdc($phase8DC)}
$phase8Screenshot=Join-Path $phase8Evidence 'native-window.png'
if($phase8Captured){$phase8Bitmap.Save($phase8Screenshot,[Drawing.Imaging.ImageFormat]::Png)}
$phase8Graphics.Dispose();$phase8Bitmap.Dispose()
$phase8Result=[pscustomobject]@{status='VERIFIED';mainProcessCount=$phase8Main.Count;visibleWindowCount=$phase8Visible.Count;rendererProcessCount=@($phase8Processes | Where-Object {$_.CommandLine -match '--type=renderer'}).Count;title=$phase8Window.MainWindowTitle;processId=$phase8Window.Id;executable=$phase8Exe;commandLine=$phase8Main[0].CommandLine;captureSucceeded=$phase8Captured;screenshot=$phase8Screenshot}
$phase8Result | ConvertTo-Json -Depth 3 | Set-Content (Join-Path $phase8Evidence 'launch.json')
$phase8Result | ConvertTo-Json -Depth 3