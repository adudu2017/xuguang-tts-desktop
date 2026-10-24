$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python -m PyInstaller --noconfirm VoiceDesk.spec
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
    Copy-Item -Path *.py -Destination dist/VoiceDesk -Force
    Copy-Item -Path assets -Destination dist/VoiceDesk -Recurse -Force
    Write-Host 'Built dist/VoiceDesk. Configure separate engine environments and models before synthesis.'
} finally { Pop-Location }
