param(
	[string]$MainModPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3149692324',
	[string]$TranslationPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3518584623'
)

$ErrorActionPreference = 'Stop'
$modRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$auditRoot = [IO.Path]::GetFullPath((Join-Path $modRoot '../../docs/reports/agot-bookmarked-russian-2026-09-18'))
$utf8 = [Text.UTF8Encoding]::new($true, $true)
$pattern = [regex]'^(?<prefix>[ \t]*(?<key>[^\s#":]+):[ \t]*(?:\d+[ \t]*)?")(?<text>.*)(?<suffix>"[ \t]*(?:#.*)?)$'
$prefixPattern = [regex]'^(?<prefix>[ \t]*(?<key>[^\s#":]+):[ \t]*(?:\d+[ \t]*)?")(?<text>.*)$'
$overlayPath = 'localization/replace/russian/zzzz_agot_bookmarked_rus_correct_l_russian.yml'
$newDescriptions = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
$authored = Get-Content -LiteralPath (Join-Path $modRoot 'docs/new-descriptions.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($property in $authored.PSObject.Properties) { $newDescriptions.Add($property.Name, $property.Value) }
if ($newDescriptions.Count -ne 4) { throw 'Expected four authored descriptions.' }

function Replace-Required([string]$Text, [string]$Before, [string]$After) {
	if (-not $Text.Contains($Before)) { throw "Expected source fragment missing: $Before" }
	return $Text.Replace($Before, $After)
}

# Verify all six sources before generating any output.
$coverage = @(Import-Csv -LiteralPath (Join-Path $auditRoot 'file-coverage.csv'))
foreach ($pair in $coverage) {
	foreach ($source in @(
		@{ Root=$MainModPath; File=$pair.MainFile; Hash=$pair.MainSHA256 },
		@{ Root=$TranslationPath; File=$pair.TranslationFile; Hash=$pair.TranslationSHA256 }
	)) {
		$path = Join-Path $source.Root $source.File
		if ((Get-FileHash -LiteralPath $path).Hash -cne $source.Hash) { throw "Upstream changed since the audit: $path" }
	}
}

$patch = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
$outputs = @()
$joinedDescriptions = 0
foreach ($pair in $coverage) {
	$relative = $pair.TranslationFile
	$sourcePath = Join-Path $TranslationPath $relative
	$lines = [regex]::Split([IO.File]::ReadAllText($sourcePath, $utf8), '(?<=\n)')
	$changes = [Collections.Generic.List[object]]::new()
	for ($i = 0; $i -lt $lines.Length; $i++) {
		$before = $lines[$i].TrimEnd([char[]]"`r`n")
		$ending = $lines[$i].Substring($before.Length)
		$entry = $pattern.Match($before)
		$joined = $false
		if (-not $entry.Success) {
			$prefix = $prefixPattern.Match($before)
			if (-not $prefix.Success) { continue }
			if ($prefix.Groups['key'].Value -cnotin @('bookmark_298_joffrey_baratheon_desc', 'bookmark_299_joffrey_baratheon_desc')) { throw "Unexpected malformed entry: $relative" }
			$continuation = $lines[$i+1].TrimEnd([char[]]"`r`n")
			$entry = $pattern.Match($before + '\n\n' + $continuation)
			if (-not $entry.Success) { throw 'Cannot reconstruct the complete Joffrey description.' }
			# Keep a blank physical line so source line numbers stay stable.
			$changes.Add([pscustomobject]@{ Line=($i+2); Key=$prefix.Groups['key'].Value; Kind='JoinedContinuation'; Before=$continuation; After='' })
			$lines[$i+1] = $lines[$i+1].Substring($continuation.Length)
			$joinedDescriptions++
			$joined = $true
		}
		$key = $entry.Groups['key'].Value
		$original = $entry.Groups['text'].Value
		$value = $original
		if ($newDescriptions.ContainsKey($key)) {
			if ($value -cne '<insert imagination>') { throw "Expected placeholder missing: $key" }
			# JSON newlines become CK3 escape sequences, never physical value breaks.
			$value = $newDescriptions[$key].Replace("`r`n", "`n").Replace("`n", '\n')
		} else {
			switch -CaseSensitive ($key) {
				'agot_bm_7899_desc' {
					$value = Replace-Required $value '\n\Выжили' '\n\nВыжили'
					$value = Replace-Required $value '\n\Аурион' '\n\nАурион'
					$value = $value.Replace('Драконий камень', 'Драконий Камень').Replace('Валирии....', 'Валирии...')
				}
				'bookmark_99_arrec_durrandon_desc' { $value += '.' }
				'bookmark_99_aenar_targaryen_desc' { $value = Replace-Required $value 'Дейенис' 'Дейнис' }
				'bookmark_99_garland_gardener_desc' { $value = Replace-Required $value 'Гарднеров' 'Гарденеров' }
				'bookmark_129_aegon_targaryen_2_desc' {
					$value = Replace-Required $value 'Эйегона' 'Эйгона'
					$value = Replace-Required $value 'Бизбери,.' 'Бизбери.'
					$value = Replace-Required $value 'сэр Кристон' 'сир Кристон'
					$value = $value.Replace('\n\n Изначально', '\n\nИзначально')
				}
				'bookmark_195_daemon_blackfyre_desc' { $value = Replace-Required $value 'Дэймон' 'Деймон' }
				'bookmark_195_daeron_targaryen_desc' {
					$value = Replace-Required $value 'присоеденил' 'присоединил'
					$value = Replace-Required $value 'его  единокровный' 'его единокровный'
				}
				'bookmark_195_harys_bracken_desc' { $value = Replace-Required $value '"Жгучий Клинок"' '«Жгучий Клинок»' }
				'bookmark_299_walder_frey_desc' { $value = Replace-Required $value "Переправы,'Покойный Лорд'" 'Переправы, «Покойный Лорд»' }
				'bookmark_300_stannis_baratheon_desc' { $value = Replace-Required $value 'полон ужасов' 'полон ошибок' }
				{ $_ -cin @('bookmark_10_aegon_targaryen_desc', 'bookmark_129_aegon_targaryen_desc', 'bookmark_153_aegon_targaryen_desc', 'bookmark_178_aegon_targaryen_desc') } { $value += '#!' }
			}
		}
		if ($joined -or $value -cne $original) {
			$after = $entry.Groups['prefix'].Value + $value + $entry.Groups['suffix'].Value
			$changes.Add([pscustomobject]@{ Line=($i+1); Key=$key; Kind=$(if ($newDescriptions.ContainsKey($key)) { 'AuthoredDescription' } else { 'Correction' }); Before=$before; After=$after })
			$lines[$i] = $after + $ending
			$patch.Add($key, $value)
		}
	}
	if ($changes.Count) {
		$outputs += [pscustomobject]@{ File=$relative; SourceSHA256=$pair.TranslationSHA256; Changes=@($changes.ToArray()); Content=[string]::Concat($lines) }
	}
}
if ($patch.Count -ne 20 -or $joinedDescriptions -ne 2 -or $outputs.Count -ne 2) { throw 'Unexpected correction coverage.' }

$manifestFiles = @()
foreach ($output in $outputs) {
	$path = Join-Path $modRoot $output.File
	[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path)) | Out-Null
	[IO.File]::WriteAllText($path, $output.Content, $utf8)
	$manifestFiles += [pscustomobject]@{ File=$output.File; SourceSHA256=$output.SourceSHA256; PatchedSHA256=(Get-FileHash -LiteralPath $path).Hash; Changes=$output.Changes }
}
$overlay = @('l_russian:', ' # Generated by Build-AGOTBookmarkedRusCorrect.ps1; source details are in docs/source-manifest.json.')
foreach ($key in ($patch.Keys | Sort-Object -CaseSensitive)) { $overlay += ' ' + $key + ':0 "' + $patch[$key] + '"' }
$overlayFullPath = Join-Path $modRoot $overlayPath
[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($overlayFullPath)) | Out-Null
[IO.File]::WriteAllText($overlayFullPath, ($overlay -join "`n") + "`n", $utf8)
$manifest = [ordered]@{
	MainWorkshopId='3149692324'; MainVersion='1.0'; TranslationWorkshopId='3518584623'; TranslationVersion='1.1'; CK3Version='1.19.0.6'
	Overlay=$overlayPath; OverlayKeys=$patch.Count; OverlaySHA256=(Get-FileHash -LiteralPath $overlayFullPath).Hash
	AuthoredDescriptionKeys=@($newDescriptions.Keys | Sort-Object -CaseSensitive); JoinedDescriptions=$joinedDescriptions; Files=$manifestFiles
}
[IO.File]::WriteAllText((Join-Path $modRoot 'docs/source-manifest.json'), ($manifest | ConvertTo-Json -Depth 8) + "`n", $utf8)
Write-Output 'Built: 20 corrected Russian keys; 4 authored descriptions; 2 complete file shadows; 2 rejoined descriptions.'
