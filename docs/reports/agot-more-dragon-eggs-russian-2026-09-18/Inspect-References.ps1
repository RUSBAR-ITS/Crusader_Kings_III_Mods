param(
    [string]$MainPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3388366564',
    [string]$AgotRussianPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2962803371',
    [string]$VanillaPath = 'E:\SteamLibrary\steamapps\common\Crusader Kings III\game'
)
$ErrorActionPreference = 'Stop'
$pairs = Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'paired-texts.csv')
$own = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
$entries = Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'catalog-entries.csv')
foreach ($entry in $entries | Where-Object {$_.Catalog -eq 'Translation'}) { if (-not $own.ContainsKey($entry.Key)) { $own.Add($entry.Key,$entry.Text) } }
$builtin = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
foreach ($entry in $entries | Where-Object {$_.Catalog -eq 'BuiltinRussian'}) { if (-not $builtin.ContainsKey($entry.Key)) { $builtin.Add($entry.Key,$entry) } }
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
foreach ($folder in @('common','events','gui','data_binding')) {
    if (-not (Test-Path -LiteralPath (Join-Path $MainPath $folder))) { continue }
    foreach ($file in Get-ChildItem -LiteralPath (Join-Path $MainPath $folder) -Recurse -File | Where-Object {$_.Extension -in @('.txt','.gui')}) {
        $relative = $file.FullName.Substring($MainPath.Length + 1).Replace('\','/')
        $hashes.Add([pscustomobject]@{File=$relative;SHA256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash})
        $lineNumber = 0
        foreach ($line in [IO.File]::ReadAllLines($file.FullName)) {
            $lineNumber++
            if ($line -match '^\s*#') { continue }
            foreach ($match in [regex]::Matches($line, '\b(?<field>title|desc|description|effect_desc|tooltip|raw_text|text|custom_tooltip|selection_tooltip|confirm_text|name|localization_key|set_artifact_name|set_artifact_description)\s*=\s*"?(?<key>[A-Za-z_][A-Za-z_0-9.]*)(?=[\s"#}]|$)')) {
                $key = $match.Groups['key'].Value
                $definition = $external[$key]
                $refs.Add([pscustomobject]@{File=$relative;Line=$lineNumber;Field=$match.Groups['field'].Value;Key=$key;LocalRussian=$own.ContainsKey($key);BuiltinRussian=$builtin.ContainsKey($key);ExternalRussian=[bool]$definition;ExternalCatalog=$definition.Catalog;ExternalFile=$definition.File;ExternalLine=$definition.Line})
            }
        }
    }
}
$refs | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'script-references-review.csv') -NoTypeInformation -Encoding UTF8
$hashes | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'script-source-files.csv') -NoTypeInformation -Encoding UTF8
$overlaps | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'external-overlaps.csv') -NoTypeInformation -Encoding UTF8


$coverage = foreach ($pair in $pairs) {
    $b=$builtin[$pair.Key]; $e=$external[$pair.Key]
    [pscustomobject]@{Key=$pair.Key;MainFile=$pair.MainFile;MainLine=$pair.MainLine;English=$pair.English;Translation=$pair.Russian;TranslationPresent=$own.ContainsKey($pair.Key);BuiltinRussian=$b.Text;BuiltinFile=$b.File;BuiltinLine=$b.Line;BuiltinIdenticalToEnglish=([bool]$b -and $b.Text -ceq $pair.English);ExternalCatalog=$e.Catalog;ExternalFile=$e.File;ExternalLine=$e.Line;ExternalRussian=$e.Text;AnyCyrillic=(@($pair.Russian,$b.Text,$e.Text) -join '') -match '[А-Яа-яЁё]'}
}
$coverage | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'coverage-with-fallbacks.csv') -Encoding UTF8 -NoTypeInformation
$coverage | Where-Object {-not $_.TranslationPresent} | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'missing-with-fallbacks.csv') -Encoding UTF8 -NoTypeInformation
$extra = foreach ($entry in $entries | Where-Object {$_.Catalog -eq 'Translation' -and $_.Key -cnotin $pairs.Key}) {
    [pscustomobject]@{Key=$entry.Key;File=$entry.File;Line=$entry.Line;Russian=$entry.Text;BuiltinRussian=$builtin.ContainsKey($entry.Key);ExternalRussian=$external.ContainsKey($entry.Key)}
}
$extra | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'extra-translation-keys.csv') -Encoding UTF8 -NoTypeInformation
Write-Output ('Script sources: '+$hashes.Count+'; references: '+$refs.Count)
