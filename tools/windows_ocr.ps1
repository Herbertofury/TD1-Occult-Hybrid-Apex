# Local Windows OCR only. Input is a bounded JSON object over stdin; no network.
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
$null = [Windows.Storage.FileAccessMode,Windows.Storage,ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult,Windows.Foundation,ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language,Windows.Globalization,ContentType=WindowsRuntime]
$apexAsTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and
    $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
function Complete-ApexOperation($Operation, $ResultType) {
    $apexTask = $apexAsTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    if (-not $apexTask.Wait(10000)) { throw 'Windows OCR operation timed out.' }
    return $apexTask.Result
}
$apexRequest = [Console]::In.ReadToEnd() | ConvertFrom-Json
$apexPath = [System.IO.Path]::GetFullPath($apexRequest.path)
$apexFile = Complete-ApexOperation ([Windows.Storage.StorageFile]::GetFileFromPathAsync($apexPath)) ([Windows.Storage.StorageFile])
$apexStream = Complete-ApexOperation ($apexFile.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
try {
    $apexDecoder = Complete-ApexOperation ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($apexStream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    if ($apexDecoder.PixelWidth -gt [Windows.Media.Ocr.OcrEngine]::MaxImageDimension -or
        $apexDecoder.PixelHeight -gt [Windows.Media.Ocr.OcrEngine]::MaxImageDimension) { throw 'Image exceeds native OCR dimension bound.' }
    $apexBitmap = Complete-ApexOperation ($apexDecoder.GetSoftwareBitmapAsync(
        [Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8, [Windows.Graphics.Imaging.BitmapAlphaMode]::Ignore)) ([Windows.Graphics.Imaging.SoftwareBitmap])
    try {
        $apexEngine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new('en-US'))
        if ($null -eq $apexEngine) { throw 'English Windows OCR is unavailable.' }
        $apexResult = Complete-ApexOperation ($apexEngine.RecognizeAsync($apexBitmap)) ([Windows.Media.Ocr.OcrResult])
        $apexLines = @($apexResult.Lines | ForEach-Object {
            @{ text=$_.Text; words=@($_.Words | ForEach-Object {
                @{ text=$_.Text; x=$_.BoundingRect.X; y=$_.BoundingRect.Y; width=$_.BoundingRect.Width; height=$_.BoundingRect.Height }
            }) }
        })
        @{ ok=$true; width=$apexDecoder.PixelWidth; height=$apexDecoder.PixelHeight; lines=$apexLines } | ConvertTo-Json -Depth 6 -Compress
    } finally { $apexBitmap.Dispose() }
} finally { $apexStream.Dispose() }
