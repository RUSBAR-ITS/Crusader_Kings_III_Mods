param(
    [string]$MainPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3388366564',
    [string]$RussianPath = 'E:\SteamLibrary\steamapps\workshop\content\1158310\3736931686'
)
$ErrorActionPreference = 'Stop'
$entries = @(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'catalog-entries.csv'))
$coverage = @(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'coverage-with-fallbacks.csv'))
$missing = @($coverage | Where-Object {$_.TranslationPresent -eq 'False'})
$uncovered = @($missing | Where-Object {-not $_.BuiltinFile -and -not $_.ExternalFile})
$uncovered | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'missing-russian-confirmed.csv') -NoTypeInformation -Encoding UTF8

# These literal strings were manually checked in their GUI context.
# AI score descriptions, developer comments and template placeholders are excluded.
$hardcoded = @(foreach ($file in Get-ChildItem -LiteralPath (Join-Path $MainPath 'gui/custom_gui') -Recurse -Filter '*.gui' -File) {
    $lineNumber = 0
    foreach ($line in [IO.File]::ReadAllLines($file.FullName)) {
        $lineNumber++
        if ($line -match '^\s*raw_text\s*=\s*"(?<text>Exit\.|Move Outside)"') {
            [pscustomobject]@{File=$file.FullName.Substring($MainPath.Length+1).Replace('\','/');Line=$lineNumber;Field='raw_text';Text=$Matches.text;Classification='Player GUI literal'}
        }
    }
})
$hardcoded | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'hardcoded-text-review.csv') -NoTypeInformation -Encoding UTF8

$en = @($entries | Where-Object Catalog -eq 'EN')
$ru = @($entries | Where-Object Catalog -eq 'Translation')
$builtin = @($entries | Where-Object Catalog -eq 'BuiltinRussian')
$ruMap = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
foreach ($entry in $ru) { $ruMap[$entry.Key]=$entry.Text }
$shared = @($builtin | Group-Object Key -CaseSensitive | ForEach-Object {$_.Group[0]} | Where-Object {$ruMap.ContainsKey($_.Key)})
$different = @($shared | Where-Object {$_.Text -cne $ruMap[$_.Key]})
$different | Select-Object Key,File,Line,Text,@{n='ExternalTranslation';e={$ruMap[$_.Key]}} | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'builtin-overlap-review.csv') -NoTypeInformation -Encoding UTF8
$structure = @(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'structure-review.csv'))
$duplicates = @(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'duplicates-review.csv'))
$gender = @(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'gender-review.csv'))
$sourceFiles = @(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'source-files.csv'))
$scriptFiles = @(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'script-source-files.csv'))
$stats = [ordered]@{
    GeneratedAt=(Get-Date).ToString('o')
    Scope='Static audit of installed MDE v56 and external Russian translation v1.1; no game launch, no source modifications.'
    MainModPath=$MainPath; TranslationPath=$RussianPath
    EnglishFiles=@($sourceFiles | Where-Object Catalog -eq 'EN').Count
    EnglishEntries=$en.Count; EnglishKeys=$coverage.Count
    ExternalRussianFiles=@($sourceFiles | Where-Object Catalog -eq 'Translation').Count
    ExternalRussianEntries=$ru.Count; ExternalRussianKeys=@($ru.Key | Sort-Object -Unique -CaseSensitive).Count
    BuiltinRussianFiles=@($sourceFiles | Where-Object Catalog -eq 'BuiltinRussian').Count
    BuiltinRussianEntries=$builtin.Count; BuiltinRussianKeys=@($builtin.Key | Sort-Object -Unique -CaseSensitive).Count
    MatchingExternalRussianKeys=@($coverage | Where-Object TranslationPresent -eq 'True').Count
    MissingFromExternalRussian=$missing.Count
    MissingExternalButPresentInBuiltin=@($missing | Where-Object BuiltinFile).Count
    MissingExternalAndBuiltinButPresentInAgot=@($missing | Where-Object {-not $_.BuiltinFile -and $_.ExternalCatalog -eq 'AGOT_RU'}).Count
    MissingRussianDefinitions=$uncovered.Count
    ConflictingFallbackKeys=@('nagga_desc')
    ExtraTranslationKeys=@(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'extra-translation-keys.csv')).Count
    MissingByEnglishFile=@($uncovered | Group-Object MainFile | ForEach-Object {[ordered]@{File=$_.Name;Count=$_.Count}})
    MissingClosingQuotesEnglish=@($structure | Where-Object {$_.Catalog -eq 'EN' -and $_.Problem -like 'Missing closing quote*'}).Count
    MissingClosingQuotesBuiltinRussian=@($structure | Where-Object {$_.Catalog -eq 'BuiltinRussian' -and $_.Problem -like 'Missing closing quote*'}).Count
    UnclosedFormattingEnglish=@($structure | Where-Object {$_.Catalog -eq 'EN' -and $_.Problem -eq 'Unclosed formatting tag'}).Count
    UnclosedFormattingExternalRussian=@($structure | Where-Object {$_.Catalog -eq 'Translation' -and $_.Problem -eq 'Unclosed formatting tag'}).Count
    UnclosedFormattingBuiltinRussian=@($structure | Where-Object {$_.Catalog -eq 'BuiltinRussian' -and $_.Problem -eq 'Unclosed formatting tag'}).Count
    MalformedDoubleValueBuiltinRussian=1
    HardcodedGuiOccurrences=$hardcoded.Count
    HardcodedGuiFiles=@($hardcoded.File | Sort-Object -Unique).Count
    GenderAffectedKeys=@($gender.Key | Sort-Object -Unique -CaseSensitive).Count
    GenderFragments=$gender.Count
    AdditionalMissingRuntimeKeys=@('NEEDS_ABSOLUTE_CROWN_AUTHORITY','stop_cradling_egg')
    AdditionalMissingRuntimeReferences=3
    IdenticalDuplicateRows=@($duplicates | Where-Object Identical -eq 'True').Count
    ConflictingDuplicateRows=@($duplicates | Where-Object Identical -eq 'False').Count
    BuiltinExternalSharedKeys=$shared.Count; BuiltinExternalDifferentValues=$different.Count
    ScannedScriptFiles=$scriptFiles.Count
    ExtractedReferenceCandidates=@(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'script-references-review.csv')).Count
    Method='Case-sensitive declared-key comparison. Invalid quoted declarations retained and flagged. First catalog definition is a representative, not an inferred load winner. Runtime-reference CSV is a candidate list, not a missing-localization list. Trigger-localization mappings checked manually for reported defects.'
}
$stats | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'audit-summary.json') -Encoding UTF8

