# Windows equivalent of `make demo`: build the UI, then serve the replay-mode demo on http://localhost:8000
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\frontend"
if (-not (Test-Path node_modules)) { npm install }
npm run build
Pop-Location
python "$root\scripts\demo.py"
