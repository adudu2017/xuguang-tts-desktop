param([ValidateSet('Qwen','Ming','Both')][string]$Engine='Both', [switch]$DownloadModels)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
function Run([string]$exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $exe (exit $LASTEXITCODE)" }
}
New-Item -ItemType Directory -Force -Path "$root\runtime", "$root\models" | Out-Null
foreach ($name in @('Qwen','Ming')) {
    if ($Engine -ne 'Both' -and $Engine -ne $name) { continue }
    $envDir = "$root\runtime\$($name.ToLower())"
    if (-not (Test-Path "$envDir\Scripts\python.exe")) { Run 'python' @('-m','venv',$envDir) }
    $py = "$envDir\Scripts\python.exe"
    Run $py @('-m','pip','install','--upgrade','pip','--index-url','https://pypi.org/simple')
    Run $py @('-m','pip','install','torch==2.5.1','torchaudio==2.5.1','--index-url','https://download.pytorch.org/whl/cu124')
    if ($name -eq 'Qwen') {
        Run $py @('-m','pip','install','qwen-tts==0.1.1','modelscope','numpy==1.26.4','librosa==0.11.0','scipy==1.13.1','scikit-learn==1.5.1','numba==0.61.2','--index-url','https://pypi.org/simple')
    } else {
        $src = "$root\runtime\Ming-3.0-tts"
        if (-not (Test-Path $src)) { Run 'git' @('clone','https://github.com/inclusionAI/Ming-3.0-tts.git',$src) }
        Run 'git' @('-C',$src,'checkout','028c1eace193e7acdb256453da89b6e9207e052b')
        Run $py @('-m','pip','install','-r',"$src\requirements.txt",'modelscope','--index-url','https://pypi.org/simple')
    }
    if ($DownloadModels) { Run $py @("$root\download-models.py",$name,"$root\models") }
}
Write-Host 'Completed. Open engine settings and select runtime Python executables and local model directories.'
