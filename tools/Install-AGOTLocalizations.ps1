param(
	[string]$GameDataPath = 'C:\Users\RUSBAR\Documents\Paradox Interactive\Crusader Kings III',
	[switch]$Apply
)
. (Join-Path $PSScriptRoot 'RepositoryText.ps1')


$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'LauncherSqlite.ps1')
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$dataRoot = [IO.Path]::GetFullPath($GameDataPath)
$databasePath = Join-Path $dataRoot 'launcher-v2.sqlite'
$loadPath = Join-Path $dataRoot 'dlc_load.json'
$modDirectory = Join-Path $dataRoot 'mod'
$utf8 = [Text.UTF8Encoding]::new($false, $true)

function Sql([string]$Value) { return "'" + $Value.Replace("'", "''") + "'" }
function Attribute([string]$Descriptor, [string]$Name) {
	$match = [regex]::Match($Descriptor, '(?m)^' + [regex]::Escape($Name) + '="([^"]+)"\s*$')
	if (-not $match.Success) { throw "Missing descriptor attribute: $Name" }
	return $match.Groups[1].Value
}
function Require-ClosedLauncher {
	$running = @(Get-Process | Where-Object { $_.ProcessName -match '^(ck3|dowser|Paradox Launcher|Paradox Launcher Helper)$' })
	if ($running.Count) { throw 'Close CK3 and the Paradox launcher before applying changes.' }
	foreach ($suffix in @('-wal', '-journal')) {
		$sidecar = $databasePath + $suffix
		if ((Test-Path -LiteralPath $sidecar) -and (Get-Item -LiteralPath $sidecar).Length -gt 0) {
			throw "Active SQLite journal found: $sidecar. Close the launcher first."
		}
	}
}

$load = Get-Content -LiteralPath $loadPath -Raw -Encoding UTF8 | ConvertFrom-Json
$mods = [Collections.Generic.List[object]]::new()
foreach ($filename in @('AGOT_RUS_CORRECT.mod', 'AGOT_SUBMOD_CORE_RUS.mod')) {
	$source = Join-Path $repoRoot ('AGOT_Submods/' + $filename)
	$descriptor = [IO.File]::ReadAllText($source, $utf8)
	$directory = [IO.Path]::GetFullPath((Attribute $descriptor 'path'))
	if (-not $directory.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "Unexpected mod root: $directory" }
	$internal = Join-Path $directory 'descriptor.mod'
	$internalText = [IO.File]::ReadAllText($internal, $utf8)
	$name = Attribute $descriptor 'name'
	if ((Attribute $internalText 'name') -cne $name) { throw "Descriptor name mismatch: $source" }
	$tagsBlock = [regex]::Match($descriptor, '(?s)tags\s*=\s*\{(.*?)\}').Groups[1].Value
	$tags = @([regex]::Matches($tagsBlock, '"([^"]+)"') | ForEach-Object { $_.Groups[1].Value })
	$mods.Add([pscustomobject]@{
		File=$filename; Registry=('mod/' + $filename); Source=$source; Directory=$directory; Name=$name
		Version=(Attribute $descriptor 'version'); RequiredVersion=(Attribute $descriptor 'supported_version')
		Tags=(ConvertTo-Json -InputObject $tags -Compress); Id=$null
	})
}

# Plan using a read-only connection. Keep all existing entries and their enabled
# flags, and place these two localizations at the end of the active AGOT playset.
$db = [Ck3LauncherDatabase]::new($databasePath, $false)
try {
	$active = $db.Query('SELECT id,name FROM playsets WHERE isActive=1 AND isRemoved=0')
	if ($active.Count -ne 1 -or $active[0]['name'] -cne 'AGOT-RUSBAR') { throw 'Expected the active AGOT-RUSBAR playset.' }
	$playsetId = $active[0]['id']
	$rows = $db.Query('SELECT pm.modId,pm.enabled,pm.position,m.gameRegistryId,m.displayName FROM playsets_mods pm JOIN mods m ON m.id=pm.modId WHERE pm.playsetId=' + (Sql $playsetId) + ' ORDER BY pm.position')
	$enabled = @($rows | Where-Object { $_['enabled'] -eq '1' } | ForEach-Object { $_['gameRegistryId'] })
	if (($enabled -join "`n") -cne (@($load.enabled_mods) -join "`n")) { throw 'Launcher and dlc_load.json disagree; review before changing either.' }
	foreach ($required in @('mod/ugc_2962333032.mod', 'mod/ugc_2962803371.mod', 'mod/ugc_3034473189.mod')) {
		if ($enabled -cnotcontains $required) { throw "Required mod is disabled: $required" }
	}
	foreach ($mod in $mods) {
		$existing = $db.Query('SELECT id,source FROM mods WHERE gameRegistryId=' + (Sql $mod.Registry))
		if ($existing.Count -gt 1 -or ($existing.Count -eq 1 -and $existing[0]['source'] -ne 'local')) { throw "Conflicting registry entry: $($mod.Registry)" }
		$mod.Id = if ($existing.Count) { $existing[0]['id'] } else { [Guid]::NewGuid().ToString() }
	}
} finally { $db.Dispose() }

$registries = @($mods | ForEach-Object Registry)
$ordered = [Collections.Generic.List[object]]::new()
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($row in $rows) {
	if (-not $seen.Add($row['modId'])) { throw 'Duplicate playset entries found.' }
	if ($registries -ccontains $row['gameRegistryId']) { continue }
	$ordered.Add([pscustomobject]@{ Id=$row['modId']; Registry=$row['gameRegistryId']; Name=$row['displayName']; Enabled=[int]$row['enabled'] })
}
foreach ($mod in $mods) { $ordered.Add([pscustomobject]@{ Id=$mod.Id; Registry=$mod.Registry; Name=$mod.Name; Enabled=1 }) }
$newEnabled = @($ordered | Where-Object Enabled -eq 1 | ForEach-Object Registry)
$plan = [ordered]@{
	Playset=$active[0]['name']; GameDataPath=$dataRoot; Apply=[bool]$Apply
	Mods=@($mods | Select-Object Name,Registry,Directory); EnabledOrder=@($ordered | Where-Object Enabled -eq 1 | ForEach-Object Name)
}
if (-not $Apply) { $plan | ConvertTo-Json -Depth 5; return }

