param(
    [string]$MainModPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2971198450',
    [string]$TranslationPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3496379669',
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
$roots = @{EN=$MainModPath;Main=$MainModPath;Translation=$TranslationPath;AGOT=$AgotPath;AGOT_RU=$AgotRussianPath}
$entryPattern = [regex]'^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<text>.*)"\s*(?:#.*)?$'
$shadowFile = 'localization/replace/english/zz_agot_unique_buildings_l_english.yml'

function Get-Tokens([string]$Text,[string]$Pattern) {
    return (([regex]::Matches($Text,$Pattern) | ForEach-Object Value | Sort-Object -CaseSensitive) -join ' || ')
}
function Read-Catalog([string]$Text,[string]$Language) {
    $result = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    $headers = 0
    foreach ($line in $Text.TrimStart([char]0xFEFF) -split '\r?\n') {
        if ($line -match '^\s*(?:#.*)?$') { continue }
        if ($line -cmatch ('^l_'+$Language+':\s*$')) { $headers++; continue }
        $match = $entryPattern.Match($line)
        if (-not $match.Success) { throw "Malformed localization: $line" }
        $value = $match.Groups['text'].Value
        if ($value -match '(?<!\\)"|\\(?![nrt"\\])' -or
            [regex]::Matches($value,'\[').Count -ne [regex]::Matches($value,'\]').Count -or
            [regex]::Matches($value,'\$').Count % 2) { throw "Broken localization template: $line" }
        $depth = 0
        foreach ($token in [regex]::Matches($value,'#!|#[A-Za-z][A-Za-z0-9_]*')) {
            if ($token.Value -eq '#!') { $depth-- } else { $depth++ }
            if ($depth -lt 0) { throw 'Formatting closes without opening.' }
        }
        if ($depth) { throw 'Unclosed formatting.' }
        $result.Add($match.Groups['key'].Value,$value)
    }
    if ($headers -ne 1) { throw "Expected one $Language header." }
    return ,$result
}

# Refuse to build from a changed Workshop snapshot.
foreach ($source in $baseline.Files) {
    $path = Join-Path $roots[$source.Catalog] $source.File
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -cne $source.SHA256) { throw "Source changed; repeat audit: $path" }
}
$catalogs = @{}
$overlays = @{}
$sourceTexts = @{}
$syntaxFix = $null
foreach ($lang in @('EN','RU')) {
    $root = if ($lang -eq 'EN') {$MainModPath} else {$TranslationPath}
    $label = if ($lang -eq 'EN') {'EN'} else {'Translation'}
    $header = if ($lang -eq 'EN') {'english'} else {'russian'}
    $sources = @($baseline.Files | Where-Object {$_.Catalog -eq $label -and $_.File.StartsWith('localization/')})
    # Include the misnamed Russian file by audited path, not by filename suffix.
    $actual = @(Get-ChildItem -LiteralPath (Join-Path $root 'localization') -Recurse -File -Filter '*.yml' | ForEach-Object {$_.FullName.Substring($root.TrimEnd('\','/').Length+1).Replace('\','/')})
    if ((($actual | Sort-Object -CaseSensitive) -join '|') -cne (($sources.File | Sort-Object -CaseSensitive) -join '|')) { throw "Changed localization inventory: $lang" }
    $catalogs[$lang] = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    $overlays[$lang] = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    foreach ($source in $sources) {
        $content = [IO.File]::ReadAllText((Join-Path $root $source.File),$utf8).Replace("`r`n","`n")
        if ($lang -eq 'EN' -and $source.File -ceq $shadowFile) {
            $bad = [regex]::Matches($content,'(?m)^\s*setting_yes_use_rebuilt_crag_desc: "The Crag starts as a fully built and functional castle\.$')
            if ($bad.Count -ne 1) { throw 'Expected exactly the audited missing closing quote.' }
            $before = $bad[0].Value
            $content = $content.Replace($before,($before+'"'))
            $syntaxFix = [ordered]@{Issue='COW-02';File=$shadowFile;Before=$before;After=($before+'"')}
        }
        $sourceTexts[$lang+':'+$source.File] = $content
        $entries = Read-Catalog $content $header
        foreach ($key in $entries.Keys) { $catalogs[$lang].Add($key,$entries[$key]) }
    }
    if ($catalogs[$lang].Count -ne 189) { throw "Expected 189 source keys: $lang" }
}
$allScriptPaths = @(foreach ($folder in @('common','events','gui','gfx/map/map_modes')) {
    Get-ChildItem -LiteralPath (Join-Path $MainModPath $folder) -Recurse -File | Where-Object {$_.Extension -in @('.txt','.gui')} | ForEach-Object {$_.FullName.Substring($MainModPath.TrimEnd('\','/').Length+1).Replace('\','/')}
})
$expectedScriptPaths = @($baseline.Files | Where-Object {$_.Catalog -eq 'Main' -and $_.File -ne 'descriptor.mod'} | ForEach-Object File)
if ((($allScriptPaths | Sort-Object -CaseSensitive) -join '|') -cne (($expectedScriptPaths | Sort-Object -CaseSensitive) -join '|')) { throw 'Changed script inventory.' }

$changes = [Collections.Generic.List[object]]::new()
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$englishEdits = @{}
foreach ($c in $corrections) {
    if ($c.Catalog -cnotin @('RU','EN') -or -not $seen.Add($c.Catalog+':'+$c.Key)) { throw 'Unknown catalog or duplicate correction.' }
    $original = $catalogs[$c.Catalog]
    if ($c.Mode -eq 'Add') {
        if ($original.ContainsKey($c.Key) -or $c.Key -cne 'cow_custom_mapmode.t') { throw 'Unexpected new key.' }
    } else {
        $header = if ($c.Catalog -eq 'RU') {'russian'} else {'english'}
        $sourceCatalog = Read-Catalog $sourceTexts[$c.Catalog+':'+$c.File] $header
        if (-not $sourceCatalog.ContainsKey($c.SourceKey) -or $sourceCatalog[$c.SourceKey] -cne $c.Before) { throw "Reviewed source text changed: $($c.Key)" }
        if ($c.Mode -eq 'Alias') {
            if ($original.ContainsKey($c.Key) -or $c.After -cne ('$'+$c.SourceKey+'$')) { throw 'Invalid new building alias.' }
        } elseif ($c.Mode -eq 'Copy') {
            if ($c.Catalog -cne 'RU' -or $c.After -cne $c.Before -or $c.File -notlike '*ruins_l_english.yml') { throw 'Unexpected unchanged copy.' }
        } elseif ($c.Mode -eq 'Replace') {
            if ($c.After -ceq $c.Before -or $c.Key -cne $c.SourceKey) { throw 'Invalid text replacement.' }
            $beforeTokens = $c.Before
            if ('COW-05' -cin $c.Issues) {
                # These two corrections intentionally drop the misleading stage-four reference.
                $wrong = if ($c.Key -ceq 'REBUILD_CASTAMERE_SECOND') {"[GetBuilding('medium_ruin_04').GetName]"} elseif ($c.Key -ceq 'REBUILD_OLDSTONES_SECOND') {"[GetBuilding('large_ruin_04').GetName]"} else {throw 'Unexpected ruin tooltip.'}
                $beforeTokens = $beforeTokens.Replace($wrong,'')
            }
            foreach ($pattern in @('\[[^\]]*\]','\$[^$]+\$','@[^!\s]+!','#!|#[A-Za-z][A-Za-z0-9_]*','\\[nrt"\\]')) {
                if ((Get-Tokens $beforeTokens $pattern) -cne (Get-Tokens $c.After $pattern)) { throw "Changed localization tokens: $($c.Key) / $pattern" }
            }
        } else { throw "Unknown correction mode: $($c.Mode)" }
    }
    $header = if ($c.Catalog -eq 'RU') {'russian'} else {'english'}
    $null = Read-Catalog ("l_${header}:`n "+$c.Key+':0 "'+$c.After+'"') $header
    if ($c.Catalog -eq 'EN' -and $c.Mode -eq 'Replace') {
        if ($c.File -cne $shadowFile) { throw 'Unexpected English shadow target.' }
        $englishEdits.Add($c.Key,$c.After)
    } else { $overlays[$c.Catalog].Add($c.Key,$c.After) }
    $changes.Add($c)
}
if ($overlays.RU.Count -ne 26 -or $overlays.EN.Count -ne 5 -or $englishEdits.Count -ne 44) { throw 'Unexpected correction totals.' }

# Preserve the original English file path to prevent parsing its malformed line.
$shadowLines = foreach ($line in $sourceTexts['EN:'+$shadowFile] -split "`n") {
    $m = $entryPattern.Match($line)
    if ($m.Success -and $englishEdits.ContainsKey($m.Groups['key'].Value)) {
        $prefix = $line.Substring(0,$m.Groups['text'].Index)
        $suffix = $line.Substring($m.Groups['text'].Index+$m.Groups['text'].Length)
        $prefix + $englishEdits[$m.Groups['key'].Value] + $suffix
    } else { $line }
}
$outputs = [ordered]@{}
$outputs[$shadowFile] = $shadowLines -join "`n"
$shadow = Read-Catalog $outputs[$shadowFile] 'english'
if ($shadow.Count -ne 185) { throw 'English shadow lost entries.' }
foreach ($key in $shadow.Keys) { $catalogs.EN[$key] = $shadow[$key] }
foreach ($lang in @('RU','EN')) {
    $header = if ($lang -eq 'RU') {'russian'} else {'english'}
    $lines = @(('l_'+$header+':'),' # Generated from docs/corrections.json; reviewed fixes only.')
    foreach ($key in $overlays[$lang].Keys | Sort-Object -CaseSensitive) { $lines += ' '+$key+':0 "'+$overlays[$lang][$key]+'"' }
    $content = ($lines -join "`n")+"`n"
    $entries = Read-Catalog $content $header
    foreach ($key in $entries.Keys) { $catalogs[$lang][$key] = $entries[$key] }
    $outputs['localization/replace/'+$header+'/zzzz_cow_agot_rus_correct_l_'+$header+'.yml'] = $content
    if ($catalogs[$lang].Count -ne 194) { throw 'Expected 194 effective COW keys including corrected aliases and map text.' }
    # All inline localization aliases resolve; no circular aliases permitted.
    foreach ($key in $catalogs[$lang].Keys) {
        $visited = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        $target = $key
        while ($catalogs[$lang][$target] -cmatch '^\$([^$]+)\$$') {
            if (-not $visited.Add($target)) { throw "Alias cycle: $key" }
            $target = $Matches[1]
            if (-not $catalogs[$lang].ContainsKey($target)) { throw "Missing alias target: $target" }
        }
    }
}
foreach ($key in $catalogs.EN.Keys) { if (-not $catalogs.RU.ContainsKey($key)) { throw "Missing effective Russian key: $key" } }
# Model Russian loading without the misnamed _l_english file. The patch must
# provide all four restoration tooltips even when that source file is skipped.
$russianByFilename = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
foreach ($file in Get-ChildItem -LiteralPath (Join-Path $TranslationPath 'localization') -Recurse -File -Filter '*_l_russian.yml') {
    $entries = Read-Catalog ([IO.File]::ReadAllText($file.FullName,$utf8)) 'russian'
    foreach ($key in $entries.Keys) { $russianByFilename.Add($key,$entries[$key]) }
}
foreach ($key in $overlays.RU.Keys) { $russianByFilename[$key] = $overlays.RU[$key] }
if ($russianByFilename.Count -ne $catalogs.RU.Count) { throw 'Coverage depends on loading the misnamed Russian file.' }
foreach ($key in $catalogs.RU.Keys) {
    if (-not $russianByFilename.ContainsKey($key) -or $russianByFilename[$key] -cne $catalogs.RU[$key]) { throw "Incorrect effective Russian text: $key" }
}
. (Join-Path $PSScriptRoot 'Test-COWAGOTContracts.ps1')
Test-COWContracts $catalogs $MainModPath $AgotPath

$descriptor = @('version="1.0.0"','tags={','    "Translation"','    "Fixes"','}',
    'name="COW-AGOT | Исправления русификатора"','supported_version="1.19.0.6"',
    'dependencies={','    "COW-AGOT: 3D Models & Bigger Castles"','    "COW-AGOT: 3D Models & Bigger Castles rus"','}') -join "`n"
$outputs['descriptor.mod'] = $descriptor+"`n"
$external = $descriptor+"`npath="""+$modRoot.Replace('\','/')+"""`n"
$externalPath = Join-Path (Split-Path -Parent $modRoot) 'COW_AGOT_RUS_CORRECT.mod'
if ($external -notmatch '(?m)^path="([^"\r\n]+)"$' -or [IO.Path]::GetFullPath($Matches[1]) -ne $modRoot) { throw 'Invalid descriptor path.' }
function Write-Or-Check([string]$Path,[string]$Content) {
    $Content=[RepositoryText]::Normalize($Content)
    if ($Check) {
        $expected = $utf8.GetPreamble()+$utf8.GetBytes($Content)
        if (-not (Test-Path -LiteralPath $Path) -or [Convert]::ToBase64String([IO.File]::ReadAllBytes($Path)) -cne [Convert]::ToBase64String($expected)) { throw "Generated file differs: $Path" }
    } else {
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Path)) | Out-Null
        [RepositoryText]::WriteAllText($Path,$Content,$utf8)
    }
}
$manifestOutputs = @()
foreach ($file in $outputs.Keys) {
    $path = Join-Path $modRoot $file
    Write-Or-Check $path $outputs[$file]
    $manifestOutputs += [pscustomobject]@{File=$file;SHA256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
}
Write-Or-Check $externalPath $external
$manifest = [ordered]@{
    MainWorkshopId='2971198450';MainVersion='5.8.7';TranslationWorkshopId='3496379669';TranslationVersion='1.0'
    RussianOverlayKeys=26;EnglishOverlayKeys=5;EnglishShadowKeys=185;EnglishChangedValues=44;EnglishSyntaxRepairs=1
    EffectiveCOWKeysPerLanguage=194;SourceHashesChecked=$baseline.Files.Count;ScriptOverrides=0
    SyntaxRepair=$syntaxFix;Corrections=@($changes.ToArray());Outputs=$manifestOutputs
    ExternalDescriptorSHA256=(Get-FileHash -LiteralPath $externalPath -Algorithm SHA256).Hash
}
Write-Or-Check (Join-Path $modRoot 'docs/source-manifest.json') (($manifest | ConvertTo-Json -Depth 8)+"`n")
$actualFiles = @(Get-ChildItem -LiteralPath (Join-Path $modRoot 'localization') -Recurse -File | ForEach-Object {$_.FullName.Substring($modRoot.Length+1).Replace('\','/')})
$expectedFiles = @($outputs.Keys | Where-Object { $_.StartsWith('localization/') })
if ((($actualFiles | Sort-Object -CaseSensitive) -join '|') -cne (($expectedFiles | Sort-Object -CaseSensitive) -join '|')) { throw 'Unexpected localization output files.' }
foreach ($folder in @('common','events','gui','gfx','history')) {
    if (Test-Path -LiteralPath (Join-Path $modRoot $folder)) { throw 'Localization-only package must not contain script/graphics overrides.' }
}
Write-Output "Validated: 26 RU overlay keys; 5 EN overlay keys; 185-key EN shadow with 44 text edits and one quote repair; 194 effective keys per language; $($baseline.Files.Count) source hashes; no script overrides."
Write-Output $(if($Check){'Package and manifest match reviewed corrections byte for byte.'}else{'Built COW_AGOT_RUS_CORRECT and repository .mod descriptor.'})
