# Windows equivalent of `make test`
$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\backend"
python -m pytest -q
$code = $LASTEXITCODE
Pop-Location
exit $code
