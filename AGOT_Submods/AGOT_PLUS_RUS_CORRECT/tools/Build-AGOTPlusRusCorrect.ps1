param(
	[string]$MainModPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2950245430',
	[string]$TranslationPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3465601037'
)
. (Join-Path $PSScriptRoot '../../../tools/RepositoryText.ps1')


$ErrorActionPreference = 'Stop'
$modRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$auditRoot = [IO.Path]::GetFullPath((Join-Path $modRoot '../../docs/reports/agot-plus-russian-2026-09-18'))
$utf8 = [Text.UTF8Encoding]::new($true, $true)
$pattern = [regex]'^(?<prefix>[ \t]*(?<key>[^\s#":]+):[ \t]*(?:\d+[ \t]*)?")(?<text>.*)(?<suffix>"[ \t]*(?:#.*)?)$'
$overlayPath = 'localization/replace/russian/zzzz_agot_plus_rus_correct_l_russian.yml'
$patch = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
foreach ($line in [IO.File]::ReadAllLines((Join-Path $modRoot $overlayPath), $utf8)) {
	$entry = $pattern.Match($line)
	if ($entry.Success) { $patch.Add($entry.Groups['key'].Value, $entry.Groups['text'].Value) }
}
if ($patch.Count -ne 33) { throw 'Expected the 33 reviewed Russian overrides.' }

$additionsPath = Join-Path $modRoot 'docs/runtime-localization-additions.json'
$additions = Get-Content -LiteralPath $additionsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$workshopRoot = Split-Path -Parent $MainModPath
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $modRoot '../..'))
foreach ($source in $additions.Sources) {
	$path = if ($source.Path.StartsWith('workshop/')) {
		Join-Path $workshopRoot $source.Path.Substring(9)
	} elseif ($source.Path.StartsWith('repository/')) {
		Join-Path $repositoryRoot $source.Path.Substring(11)
	} else { throw "Unknown additions source: $($source.Path)" }
	if ((Get-FileHash -LiteralPath $path).Hash -cne $source.SHA256) { throw "Runtime name source changed: $path. Review before rebuilding." }
}
$addedKeys = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$addedLines = @('l_russian:', ' # Generated from docs/runtime-localization-additions.json.')
foreach ($entry in $additions.Entries) {
	if (-not $addedKeys.Add($entry.Key) -or $patch.ContainsKey($entry.Key)) { throw "Duplicate added key: $($entry.Key)" }
	if ($entry.Value -match '["\r\n]' -or [string]::IsNullOrWhiteSpace($entry.Value)) { throw "Invalid added value: $($entry.Key)" }
	$addedLines += ' ' + $entry.Key + ':0 "' + $entry.Value + '"'
}
if ($addedKeys.Count -ne 386) { throw 'Expected 386 reviewed runtime names.' }

# Reject changed sources before producing any files. These hashes cover the
# complete audit, including definitions that could conflict with the overlay.
$coverage = @(Import-Csv -LiteralPath (Join-Path $auditRoot 'file-coverage.csv'))
foreach ($pair in $coverage) {
	foreach ($source in @(
		@{ Root=$MainModPath; File=$pair.MainFile; Hash=$pair.MainSHA256 },
		@{ Root=$TranslationPath; File=$pair.TranslationFile; Hash=$pair.TranslationSHA256 }
	)) {
		$path = Join-Path $source.Root $source.File
		if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -cne $source.Hash) {
			throw "Upstream changed since the audit: $path. Review before rebuilding."
		}
	}
}

