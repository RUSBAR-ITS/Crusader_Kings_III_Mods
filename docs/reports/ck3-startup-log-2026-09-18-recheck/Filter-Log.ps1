param([string]$GamePath='E:\SteamLibrary\steamapps\common\Crusader Kings III\game')
. (Join-Path $PSScriptRoot '../../../tools/RepositoryText.ps1')

$ErrorActionPreference='Stop'
$mods=@(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'active-mods.csv'))
$repoRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$raw=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'snapshot/error.log'))
$entries=[Collections.Generic.List[object]]::new()
$heads=[regex]::Matches($raw,'(?m)^\[(?<time>[^\]]+)\]\[(?<severity>[^\]]+)\]\[(?<component>[^\]]+)\]: ')
$dupeKeys=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$dupeFiles=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
$line=1;$previousIndex=0
for($i=0;$i -lt $heads.Count;$i++){
    $head=$heads[$i];$end=if($i+1 -lt $heads.Count){$heads[$i+1].Index}else{$raw.Length}
    $line += [regex]::Matches($raw.Substring($previousIndex,$head.Index-$previousIndex),"`n").Count
    $previousIndex=$head.Index
    $body=$raw.Substring($head.Index+$head.Length,$end-$head.Index-$head.Length).TrimEnd()
    $entry=[pscustomobject]@{Line=$line;Time=$head.Groups['time'].Value;Component=$head.Groups['component'].Value;Message=$body;Category='';Owner='';Files='';Key='';FirstFile='';SecondFile=''}
    if($body -match "^Duplicate localization key\. Key '([^']+)' is defined in both '([^']+)' and '([^']+)'\."){
        $entry.Key=$Matches[1];$entry.FirstFile=$Matches[2];$entry.SecondFile=$Matches[3]
        $null=$dupeKeys.Add($entry.Key);$null=$dupeFiles.Add($entry.FirstFile);$null=$dupeFiles.Add($entry.SecondFile)
    }
    $entries.Add($entry)
}

