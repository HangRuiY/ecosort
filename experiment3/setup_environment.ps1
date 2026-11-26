param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Creating the Python 3.12 environment failed.' }
}
$env:PIP_CACHE_DIR = Join-Path $PSScriptRoot '.pip-cache'
& './.venv/Scripts/python.exe' -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip setup failed.' }
& './.venv/Scripts/python.exe' -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) { throw 'CUDA PyTorch installation failed.' }
& './.venv/Scripts/python.exe' -m pip install -r requirements-lock.txt --extra-index-url https://pypi.nvidia.com --extra-index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE -ne 0) { throw 'Experiment dependencies installation failed.' }
& './.venv/Scripts/python.exe' -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency verification failed.' }
