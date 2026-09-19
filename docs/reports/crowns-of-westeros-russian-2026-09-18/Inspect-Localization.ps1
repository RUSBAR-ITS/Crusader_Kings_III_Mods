param(
    [string]$MainPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\2995674648',
    [string]$RussianPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3412539516'
)
$ErrorActionPreference = 'Stop'
$out = $PSScriptRoot
$inventory = [Collections.Generic.List[object]]::new()
$structure = [Collections.Generic.List[object]]::new()
function Read-Catalog([string]$root, [string]$language, [string]$label) {
    $map = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
    foreach ($file in Get-ChildItem -LiteralPath (Join-Path $root 'localization') -Recurse -File -Filter "*_l_$language.yml") {
        $relative = $file.FullName.Substring($root.Length + 1).Replace('\','/')
        $bytes = [IO.File]::ReadAllBytes($file.FullName)
        $content = [Text.UTF8Encoding]::new($false,$true).GetString($bytes).TrimStart([char]0xFEFF)
        $count = 0; $n = 0
        foreach ($line in $content -split '\r?\n') {
            $n++
            if ($line -match '^\s*(#.*)?$' -or $line -match '^\s*l_\w+:\s*$') { continue }
            if ($line -notmatch '^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<text>.*)"\s*(?:#.*)?$') {
                if ($line -match '^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<text>.*)$') {
                    $structure.Add([pscustomobject]@{Catalog=$label;File=$relative;Line=$n;Key=$Matches.key;Problem='Missing closing quote; declared key retained';Text=$line})
                } else {
                    $structure.Add([pscustomobject]@{Catalog=$label;File=$relative;Line=$n;Key='';Problem='Unparsed non-comment line';Text=$line})
                    continue
                }
            }
            $key = $Matches.key; $value = $Matches.text; $count++
            if ($map.ContainsKey($key)) { throw "Duplicate key in ${label}: $key" }
            $map.Add($key, [pscustomobject]@{Key=$key;File=$relative;Line=$n;Text=$value})
            $problems = [Collections.Generic.List[string]]::new()
            if ([regex]::Matches($value,'\[').Count -ne [regex]::Matches($value,'\]').Count) { $problems.Add('Square bracket imbalance') }
            if ([regex]::Matches($value,'\$').Count % 2) { $problems.Add('Dollar delimiter imbalance') }
            if ($value -match '(?<!\\)"') { $problems.Add('Inner double quote: review') }
            if ($value -match '\\(?![ntr"\\])') { $problems.Add('Unexpected escape: review') }
            $depth=0
            foreach ($token in [regex]::Matches($value,'#!|#[A-Za-z][A-Za-z0-9_]*')) {
                if ($token.Value -eq '#!') { $depth-- } else { $depth++ }
                if ($depth -lt 0) { $problems.Add('Formatting closes without opening'); $depth=0 }
            }
            if ($depth -gt 0) { $problems.Add('Unclosed formatting tag') }
            foreach ($problem in $problems) { $structure.Add([pscustomobject]@{Catalog=$label;File=$relative;Line=$n;Key=$key;Problem=$problem;Text=$value}) }
        }
        $inventory.Add([pscustomobject]@{Catalog=$label;File=$relative;Entries=$count;BOM=($bytes.Length -ge 3 -and $bytes[0] -eq 239 -and $bytes[1] -eq 187 -and $bytes[2] -eq 191);SHA256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash})
    }
    return ,$map
}
$en = Read-Catalog $MainPath 'english' 'EN'
$ru = Read-Catalog $RussianPath 'russian' 'Translation'
$builtin = Read-Catalog $MainPath 'russian' 'BuiltinRussian'
$pairs = [Collections.Generic.List[object]]::new()
$tokens = [Collections.Generic.List[object]]::new()
$latin = [Collections.Generic.List[object]]::new()
foreach ($key in $en.Keys | Sort-Object -CaseSensitive) {
    $a=$en[$key]; $b=$ru[$key]
    $pairs.Add([pscustomobject]@{Key=$key;MainFile=$a.File;MainLine=$a.Line;TranslationFile=$b.File;TranslationLine=$b.Line;English=$a.Text;Russian=$b.Text;BuiltinRussian=$builtin[$key].Text})
    foreach ($kind in @('Expressions','References','Icons','Formatting','Escapes')) {
        $pattern = switch ($kind) { Expressions {'\[[^\]]*\]'} References {'\$[^$]+\$'} Icons {'@[^!\s]+!'} Formatting {'#!|#[A-Za-z][A-Za-z0-9_]*'} Escapes {'\\.'} }
        $left=([regex]::Matches($a.Text,$pattern) | ForEach-Object Value | Sort-Object -CaseSensitive) -join ' || '
        $right=([regex]::Matches($b.Text,$pattern) | ForEach-Object Value | Sort-Object -CaseSensitive) -join ' || '
        if ($left -cne $right) { $tokens.Add([pscustomobject]@{Key=$key;Kind=$kind;File=$b.File;Line=$b.Line;EnglishTokens=$left;RussianTokens=$right}) }
    }
    $visible=$b.Text -replace '\[[^\]]*\]','' -replace '\$[^$]+\$','' -replace '@[^!\s]+!','' -replace '#[A-Za-z0-9_!]+','' -replace '\\[ntr]',' '
    if ($visible -match '[A-Za-z]') { $latin.Add([pscustomobject]@{Key=$key;File=$b.File;Line=$b.Line;VisibleText=$visible}) }
}
$pairs | Export-Csv -LiteralPath (Join-Path $out 'paired-texts.csv') -Encoding UTF8 -NoTypeInformation
$inventory | Export-Csv -LiteralPath (Join-Path $out 'source-files.csv') -Encoding UTF8 -NoTypeInformation
$structure | Export-Csv -LiteralPath (Join-Path $out 'structure-review.csv') -Encoding UTF8 -NoTypeInformation
$tokens | Export-Csv -LiteralPath (Join-Path $out 'token-differences-review.csv') -Encoding UTF8 -NoTypeInformation
$latin | Export-Csv -LiteralPath (Join-Path $out 'latin-text-review.csv') -Encoding UTF8 -NoTypeInformation
$stats=[ordered]@{
    EnglishKeys=$en.Count; TranslationKeys=$ru.Count; BuiltinRussianKeys=$builtin.Count
    ExtraTranslationKeys=@($ru.Keys | Where-Object { -not $en.ContainsKey($_) })
    BuiltinMissingFromTranslation=@($builtin.Keys | Where-Object { -not $ru.ContainsKey($_) })
    BuiltinIdenticalToEnglish=@($builtin.Keys | Where-Object { $en.ContainsKey($_) -and $builtin[$_].Text -ceq $en[$_].Text }).Count
    StructureReviewRows=$structure.Count; TokenReviewRows=$tokens.Count; LatinReviewRows=$latin.Count
}
$stats | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $out 'detailed-summary.json') -Encoding UTF8
$stats | ConvertTo-Json -Depth 3
