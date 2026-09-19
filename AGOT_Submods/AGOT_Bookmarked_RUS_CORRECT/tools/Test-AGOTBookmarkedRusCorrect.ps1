param(
	[string]$MainModPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3149692324',
	[string]$TranslationPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3518584623'
)
. (Join-Path $PSScriptRoot '../../../tools/RepositoryText.ps1')


$ErrorActionPreference = 'Stop'
$modRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$auditRoot = [IO.Path]::GetFullPath((Join-Path $modRoot '../../docs/reports/agot-bookmarked-russian-2026-09-18'))
$utf8 = [Text.UTF8Encoding]::new($true, $true)
$pattern = [regex]'^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<text>.*)"\s*(?:#.*)?$'
$manifest = Get-Content -LiteralPath (Join-Path $modRoot 'docs/source-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json

function Read-Catalog([string]$Path, [switch]$CheckStructure) {
	$bytes = [IO.File]::ReadAllBytes($Path)
	if ($bytes.Length -lt 3 -or $bytes[0] -ne 239 -or $bytes[1] -ne 187 -or $bytes[2] -ne 191) { throw "Missing BOM: $Path" }
	$lines = $utf8.GetString($bytes).TrimStart([char]0xFEFF) -split '\r?\n'
	$language = if ($Path -match '_l_russian.yml$') { 'russian' } else { 'english' }
	$headerCount = 0
	$entries = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
	for ($i = 0; $i -lt $lines.Length; $i++) {
		if ($lines[$i] -match '^\s*(?:#.*)?$') { continue }
		if ($lines[$i] -cmatch ('^l_' + $language + ':\s*$')) { $headerCount++; continue }
		$entry = $pattern.Match($lines[$i])
		if (-not $entry.Success) { throw "Malformed active line: ${Path}:$($i+1)" }
		$value = $entry.Groups['text'].Value
		if ($CheckStructure) {
			if ($value -match '<insert imagination>|\\(?![nrt"\\])' -or
				[regex]::Matches($value, '\[').Count -ne [regex]::Matches($value, '\]').Count -or
				[regex]::Matches($value, '\$').Count % 2 -ne 0) { throw "Bad template: ${Path}:$($i+1)" }
			$depth = 0
			foreach ($token in [regex]::Matches($value, '#[A-Za-z0-9_]+|#!')) {
				if ($token.Value -eq '#!') { $depth-- } else { $depth++ }
				if ($depth -lt 0) { throw "Unexpected format end: ${Path}:$($i+1)" }
			}
			if ($depth -ne 0) { throw "Unclosed format tag: ${Path}:$($i+1)" }
		}
		$entries.Add($entry.Groups['key'].Value, $value)
	}
	if ($headerCount -ne 1) { throw "Expected one language header: $Path" }
	return ,$entries
}

$overlay = Read-Catalog (Join-Path $modRoot $manifest.Overlay) -CheckStructure
if ($overlay.Count -ne 20 -or $manifest.OverlayKeys -ne 20) { throw 'Expected 20 corrected keys.' }
if ((Get-FileHash -LiteralPath (Join-Path $modRoot $manifest.Overlay)).Hash -cne $manifest.OverlaySHA256) { throw 'Overlay differs from its build manifest.' }
$files = @(rg --files (Join-Path $modRoot 'localization') -g '*.yml')
if ($files.Count -ne 3 -or $manifest.Files.Count -ne 2) { throw 'Unexpected packaged files.' }
foreach ($path in $files) { $null = Read-Catalog $path -CheckStructure }

# Reconstruct every shadow from the original physical lines. Both continuation
# lines must move into the value rather than disappearing from the description.
$continuations = 0
foreach ($file in $manifest.Files) {
	$source = Join-Path $TranslationPath $file.File
	$destination = Join-Path $modRoot $file.File
	if ((Get-FileHash -LiteralPath $source).Hash -cne $file.SourceSHA256) { throw "Source changed: $source" }
	if ((Get-FileHash -LiteralPath $destination).Hash -cne $file.PatchedSHA256) { throw "Shadow changed: $destination" }
	$lines = [regex]::Split([IO.File]::ReadAllText($source, $utf8), '(?<=\n)')
	foreach ($change in $file.Changes) {
		$i = $change.Line - 1
		$before = $lines[$i].TrimEnd([char[]]"`r`n")
		if ($before -cne $change.Before) { throw "Incorrect manifest position: ${source}:$($change.Line)" }
		if ($change.Kind -eq 'JoinedContinuation') {
			$firstLine = $lines[$i-1].TrimEnd([char[]]"`r`n")
			$complete = $pattern.Match($firstLine + '\n\n' + $before)
			if (-not $complete.Success -or $complete.Groups['text'].Value -cne $overlay[$change.Key]) { throw 'Joffrey continuation was lost or altered.' }
			if ($change.After -cne '') { throw 'Continuation must become a blank physical line.' }
			$continuations++
		} else {
			$entry = $pattern.Match($change.After)
			if (-not $entry.Success -or $entry.Groups['text'].Value -cne $overlay[$change.Key]) { throw "Shadow/overlay mismatch: $($change.Key)" }
		}
		$lines[$i] = $change.After + $lines[$i].Substring($before.Length)
	}
	if ([RepositoryText]::Normalize([string]::Concat($lines)) -cne [IO.File]::ReadAllText($destination, $utf8)) { throw "Unrecorded changes: $destination" }
}
if ($continuations -ne 2 -or $manifest.JoinedDescriptions -ne 2) { throw 'Expected two complete Joffrey repairs.' }

$english = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
$russian = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
foreach ($pair in (Import-Csv -LiteralPath (Join-Path $auditRoot 'file-coverage.csv'))) {
	$enPath = Join-Path $MainModPath $pair.MainFile
	$ruPath = Join-Path $TranslationPath $pair.TranslationFile
	if ((Get-FileHash -LiteralPath $enPath).Hash -cne $pair.MainSHA256 -or (Get-FileHash -LiteralPath $ruPath).Hash -cne $pair.TranslationSHA256) { throw 'Audited sources changed.' }
	$en = Read-Catalog $enPath
	foreach ($key in $en.Keys) { $english.Add($key, $en[$key]) }
	$shadow = Join-Path $modRoot $pair.TranslationFile
	$ru = Read-Catalog $(if (Test-Path -LiteralPath $shadow) { $shadow } else { $ruPath }) -CheckStructure
	if ($ru.Count -ne [int]$pair.RussianEntries) { throw 'Shadow lost or added keys.' }
	foreach ($key in $ru.Keys) {
		$russian.Add($key, $ru[$key])
		if ($overlay.ContainsKey($key) -and $ru[$key] -cne $overlay[$key]) { throw "Conflicting overlay value: $key" }
	}
}
if ($english.Count -ne 146 -or $russian.Count -ne 146) { throw 'Expected complete 146-key coverage.' }
foreach ($key in $english.Keys) { if (-not $russian.ContainsKey($key)) { throw "Missing key: $key" } }
foreach ($issue in (Import-Csv -LiteralPath (Join-Path $auditRoot 'confirmed-technical-issues.csv'))) {
	if (-not $overlay.ContainsKey($issue.Key)) { throw "Uncovered technical finding: $($issue.Key)" }
}
$authored = Get-Content -LiteralPath (Join-Path $modRoot 'docs/new-descriptions.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($placeholder in (Import-Csv -LiteralPath (Join-Path $auditRoot 'confirmed-placeholders.csv'))) {
	$key = $placeholder.Key
	if (-not $overlay.ContainsKey($key) -or $overlay[$key].Length -lt 300 -or $overlay[$key] -notmatch '[\u0400-\u04FF]') { throw "Incomplete authored description: $key" }
	if ($overlay[$key] -cne $authored.$key.Replace("`r`n", "`n").Replace("`n", '\n')) { throw "Authored source differs from output: $key" }
}

# Preserve scope expressions and localization references in every source key.
$tokenPattern = '\[[^\]]*\]|\$[^$]+\$|@[A-Za-z0-9_]+!'
foreach ($key in $russian.Keys) {
	$enTokens = ([regex]::Matches($english[$key], $tokenPattern) | ForEach-Object Value | Sort-Object -CaseSensitive) -join '|'
	$ruTokens = ([regex]::Matches($russian[$key], $tokenPattern) | ForEach-Object Value | Sort-Object -CaseSensitive) -join '|'
	if ($enTokens -cne $ruTokens) { throw "Changed references/scopes: $key" }
}
foreach ($value in $russian.Values) {
	if ($value -match 'Эйегона|Бизбери,\.|присоеденил|Гарднеров|Дейенис|Дэймон|его  единокровный|Переправы,''|полон ужасов') { throw 'An audited wording defect remains.' }
}
if ($russian['bookmark_300_stannis_baratheon_desc'] -cne 'Год темен и полон ошибок.') { throw 'Original Stannis joke was not restored.' }

$descriptor = Get-Content -LiteralPath (Join-Path $modRoot 'descriptor.mod') -Raw -Encoding UTF8
$external = Get-Content -LiteralPath ($modRoot + '.mod') -Raw -Encoding UTF8
if ($descriptor -match 'replace_path\s*=|remote_file_id\s*=' -or $external -match 'replace_path\s*=') { throw 'Unexpected descriptor directive.' }
$pathMatch = [regex]::Match($external, '(?m)^path="([^"]+)"$')
if (-not $pathMatch.Success -or [IO.Path]::GetFullPath($pathMatch.Groups[1].Value) -ine $modRoot) { throw 'External descriptor points elsewhere.' }
Write-Output 'PASS: 146/146 keys; 20 corrections; all 7 technical findings fixed; 4 complete authored descriptions.'
Write-Output 'PASS: both Joffrey paragraphs preserved; formatting, escapes, UTF-8 BOM and dynamic references verified.'
Write-Output 'PASS: all 6 source files unchanged; shadows preserve unrelated content; descriptor path verified.'
