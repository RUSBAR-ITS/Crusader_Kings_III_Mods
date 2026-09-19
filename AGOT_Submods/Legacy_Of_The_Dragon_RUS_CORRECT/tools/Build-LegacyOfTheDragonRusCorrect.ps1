param(
    [string]$MainModPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3101422928',
    [string]$TranslationPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3713762177',
    [string]$AgotPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2962333032',
    [string]$AgotRussianPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2962803371',
    [switch]$Check
)
. (Join-Path $PSScriptRoot '../../../tools/RepositoryText.ps1')


$ErrorActionPreference = 'Stop'
$modRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$utf8 = [Text.UTF8Encoding]::new($true, $true)
$baseline = Get-Content -LiteralPath (Join-Path $modRoot 'docs/source-baseline.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$corrections = Get-Content -LiteralPath (Join-Path $modRoot 'docs/corrections.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$scriptCorrections = Get-Content -LiteralPath (Join-Path $modRoot 'docs/script-corrections.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$entryPattern = [regex]'^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<text>.*)"\s*(?:#.*)?$'
$genderPattern = [regex]"\[Select_CString\(ancestor_1\.IsFemale, '([^']+)', '([^']+)'\)\]"

function Read-Catalog([string]$Text, [string]$Language) {
    $entries = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    $headers = 0
    foreach ($line in $Text.TrimStart([char]0xFEFF) -split '\r?\n') {
        if ($line -match '^\s*(?:#.*)?$') { continue }
        if ($line -cmatch ('^l_' + $Language + ':\s*$')) { $headers++; continue }
        $match = $entryPattern.Match($line)
        if (-not $match.Success) { throw "Malformed localization: $line" }
        $value = $match.Groups['text'].Value
        if ([regex]::Matches($value,'\[').Count -ne [regex]::Matches($value,'\]').Count -or
            [regex]::Matches($value,'\$').Count % 2 -ne 0 -or $value -match '\\(?![nrt"\\])') { throw 'Broken localization template.' }
        $depth = 0
        foreach ($token in [regex]::Matches($value, '#!|#[A-Za-z][A-Za-z0-9_]*')) {
            if ($token.Value -eq '#!') { $depth-- } else { $depth++ }
            if ($depth -lt 0) { throw 'Unexpected formatting close.' }
        }
        if ($depth -ne 0) { throw 'Unclosed formatting.' }
        $entries.Add($match.Groups['key'].Value, $value)
    }
    if ($headers -ne 1) { throw "Expected one $Language header." }
    return ,$entries
}

function Get-Tokens([string]$Text, [string]$Pattern) {
    return (@([regex]::Matches($Text, $Pattern) | ForEach-Object { $_.Value } | Sort-Object -CaseSensitive) -join ' || ')
}

# Stop on Workshop updates before changing generated files.
foreach ($source in $baseline.Sources) {
    $root = switch ($source.Catalog) { RU {$TranslationPath} AGOT_EN {$AgotPath} AGOT_RU {$AgotRussianPath} default {$MainModPath} }
    $path = Join-Path $root $source.File
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -cne $source.SHA256) { throw "Source changed; repeat the audit: $path" }
}

