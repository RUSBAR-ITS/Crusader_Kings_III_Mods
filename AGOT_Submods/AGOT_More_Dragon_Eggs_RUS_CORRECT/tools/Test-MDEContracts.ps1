function Assert-MDEValue([string]$Key,[string]$Value){
    if($Value -match '(?<!\\)"|\\(?![nrt"\\])' -or
        [regex]::Matches($Value,'\[').Count -ne [regex]::Matches($Value,'\]').Count -or
        [regex]::Matches($Value,'\$').Count % 2){throw "Broken localization template: $Key"}
    $depth=0
    foreach($token in [regex]::Matches($Value,'#!|#[A-Za-z][A-Za-z0-9_]*')){
        if($token.Value -eq '#!'){$depth--}else{$depth++}
        if($depth -lt 0){throw "Unexpected formatting close: $Key"}
    }
    if($depth){throw "Unclosed formatting: $Key"}
}
function Get-MDETokens([string]$Value,[string]$Pattern){
    return (([regex]::Matches($Value,$Pattern)|ForEach-Object Value|Sort-Object -CaseSensitive)-join '|')
}
function Test-MDEContracts($Outputs,$SourceTexts,$EN,$RU,$Builtin,$Russian,$ScriptChanges,$Roots,$GenderFixes){
    $effectiveEN=New-Map;$effectiveRU=New-Map
    $enPatch=New-Map;$ruPatch=New-Map
    $normalRU=New-Map;$replaceRU=New-Map
    foreach($file in $Outputs.Keys | Where-Object {$_ -like 'localization/*'}){
        $lang=if($file -like '*_l_russian.yml'){'russian'}else{'english'}
        if($Outputs[$file] -cnotmatch ('\Al_'+$lang+':\r?\n')){throw "Invalid language header: $file"}
        $entries=Read-Entries $Outputs[$file]
        foreach($key in $entries.Keys){
            Assert-MDEValue $key $entries[$key]
            $map=if($lang -eq 'english'){$enPatch}elseif($file -like 'localization/replace/*'){$replaceRU}else{$normalRU}
            if($map.ContainsKey($key) -and $map[$key] -cne $entries[$key]){throw "Conflicting patch definitions: $key"}
            $map[$key]=$entries[$key]
        }
    }
    # Normal-path shadows suppress upstream declarations. Reviewed replace
    # definitions still take priority over retained normal-path definitions.
    foreach($map in @($normalRU,$replaceRU)){foreach($key in $map.Keys){$ruPatch[$key]=$map[$key]}}
    # Test both potential orders of the external and builtin Russian catalogs.
    # Original files shadowed at identical paths must parse without malformed quotes.
    $loadedRU=New-Map
    foreach($sourceKey in $SourceTexts.Keys){
        $file=$sourceKey.Substring($sourceKey.IndexOf(':')+1)
        $text=if($Outputs.ContainsKey($file)){$Outputs[$file]}else{$SourceTexts[$sourceKey]}
        $entries=Read-Entries $text
        if($entries.ContainsKey('nagga_desc')){throw "Conflicting MDE travel-key declaration remains: $sourceKey"}
        foreach($key in $entries.Keys){
            if($entries[$key] -match '(?<!\\)"'){throw "Malformed physical localization value remains: $sourceKey / $key"}
            if($sourceKey.StartsWith('Translation:')){
                if($loadedRU.ContainsKey($key)){throw "Duplicate external Russian declaration remains: $key"}
                $loadedRU.Add($key,$entries[$key])
            }
        }
    }
    if($loadedRU.Count -ne 1044){throw 'Expected 1044 unique external Russian definitions after namespacing.'}
    foreach($key in @('mde_dragon_egg_gen_parent','mde_dragon_egg_gen_parents')){
        if(-not $loadedRU.ContainsKey($key) -or $loadedRU[$key] -cne $RU[$key]){throw "Unique artifact parent label lost: $key"}
    }
    # These two shadows may only comment definitions. Reversing those comments
    # must recover the complete upstream text, including the two parent labels.
    foreach($file in @('localization/russian/dp_artifacts_l_russian.yml','localization/russian/mde_artifacts_l_russian.yml')){
        $reversed=$Outputs[$file] -creplace '(?m)^# MDE compatibility: ',''
        if($reversed -cne $SourceTexts['Translation:'+$file]){throw "Unreviewed translation shadow edit: $file"}
    }
    foreach($key in $EN.Keys){if($key -cne 'nagga_desc'){$effectiveEN[$key]=$EN[$key]}}
    foreach($key in $enPatch.Keys){$effectiveEN[$key]=$enPatch[$key]}
    $required=@($EN.Keys|Where-Object {$_ -cne 'nagga_desc'})+@('MDE_nagga_desc','MDE_gui_exit','MDE_gui_move_outside','NEEDS_ABSOLUTE_CROWN_AUTHORITY','stop_cradling_egg')
    foreach($order in @(@($Builtin,$loadedRU),@($loadedRU,$Builtin))){
        $effectiveRU=New-Map
        foreach($map in $order){foreach($key in $map.Keys){$effectiveRU[$key]=$map[$key]}}
        foreach($key in $ruPatch.Keys){$effectiveRU[$key]=$ruPatch[$key]}
        foreach($key in $required){
            if(-not $effectiveRU.ContainsKey($key)){throw "Untranslated runtime key: $key"}
            Assert-MDEValue $key $effectiveRU[$key]
        }
        foreach($key in $loadedRU.Keys){
            $expected=if($Russian.ContainsKey($key)){$Russian[$key]}else{$RU[$key]}
            if($effectiveRU[$key] -cne $expected){throw "External Russian translation lost to builtin value: $key"}
        }
    }
    foreach($key in $effectiveEN.Keys){Assert-MDEValue $key $effectiveEN[$key]}

    # All new translations preserve engine expressions, aliases and icons.
    # The two Concept replacements only inflect existing Russian concepts.
    $conceptKeys=@('message_filter_dragon_egg_created_desc','DRAGONPIT_VIEW_DRAGONPIT_HOLDER')
    foreach($key in $Russian.Keys){
        if(-not $EN.ContainsKey($key)){continue}
        $before=if($RU.ContainsKey($key)){$RU[$key]}else{$EN[$key]}
        $after=$Russian[$key]
        if($key -cin $conceptKeys){$after=$after -replace "\[Concept\('dragon', 'дракона'\)\|E\]",'[dragon|E]' -replace "\[Concept\('dragonpit', 'драконьего логова'\)\|E\]",'[dragonpit|E]'}
        foreach($pattern in @('\[[^\]]*\]','@[^!\s]+!','\$[^$]+\$')){
            # Greyscale intentionally reuses AGOT's existing localized dragon name.
            $afterTokens=$after
            if($key -cin @('maegor_12_desc','dragon_egg_maegor_12_desc') -and $pattern -ceq '\$[^$]+\$'){$afterTokens=$after.Replace('$Greyscale$','')}
            if((Get-MDETokens $before $pattern) -cne (Get-MDETokens $afterTokens $pattern)){throw "Changed protected localization tokens: $key / $pattern"}
        }
    }
    foreach($fix in $GenderFixes){if($effectiveRU[$fix[0]].Contains($fix[1])){throw "Gender defect remains: $($fix[0])"}}
    foreach($key in $Russian.Keys | Where-Object {$_ -match '^setting_1_in_|^setting_dragon_hatching_\d+_percent'}){
        if((Get-MDETokens $EN[$key] '\d+(?:\.\d+)?') -cne (Get-MDETokens ($Russian[$key].Replace(',','.')) '\d+(?:\.\d+)?')){throw "Changed numerical probability: $key"}
    }

    # Namespaces: the MDE branch and artifact catalog use the prefixed key.
    # The unprefixed travel key keeps the exact text shipped by AGOT.
    if($enPatch.ContainsKey('nagga_desc') -or $ruPatch.ContainsKey('nagga_desc')){throw 'Patch overrides AGOT travel key.'}
    if($enPatch['MDE_nagga_desc'] -cne 'Nagga' -or $ruPatch['MDE_nagga_desc'] -cne 'Нагга'){throw 'Prefixed dragon name is missing.'}
    $artifactText=$Outputs['localization/replace/english/agot/agot_artifacts/mde_artifacts_l_english.yml']
    if($artifactText -cmatch '(?m)^\s*nagga_desc:'){throw 'Original conflicting MDE declaration remains.'}
    $nameSelector=$Outputs['common/customizable_localization/00_more_dragon_eggs_loc.txt']
    if($nameSelector -cmatch '(?m)^\s*localization_key\s*=\s*nagga_desc\b' -or
        [regex]::Matches($nameSelector,'(?m)^\s*localization_key\s*=\s*MDE_nagga_desc\b').Count -ne 1){throw 'Nagga artifact selector does not use the prefixed key.'}
    foreach($case in @(@('AGOT','english'),@('AGOT_RU','russian'))){
        $path=Join-Path $Roots[$case[0]] ('localization/'+$case[1]+'/agot/gui/agot_travel_planner_window_l_'+$case[1]+'.yml')
        $travel=Read-Entries ([IO.File]::ReadAllText($path))
        if(-not $travel.ContainsKey('nagga_desc') -or $travel['nagga_desc'].Length -lt 50){throw 'AGOT travel source changed.'}
    }

    # Reverse every allowlisted script edit. Any unrelated script/GUI change fails.
    $scriptFiles=@($Outputs.Keys | Where-Object {$_ -like 'common/*' -or $_ -like 'gui/*'})
    if($scriptFiles.Count -ne 11){throw 'Expected 9 GUI and 2 common overrides.'}
    foreach($file in $scriptFiles){
        $reversed=$Outputs[$file]
        $edits=@($ScriptChanges|Where-Object File -ceq $file)
        [array]::Reverse($edits)
        foreach($edit in $edits){
            if([regex]::Matches($reversed,[regex]::Escape($edit.After)).Count -ne $edit.Count){throw "Script replacement drift: $file"}
            $reversed=$reversed.Replace($edit.After,$edit.Before)
        }
        if($reversed -cne [IO.File]::ReadAllText((Join-Path $Roots.Main $file))){throw "Unreviewed script change: $file"}
    }
    $guiText=($scriptFiles | Where-Object {$_ -like 'gui/*'} | ForEach-Object {$Outputs[$_]}) -join "`n"
    if($guiText -match 'raw_text\s*=\s*"(?:Exit\.|Move Outside)"'){throw 'Hardcoded GUI literal remains.'}
    if([regex]::Matches($guiText,'text = "MDE_gui_exit"').Count -ne 10 -or [regex]::Matches($guiText,'text = "MDE_gui_move_outside"').Count -ne 1){throw 'Localized GUI label coverage mismatch.'}
    $law=$Outputs['common/laws/02_mde_realm_laws.txt']
    if($law -notmatch '(?s)text\s*=\s*"NEEDS_ABSOLUTE_CROWN_AUTHORITY"\s*has_realm_law\s*=\s*crown_authority_3\s*\}'){throw 'Tooltip does not wrap its real condition.'}
    if([regex]::Matches($law,'has_realm_law\s*=\s*crown_authority_3').Count -ne [regex]::Matches([IO.File]::ReadAllText((Join-Path $Roots.Main 'common/laws/02_mde_realm_laws.txt')),'has_realm_law\s*=\s*crown_authority_3').Count){throw 'Crown-authority condition count changed.'}

    # Check every simple $alias$ in the generated package, including AGOT Greyscale.
    foreach($catalog in @($effectiveRU,$effectiveEN)){
        foreach($key in $catalog.Keys){
            $visited=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
            $target=$key
            while($catalog.ContainsKey($target) -and $catalog[$target] -cmatch '^\$([^$]+)\$$'){
                if(-not $visited.Add($target)){throw "Alias cycle: $key"}
                $target=$Matches[1]
            }
        }
    }
    $names=Read-Entries ([IO.File]::ReadAllText((Join-Path $Roots.AGOT_RU 'localization/replace/russian/agot/names/agot_dragon_names_l_russian.yml')))
    $traits=Read-Entries ([IO.File]::ReadAllText((Join-Path $Roots.AGOT_RU 'localization/russian/agot/agot_traits_l_russian.yml')))
    if($names['Greyscale'] -cne '$trait_greyscale$' -or $traits['trait_greyscale'] -cne 'Серая хворь'){throw 'Greyscale name reference changed.'}
    return [ordered]@{RequiredMDEKeysPerLanguage=$required.Count;RussianMissing=0;FormattingErrors=0;QuoteErrors=0;GuiLocalizedOccurrences=11;ScriptFiles=11;RussianCatalogOrdersChecked=2;AllSourceEditsReversible=$true;NaggaTravelKeyPreserved=$true;NaggaPhysicalCatalogsChecked=2;ExternalRussianDuplicateKeys=0;ExternalRussianKeysAfterNamespacing=$loadedRU.Count;UniqueArtifactParentLabelsPreserved=2;TranslationShadowsReversible=$true;CrownAuthorityConditionPreserved=$true;GameLaunched=$false}
}