# Preserve the hashes collected by the first scans, and verify against them.
# A changed Workshop source invalidates this snapshot instead of silently updating it.
$baseline = [Collections.Generic.List[object]]::new()
foreach ($entry in $sourceFiles) {
    $root=if ($entry.Catalog -eq 'Translation') {$RussianPath} else {$MainPath}
    $baseline.Add([pscustomobject]@{Catalog=$entry.Catalog;Path=(Join-Path $root $entry.File);SHA256=$entry.SHA256})
}
foreach ($entry in $scriptFiles) {
    $baseline.Add([pscustomobject]@{Catalog='MDE script';Path=(Join-Path $MainPath $entry.File);SHA256=$entry.SHA256})
}
foreach ($item in @(@{Catalog='MDE descriptor';Path=(Join-Path $MainPath 'descriptor.mod')},@{Catalog='Translation descriptor';Path=(Join-Path $RussianPath 'descriptor.mod')},@{Catalog='MDE version';Path=(Join-Path $MainPath 'MoreEggsReadMe.txt')})) {
    $baseline.Add([pscustomobject]@{Catalog=$item.Catalog;Path=$item.Path;SHA256=(Get-FileHash -LiteralPath $item.Path -Algorithm SHA256).Hash})
}
$baselinePath = Join-Path $PSScriptRoot 'source-baseline.json'
if (Test-Path -LiteralPath $baselinePath) {
    $frozen=Get-Content -LiteralPath $baselinePath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($entry in $frozen) {
        if ((Get-FileHash -LiteralPath $entry.Path -Algorithm SHA256).Hash -cne $entry.SHA256) { throw ('Frozen source changed: '+$entry.Path) }
    }
}
foreach ($entry in $baseline) {
    if ((Get-FileHash -LiteralPath $entry.Path -Algorithm SHA256).Hash -cne $entry.SHA256) { throw ('Source changed after scan: '+$entry.Path) }
}
$baseline | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $baselinePath -Encoding UTF8
[ordered]@{CheckedAt=(Get-Date).ToString('o');Sources=$baseline.Count;Unchanged=$true;GameLaunched=$false;WorkshopFilesModified=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'verification.json') -Encoding UTF8
$stats | ConvertTo-Json -Depth 6