$catalogs = @{}
$patches = @{}
foreach ($language in @('EN','RU')) {
    $catalogs[$language] = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    $patches[$language] = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    $root = if ($language -eq 'RU') { $TranslationPath } else { $MainModPath }
    $header = if ($language -eq 'RU') { 'russian' } else { 'english' }
    $localizationSources = @($baseline.Sources | Where-Object { $_.Catalog -eq $language -and $_.File.StartsWith('localization/') })
    $actualPaths = @(Get-ChildItem -LiteralPath (Join-Path $root 'localization') -File -Recurse -Filter "*_l_$header.yml" | ForEach-Object { $_.FullName.Substring($root.TrimEnd('\','/').Length + 1).Replace('\','/') })
    if ((($actualPaths | Sort-Object -CaseSensitive) -join '|') -cne (($localizationSources.File | Sort-Object -CaseSensitive) -join '|')) { throw "Localization file inventory changed: $language" }
    foreach ($source in $localizationSources) {
        $entries = Read-Catalog ([IO.File]::ReadAllText((Join-Path $root $source.File), $utf8)) $header
        foreach ($key in $entries.Keys) { $catalogs[$language].Add($key, $entries[$key]) }
    }
    if ($catalogs[$language].Count -ne 260) { throw "Expected 260 $language keys." }
}
foreach ($key in $catalogs.EN.Keys) { if (-not $catalogs.RU.ContainsKey($key)) { throw "Missing Russian key: $key" } }

$external = @{}
foreach ($language in @('EN','RU')) {
    $external[$language] = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    $source = @($baseline.Sources | Where-Object { $_.Catalog -eq ('AGOT_' + $language) })
    if ($source.Count -ne 1) { throw 'Expected one AGOT house customizer catalog per language.' }
    $root = if ($language -eq 'RU') { $AgotRussianPath } else { $AgotPath }
    foreach ($line in [IO.File]::ReadAllLines((Join-Path $root $source[0].File))) {
        $match = $entryPattern.Match($line)
        if ($match.Success) { $external[$language].Add($match.Groups['key'].Value, $match.Groups['text'].Value) }
    }
}

$changes = @()
foreach ($correction in $corrections) {
    if ($correction.Catalog -notin @('RU','EN')) { throw 'Unknown correction catalog.' }
    if ($correction.Alias) {
        if ($catalogs[$correction.Catalog].ContainsKey($correction.Key)) { throw 'New alias already exists in the source.' }
        if ($correction.Alias -notmatch '^\$([^$]+)\$$' -or -not $external[$correction.Catalog].ContainsKey($Matches[1])) { throw 'Alias target missing from AGOT.' }
        $patches[$correction.Catalog].Add($correction.Key, $correction.Alias)
        $changes += [pscustomobject]@{Issue=$correction.Issue;Catalog=$correction.Catalog;File='';Key=$correction.Key;Before=$null;After=$correction.Alias}
        continue
    }
    $root = if ($correction.Catalog -eq 'RU') { $TranslationPath } else { $MainModPath }
    $header = if ($correction.Catalog -eq 'RU') { 'russian' } else { 'english' }
    $entries = Read-Catalog ([IO.File]::ReadAllText((Join-Path $root $correction.File), $utf8)) $header
    if (-not $entries.ContainsKey($correction.Key)) { throw "Missing source key: $($correction.Key)" }
    $before = $entries[$correction.Key]
    $after = $before
    foreach ($replacement in $correction.Replacements) {
        if ([string]::IsNullOrEmpty($replacement.Before) -or
            [regex]::Matches($after, [regex]::Escape($replacement.Before)).Count -ne $replacement.Count) { throw "Source fragment count differs: $($correction.Key)" }
        $after = $after.Replace($replacement.Before, $replacement.After)
    }
    if ($after -ceq $before) { throw "Correction has no effect: $($correction.Key)" }
    # Preserve scopes and formatting, with the two explicitly reviewed expression changes.
    $comparableBefore = $before
    if ($correction.Issue -eq 'LOTD-007') { $comparableBefore = $comparableBefore.Replace('[maegor.GetTitledFirstName]', '') }
    $withoutGender = $genderPattern.Replace($after, '')
    foreach ($pattern in @('\[[^\]]*\]', '\$[^$]+\$', '@[A-Za-z0-9_]+!', '#!|#[A-Za-z][A-Za-z0-9_]*')) {
        if ((Get-Tokens $comparableBefore $pattern) -cne (Get-Tokens $withoutGender $pattern)) { throw "Lost or changed tokens in $($correction.Key): $pattern" }
    }
    if ($correction.Issue -eq 'LOTD-006') {
        if ([regex]::Matches($after, '\\n').Count -ne 2) { throw 'Expected one new paragraph in the rule tooltip.' }
    } elseif ((Get-Tokens $before '\\[nrt"\\]') -cne (Get-Tokens $after '\\[nrt"\\]')) { throw 'Changed control sequences.' }
    $patches[$correction.Catalog].Add($correction.Key, $after)
    $changes += [pscustomobject]@{ Issue=$correction.Issue; Catalog=$correction.Catalog; File=$correction.File; Key=$correction.Key; Before=$before; After=$after }
}
if ($patches.RU.Count -ne 17 -or $patches.EN.Count -ne 8) { throw 'Expected 17 Russian and eight English entries.' }

$outputs = [ordered]@{}
foreach ($language in @('RU','EN')) {
    $header = if ($language -eq 'RU') { 'russian' } else { 'english' }
    $lines = @(('l_' + $header + ':'), ' # Generated from docs/corrections.json; only reviewed changed keys.')
    foreach ($key in $patches[$language].Keys | Sort-Object -CaseSensitive) { $lines += ' ' + $key + ':0 "' + $patches[$language][$key] + '"' }
    $content = ($lines -join "`n") + "`n"
    $overlay = Read-Catalog $content $header
    foreach ($key in $overlay.Keys) { $catalogs[$language][$key] = $overlay[$key] }
    $outputs[('localization/replace/' + $header + '/zzzz_legacy_of_the_dragon_rus_correct_l_' + $header + '.yml')] = $content
    if ($catalogs[$language].Count -ne 262) { throw 'Expected 260 original keys plus two aliases.' }
    foreach ($key in $catalogs[$language].Keys) {
        foreach ($reference in [regex]::Matches($catalogs[$language][$key], '\$([^$]+)\$')) {
            $target = $reference.Groups[1].Value
            if (-not $catalogs[$language].ContainsKey($target) -and -not $external[$language].ContainsKey($target)) { throw "Unresolved localization alias: $target" }
        }
    }
}

foreach ($group in $scriptCorrections | Group-Object File) {
    $content = [IO.File]::ReadAllText((Join-Path $MainModPath $group.Name), $utf8).Replace("`r`n", "`n")
    foreach ($change in $group.Group) {
        if (-not $change.Before -or [regex]::Matches($content, [regex]::Escape($change.Before)).Count -ne 1) { throw "Script fragment differs: $($group.Name)" }
        $content = $content.Replace($change.Before, $change.After)
    }
    $withoutComments = $content -replace '(?m)#.*$', '' -replace '"[^"\r\n]*"', '""'
    if ([regex]::Matches($withoutComments, '\{').Count -ne [regex]::Matches($withoutComments, '\}').Count) { throw "Unbalanced script: $($group.Name)" }
    $outputs[$group.Name] = $content
}

# Behavioral checks operate on the resulting scripts and effective localization.
. (Join-Path $PSScriptRoot 'Test-LegacyOfTheDragonContracts.ps1')
Test-LegacyContracts -Outputs $outputs -Catalogs $catalogs -MainModPath $MainModPath

$descriptor = @(
    'version="1.0.0"', 'tags={', '    "Translation"', '    "Fixes"', '}',
    ('name="' + $baseline.ModName + '"'), 'supported_version="1.19.0.6"',
    'dependencies={', ('    "' + $baseline.MainName + '"'), ('    "' + $baseline.TranslationName + '"'), '}'
) -join "`n"
$outputs['descriptor.mod'] = $descriptor + "`n"
$externalDescriptor = $descriptor + "`npath=""" + $modRoot.Replace('\','/') + """`n"
$externalPath = Join-Path (Split-Path -Parent $modRoot) 'LEGACY_OF_THE_DRAGON_RUS_CORRECT.mod'
if ($externalDescriptor -notmatch '(?m)^path="([^"\r\n]+)"$' -or [IO.Path]::GetFullPath($Matches[1]) -ne $modRoot) { throw 'Incorrect external descriptor path.' }
foreach ($line in $externalDescriptor -split '\r?\n') { if ([regex]::Matches($line, '"').Count % 2) { throw 'Malformed descriptor string.' } }

function Write-Or-Check([string]$Path, [string]$Content) {
    $Content=[RepositoryText]::Normalize($Content)
    if ($Check) {
        $expectedBytes = $utf8.GetPreamble() + $utf8.GetBytes($Content)
        if (-not (Test-Path -LiteralPath $Path) -or
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($Path)) -cne [Convert]::ToBase64String($expectedBytes)) { throw "Generated file differs: $Path" }
    } else {
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Path)) | Out-Null
        [RepositoryText]::WriteAllText($Path, $Content, $utf8)
    }
}

$manifestOutputs = @()
foreach ($file in $outputs.Keys) {
    $path = Join-Path $modRoot $file
    Write-Or-Check $path $outputs[$file]
    $manifestOutputs += [pscustomobject]@{File=$file; SHA256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
}
Write-Or-Check $externalPath $externalDescriptor
$manifest = [ordered]@{
    MainWorkshopId='3101422928'; MainVersion='1.3.1'; TranslationWorkshopId='3713762177'; TranslationVersion='1.0.0'
    RussianEntries=$patches.RU.Count; EnglishEntries=$patches.EN.Count; AddedKeysPerLanguage=2; EffectiveKeysPerLanguage=262
    Changes=$changes; ScriptChanges=$scriptCorrections; Outputs=$manifestOutputs; ExternalDescriptorSHA256=(Get-FileHash -LiteralPath $externalPath -Algorithm SHA256).Hash
}
Write-Or-Check (Join-Path $modRoot 'docs/source-manifest.json') (($manifest | ConvertTo-Json -Depth 8) + "`n")
if ($Check) {
    $actualFiles = @(Get-ChildItem -LiteralPath (Join-Path $modRoot 'localization'),(Join-Path $modRoot 'common'),(Join-Path $modRoot 'events') -File -Recurse)
    if ($actualFiles.Count -ne 5) { throw 'Expected two localization overlays and three script overrides.' }
}
Write-Output "Validated: 262 effective keys per language; 17 RU and 8 EN entries; two new aliases per language; three script overrides; $($baseline.Sources.Count) source hashes."
Write-Output $(if ($Check) { 'Package and manifest match reviewed corrections byte for byte.' } else { 'Built Legacy_Of_The_Dragon_RUS_CORRECT and its external .mod descriptor.' })
