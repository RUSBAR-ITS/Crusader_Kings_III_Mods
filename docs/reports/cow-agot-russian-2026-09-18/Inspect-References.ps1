param(
    [string]$MainPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2971198450',
    [string]$AgotRussianPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2962803371',
    [string]$VanillaPath = 'E:\SteamLibrary\steamapps\common\Crusader Kings III\game'
)
$ErrorActionPreference = 'Stop'
$pairs = Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'paired-texts.csv')
$own = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
foreach ($pair in $pairs) { $own.Add($pair.Key, $pair.Russian) }
$external = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
$overlaps = [Collections.Generic.List[object]]::new()
foreach ($catalog in @(@{Label='AGOT_RU';Root=$AgotRussianPath},@{Label='CK3';Root=$VanillaPath})) {
    foreach ($file in Get-ChildItem -LiteralPath (Join-Path $catalog.Root 'localization') -Recurse -File -Filter '*_l_russian.yml') {
        $content = [IO.File]::ReadAllText($file.FullName)
        if ($content -notmatch '(?m)^\s*l_russian:\s*$') { continue }
        $lineNumber = 0
        foreach ($line in $content -split '\r?\n') {
            $lineNumber++
            if ($line -notmatch '^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<value>.*)"\s*(?:#.*)?$') { continue }
            $key = $Matches.key
            $entry = [pscustomobject]@{Catalog=$catalog.Label;File=$file.FullName;Line=$lineNumber;Key=$key;Text=$Matches.value}
            if (-not $external.ContainsKey($key)) { $external.Add($key, $entry) }
            if ($own.ContainsKey($key)) { $overlaps.Add($entry) }
        }
    }
}
$refs = [Collections.Generic.List[object]]::new()
$hashes = [Collections.Generic.List[object]]::new()
foreach ($folder in @('common','events','gui','gfx/map/map_modes')) {
    foreach ($file in Get-ChildItem -LiteralPath (Join-Path $MainPath $folder) -Recurse -File | Where-Object {$_.Extension -in @('.txt','.gui')}) {
        $relative = $file.FullName.Substring($MainPath.Length + 1).Replace('\','/')
        $hashes.Add([pscustomobject]@{File=$relative;SHA256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash})
        $lineNumber = 0
        foreach ($line in [IO.File]::ReadAllLines($file.FullName)) {
            $lineNumber++
            if ($line -match '^\s*#') { continue }
            foreach ($match in [regex]::Matches($line, '\b(?<field>title|desc|description|effect_desc|text|custom_tooltip|selection_tooltip|confirm_text|name)\s*=\s*"?(?<key>[A-Za-z_][A-Za-z_0-9.]*)(?=[\s"#}]|$)')) {
                $key = $match.Groups['key'].Value
                $definition = $external[$key]
                $refs.Add([pscustomobject]@{File=$relative;Line=$lineNumber;Field=$match.Groups['field'].Value;Key=$key;LocalRussian=$own.ContainsKey($key);ExternalRussian=[bool]$definition;ExternalCatalog=$definition.Catalog;ExternalFile=$definition.File;ExternalLine=$definition.Line})
            }
        }
    }
}
$refs | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'script-references-review.csv') -NoTypeInformation -Encoding UTF8
$hashes | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'script-source-files.csv') -NoTypeInformation -Encoding UTF8
$overlaps | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'external-overlaps.csv') -NoTypeInformation -Encoding UTF8
$refs | Where-Object {-not $_.LocalRussian -and -not $_.ExternalRussian} | Group-Object Key | Select-Object Name,Count | Format-Table -AutoSize

# Implicit building localization candidates. Missing type descriptions can fall
# back to level descriptions; graphical-only buildings need manual exclusion.
$implicit = [Collections.Generic.List[object]]::new()
foreach ($file in Get-ChildItem -LiteralPath (Join-Path $MainPath 'common/buildings') -File -Filter '*.txt') {
    $content = [IO.File]::ReadAllText($file.FullName)
    foreach ($match in [regex]::Matches($content, '(?m)^(?<id>[A-Za-z_0-9]+)\s*=\s*\{')) {
        $id = $match.Groups['id'].Value
        foreach ($key in @("building_$id", "building_${id}_desc", "building_type_$id", "building_type_${id}_desc")) {
            $def = $external[$key]
            $implicit.Add([pscustomobject]@{File=$file.Name;Line=([regex]::Matches($content.Substring(0,$match.Index),"`n").Count+1);Building=$id;Key=$key;LocalRussian=$own.ContainsKey($key);ExternalRussian=[bool]$def;ExternalFile=$def.File;ExternalLine=$def.Line})
        }
    }
}
$implicit | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'implicit-building-keys-review.csv') -Encoding UTF8 -NoTypeInformation
$implicit | Where-Object {-not $_.LocalRussian -and -not $_.ExternalRussian -and $_.File -ne '99_background_graphics_buildings.txt' -and $_.Key -notlike 'building_type_*'} | Select-Object Building,Key | Format-Table -AutoSize
