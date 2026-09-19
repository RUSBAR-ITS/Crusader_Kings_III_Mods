param(
	[string]$MainModPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2950245430',
	[string]$TranslationPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3465601037',
	[string]$GamePath = 'E:\SteamLibrary\steamapps\common\Crusader Kings III\game'
)
. (Join-Path $PSScriptRoot '../../../tools/RepositoryText.ps1')


$ErrorActionPreference = 'Stop'
$modRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$auditRoot = [IO.Path]::GetFullPath((Join-Path $modRoot '../../docs/reports/agot-plus-russian-2026-09-18'))
$utf8 = [Text.UTF8Encoding]::new($true, $true)
$pattern = [regex]'^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<text>.*)"\s*(?:#.*)?$'
$manifest = Get-Content -LiteralPath (Join-Path $modRoot 'docs/source-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json

function Read-Entries([string]$Path, [switch]$CheckStructure) {
	$bytes = [IO.File]::ReadAllBytes($Path)
	if ($bytes.Length -lt 3 -or $bytes[0] -ne 239 -or $bytes[1] -ne 187 -or $bytes[2] -ne 191) { throw "Missing UTF-8 BOM: $Path" }
	$lines = $utf8.GetString($bytes).TrimStart([char]0xFEFF) -split '\r?\n'
	$language = if ($Path -match '_l_russian.yml$') { 'russian' } else { 'english' }
	if ($lines[0] -cne "l_${language}:") { throw "Wrong language header: $Path" }
	for ($i = 1; $i -lt $lines.Length; $i++) {
		if ($lines[$i] -match '^\s*(?:#.*)?$') { continue }
		$match = $pattern.Match($lines[$i])
		if (-not $match.Success) { throw "Malformed entry: ${Path}:$($i+1)" }
		$value = $match.Groups['text'].Value
		if ($CheckStructure) {
			if ([regex]::Matches($value, '\[').Count -ne [regex]::Matches($value, '\]').Count -or
				[regex]::Matches($value, '\$').Count % 2 -ne 0 -or
				[regex]::Matches($value, '#[A-Za-z0-9_]+').Count -ne [regex]::Matches($value, '#!').Count -or
				$value -match '#Lady\b|GetShortUINameNotMeNotMe') { throw "Broken template: ${Path}:$($i+1)" }
		}
		[pscustomobject]@{ Key=$match.Groups['key'].Value; Text=$value }
	}
}

function Get-Tokens([string]$Value) {
	return (([regex]::Matches($Value, '\[[^\]]*\]|\$[^$]+\$|@[A-Za-z_0-9]+!|#!|#[A-Za-z0-9_]+|\\[nrt]') | ForEach-Object Value | Sort-Object -CaseSensitive) -join "`n")
}

$overlay = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
foreach ($entry in (Read-Entries (Join-Path $modRoot $manifest.Overlay) -CheckStructure)) { $overlay.Add($entry.Key, $entry.Text) }
if ($overlay.Count -ne 33 -or $overlay.Count -ne $manifest.OverlayKeys) { throw 'Expected 33 unique Russian overrides.' }
if ((Get-FileHash -LiteralPath (Join-Path $modRoot $manifest.Overlay)).Hash -cne $manifest.OverlaySHA256) { throw 'Overlay changed; rebuild first.' }
$files = @(rg --files (Join-Path $modRoot 'localization') -g '*.yml')
if ($files.Count -ne 8 -or $files.Count -ne $manifest.Files.Count + 2) { throw 'Unexpected packaged files.' }
foreach ($file in $files) { $null = @(Read-Entries $file -CheckStructure) }

# Validate the added names against actual trait definitions and the saved engine
# diagnostics, independently of the reviewed translation list.
$runtime = $manifest.RuntimeNames
$additionsFile = Join-Path $modRoot $runtime.Definitions
$additions = Get-Content -LiteralPath $additionsFile -Raw -Encoding UTF8 | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $additionsFile).Hash -cne $runtime.DefinitionsSHA256) { throw 'Runtime name definitions changed; rebuild first.' }
$runtimePath = Join-Path $modRoot $runtime.File
if ((Get-FileHash -LiteralPath $runtimePath).Hash -cne $runtime.SHA256) { throw 'Runtime names changed; rebuild first.' }
$names = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
foreach ($entry in (Read-Entries $runtimePath -CheckStructure)) { $names.Add($entry.Key, $entry.Text) }
if ($names.Count -ne 386 -or $runtime.Keys -ne 386 -or $additions.Entries.Count -ne 386) { throw 'Expected 386 runtime names.' }
$expectedKeys = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($group in @(
	@{ File='asoiaf_canon_children_traits.txt'; Kind='Character'; Count=291 },
	@{ File='asoiaf_crown_death_traits.txt'; Kind='Crown'; Count=94 }
)) {
	$text = [IO.File]::ReadAllText((Join-Path $MainModPath ('common/traits/' + $group.File)))
	$traits = [regex]::Matches($text, '(?m)^(asoiaf_\w+)\s*=\s*\{')
	if ($traits.Count -ne $group.Count) { throw "Trait coverage changed: $($group.File)" }
	foreach ($trait in $traits) {
		$key = 'trait_' + $trait.Groups[1].Value
		if (-not $expectedKeys.Add($key) -or -not $names.ContainsKey($key)) { throw "Missing/duplicate trait name: $key" }
	}
	if (@($additions.Entries | Where-Object Kind -eq $group.Kind).Count -ne $group.Count) { throw "Wrong name group: $($group.Kind)" }
}
$null = $expectedKeys.Add('Alyrie')
$workshopRoot = Split-Path -Parent $MainModPath
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $modRoot '../..'))
$sourcePaths = @{}
foreach ($source in $additions.Sources) {
	$path = if ($source.Path.StartsWith('workshop/')) { Join-Path $workshopRoot $source.Path.Substring(9) }
		elseif ($source.Path.StartsWith('repository/')) { Join-Path $repositoryRoot $source.Path.Substring(11) }
		else { throw "Unknown additions source: $($source.Path)" }
	if ((Get-FileHash -LiteralPath $path).Hash -cne $source.SHA256) { throw "Runtime name source changed: $path" }
	$sourcePaths[$source.Path] = $path
}
foreach ($entry in $additions.Entries) {
	if (-not $expectedKeys.Contains($entry.Key) -or $names[$entry.Key] -cne $entry.Value -or $overlay.ContainsKey($entry.Key)) { throw "Unexpected added name: $($entry.Key)" }
	$withoutRegnalNumbers = $entry.Value -creplace '\b[IVX]+\b', ''
	if ($entry.Key -ne 'Alyrie' -and ($entry.Value -notmatch '[\u0400-\u04FF]' -or $withoutRegnalNumbers -match '[\[\]$@#A-Za-z_]')) { throw "Untranslated runtime label: $($entry.Key)" }
	foreach ($reference in $entry.LocalizationSources) {
		$line = [IO.File]::ReadAllLines($sourcePaths[$reference.Path])[$reference.Line - 1]
		$match = $pattern.Match($line)
		if (-not $match.Success -or $match.Groups['key'].Value -cne $reference.Key -or $match.Groups['text'].Value -cne $reference.Value) { throw "Localization provenance mismatch: $($entry.Key)" }
	}
	foreach ($reference in $entry.Evidence) {
		if (-not $sourcePaths.ContainsKey($reference.Path)) { throw "Untracked evidence: $($reference.Path)" }
	}
}
if ($names['Alyrie'] -cne '$Alerie$') { throw 'Alyrie must use the existing Alerie localization.' }
$nameReference = @($additions.Entries | Where-Object Key -eq 'Alyrie')[0].LocalizationSources[0]
if ($nameReference.Key -cne 'Alerie' -or $nameReference.Value -notmatch '[\u0400-\u04FF]') { throw 'Alyrie alias target is not translated.' }
$logKeys = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($row in Import-Csv -LiteralPath (Join-Path $repositoryRoot $additions.BaselineReport)) {
	foreach ($match in [regex]::Matches($row.Message, '\btrait_asoiaf_\w+')) { $null = $logKeys.Add($match.Value) }
	if ($row.Message -match '\bUnrecognized loc key Alyrie\.') { $null = $logKeys.Add('Alyrie') }
}
if (-not $expectedKeys.SetEquals($logKeys)) { throw "Runtime names do not match the saved 386 engine diagnostics ($($logKeys.Count) keys)." }

