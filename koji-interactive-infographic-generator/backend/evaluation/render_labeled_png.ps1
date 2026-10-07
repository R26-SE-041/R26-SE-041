param(
    [Parameter(Mandatory = $true)][string]$ImagePath,
    [Parameter(Mandatory = $true)][string]$AnnotationsPath,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = "Stop"
trap {
    Write-Error ("{0} at line {1}: {2}" -f $_.Exception.Message, $_.InvocationInfo.ScriptLineNumber, $_.InvocationInfo.Line)
    exit 1
}
Add-Type -AssemblyName System.Drawing

function New-RoundedRectanglePath {
    param([float]$X, [float]$Y, [float]$Width, [float]$Height, [float]$Radius)
    $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
    $diameter = $Radius * 2
    $path.AddArc($X, $Y, $diameter, $diameter, 180, 90)
    $path.AddArc($X + $Width - $diameter, $Y, $diameter, $diameter, 270, 90)
    $path.AddArc($X + $Width - $diameter, $Y + $Height - $diameter, $diameter, $diameter, 0, 90)
    $path.AddArc($X, $Y + $Height - $diameter, $diameter, $diameter, 90, 90)
    $path.CloseFigure()
    return $path
}

$sourceBytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $ImagePath))
$stream = [System.IO.MemoryStream]::new($sourceBytes)
$source = [System.Drawing.Image]::FromStream($stream)
$canvas = [System.Drawing.Bitmap]::new(1000, 1000, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$graphics = [System.Drawing.Graphics]::FromImage($canvas)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$graphics.Clear([System.Drawing.Color]::White)
$graphics.DrawImage($source, 0, 0, 1000, 1000)

$annotations = Get-Content -Raw -LiteralPath $AnnotationsPath | ConvertFrom-Json
$linePen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(8, 145, 178), 2)
$anchorBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(6, 182, 212))
$boxBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(240, 8, 51, 68))
$textBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
$font = [System.Drawing.Font]::new("Arial", 17, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)

foreach ($item in $annotations) {
    if ($item.verified -ne $true) { continue }
    $anchorX = [float]$item.anchor_x * 1000
    $anchorY = [float]$item.anchor_y * 1000
    $labelX = [float]$item.label_x * 1000
    $labelY = [float]$item.label_y * 1000
    $label = [string]$item.label
    $labelWidth = [Math]::Min(270, [Math]::Max(110, $label.Length * 10 + 28))
    $lineEndX = if ($labelX -lt $anchorX) { $labelX + $labelWidth } else { $labelX }
    $graphics.DrawLine($linePen, $anchorX, $anchorY, $lineEndX, $labelY)
    $graphics.FillEllipse($anchorBrush, $anchorX - 6, $anchorY - 6, 12, 12)
    $graphics.FillEllipse($anchorBrush, $lineEndX - 3, $labelY - 3, 6, 6)
    $boxPath = New-RoundedRectanglePath -X $labelX -Y ($labelY - 18) -Width $labelWidth -Height 36 -Radius 8
    $graphics.FillPath($boxBrush, $boxPath)
    $graphics.DrawString($label, $font, $textBrush, $labelX + 14, $labelY - 11)
    $boxPath.Dispose()
}

$outputDirectory = Split-Path -Parent $OutputPath
if ($outputDirectory) { [System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null }
$canvas.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)

$font.Dispose()
$textBrush.Dispose()
$boxBrush.Dispose()
$anchorBrush.Dispose()
$linePen.Dispose()
$graphics.Dispose()
$canvas.Dispose()
$source.Dispose()
$stream.Dispose()
