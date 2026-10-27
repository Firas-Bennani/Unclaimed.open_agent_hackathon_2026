# Windows equivalent of `make eval` (pass e.g. -- --limit 20)
$root = Split-Path -Parent $PSScriptRoot
python "$root\eval\run.py" @args