Require-ClosedLauncher
$backup = Join-Path $dataRoot ('mod_backups/AGOT_localizations_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [Guid]::NewGuid().ToString('N').Substring(0,8))
[IO.Directory]::CreateDirectory($backup) | Out-Null
Copy-Item -LiteralPath $databasePath -Destination (Join-Path $backup 'launcher-v2.sqlite')
Copy-Item -LiteralPath $loadPath -Destination (Join-Path $backup 'dlc_load.json')
$previousDescriptors = @{}
foreach ($mod in $mods) {
	$target = Join-Path $modDirectory $mod.File
	$previousDescriptors[$mod.File] = Test-Path -LiteralPath $target
	if ($previousDescriptors[$mod.File]) { Copy-Item -LiteralPath $target -Destination (Join-Path $backup $mod.File) }
}
$db = [Ck3LauncherDatabase]::new($databasePath, $true)
$transaction = $false
$committed = $false
try {
	$db.Execute('PRAGMA foreign_keys=ON')
	$db.Execute('BEGIN IMMEDIATE')
	$transaction = $true
	$timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
	foreach ($mod in $mods) {
		$exists = $db.Query('SELECT id FROM mods WHERE id=' + (Sql $mod.Id))
		if ($exists.Count -eq 0) {
			$db.Execute('INSERT INTO mods (id,gameRegistryId,displayName,version,requiredVersion,dirPath,status,source,tags,createdDate,timeUpdated,isNew) VALUES (' +
				((@((Sql $mod.Id),(Sql $mod.Registry),(Sql $mod.Name),(Sql $mod.Version),(Sql $mod.RequiredVersion),(Sql $mod.Directory),"'ready_to_play'","'local'",(Sql $mod.Tags),[string]$timestamp,[string]$timestamp,'0')) -join ',') + ')')
		} else {
			$db.Execute('UPDATE mods SET displayName=' + (Sql $mod.Name) + ',version=' + (Sql $mod.Version) + ',requiredVersion=' + (Sql $mod.RequiredVersion) +
				',dirPath=' + (Sql $mod.Directory) + ',tags=' + (Sql $mod.Tags) + ",status='ready_to_play',timeUpdated=" + $timestamp + ' WHERE id=' + (Sql $mod.Id))
		}
	}
	for ($i=0; $i -lt $ordered.Count; $i++) {
		$row = $ordered[$i]
		$where = 'playsetId=' + (Sql $playsetId) + ' AND modId=' + (Sql $row.Id)
		$existing = $db.Query('SELECT modId FROM playsets_mods WHERE ' + $where)
		if ($existing.Count) { $db.Execute('UPDATE playsets_mods SET position=' + $i + ',enabled=' + $row.Enabled + ' WHERE ' + $where) }
		else { $db.Execute('INSERT INTO playsets_mods (playsetId,modId,enabled,position) VALUES (' + (Sql $playsetId) + ',' + (Sql $row.Id) + ',' + $row.Enabled + ',' + $i + ')') }
	}
	# Launcher playset timestamps use milliseconds; mod timestamps use seconds.
	$db.Execute("UPDATE playsets SET loadOrder='custom',updatedOn=" + ($timestamp * 1000) + ' WHERE id=' + (Sql $playsetId))
	foreach ($mod in $mods) { Copy-Item -LiteralPath $mod.Source -Destination (Join-Path $modDirectory $mod.File) -Force }
	$load.enabled_mods = $newEnabled
	[RepositoryText]::WriteAllText($loadPath, ($load | ConvertTo-Json -Compress -Depth 10), $utf8)
	$actual = @($db.Query('SELECT m.gameRegistryId FROM playsets_mods pm JOIN mods m ON m.id=pm.modId WHERE pm.enabled=1 AND pm.playsetId=' + (Sql $playsetId) + ' ORDER BY pm.position') | ForEach-Object { $_['gameRegistryId'] })
	$savedLoad = Get-Content -LiteralPath $loadPath -Raw -Encoding UTF8 | ConvertFrom-Json
	if (($actual -join "`n") -cne ($newEnabled -join "`n") -or (@($savedLoad.enabled_mods) -join "`n") -cne ($newEnabled -join "`n")) { throw 'Installed load order verification failed.' }
	if ($db.Query('PRAGMA quick_check')[0]['quick_check'] -cne 'ok' -or $db.Query('PRAGMA foreign_key_check').Count -ne 0) { throw 'SQLite integrity check failed.' }
	$db.Execute('COMMIT')
	$committed = $true
} catch {
	if ($transaction -and -not $committed) { $db.Execute('ROLLBACK') }
	Copy-Item -LiteralPath (Join-Path $backup 'dlc_load.json') -Destination $loadPath -Force
	foreach ($mod in $mods) {
		$target = Join-Path $modDirectory $mod.File
		if ($previousDescriptors[$mod.File]) { Copy-Item -LiteralPath (Join-Path $backup $mod.File) -Destination $target -Force }
		elseif (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target }
	}
	throw
} finally { $db.Dispose() }
$plan['Backup'] = $backup
$plan['Result'] = 'Registered in launcher and enabled in the active playset and dlc_load.json.'
$plan | ConvertTo-Json -Depth 5
