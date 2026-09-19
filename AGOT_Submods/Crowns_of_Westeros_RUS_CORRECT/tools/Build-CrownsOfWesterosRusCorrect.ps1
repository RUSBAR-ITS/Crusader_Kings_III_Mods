param(
    [string]$MainModPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2995674648',
    [string]$TranslationPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3412539516',
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$modRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$utf8 = [Text.UTF8Encoding]::new($true, $true)
$baseline = Get-Content -LiteralPath (Join-Path $modRoot 'docs/source-baseline.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$corrections = Get-Content -LiteralPath (Join-Path $modRoot 'docs/corrections.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$entryPattern = [regex]'^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<text>.*)"\s*(?:#.*)?$'
$genderPattern = [regex]"\[Select_CString\(ROOT\.Char\.IsFemale, '([^']+)', '([^']+)'\)\]"

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
    $root = if ($source.Catalog -eq 'RU') { $TranslationPath } else { $MainModPath }
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
    if ($catalogs[$language].Count -ne 689) { throw "Expected 689 $language keys." }
}
foreach ($key in $catalogs.EN.Keys) { if (-not $catalogs.RU.ContainsKey($key)) { throw "Missing Russian key: $key" } }

$changes = @()
foreach ($correction in $corrections) {
    if ($correction.Catalog -notin @('RU','EN')) { throw 'Unknown correction catalog.' }
    $root = if ($correction.Catalog -eq 'RU') { $TranslationPath } else { $MainModPath }
    $header = if ($correction.Catalog -eq 'RU') { 'russian' } else { 'english' }
    $entries = Read-Catalog ([IO.File]::ReadAllText((Join-Path $root $correction.File), $utf8)) $header
    if (-not $entries.ContainsKey($correction.Key)) { throw "Missing source key: $($correction.Key)" }
    $before = $entries[$correction.Key]
    if ([string]::IsNullOrEmpty($correction.Before) -or
        [regex]::Matches($before, [regex]::Escape($correction.Before)).Count -ne $correction.Count) { throw "Source fragment count differs: $($correction.Key)" }
    $after = $before.Replace($correction.Before, $correction.After)
    if ($after -ceq $before) { throw "Correction has no effect: $($correction.Key)" }
    # Only four reviewed ROOT gender selectors may be introduced; keep other scopes and tokens.
    $withoutGender = $genderPattern.Replace($after, '')
    foreach ($pattern in @('\[[^\]]*\]', '\$[^$]+\$', '@[A-Za-z0-9_]+!', '#!|#[A-Za-z][A-Za-z0-9_]*')) {
        if ((Get-Tokens $before $pattern) -cne (Get-Tokens $withoutGender $pattern)) { throw "Lost or changed tokens in $($correction.Key): $pattern" }
    }
    if ($correction.Issue -eq 'SOURCE-04') {
        if ($after.Contains('/n') -or [regex]::Matches($after, '\\n').Count -ne 6) { throw 'Incorrect English paragraph repair.' }
    } elseif ((Get-Tokens $before '\\[nrt"\\]') -cne (Get-Tokens $after '\\[nrt"\\]')) { throw 'Changed control sequences.' }
    $patches[$correction.Catalog].Add($correction.Key, $after)
    $changes += [pscustomobject]@{ Issue=$correction.Issue; Catalog=$correction.Catalog; File=$correction.File; Key=$correction.Key; Before=$before; After=$after }
}
if ($patches.RU.Count -ne 24 -or $patches.EN.Count -ne 5) { throw 'Expected 24 Russian and five English overrides.' }

$outputs = [ordered]@{}
foreach ($language in @('RU','EN')) {
    $header = if ($language -eq 'RU') { 'russian' } else { 'english' }
    $lines = @(('l_' + $header + ':'), ' # Generated from docs/corrections.json; only reviewed changed keys.')
    foreach ($key in $patches[$language].Keys | Sort-Object -CaseSensitive) { $lines += ' ' + $key + ':0 "' + $patches[$language][$key] + '"' }
    $content = ($lines -join "`n") + "`n"
    $overlay = Read-Catalog $content $header
    foreach ($key in $overlay.Keys) { $catalogs[$language][$key] = $overlay[$key] }
    $outputs[('localization/replace/' + $header + '/zzzz_crowns_of_westeros_rus_correct_l_' + $header + '.yml')] = $content
}

# Check both grammatical branches and the same artifact names across interfaces.
$genderCases = @(
    @{Key='ntc_find_lost_crown_event.6.desc'; Female='я позволила'; Male='я позволил'},
    @{Key='ntc_find_lost_crown_event.7.desc'; Female='ты победила'; Male='ты победил'},
    @{Key='ntc_find_lost_crown_event.7.a'; Female='Рада, что'; Male='Рад, что'},
    @{Key='agot_commission_special_artifact_crown.1313.d'; Female='Я передумала.'; Male='Я передумал.'}
)
foreach ($case in $genderCases) {
    $value = $catalogs.RU[$case.Key]
    if ($genderPattern.Matches($value).Count -ne 1 -or
        -not $genderPattern.Replace($value, '$1').Contains($case.Female) -or
        -not $genderPattern.Replace($value, '$2').Contains($case.Male)) { throw "Incorrect gender branches: $($case.Key)" }
}
foreach ($language in @('EN','RU')) {
    foreach ($sex in @('','female_')) {
        $label = $catalogs[$language]['PORTRAIT_MODIFIER_custom_headgear_' + $sex + 'garlandgardener_crown'] -replace '^@[^!]+!\s*',''
        if ($label -cne $catalogs[$language]['garlandgardener_crown_name']) { throw 'Wynafryd artifact/portrait mismatch.' }
    }
}
foreach ($crown in @('goldfyre','greenpyre')) {
    foreach ($sex in @('','female_')) {
        $label = $catalogs.RU['PORTRAIT_MODIFIER_custom_headgear_' + $sex + $crown + '_crown'] -replace '^@[^!]+!\s*','' -replace ' \([^)]*\)$',''
        if ($label -cne $catalogs.RU[$crown + '_crown_name']) { throw 'Hybrid artifact/portrait mismatch.' }
    }
}

$descriptor = @(
    'version="1.0.0"', 'tags={', '    "Translation"', '    "Fixes"', '}',
    ('name="' + $baseline.ModName + '"'), 'supported_version="1.19.0.6"',
    'dependencies={', ('    "' + $baseline.MainName + '"'), ('    "' + $baseline.TranslationName + '"'), '}'
) -join "`n"
$outputs['descriptor.mod'] = $descriptor + "`n"
$externalDescriptor = $descriptor + "`npath=""" + $modRoot.Replace('\','/') + """`n"
$externalPath = Join-Path (Split-Path -Parent $modRoot) 'CROWNS_OF_WESTEROS_RUS_CORRECT.mod'
if ($externalDescriptor -notmatch '(?m)^path="([^"\r\n]+)"$' -or [IO.Path]::GetFullPath($Matches[1]) -ne $modRoot) { throw 'Incorrect external descriptor path.' }
foreach ($line in $externalDescriptor -split '\r?\n') { if ([regex]::Matches($line, '"').Count % 2) { throw 'Malformed descriptor string.' } }

function Write-Or-Check([string]$Path, [string]$Content) {
    if ($Check) {
        $expectedBytes = $utf8.GetPreamble() + $utf8.GetBytes($Content)
        if (-not (Test-Path -LiteralPath $Path) -or
            [Convert]::ToBase64String([IO.File]::ReadAllBytes($Path)) -cne [Convert]::ToBase64String($expectedBytes)) { throw "Generated file differs: $Path" }
    } else {
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Path)) | Out-Null
        [IO.File]::WriteAllText($Path, $Content, $utf8)
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
    MainWorkshopId='2995674648'; MainVersion='1.0'; TranslationWorkshopId='3412539516'; TranslationVersion='1'
    RussianOverrides=$patches.RU.Count; EnglishOverrides=$patches.EN.Count; EffectiveKeysPerLanguage=689
    Changes=$changes; Outputs=$manifestOutputs; ExternalDescriptorSHA256=(Get-FileHash -LiteralPath $externalPath -Algorithm SHA256).Hash
}
Write-Or-Check (Join-Path $modRoot 'docs/source-manifest.json') (($manifest | ConvertTo-Json -Depth 8) + "`n")
if ($Check) {
    $actualFiles = @(Get-ChildItem -LiteralPath (Join-Path $modRoot 'localization') -File -Recurse)
    if ($actualFiles.Count -ne 2 -or (Test-Path -LiteralPath (Join-Path $modRoot 'common')) -or (Test-Path -LiteralPath (Join-Path $modRoot 'events'))) { throw 'Unexpected game files in a localization-only patch.' }
}
Write-Output "Validated: 689 effective keys per language; 24 RU and 5 EN overrides; preserved scopes, references, icons and formatting; four female/male forms; consistent artifact/portrait names; $($baseline.Sources.Count) source hashes."
Write-Output $(if ($Check) { 'Package and manifest match reviewed corrections byte for byte.' } else { 'Built Crowns_of_Westeros_RUS_CORRECT and its external .mod descriptor.' })
