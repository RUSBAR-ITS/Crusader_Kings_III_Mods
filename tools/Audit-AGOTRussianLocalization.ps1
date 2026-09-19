param(
	[string]$MainModPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2962333032',
	[string]$TranslationPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2962803371',
	[string]$GamePath = 'E:\SteamLibrary\steamapps\common\Crusader Kings III\game',
	[string]$OutputPath
)
. (Join-Path $PSScriptRoot 'RepositoryText.ps1')


$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
	$OutputPath = Join-Path $PSScriptRoot '../docs/reports/agot-russian-2026-09-18'
}
$OutputPath = [IO.Path]::GetFullPath($OutputPath)
$diagnostics = [Collections.Generic.List[object]]::new()
$entryPattern = [regex]::new('^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<text>.*)"\s*(?:#.*)?$')
$keyPrefix = [regex]::new('^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<text>.*)$')
$strictUtf8 = [Text.UTF8Encoding]::new($false, $true)

function Read-LocalizationCatalog {
	param([string]$Root, [string]$Language, [string]$Label)

	$rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
	$paths = @(rg --files (Join-Path $rootFull 'localization') -g "*_l_$Language.yml" | Sort-Object)
	if ($LASTEXITCODE -ne 0 -or $paths.Count -eq 0) { throw "No $Language localization files in $Root" }
	$catalog = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
	$entryCount = 0
	foreach ($path in $paths) {
		$relative = $path.Substring($rootFull.Length + 1).Replace('\', '/')
		$bytes = [IO.File]::ReadAllBytes($path)
		$content = $strictUtf8.GetString($bytes).TrimStart([char]0xFEFF)
		$lines = $content -split '\r?\n'
		if ($bytes.Length -lt 3 -or $bytes[0] -ne 239 -or $bytes[1] -ne 187 -or $bytes[2] -ne 191) {
			$diagnostics.Add([pscustomobject]@{ Catalog=$Label; File=$relative; Line=1; Problem='Missing UTF-8 BOM' })
		}
		$headerPattern = '(?m)^\s*l_' + [regex]::Escape($Language) + ':\s*(?:#.*)?$'
		if ($content -notmatch $headerPattern) {
			$diagnostics.Add([pscustomobject]@{ Catalog=$Label; File=$relative; Line=1; Problem='Missing expected language header; file excluded' })
			continue
		}
		for ($index = 0; $index -lt $lines.Count; $index++) {
			$line = $lines[$index]
			if ($line -match '^\s*(?:#.*)?$' -or $line -match '^\s*l_[a-z_]+:\s*(?:#.*)?$') { continue }
			$match = $entryPattern.Match($line)
			if (-not $match.Success) {
				# Count declared keys even when the closing quote is missing, but
				# report the malformed entry separately from absent translations.
				$match = $keyPrefix.Match($line)
				if (-not $match.Success) { continue }
				$diagnostics.Add([pscustomobject]@{ Catalog=$Label; File=$relative; Line=($index+1); Problem='Malformed localization entry; key counted, syntax needs review' })
			}
			$key = $match.Groups['key'].Value
			$entry = [pscustomobject]@{ Key=$key; File=$relative; Line=($index+1); Text=$match.Groups['text'].Value }
			if (-not $catalog.ContainsKey($key)) { $catalog.Add($key, [Collections.Generic.List[object]]::new()) }
			$catalog[$key].Add($entry)
			$entryCount++
		}
	}
	return [pscustomobject]@{ Keys=$catalog; FileCount=$paths.Count; EntryCount=$entryCount }
}

# Compare key presence across all files, including localization/replace.
# Duplicate entries are retained; no engine load-order precedence is assumed.
$main = Read-LocalizationCatalog -Root $MainModPath -Language english -Label AGOT
$translation = Read-LocalizationCatalog -Root $TranslationPath -Language russian -Label Translation
$vanilla = Read-LocalizationCatalog -Root $GamePath -Language russian -Label CK3
$missing = [Collections.Generic.List[object]]::new()
$identical = [Collections.Generic.List[object]]::new()
$proseCandidates = [Collections.Generic.List[object]]::new()

foreach ($key in ($main.Keys.Keys | Sort-Object -CaseSensitive)) {
	$english = $main.Keys[$key][0]
	if (-not $translation.Keys.ContainsKey($key)) {
		$fallback = if ($vanilla.Keys.ContainsKey($key)) { $vanilla.Keys[$key][0] } else { $null }
		$alternateKey = if ($translation.Keys.ContainsKey($key + '_hash')) { $key + '_hash' } else { '' }
		$missing.Add([pscustomobject]@{
			Key=$key; MainFile=$english.File; MainLine=$english.Line; English=$english.Text
			BaseRussianAvailable=($null -ne $fallback)
			BaseRussianFile=$(if ($fallback) { $fallback.File } else { '' })
			BaseRussianLine=$(if ($fallback) { $fallback.Line } else { '' })
			BaseRussian=$(if ($fallback) { $fallback.Text } else { '' })
			RelatedTranslationKey=$alternateKey
		})
		continue
	}
	# Identical names, references, and technical strings are not translation errors.
	# Prose candidates are a review aid, not a definitive untranslated-string count.
	$equalEntry = $null
	foreach ($ru in $translation.Keys[$key]) {
		foreach ($en in $main.Keys[$key]) {
			if ([string]::Equals($ru.Text, $en.Text, [StringComparison]::Ordinal)) {
				$equalEntry = [pscustomobject]@{ Key=$key; MainFile=$en.File; MainLine=$en.Line; TranslationFile=$ru.File; TranslationLine=$ru.Line; Text=$en.Text }
				break
			}
		}
		if ($equalEntry) { break }
	}
	if ($equalEntry) {
		$identical.Add($equalEntry)
		$visible = $equalEntry.Text -replace '\[[^\]]*\]', '' -replace '\$[^$]+\$', '' -replace '@[^!\s]+!', '' -replace '#[A-Za-z0-9_!]+', '' -replace '\\[ntr]', ' '
		if ($visible -notmatch '[\u0400-\u04FF]' -and [regex]::Matches($visible, '[A-Za-z]+').Count -ge 3 -and
			$visible -match '(?i)\b(the|this|that|your|you|have|has|will|with|from|cannot|should|their|these|they|would)\b') {
			$proseCandidates.Add($equalEntry)
		}
	}
}

$uncovered = @($missing | Where-Object { -not $_.BaseRussianAvailable })
$stats = [ordered]@{
	GeneratedAt=(Get-Date).ToString('o')
	MainModPath=$MainModPath; TranslationPath=$TranslationPath; GamePath=$GamePath
	MainEnglishFiles=$main.FileCount; MainEnglishEntries=$main.EntryCount; MainUniqueKeys=$main.Keys.Count
	TranslationRussianFiles=$translation.FileCount; TranslationRussianEntries=$translation.EntryCount; TranslationUniqueKeys=$translation.Keys.Count
	VanillaRussianFiles=$vanilla.FileCount; VanillaRussianUniqueKeys=$vanilla.Keys.Count
	MissingFromTranslation=$missing.Count; CoveredByVanillaRussian=($missing.Count-$uncovered.Count); MissingRussianEverywhere=$uncovered.Count
	IdenticalTextKeys=$identical.Count; IdenticalEnglishProseCandidates=$proseCandidates.Count
	MainDuplicateKeys=@($main.Keys.Values | Where-Object Count -gt 1).Count
	TranslationDuplicateKeys=@($translation.Keys.Values | Where-Object Count -gt 1).Count
	DiagnosticCount=$diagnostics.Count
	Method='Case-sensitive declared-key comparison, including entries with missing closing quotes flagged in diagnostics. Duplicate definitions retained. Identical-text results match at least one source and translation definition; engine precedence and runtime references are not inferred.'
}
[IO.Directory]::CreateDirectory($OutputPath) | Out-Null
[RepositoryText]::WriteAllLines((Join-Path $OutputPath 'missing-from-translation.csv'), [string[]]@($missing | ConvertTo-Csv -NoTypeInformation), [Text.UTF8Encoding]::new($true))
[RepositoryText]::WriteAllLines((Join-Path $OutputPath 'missing-russian.csv'), [string[]]@($uncovered | ConvertTo-Csv -NoTypeInformation), [Text.UTF8Encoding]::new($true))
[RepositoryText]::WriteAllLines((Join-Path $OutputPath 'identical-text-review.csv'), [string[]]@($identical | ConvertTo-Csv -NoTypeInformation), [Text.UTF8Encoding]::new($true))
[RepositoryText]::WriteAllLines((Join-Path $OutputPath 'english-prose-review.csv'), [string[]]@($proseCandidates | ConvertTo-Csv -NoTypeInformation), [Text.UTF8Encoding]::new($true))
[RepositoryText]::WriteAllLines((Join-Path $OutputPath 'diagnostics.csv'), [string[]]@($diagnostics | ConvertTo-Csv -NoTypeInformation), [Text.UTF8Encoding]::new($true))
[RepositoryText]::WriteAllText((Join-Path $OutputPath 'summary.json'), ($stats | ConvertTo-Json -Depth 3), [Text.UTF8Encoding]::new($true))
$stats | ConvertTo-Json -Depth 3