# Inspect actual active definitions, including the corrective replace files.
# Later descriptor order is recorded as a candidate VFS owner, not a proof of
# localization precedence across different physical paths.
$definitions=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
foreach($mod in $mods){
    $root=$mod.Path.TrimEnd('/','\')
    $isRepository=[IO.Path]::GetFullPath($root).StartsWith($repoRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)
    $locRoot=Join-Path $root 'localization'
    if(-not(Test-Path -LiteralPath $locRoot)){continue}
    foreach($file in Get-ChildItem -LiteralPath $locRoot -Recurse -File -Filter '*.yml'){
        $relative=$file.FullName.Substring($root.Length+1).Replace('\','/')
        if(-not $isRepository -and -not $dupeFiles.Contains($relative)){continue}
        $n=0
        foreach($text in [IO.File]::ReadAllLines($file.FullName)){
            $n++
            # Collect even malformed tails so duplicate ownership remains
            # visible. This extractor is not a localization syntax validator.
            if($text -notmatch '^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<value>.*)"(?<tail>.*)$'){continue}
            $key=$Matches.key;$value=$Matches.value;$tail=$Matches.tail
            if(-not $dupeKeys.Contains($key)){continue}
            if(-not $definitions.ContainsKey($key)){$definitions[$key]=[Collections.Generic.List[object]]::new()}
            $definitions[$key].Add([pscustomobject]@{Key=$key;Order=[int]$mod.Order;Mod=$mod.Name;Path=$file.FullName;File=$relative;Line=$n;Value=$value;TrailingText=$tail;Repository=$isRepository})
        }
    }
}
$owners=@{}
function Resolve-LogFile([string]$File){
    if($owners.ContainsKey($File)){return $owners[$File]}
    $providers=@($mods|Where-Object {Test-Path -LiteralPath (Join-Path $_.Path $File) -PathType Leaf})
    $value=if($providers.Count){$providers[-1].Name}elseif(Test-Path -LiteralPath (Join-Path $GamePath $File)){'CK3'}else{'Unresolved file'}
    $owners[$File]=$value
    return $value
}
$duplicateReview=[Collections.Generic.List[object]]::new()
# Reviewed source pairs in THIS snapshot. This only classifies the duplicate
# diagnostic, never syntax errors or missing keys from the same files.
$reviewedPairs=@{
    'localization/russian/gui/DI_RUS_l_russian.yml | localization/russian/gui/DI_l_russian.yml'='Expected external translation override'
    'localization/russian/custom_localization/DI_RUS_custom_loc_l_russian.yml | localization/russian/custom_localization/DI_custom_loc_l_russian.yml'='Expected external translation override'
    'localization/russian/targ_artifacts_l_russian.yml | localization/russian/artifacts/targ_artifacts_l_russian.yml'='Expected external translation override'
    'localization/russian/valyrian_modifiers_l_russian.yml | localization/russian/modifiers/valyrian_modifiers_l_russian.yml'='Expected external translation override'
    'localization/russian/ntc_artifacts_l_russian.yml | localization/russian/agot/artifacts/agot_artifacts_l_russian.yml'='Reviewed same-object mod override'
    'localization/russian/agot_westeroscrowns_portrait_modifiers_l_russian.yml | localization/russian/agot/portraits/agot_portrait_modifiers_l_russian.yml'='Reviewed same-object mod override'
    'localization/russian/more_dragon_eggs_events_l_russian.yml | localization/russian/agot/event_localization/agot_dragon_maintenance_l_russian.yml'='Reviewed same-object mod override'
    'localization/russian/more_dragon_eggs_events_l_russian.yml | localization/russian/agot/event_localization/filler_events/agot_filler_events_crownlands_l_russian.yml'='Reviewed same-object mod override'
    'localization/russian/agot/gui/agot_common_l_russian.yml | localization/russian/gui/asoiaf_character_window_l_russian.yml'='Reviewed same-object mod override'
}
foreach($entry in $entries){
    if($entry.Key){
        $defs=if($definitions.ContainsKey($entry.Key)){@($definitions[$entry.Key].ToArray())}else{@()}
        $repo=@($defs|Where-Object Repository)
        $values=@($defs.Value|Sort-Object -Unique -CaseSensitive)
        $pair=$entry.FirstFile+' | '+$entry.SecondFile
        if($repo.Count -and @($repo.Value|Sort-Object -Unique -CaseSensitive).Count -eq 1){
            $entry.Category='Expected corrective localization override'
        }elseif($defs.Count -gt 1 -and $values.Count -eq 1){
            $entry.Category='Identical localization definitions'
        }elseif($reviewedPairs.ContainsKey($pair) -and
            @($defs|Where-Object File -eq $entry.FirstFile).Count -gt 0 -and
            @($defs|Where-Object File -eq $entry.SecondFile).Count -gt 0){
            $entry.Category=$reviewedPairs[$pair]
        }else{
            $entry.Category='Localization duplicate needs review'
        }
        $entry.Owner=($defs.Mod|Sort-Object -Unique)-join ' | '
        $entry.Files=$entry.FirstFile+' | '+$entry.SecondFile
        $duplicateReview.Add([pscustomobject]@{LogLine=$entry.Line;Key=$entry.Key;Category=$entry.Category;FirstFile=$entry.FirstFile;SecondFile=$entry.SecondFile;RepositoryDefinitions=$repo.Count;DistinctValues=$values.Count;Mods=$entry.Owner})
        continue
    }
    $files=@([regex]::Matches($entry.Message,'(?:localization|common|events|gui|gfx|history)/[^\r\n"''<>]*?\.(?:yml|txt|gui|asset|mesh|dds|png)')|ForEach-Object Value|Sort-Object -Unique)
    $entry.Files=$files-join ' | '
    $entry.Owner=(@($files|ForEach-Object {Resolve-LogFile $_}|Sort-Object -Unique))-join ' | '
    if($entry.Message -match '(?i)save games/.*\.ck3' -and $entry.Component -match '^portraitcontext\.'){$entry.Category='Save portrait / DNA compatibility'}
    elseif($entry.Component -match '^(localization_reader|jomini_custom_text|jomini_dynamicdescription|pdx_locstring|pdx_gui_localize)\.'){$entry.Category='Localization / dynamic text error'}
    elseif($entry.Component -match '^(pdx_data_factory|pdx_data_statementparser|pdx_gui_factory)\.'){$entry.Category='GUI expression / binding error'}
    elseif($entry.Component -match '^(portraitcontext|portraitanimations|portraitaccessories|dnamodifier|pdxassetutil|pdx_3dtypes|pdx_entity|pdx_blend_shape_database|coat_of_arms_render_description|game_icons|artifact_visual_type)\.'){$entry.Category='Graphics / portrait source error'}
    elseif($entry.Component -match '^dlc_descriptor\.'){$entry.Category='Mod descriptor warning'}
    elseif($entry.Component -match '^(history|title_links|faith_links)\.'){$entry.Category='History / title / faith reference error'}
    elseif($entry.Component -match '^(jomini_|pdx_persistent_reader|decision_type|static_modifier|opinion_modifier|character_currency_effects_impl|artifact_feature)'){$entry.Category='Script / database error'}
    else{$entry.Category='Other error'}
}
$entries|Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'classified-entries.csv') -NoTypeInformation -Encoding UTF8
$duplicateReview|Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'localization-duplicates.csv') -NoTypeInformation -Encoding UTF8
$allDefs=@(foreach($key in $definitions.Keys){foreach($def in $definitions[$key]){$def}})
$allDefs|Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'duplicate-definitions.csv') -NoTypeInformation -Encoding UTF8
$noise=@('Expected corrective localization override','Identical localization definitions','Expected external translation override','Reviewed same-object mod override')
$remaining=@($entries|Where-Object {$_.Category -cnotin $noise})
$separateSave=@($remaining|Where-Object Category -eq 'Save portrait / DNA compatibility')
$actionable=@($remaining|Where-Object Category -ne 'Save portrait / DNA compatibility')
function Write-LogEntries($List,[string]$Name){
    $text=($List|ForEach-Object {'['+$_.Time+']['+$_.Component+'] [original line '+$_.Line+'] '+$_.Message})-join "`n"
    [RepositoryText]::WriteAllText((Join-Path $PSScriptRoot $Name),$text,[Text.UTF8Encoding]::new($true))
}
Write-LogEntries $actionable 'errors-filtered.log'
Write-LogEntries $separateSave 'save-portrait-errors.log'
Write-LogEntries @($entries|Where-Object {$_.Category -cin $noise}) 'expected-localization-duplicates.log'
Write-LogEntries @($actionable|Where-Object {$_.Category -in @('Localization / dynamic text error','GUI expression / binding error')}) 'localization-and-ui-errors.log'
$actionable|Group-Object Category,Owner,Files|Sort-Object Count -Descending|ForEach-Object {
    [pscustomobject]@{Count=$_.Count;Category=$_.Group[0].Category;Owner=$_.Group[0].Owner;Files=$_.Group[0].Files;FirstLogLine=$_.Group[0].Line}
}|Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'file-summary.csv') -NoTypeInformation -Encoding UTF8
$categorySummary=@($entries|Group-Object Category|Sort-Object Count -Descending|ForEach-Object {[ordered]@{Category=$_.Name;Count=$_.Count}})
$ownerSummary=@($actionable|Group-Object Owner|Sort-Object Count -Descending|ForEach-Object {[ordered]@{Owner=$_.Name;Count=$_.Count}})
$ownerSummary|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $PSScriptRoot 'owner-summary.json') -Encoding UTF8
# Normalize repeated save/header details only; keep different source lines and
# individual missing keys available in the full filtered log.
$groups=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
foreach($entry in $actionable){
    $signature=$entry.Component+' '+$entry.Message
    if(-not $groups.ContainsKey($signature)){$groups[$signature]=[pscustomobject]@{Count=0;Category=$entry.Category;Owner=$entry.Owner;FirstLogLine=$entry.Line;Component=$entry.Component;Message=$entry.Message}}
    $groups[$signature].Count++
}
$groups.Values|Sort-Object Count -Descending|Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'errors-grouped.csv') -NoTypeInformation -Encoding UTF8
$summary=[ordered]@{Entries=$entries.Count;LocalizationDuplicates=$duplicateReview.Count;FilteredExpectedDuplicates=$entries.Count-$remaining.Count;DuplicatesNeedingReview=@($entries|Where-Object Category -eq 'Localization duplicate needs review').Count;SavePortraitErrorsSeparated=$separateSave.Count;RemainingEntries=$actionable.Count;DistinctRemainingMessages=$groups.Count;Categories=$categorySummary}
$summary|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $PSScriptRoot 'classification-summary.json') -Encoding UTF8
$summary|ConvertTo-Json -Depth 5