# Reconstruct complete shadows to detect unrelated edits or missing source lines.
$repairCount = 0
foreach ($file in $manifest.Files) {
	$root = if ($file.Catalog -eq 'Translation') { $TranslationPath } else { $MainModPath }
	$source = Join-Path $root $file.File
	$destination = Join-Path $modRoot $file.File
	if ((Get-FileHash -LiteralPath $source).Hash -cne $file.SourceSHA256) { throw "Source changed: $source" }
	if ((Get-FileHash -LiteralPath $destination).Hash -cne $file.PatchedSHA256) { throw "Output changed: $destination" }
	$lines = [regex]::Split([IO.File]::ReadAllText($source, $utf8), '(?<=\n)')
	foreach ($change in $file.Changes) {
		$i = $change.Line - 1
		$before = $lines[$i].TrimEnd([char[]]"`r`n")
		if ($before -cne $change.Before) { throw "Manifest mismatch: $source" }
		$lines[$i] = $change.After + $lines[$i].Substring($before.Length)
		$repairCount++
	}
	if ([RepositoryText]::Normalize([string]::Concat($lines)) -cne [IO.File]::ReadAllText($destination, $utf8)) { throw "Unrecorded edits: $destination" }
}
if ($repairCount -ne 8 -or $manifest.EnglishRepairs -ne 5) { throw 'Missing source repairs.' }

