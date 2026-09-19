param(
	[string]$MainModPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2962333032',
	[string]$TranslationPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2962803371',
	[string]$GamePath = 'E:\SteamLibrary\steamapps\common\Crusader Kings III\game'
)

$ErrorActionPreference = 'Stop'
$modRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$utf8 = [Text.UTF8Encoding]::new($true, $true)
$pattern = [regex]'^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<text>.*)"\s*(?:#.*)?$'
$manifest = Get-Content -LiteralPath (Join-Path $modRoot 'docs/source-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$baseline = Get-Content -LiteralPath (Join-Path $modRoot 'docs/audit-baseline.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$runtimeRepairs = Get-Content -LiteralPath (Join-Path $modRoot 'docs/runtime-localization-repairs.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$strictPattern = [regex]'^\s*[^\s#":]+:[ \t]*(?:\d+[ \t]+)?"(?:[^"\\]|\\[nrt"\\])*"[ \t]*(?:#.*)?$'
$overlay = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
foreach ($line in [IO.File]::ReadAllLines((Join-Path $modRoot $manifest.Overlay), $utf8)) {
	$entry = $pattern.Match($line)
	if ($entry.Success) { $overlay.Add($entry.Groups['key'].Value, $entry.Groups['text'].Value) }
}
if ($overlay.Count -ne $manifest.OverlayKeys) { throw 'Rebuild after changing the overlay.' }

# Check actual packaged bytes and parse all active lines, not just known fixes.
$localizationFiles = @(rg --files (Join-Path $modRoot 'localization') -g '*.yml')
if ($LASTEXITCODE -ne 0) { throw 'No localization files found.' }
foreach ($file in $localizationFiles) {
	$bytes = [IO.File]::ReadAllBytes($file)
	if ($bytes.Length -lt 3 -or $bytes[0] -ne 239 -or $bytes[1] -ne 187 -or $bytes[2] -ne 191) { throw "Missing UTF-8 BOM: $file" }
	$content = $utf8.GetString($bytes).TrimStart([char]0xFEFF)
	$language = if ($file -match '_l_russian.yml$') { 'russian' } elseif ($file -match '_l_english.yml$') { 'english' } else { throw "Unexpected filename: $file" }
	$lines = $content -split '\r?\n'
	if ($lines[0] -cne "l_${language}:") { throw "Wrong language header: $file" }
	for ($i = 1; $i -lt $lines.Length; $i++) {
		if ($lines[$i] -match '^\s*(?:#.*)?$') { continue }
		if (-not $strictPattern.IsMatch($lines[$i])) { throw "Malformed localization: ${file}:$($i+1)" }
	}
}
if ($localizationFiles.Count -ne $manifest.Files.Count + 1) { throw 'Unexpected packaged localization files.' }

# Reconstruct every shadow from the untouched Workshop source. This catches
# accidental deletions, stale sources, and unrelated edits to copied files.
$quoteCount = 0
$runtimeCount = 0
foreach ($file in $manifest.Files) {
	$root = if ($file.Catalog -eq 'Translation') { $TranslationPath } else { $MainModPath }
	$source = Join-Path $root $file.File
	$destination = Join-Path $modRoot $file.File
	if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -cne $file.SourceSHA256) { throw "Upstream file changed: $source" }
	if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -cne $file.PatchedSHA256) { throw "Shadow file changed: $destination" }
	$lines = [regex]::Split([IO.File]::ReadAllText($source, $utf8), '(?<=\n)')
	foreach ($change in $file.Changes) {
		$i = $change.Line - 1
		$body = $lines[$i].TrimEnd([char[]]"`r`n")
		if ($body -cne $change.Before) { throw "Manifest mismatch: ${source}:$($change.Line)" }
		if ($change.Kind -eq 'ClosingQuote') {
			if ($change.After -cne ($change.Before + '"')) { throw 'A quote repair changed more than the closing quote.' }
			$quoteCount++
		} else {
			if ($change.Kind -eq 'RuntimeSyntax') {
				$fix = @($runtimeRepairs | Where-Object { $_.File -ceq $file.File -and $_.Key -ceq $change.Key })
				if ($fix.Count -ne 1 -or $fix[0].Before -cne $change.Before -or $fix[0].After -cne $change.After) { throw "Unexpected runtime repair: $($change.Key)" }
				$runtimeCount++
			}
			$entry = $pattern.Match($change.After)
			if (-not $entry.Success -or $entry.Groups['text'].Value -cne $overlay[$change.Key]) { throw "Shadow/overlay mismatch: $($change.Key)" }
		}
		$lines[$i] = $change.After + $lines[$i].Substring($body.Length)
	}
	if ([string]::Concat($lines) -cne [IO.File]::ReadAllText($destination, $utf8)) { throw "Unrecorded changes in $destination" }
}
if ($quoteCount -ne 9 -or $quoteCount -ne $manifest.ClosingQuoteRepairs) { throw 'Expected all nine audited quote repairs.' }
if ($runtimeCount -ne 7 -or $runtimeCount -ne $manifest.RuntimeSyntaxRepairs) { throw 'Expected all seven runtime localization repairs.' }

# Build the effective Russian catalog with same-path shadows applied. Retain
# duplicates instead of assuming an undocumented order between replacement files.
$russian = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
$translationRoot = [IO.Path]::GetFullPath($TranslationPath).TrimEnd('\', '/')
foreach ($file in (rg --files (Join-Path $translationRoot 'localization') -g '*_l_russian.yml')) {
	$relative = $file.Substring($translationRoot.Length + 1).Replace('\', '/')
	$shadow = Join-Path $modRoot $relative
	$effective = if (Test-Path -LiteralPath $shadow) { $shadow } else { $file }
	foreach ($line in [IO.File]::ReadAllLines($effective, $utf8)) {
		$entry = $pattern.Match($line)
		if (-not $entry.Success) { continue }
		$key = $entry.Groups['key'].Value
		$value = $entry.Groups['text'].Value
		if (-not $russian.ContainsKey($key)) { $russian.Add($key, [Collections.Generic.List[string]]::new()) }
		$russian[$key].Add($value)
		if ($relative.StartsWith('localization/replace/') -and $overlay.ContainsKey($key) -and $value -cne $overlay[$key]) {
			throw "Conflicting replacement definition: ${relative}:$key"
		}
	}
}
foreach ($key in $baseline.MissingRussianKeys) {
	if (-not $overlay.ContainsKey($key)) { throw "Missing audited key: $key" }
}
foreach ($row in $baseline.EnglishProse) {
	if (-not $overlay.ContainsKey($row.Key) -or $overlay[$row.Key] -ceq $row.Text) { throw "Untranslated audited prose: $($row.Key)" }
}
foreach ($row in $baseline.VanillaFallbacks) {
	$baseFile = Join-Path $GamePath $row.BaseRussianFile
	if (Test-Path -LiteralPath (Join-Path $modRoot $row.BaseRussianFile)) { throw "Unexpected shadow of fallback file: $baseFile" }
	$found = $false
	foreach ($line in [IO.File]::ReadAllLines($baseFile, $utf8)) {
		$entry = $pattern.Match($line)
		if ($entry.Success -and $entry.Groups['key'].Value -ceq $row.Key) { $found = $true; break }
	}
	if (-not $found) { throw "Missing vanilla fallback: $($row.Key)" }
}

function Get-TemplateTokens([string]$Value) {
	# Concept() adds a Russian grammatical form while retaining the same concept.
	$normalized = $Value -replace "\[Concept\('([^']+)', '[^']*'\)\|E\]", '[$1|E]'
	$tokens = [regex]::Matches($normalized, '\[[^\]]*\]|\$[^$]+\$|@[A-Za-z_0-9]+!|#!|#[A-Za-z0-9_]+(?:;[A-Za-z0-9_:]+)*|\\[nrt]')
	return (($tokens | ForEach-Object Value | Sort-Object -CaseSensitive) -join "`n")
}

# Compare overrides to original Russian definitions, including all dynamic
# scopes, dollar references, icons, formatting tags and escaped line breaks.
$originals = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
foreach ($file in (rg --files (Join-Path $TranslationPath 'localization') -g '*_l_russian.yml')) {
	foreach ($line in [IO.File]::ReadAllLines($file, $utf8)) {
		$entry = $pattern.Match($line)
		if (-not $entry.Success) { continue }
		$key = $entry.Groups['key'].Value
		if (-not $overlay.ContainsKey($key)) { continue }
		if (-not $originals.ContainsKey($key)) { $originals.Add($key, [Collections.Generic.List[string]]::new()) }
		$originals[$key].Add($entry.Groups['text'].Value)
	}
}
foreach ($key in $overlay.Keys) {
	$runtimeFix = @($runtimeRepairs | Where-Object Key -CEQ $key)
	if ($runtimeFix.Count) {
		# The original dynamic expressions were broken. Their explicitly
		# reviewed replacements, rather than those tokens, are the contract.
		$fixed = $pattern.Match($runtimeFix[0].After)
		if (-not $fixed.Success -or $fixed.Groups['text'].Value -cne $overlay[$key]) { throw "Runtime overlay mismatch: $key" }
		continue
	}
	if ($baseline.MissingRussianKeys -ccontains $key) {
		foreach ($reference in [regex]::Matches($overlay[$key], '\$([^$]+)\$')) {
			if (-not $russian.ContainsKey($reference.Groups[1].Value)) { throw "Unresolved alias in $key" }
		}
		continue
	}
	if (-not $originals.ContainsKey($key)) { throw "Unknown override key: $key" }
	$actual = Get-TemplateTokens $overlay[$key]
	$matching = @($originals[$key] | Where-Object { (Get-TemplateTokens $_) -ceq $actual })
	if ($matching.Count -eq 0) { throw "Changed template tokens in $key" }
}

$descriptor = Get-Content -LiteralPath (Join-Path $modRoot 'descriptor.mod') -Raw -Encoding UTF8
if ($descriptor -match 'replace_path\s*=') { throw 'The patch must not discard upstream directories.' }
Write-Output "PASS: $($overlay.Count) overlay keys; $($localizationFiles.Count) UTF-8 BOM files; nine exact quote repairs."
Write-Output "PASS: seven missing keys, 33 prose candidates, eight vanilla fallbacks, aliases and template tokens."
Write-Output 'PASS: Workshop sources unchanged; file shadows match the manifest; no conflicting replacement values.'
Write-Output 'PASS: seven runtime repairs; strict version separators, quotes and escapes in every packaged file.'
