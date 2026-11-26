param([string]$DocumentPath = '', [string]$OutputDirectory = '')
$ErrorActionPreference = 'Stop'
$inputDocument = if ($DocumentPath) { [System.IO.Path]::GetFullPath($DocumentPath) } else { Join-Path $PSScriptRoot 'reports/实验三报告_循智EcoSort.docx' }
$qaDirectory = if ($OutputDirectory) { [System.IO.Path]::GetFullPath($OutputDirectory) } else { Join-Path $PSScriptRoot 'reports/qa' }
New-Item -ItemType Directory -Force -Path $qaDirectory | Out-Null
$outputPdf = Join-Path $qaDirectory 'report_render.pdf'
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($inputDocument, $false, $true)
    $document.ExportAsFixedFormat($outputPdf, 17)
    Write-Output $outputPdf
} finally {
    if ($null -ne $document) { $document.Close(0); [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) }
    if ($null -ne $word) { $word.Quit(); [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) }
}
