param(
	[string]$MainModPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2962333032',
	[string]$TranslationPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2962803371'
)

$ErrorActionPreference = 'Stop'
$modRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$utf8 = [Text.UTF8Encoding]::new($true, $true)
$pattern = [regex]'^(?<prefix>[ \t]*(?<key>[^\s#":]+):[ \t]*(?:\d+[ \t]*)?")(?<text>.*)(?<suffix>"[ \t]*(?:#.*)?)$'
$patch = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
$overlayPath = 'localization/replace/russian/zzzz_agot_rus_correct_l_russian.yml'
foreach ($line in [IO.File]::ReadAllLines((Join-Path $modRoot $overlayPath), $utf8)) {
	$entry = $pattern.Match($line)
	if ($entry.Success) { $patch.Add($entry.Groups['key'].Value, $entry.Groups['text'].Value) }
}
if ($patch.Count -eq 0) { throw 'The translation overlay is empty.' }
$runtimeRepairs = Get-Content -LiteralPath (Join-Path $modRoot 'docs/runtime-localization-repairs.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$seenRuntimeRepairs = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)

# Full-file shadows remove syntax errors before the engine parses upstream files.
# Existing localization/replace definitions also receive the same translations,
# so precedence between different replacement files cannot restore English text.
$repairs = @{
	'localization/replace/russian/agot/00_agot_titles_l_russian.yml' = @('b_jagjebaj')
	'localization/russian/agot/event_localization/decision_events/agot_events_decisions_l_russian.yml' = @('agot_decisions_events.0102.intro.sacrifice_child')
	'localization/russian/agot/triggers/agot_triggers_l_russian.yml' = @('IS_CURRENT_DRAGONRIDER_TRIGGER_THIRD')
	'localization/english/agot/event_localization/agot_septon_l_english.yml' = @('agot_septon_events.0001.t')
	'localization/english/agot/gui/agot_dragon_customizer_l_english.yml' = @('dragon_fire_smoke_value_de_gui_tt')
	'localization/replace/english/agot/00_agot_titles_l_english.yml' = @('b_jagjebaj')
	'localization/replace/english/gui/common_l_english.yml' = @('cooltip_spouse_listing', 'cooltip_betrothed_listing', 'cooltip_concubine_listing')
}
$sources = @(
	@{ Label='Translation'; Root=$TranslationPath; Language='russian' },
	@{ Label='AGOT'; Root=$MainModPath; Language='english' }
)
$outputs = [Collections.Generic.List[object]]::new()
$seenRepairs = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($source in $sources) {
	$root = [IO.Path]::GetFullPath($source.Root).TrimEnd('\', '/')
	$files = @(rg --files (Join-Path $root 'localization') -g "*_l_$($source.Language).yml" | Sort-Object)
	if ($LASTEXITCODE -ne 0) { throw "Cannot enumerate $root" }
	foreach ($file in $files) {
		$relative = $file.Substring($root.Length + 1).Replace('\', '/')
		$repairKeys = @($repairs[$relative]) | Where-Object { $_ }
		$runtimeForFile = @($runtimeRepairs | Where-Object File -CEQ $relative)
		$isReplacement = $source.Label -eq 'Translation' -and $relative.StartsWith('localization/replace/')
		if (-not $isReplacement -and $repairKeys.Count -eq 0 -and $runtimeForFile.Count -eq 0) { continue }
		$content = [IO.File]::ReadAllText($file, $utf8)
		$lines = [regex]::Split($content, '(?<=\n)')
		$changes = [Collections.Generic.List[object]]::new()
		for ($i = 0; $i -lt $lines.Length; $i++) {
			$before = $lines[$i].TrimEnd([char[]]"`r`n")
			$ending = $lines[$i].Substring($before.Length)
			$runtimeFix = @($runtimeForFile | Where-Object { $_.Line -eq ($i+1) })
			if ($runtimeFix.Count) {
				if ($runtimeFix.Count -ne 1 -or $before -cne $runtimeFix[0].Before) { throw "Runtime repair changed upstream: ${relative}:$($i+1)" }
				$fix = $runtimeFix[0]
				$fixedEntry = $pattern.Match($fix.After)
				if (-not $fixedEntry.Success -or $patch[$fix.Key] -cne $fixedEntry.Groups['text'].Value) { throw "Runtime repair / overlay mismatch: $($fix.Key)" }
				$changes.Add([pscustomobject]@{ Line=($i+1); Key=$fix.Key; Kind='RuntimeSyntax'; Before=$before; After=$fix.After })
				$lines[$i] = $fix.After + $ending
				$null = $seenRuntimeRepairs.Add($relative + ':' + $fix.Key)
				continue
			}
			$entry = $pattern.Match($before)
			if ($entry.Success) {
				$key = $entry.Groups['key'].Value
				if ($isReplacement -and $patch.ContainsKey($key) -and $entry.Groups['text'].Value -cne $patch[$key]) {
					$after = $entry.Groups['prefix'].Value + $patch[$key] + $entry.Groups['suffix'].Value
					$changes.Add([pscustomobject]@{ Line=($i+1); Key=$key; Kind='Translation'; Before=$before; After=$after })
					$lines[$i] = $after + $ending
				}
				continue
			}
			foreach ($key in $repairKeys) {
				if ($before -cmatch ('^\s*' + [regex]::Escape($key) + ':\s*(?:\d+\s*)?"[^"\r\n]*$')) {
					$after = $before + '"'
					$changes.Add([pscustomobject]@{ Line=($i+1); Key=$key; Kind='ClosingQuote'; Before=$before; After=$after })
					$lines[$i] = $after + $ending
					$null = $seenRepairs.Add($relative + ':' + $key)
				}
			}
		}
		if ($changes.Count -gt 0) {
			$outputs.Add([pscustomobject]@{
				Catalog=$source.Label; File=$relative; SourceSHA256=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash
				Changes=@($changes.ToArray()); Content=[string]::Concat($lines)
			})
		}
	}
}

# Fail before writing if an upstream update changes the audited repair locations.
if ($seenRuntimeRepairs.Count -ne $runtimeRepairs.Count) { throw 'Not all runtime localization repairs were applied.' }
foreach ($file in $repairs.Keys) {
	foreach ($key in $repairs[$file]) {
		if (-not $seenRepairs.Contains($file + ':' + $key)) { throw "Expected broken entry changed upstream: ${file}:$key. Review before rebuilding." }
	}
}
$manifestFiles = [Collections.Generic.List[object]]::new()
foreach ($output in $outputs) {
	$destination = Join-Path $modRoot $output.File
	[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination)) | Out-Null
	[IO.File]::WriteAllText($destination, $output.Content, $utf8)
	$manifestFiles.Add([pscustomobject]@{
		Catalog=$output.Catalog; File=$output.File; SourceSHA256=$output.SourceSHA256
		PatchedSHA256=(Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash; Changes=$output.Changes
	})
}
$manifest = [ordered]@{
	AGOTVersion='0.5.2.1'; CK3Version='1.19.0.6'; TranslationWorkshopId='2962803371'
	Overlay=$overlayPath; OverlayKeys=$patch.Count; ClosingQuoteRepairs=$seenRepairs.Count
	RuntimeSyntaxRepairs=$seenRuntimeRepairs.Count
	Files=@($manifestFiles.ToArray())
}
[IO.Directory]::CreateDirectory((Join-Path $modRoot 'docs')) | Out-Null
[IO.File]::WriteAllText((Join-Path $modRoot 'docs/source-manifest.json'), ($manifest | ConvertTo-Json -Depth 8) + "`n", $utf8)
Write-Output "Built $($outputs.Count) upstream file shadows, $($seenRepairs.Count) quote repairs, $($seenRuntimeRepairs.Count) runtime repairs, $($patch.Count) overlay keys."
