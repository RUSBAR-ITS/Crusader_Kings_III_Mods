param(
	[string]$GameDataPath = 'C:\Users\RUSBAR\Documents\Paradox Interactive\Crusader Kings III',
	[string]$Query = "SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'LauncherSqlite.ps1')
$db = [Ck3LauncherDatabase]::new((Join-Path $GameDataPath 'launcher-v2.sqlite'), $false)
try { $db.Query($Query) | ConvertTo-Json -Depth 6 }
finally { $db.Dispose() }