$originalRussian = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
$coverage = @(Import-Csv -LiteralPath (Join-Path $auditRoot 'file-coverage.csv'))
foreach ($pair in $coverage) {
	foreach ($source in @(
		@{ Root=$MainModPath; File=$pair.MainFile; Hash=$pair.MainSHA256; Russian=$false },
		@{ Root=$TranslationPath; File=$pair.TranslationFile; Hash=$pair.TranslationSHA256; Russian=$true }
	)) {
		$path = Join-Path $source.Root $source.File
		if ((Get-FileHash -LiteralPath $path).Hash -cne $source.Hash) { throw "Audited source changed: $path" }
		$shadow = Join-Path $modRoot $source.File
		$effective = if (Test-Path -LiteralPath $shadow) { $shadow } else { $path }
		# All English files must parse and have balanced formatting after shadows.
		$entries = @(Read-Entries $effective -CheckStructure:(-not $source.Russian))
		if ($source.Russian) {
			foreach ($entry in (Read-Entries $path)) { $originalRussian[$entry.Key] = $entry.Text }
			foreach ($entry in $entries) {
				if ($source.File.StartsWith('localization/replace/') -and $overlay.ContainsKey($entry.Key) -and $entry.Text -cne $overlay[$entry.Key]) { throw "Conflicting replacement: $($entry.Key)" }
			}
		}
	}
}

$untranslated = @(Import-Csv -LiteralPath (Join-Path $auditRoot 'confirmed-untranslated.csv'))
if ($untranslated.Count -ne 29) { throw 'Unexpected audit baseline.' }
foreach ($row in $untranslated) {
	if (-not $overlay.ContainsKey($row.Key) -or $overlay[$row.Key] -ceq $row.Text -or $overlay[$row.Key] -notmatch '[\u0400-\u04FF]') { throw "Untranslated audited key: $($row.Key)" }
}
foreach ($key in $overlay.Keys) {
	if (-not $originalRussian.ContainsKey($key)) { throw "Unknown override: $key" }
	$expected = $originalRussian[$key]
	if ($key -like 'death_aegonvi_murder_known*') { continue }
	if ($key -like 'asoiaf_cersei_jaime_lover_desc*') { $expected = $expected.Replace('GetShortUINameNotMeNotMe', 'GetShortUINameNotMe') }
	if ($key -eq 'lp_feudal_government_desc') { $expected += '#!' }
	if ((Get-Tokens $expected) -cne (Get-Tokens $overlay[$key])) { throw "Unexpected template change: $key" }
	if ($key -like 'asoiaf_cersei_jaime_lover_desc*' -or $key -eq 'lp_feudal_government_desc') {
		if ($overlay[$key] -cne $expected) { throw "Unrelated wording change: $key" }
	}
}

# The singular concept must still use the corrected plural description.
$concept = 'game_concept_asoiaf_canon_children_concept_desc'
if ($originalRussian['game_concept_asoiaf_canon_child_concept_desc'] -cne ('$' + $concept + '$')) { throw 'Concept alias changed upstream.' }
if ($overlay[$concept] -cne $originalRussian[$concept].Replace('динамически становиться родителями', 'рождаться')) { throw 'Unexpected concept wording change.' }

# Preserve the ironic quotes and gender selection. Killer naming follows CK3's
# established local-player/non-player template instead of a nominative UI name.
$death = $overlay['death_aegonvi_murder_known']
if ($death -cne "[Select_CString(CHARACTER.IsFemale, 'была «убита»', 'был «убит»')]") { throw 'Incorrect death gender/quotation handling.' }
$vanillaDeath = @(Read-Entries (Join-Path $GamePath 'localization/russian/death_reasons_l_russian.yml')) | Where-Object Key -eq 'death_murder_known'
$naming = "[Select_CString(TARGET_CHARACTER.IsLocalPlayer, '', 'персонажем ')][TARGET_CHARACTER.GetNamePossessiveOrMy][Select_CString(TARGET_CHARACTER.IsLocalPlayer, 'им персонажем', '')]"
if (-not $vanillaDeath.Text.Replace(' )', ')').Contains($naming)) { throw 'Vanilla killer naming changed; review the template.' }
if ($overlay['death_aegonvi_murder_known_killer'] -cne ($death + ' ' + $naming)) { throw 'Incorrect killer naming template.' }

$descriptor = Get-Content -LiteralPath (Join-Path $modRoot 'descriptor.mod') -Raw -Encoding UTF8
$external = Get-Content -LiteralPath ($modRoot + '.mod') -Raw -Encoding UTF8
if ($descriptor -match 'replace_path\s*=|remote_file_id\s*=' -or $external -match 'replace_path\s*=') { throw 'Unexpected descriptor directive.' }
$pathMatch = [regex]::Match($external, '(?m)^path="([^"]+)"$')
if (-not $pathMatch.Success -or [IO.Path]::GetFullPath($pathMatch.Groups[1].Value) -ine $modRoot) { throw 'External descriptor points elsewhere.' }
Write-Output 'PASS: 29 translations; 2 relationship fixes; concept description and alias; gender-aware death reasons.'
Write-Output 'PASS: 8 UTF-8 BOM files; 5 English repairs; balanced templates; matching replacement definitions.'
Write-Output 'PASS: all 98 audited sources unchanged; complete shadows preserve unrelated lines; descriptor path verified.'
Write-Output 'PASS: 291 character traits, 94 crown traits and Alyrie; exact saved-log coverage; translation provenance and source hashes verified.'
