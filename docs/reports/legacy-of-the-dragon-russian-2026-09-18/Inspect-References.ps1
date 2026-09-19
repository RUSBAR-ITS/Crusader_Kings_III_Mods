param(
    [string]$MainPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3101422928',
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
foreach ($folder in @('common','events','gui')) {
    foreach ($file in Get-ChildItem -LiteralPath (Join-Path $MainPath $folder) -Recurse -File | Where-Object {$_.Extension -in @('.txt','.gui')}) {
        $relative = $file.FullName.Substring($MainPath.Length + 1).Replace('\','/')
        $hashes.Add([pscustomobject]@{File=$relative;SHA256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash})
        $lineNumber = 0
        foreach ($line in [IO.File]::ReadAllLines($file.FullName)) {
            $lineNumber++
            if ($line -match '^\s*#') { continue }
            foreach ($match in [regex]::Matches($line, '\b(?<field>title|desc|description|text|custom_tooltip|selection_tooltip|confirm_text|name)\s*=\s*"?(?<key>[A-Za-z_][A-Za-z_0-9.]*)(?=[\s"#}]|$)')) {
                $key = $match.Groups['key'].Value
                $definition = $external[$key]
                $refs.Add([pscustomobject]@{File=$relative;Line=$lineNumber;Field=$match.Groups['field'].Value;Key=$key;LocalRussian=$own.ContainsKey($key);ExternalRussian=[bool]$definition;ExternalCatalog=$definition.Catalog;ExternalFile=$definition.File;ExternalLine=$definition.Line})
            }
        }
    }
}
$contracts = [Collections.Generic.List[object]]::new()
$memoryText = [IO.File]::ReadAllText((Join-Path $MainPath 'common/character_memory_types/lotd_memories.txt'))
foreach ($block in [regex]::Matches($memoryText, '(?ms)^(?<type>[A-Za-z_][A-Za-z_0-9]*)\s*=\s*\{.*?(?=^[A-Za-z_][A-Za-z_0-9]*\s*=\s*\{|\z)')) {
    $participants = [regex]::Match($block.Value, 'participants\s*=\s*\{([^}]*)\}').Groups[1].Value
    $allowed = @('owner') + @([regex]::Matches($participants, '[A-Za-z_][A-Za-z_0-9]*') | ForEach-Object {$_.Value})
    foreach ($description in [regex]::Matches($block.Value, '\bdesc\s*=\s*(?<key>[A-Za-z_0-9]+)')) {
        $key = $description.Groups['key'].Value
        $used = @([regex]::Matches($own[$key], '\b([A-Za-z_][A-Za-z_0-9]*)\.(?:Get|Is)[A-Za-z]+') | ForEach-Object {$_.Groups[1].Value} | Sort-Object -Unique)
        $contracts.Add([pscustomobject]@{Memory=$block.Groups['type'].Value;Key=$key;RussianExists=$own.ContainsKey($key);AllowedScopes=($allowed -join ',');UsedScopes=($used -join ',');UnavailableScopes=(@($used | Where-Object {$_ -cnotin $allowed}) -join ',')})
    }
}
$refs | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'script-references-review.csv') -NoTypeInformation -Encoding UTF8
$hashes | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'script-source-files.csv') -NoTypeInformation -Encoding UTF8
$overlaps | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'external-overlaps.csv') -NoTypeInformation -Encoding UTF8
$contracts | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'memory-contracts.csv') -NoTypeInformation -Encoding UTF8
$refs | Where-Object {-not $_.LocalRussian -and -not $_.ExternalRussian} | Group-Object Key | Select-Object Name,Count | Format-Table -AutoSize
Write-Output "Reviewed $($contracts.Count) memory descriptions; $($hashes.Count) script/GUI files; $($overlaps.Count) external duplicate definitions."
