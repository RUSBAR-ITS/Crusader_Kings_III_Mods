$ErrorActionPreference='Stop'
$previous=Join-Path $PSScriptRoot '../ck3-agot-plus-fix-log-2026-09-18'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$before=@(Import-Csv -LiteralPath (Join-Path $previous 'classified-entries.csv'))
$after=@(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'classified-entries.csv'))
function Signature($Row){
    $message=$Row.Message -replace '\[args#\d+\]','[args#*]'
    # Edits move source lines. Preserve full original diagnostics in the CSVs;
    # normalize only source line references for a multiset comparison.
    $message=$message -replace '(?i)\b(near line|line):\s*\d+','$1: *'
    $message=$message -replace '(?i)\bline\s+\d+','line *'
    $Row.Component+' '+$message
}
function Index($Rows){
    $index=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
    foreach($row in $Rows){
        if($row.Key -or $row.Category -eq 'Save portrait / DNA compatibility'){continue}
        $key=Signature $row
        if(-not $index.ContainsKey($key)){$index[$key]=[Collections.Generic.List[object]]::new()}
        $index[$key].Add($row)
    }
    return ,$index
}
$old=Index $before
$new=Index $after
$changes=@(foreach($key in @(@($old.Keys)+@($new.Keys)|Sort-Object -Unique -CaseSensitive)){
    $oldCount=if($old.ContainsKey($key)){$old[$key].Count}else{0}
    $newCount=if($new.ContainsKey($key)){$new[$key].Count}else{0}
    if($oldCount -eq $newCount){continue}
    $sample=if($newCount){$new[$key][0]}else{$old[$key][0]}
    [pscustomobject]@{BeforeCount=$oldCount;AfterCount=$newCount;Difference=$newCount-$oldCount;Category=$sample.Category;Owner=$sample.Owner;ExampleLine=$sample.Line;Component=$sample.Component;Message=$sample.Message;Signature=$key}
})
$changes|Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'changed-messages.csv') -NoTypeInformation -Encoding UTF8
$changes|Where-Object {[int]$_.Difference -gt 0}|Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'new-messages.csv') -NoTypeInformation -Encoding UTF8
$changes|Where-Object {[int]$_.Difference -lt 0}|Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'disappeared-messages.csv') -NoTypeInformation -Encoding UTF8
$targets=@(Import-Csv -LiteralPath (Join-Path $repo 'AGOT_Submods/AGOT_PLUS_FIX/docs/stage2-targeted-log-messages.csv'))
$verification=@(foreach($target in $targets){
    $signature=Signature $target
    [pscustomobject]@{IssueClass=$target.IssueClass;BeforeLogLine=$target.LogLine;Component=$target.Component;Message=$target.Message;PresentAfter=$new.ContainsKey($signature);AfterCount=$(if($new.ContainsKey($signature)){$new[$signature].Count}else{0})}
})
$verification|Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'fix-verification.csv') -NoTypeInformation -Encoding UTF8
$firstTargets=@(Import-Csv -LiteralPath (Join-Path $repo 'AGOT_Submods/AGOT_PLUS_FIX/docs/targeted-log-messages.csv'))
$firstRemaining=@($firstTargets|Where-Object {$new.ContainsKey((Signature $_))}).Count
$extraMessage='No on_action scripted with tag asoiaf_alternative_arryn_sigil cannot link'
$oldMods=Import-Csv -LiteralPath (Join-Path $previous 'active-mods.csv')
$newMods=Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'active-mods.csv')
$sameMods=(@($oldMods|ForEach-Object {$_.Order+' '+$_.Descriptor+' '+$_.Path}) -join '|') -ceq (@($newMods|ForEach-Object {$_.Order+' '+$_.Descriptor+' '+$_.Path}) -join '|')
$summary=[ordered]@{
    BeforeEntries=$before.Count;AfterEntries=$after.Count;NetRemoved=$before.Count-$after.Count
    ExpectedDuplicates=@($after|Where-Object Key).Count
    BeforeWithoutDuplicatesOrGraphics=@($before|Where-Object {-not $_.Key -and $_.Category -notin @('Graphics / portrait source error','Save portrait / DNA compatibility')}).Count
    AfterWithoutDuplicatesOrGraphics=@($after|Where-Object {-not $_.Key -and $_.Category -notin @('Graphics / portrait source error','Save portrait / DNA compatibility')}).Count
    AddedOccurrences=($changes|Where-Object {[int]$_.Difference -gt 0}|Measure-Object Difference -Sum).Sum
    RemovedOccurrences=-($changes|Where-Object {[int]$_.Difference -lt 0}|Measure-Object Difference -Sum).Sum
    AddedSignatures=@($changes|Where-Object {[int]$_.Difference -gt 0}).Count
    Targets=$verification.Count;TargetsRemaining=@($verification|Where-Object PresentAfter).Count
    Stage1TargetsRemaining=$firstRemaining
    RemovedArrynHookPresent=@($after|Where-Object Message -CEQ $extraMessage).Count -gt 0
    SameActiveModsAndOrder=$sameMods
    Normalization='Entry timestamps omitted; args counters and source line references normalized; component, file, function, IDs and message text retained. Counts compared as multisets.'
}
$summary|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $PSScriptRoot 'comparison-summary.json') -Encoding UTF8
$summary|ConvertTo-Json -Depth 4