$englishRepairs = @{
	'the_bog_min_combat_roll' = '[command_modifier_i|E]Minimum [combat_roll|E] in the Bog'
	'lp_feudal_government_desc' = 'AppendFormatEnd'
	'setting_asoiaf_targaryen_invasion_claimants_dragon_bonded' = 'AppendFormatEnd'
	'asoiaf_Targaryen_61_1_modifier' = 'AppendFormatEnd'
	'asoiaf_Tully_5_modifier' = '[asoiaf_canon_children_concept|E]: #bold Lady Stoneheart#!'
}
$outputs = [Collections.Generic.List[object]]::new()
$englishChanged = 0
$russianChanged = 0
foreach ($source in @(
	@{ Label='Translation'; Root=$TranslationPath; Column='TranslationFile' },
	@{ Label='AGOT+'; Root=$MainModPath; Column='MainFile' }
)) {
	foreach ($pair in $coverage) {
		$relative = $pair.($source.Column)
		$isRussian = $source.Label -eq 'Translation'
		if ($isRussian -and -not $relative.StartsWith('localization/replace/')) { continue }
		$path = Join-Path $source.Root $relative
		$lines = [regex]::Split([IO.File]::ReadAllText($path, $utf8), '(?<=\n)')
		$changes = [Collections.Generic.List[object]]::new()
		for ($i = 0; $i -lt $lines.Length; $i++) {
			$before = $lines[$i].TrimEnd([char[]]"`r`n")
			$ending = $lines[$i].Substring($before.Length)
			$entry = $pattern.Match($before)
			$after = $null
			$key = ''
			if ($entry.Success) {
				$key = $entry.Groups['key'].Value
				$value = $entry.Groups['text'].Value
				if ($isRussian -and $patch.ContainsKey($key) -and $value -cne $patch[$key]) {
					$after = $entry.Groups['prefix'].Value + $patch[$key] + $entry.Groups['suffix'].Value
					$russianChanged++
				} elseif (-not $isRussian -and $englishRepairs.ContainsKey($key)) {
					$replacement = if ($englishRepairs[$key] -eq 'AppendFormatEnd') { $value + '#!' } else { $englishRepairs[$key] }
					$after = $entry.Groups['prefix'].Value + $replacement + $entry.Groups['suffix'].Value
					$englishChanged++
				}
			} elseif (-not $isRussian -and $before -ceq ' the_bog_min_combat_roll:1 "') {
				$key = 'the_bog_min_combat_roll'
				$after = ' the_bog_min_combat_roll:1 "' + $englishRepairs[$key] + '"'
				$englishChanged++
			}
			if ($null -ne $after) {
				$changes.Add([pscustomobject]@{ Line=($i+1); Key=$key; Before=$before; After=$after })
				$lines[$i] = $after + $ending
			}
		}
		if ($changes.Count) {
			$outputs.Add([pscustomobject]@{
				Catalog=$source.Label; File=$relative; SourceSHA256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
				Changes=@($changes.ToArray()); Content=[string]::Concat($lines)
			})
		}
	}
}
if ($englishChanged -ne 5 -or $russianChanged -ne 3 -or $outputs.Count -ne 6) { throw 'Unexpected shadow coverage.' }

# Same-path files replace malformed English input before parsing. Matching
# Russian replacement files share the overlay values regardless of file order.
$manifestFiles = @()
foreach ($output in $outputs) {
	$destination = Join-Path $modRoot $output.File
	[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination)) | Out-Null
	[RepositoryText]::WriteAllText($destination, $output.Content, $utf8)
	$manifestFiles += [pscustomobject]@{
		Catalog=$output.Catalog; File=$output.File; SourceSHA256=$output.SourceSHA256
		PatchedSHA256=(Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash; Changes=$output.Changes
	}
}
$addedDestination = Join-Path $modRoot $additions.Output
[RepositoryText]::WriteAllText($addedDestination, ($addedLines -join "`n") + "`n", $utf8)
$manifest = [ordered]@{
	AGOTPlusVersion='1.0.0'; TranslationVersion='1.1'; CK3Version='1.19.0.6'
	MainWorkshopId='2950245430'; TranslationWorkshopId='3465601037'
	Overlay=$overlayPath; OverlayKeys=$patch.Count
	OverlaySHA256=(Get-FileHash -LiteralPath (Join-Path $modRoot $overlayPath) -Algorithm SHA256).Hash
	RuntimeNames=[ordered]@{
		File=$additions.Output; Keys=$addedKeys.Count; Counts=$additions.Counts
		SHA256=(Get-FileHash -LiteralPath $addedDestination).Hash
		Definitions='docs/runtime-localization-additions.json'
		DefinitionsSHA256=(Get-FileHash -LiteralPath $additionsPath).Hash
		SourceFiles=$additions.Sources.Count
	}
	EnglishRepairs=$englishChanged; RussianReplacementRepairs=$russianChanged; Files=$manifestFiles
}
[IO.Directory]::CreateDirectory((Join-Path $modRoot 'docs')) | Out-Null
[RepositoryText]::WriteAllText((Join-Path $modRoot 'docs/source-manifest.json'), ($manifest | ConvertTo-Json -Depth 8) + "`n", $utf8)
Write-Output "Built: 33 Russian overrides; 386 runtime names; 6 file shadows; 5 English repairs; 3 synchronized Russian replacements."
