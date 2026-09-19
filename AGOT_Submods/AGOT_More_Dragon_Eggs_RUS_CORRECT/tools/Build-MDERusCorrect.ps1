param(
    [string]$MainModPath='E:\SteamLibrary\steamapps\workshop\content\1158310\3388366564',
    [string]$TranslationPath='E:\SteamLibrary\steamapps\workshop\content\1158310\3736931686',
    [string]$AgotPath='E:\SteamLibrary\steamapps\workshop\content\1158310\2962333032',
    [string]$AgotRussianPath='E:\SteamLibrary\steamapps\workshop\content\1158310\2962803371',
    [switch]$Check
)
$ErrorActionPreference='Stop'
$modRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$utf8=[Text.UTF8Encoding]::new($true,$true)
$roots=@{Main=$MainModPath;Translation=$TranslationPath;AGOT=$AgotPath;AGOT_RU=$AgotRussianPath}
$baseline=Get-Content -LiteralPath (Join-Path $modRoot 'docs/source-baseline.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach($source in $baseline){
    $path=Join-Path $roots[$source.Catalog] $source.File
    if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -cne $source.SHA256){throw "Source changed; repeat audit: $path"}
}
foreach($label in @('Main','Translation')){
    $sourceRoot=$roots[$label].TrimEnd('\','/')
    $actual=@(Get-ChildItem -LiteralPath (Join-Path $sourceRoot 'localization') -Recurse -File -Filter '*.yml' | Where-Object {$_.Name -match '_l_(english|russian)\.yml$'} | ForEach-Object {$_.FullName.Substring($sourceRoot.Length+1).Replace('\','/')})
    $expected=@($baseline | Where-Object {$_.Catalog -eq $label -and $_.File -like 'localization/*'} | ForEach-Object File)
    if((($actual|Sort-Object -CaseSensitive)-join '|') -cne (($expected|Sort-Object -CaseSensitive)-join '|')){throw "Localization inventory changed: $label"}
}
$actualScripts=@(foreach($folder in @('common','events','gui','data_binding')){Get-ChildItem -LiteralPath (Join-Path $MainModPath $folder) -Recurse -File | Where-Object {$_.Extension -in @('.txt','.gui')} | ForEach-Object {$_.FullName.Substring($MainModPath.TrimEnd('\','/').Length+1).Replace('\','/')}})
$expectedScripts=@($baseline | Where-Object {$_.Catalog -eq 'Main' -and $_.File -match '^(common|events|gui|data_binding)/'} | ForEach-Object File)
if((($actualScripts|Sort-Object -CaseSensitive)-join '|') -cne (($expectedScripts|Sort-Object -CaseSensitive)-join '|')){throw 'Script inventory changed.'}
function New-Map { return ,([Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)) }
function Read-Entries([string]$Text,[switch]$AllowMalformed){
    $result=New-Map
    foreach($line in $Text.TrimStart([char]0xFEFF) -split '\r?\n'){
        if($line -match '^\s*(#.*)?$|^\s*l_(english|russian):\s*$'){continue}
        if($line -match '^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<value>.*)"\s*(?:#.*)?$'){
            $result.Add($Matches.key,$Matches.value)
        }elseif($AllowMalformed -and $line -match '^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<value>.*)$'){
            $result.Add($Matches.key,$Matches.value)
        }else{throw "Unparsed localization line: $line"}
    }
    return ,$result
}
$en=New-Map; $ru=New-Map; $builtin=New-Map
$sourceTexts=New-Map
foreach($source in $baseline | Where-Object {$_.File -like 'localization/*' -and $_.Catalog -in @('Main','Translation')}){
    $content=[IO.File]::ReadAllText((Join-Path $roots[$source.Catalog] $source.File),$utf8).Replace("`r`n","`n")
    $sourceTexts.Add($source.Catalog+':'+$source.File,$content)
    $map=if($source.Catalog -eq 'Translation'){$ru}elseif($source.File -like '*_l_english.yml'){$en}else{$builtin}
    $entries=Read-Entries $content -AllowMalformed
    foreach($key in $entries.Keys){if(-not $map.ContainsKey($key)){$map.Add($key,$entries[$key])}}
}
if($en.Count -ne 1043 -or $ru.Count -ne 895 -or $builtin.Count -ne 711){throw 'Source catalog counts changed.'}
$reviewed=Read-Entries ([IO.File]::ReadAllText((Join-Path $modRoot 'docs/russian-reviewed.yml'),$utf8))
$russian=New-Map; $english=New-Map
$reasons=New-Map
foreach($key in $reviewed.Keys){$russian[$key]=$reviewed[$key];$reasons[$key]='Reviewed translation / compatibility label'}

# Complete missing current definitions. Reuse existing names rather than inventing
# a second spelling for a dragon already translated in the external mod.
$percentages=@{'1200'='0,083';'900'='0,111';'600'='0,167';'300'='0,333';'150'='0,667';'50'='2';'25'='4';'5'='20';'2'='50'}
foreach($key in $en.Keys | Sort-Object -CaseSensitive){
    if($key -ceq 'nagga_desc' -or $russian.ContainsKey($key)){continue}
    if($key -cmatch '^setting_1_in_(1200|900|600|300|150|50|25|5|2)(_ai)?(_desc)?$'){
        $denominator=$Matches[1];$ai=[bool]$Matches[2];$desc=[bool]$Matches[3]
        if($desc){
            $actor=if($ai){'персонажа ИИ'}else{'игрока'}
            $value='Вероятность получить драконьи яйца при посещении соответствующего места или принятии решения для '+$actor+' — около 1/'+$denominator+' ('+$percentages[$denominator]+'%).'
            if($denominator -eq '300'){$value+=' Это стандартная вероятность в AGOT.'}
        }else{$value='1/'+$denominator;if($denominator -eq '300'){$value+=' (по умолчанию)'}}
        $russian[$key]=$value;$reasons[$key]='Reviewed probability template; player / AI kept separate';continue
    }
    if($key -cmatch '^setting_dragon_hatching_(5|25|50|75|95)_percent(_desc)?$'){
        $chance=$Matches[1];$desc=[bool]$Matches[2]
        $russian[$key]=if($desc){'Яйцо со средней вероятностью вылупления имеет около '+$chance+'% шанса дать дракона. Для яиц с большей или меньшей вероятностью этот шанс соответственно повышается или понижается.'}else{'Вероятность '+$chance+'%'}
        $reasons[$key]='Reviewed hatching probability template';continue
    }
    if($ru.ContainsKey($key)){continue}
    if($builtin.ContainsKey($key)){
        $russian[$key]=$builtin[$key];$reasons[$key]='Reviewed builtin Russian fallback';continue
    }
    if($key.EndsWith('_desc',[StringComparison]::Ordinal)){
        $stem=$key.Substring(0,$key.Length-5)
        $nameKey='dragon_egg_'+$stem+'_ui_desc'
        if($ru.ContainsKey($nameKey) -and $ru[$nameKey] -cmatch '^Из этого яйца вылупится (.+)\.$'){
            $russian[$key]=$Matches[1];$reasons[$key]='Name from external translation: '+$nameKey;continue
        }
    }
    $visible=$en[$key] -replace '\[[^\]]*\]','' -replace '\$[^$]+\$','' -replace '#[A-Za-z0-9_!;]+',''
    if($visible -notmatch '[A-Za-z]'){
        $russian[$key]=$en[$key];$reasons[$key]='Language-independent expression / numeric value';continue
    }
    throw "Missing reviewed Russian translation: $key = $($en[$key])"
}

# Masculine fragments were confirmed against the actual character scopes.
# Neutral wording keeps all existing scope expressions unchanged.
$genderFixes=@(
    @('mde_egg_access_gained_interface_tt','будет защищён','получит защиту'),
    @('mde_decisions_events.1000.desc','я знал давно','мне давно было известно'),
    @('mde_decisions_events.3000.desc.self','Я раскрыл миру','Я объявляю миру'),
    @('mde_decisions_events.3000.desc.other','открыл миру','объявляет миру'),
    @('mde_dragon_eggs_events.0006.desc','растерянный и встревоженный','в растерянности и тревоге'),
    @('mde_dragon_eggs_events.0007.desc_missing','Я нашёл','Мне удалось найти'),
    @('mde_dragon_eggs_events.0009.desc','я нашёл','мне удалось найти'),
    @('mde_dragon_eggs_events.0013.desc','я потрясён силой','я поражаюсь силе'),
    @('mde_dragon_eggs_events.0013.desc','Охваченный одержимостью','Поддавшись одержимости')
)
foreach($fix in $genderFixes){
    $value=if($russian.ContainsKey($fix[0])){$russian[$fix[0]]}else{$ru[$fix[0]]}
    if(-not $value.Contains($fix[1])){throw 'Gender correction no longer matches source.'}
    $russian[$fix[0]]=$value.Replace($fix[1],$fix[2]);$reasons[$fix[0]]='MDE-06: gender-neutral wording'
}
$russian['INVITE_TO_KINGSGUARD_TT']=$ru['INVITE_TO_KINGSGUARD_TT']+'#!'
$reasons['INVITE_TO_KINGSGUARD_TT']='MDE-04: close formatting'

# Explicitly prefer the external translation over conflicting builtin replace
# values, even where its own file lives outside localization/replace.
foreach($key in $builtin.Keys){
    if($ru.ContainsKey($key) -and $ru[$key] -cne $builtin[$key] -and -not $russian.ContainsKey($key)){
        $russian[$key]=$ru[$key];$reasons[$key]='Preserve external RU over different builtin replace definition'
    }
}

$english['MDE_gui_exit']='Close'
$english['MDE_gui_move_outside']='Move Outside'
$english['NEEDS_ABSOLUTE_CROWN_AUTHORITY']='Requires Absolute Crown Authority.'
$english['stop_cradling_egg']='Stop cradling the previous dragon egg.'
$english['mde_dragon_no_parent_line']='Its origins are unknown.'
$english['SHOW_EGGS']=$en['SHOW_EGGS'].Replace('exising','existing')
$english['agot_dragon_hatching.0403.desc']=$en['agot_dragon_hatching.0403.desc'].Replace('dilligently','diligently')
$english['mde_dragon_eggs_events.0016.desc']=$en['mde_dragon_eggs_events.0016.desc'].Replace('who could his power','who could rival his power')
$english['dragon_pen.tt.unlocked_by_requirements']='You lack the requirements to recruit a dragonkeeper or build a dragoncoop.'
foreach($key in @('mde_start_demand_egg_event_chain','a_crown_for_a_king_decision_tooltip','agot_dragon_hatching.0403.opt.e.tt','NO_DRAGONS_TOOLTIP','NO_EGG_TOOLTIP','NO_DRAGONPITS_TOOLTIP','NO_KINGSGUARD_TOOLTIP','NO_VALYRIAN_STEEL_TOOLTIP')){
    if(-not $en[$key].EndsWith('#')){throw 'Unexpected formatting source.'}
    $english[$key]=$en[$key]+'!'
}
foreach($key in @('agot_ninepenny.0035.b.tt','INVITE_TO_KINGSGUARD_TT')){$english[$key]=$en[$key]+'#!'}

$outputs=New-Map
$shadows=@(
    'localization/replace/english/more_dragon_eggs_gamerules_l_english.yml',
    'localization/replace/english/agot/agot_artifacts/mde_artifacts_l_english.yml',
    'localization/replace/russian/more_dragon_eggs_gamerules_l_russian.yml',
    'localization/replace/russian/mde_demand_egg_events_l_russian.yml'
)
$shadowRussian=New-Map
$syntaxRepairs=[Collections.Generic.List[object]]::new()
foreach($file in $shadows){
    $isRussian=$file.Contains('/russian/')
    $lines=foreach($line in $sourceTexts['Main:'+$file] -split "`n"){
        if($line -match '^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"'){
            $key=$Matches.key
            if($line -notmatch '"\s*(?:#.*)?$'){$syntaxRepairs.Add([pscustomobject]@{File=$file;Key=$key;Problem='Missing closing quote'})}
            if($isRussian){
                $value=if($russian.ContainsKey($key)){$russian[$key]}elseif($ru.ContainsKey($key)){$ru[$key]}else{$builtin[$key]}
                $shadowRussian[$key]=$value
            }else{
                $value=if($english.ContainsKey($key)){$english[$key]}else{$en[$key]}
                if($key -ceq 'nagga_desc'){$key='MDE_nagga_desc'}
            }
            ' '+$key+':0 "'+$value+'"'
        }else{$line}
    }
    $outputs[$file]=$lines -join "`n"
}
if($syntaxRepairs.Count -ne 11){throw 'Expected eleven missing-quote repairs.'}

# The original EN nagga_desc declaration is gone at its physical file path.
# AGOT's original travel description remains free to load in both languages.
$scriptChanges=[Collections.Generic.List[object]]::new()
function Patch-Script([string]$File,[string]$Before,[string]$After,[int]$Count){
    $original=[IO.File]::ReadAllText((Join-Path $MainModPath $File),$utf8)
    $text=if($outputs.ContainsKey($File)){$outputs[$File]}else{$original}
    $matches=[regex]::Matches($text,[regex]::Escape($Before)).Count
    if($matches -ne $Count){throw "Unexpected occurrence count in $File : $matches"}
    $outputs[$File]=$text.Replace($Before,$After)
    $scriptChanges.Add([pscustomobject]@{File=$File;Before=$Before;After=$After;Count=$Count})
}
Patch-Script 'common/customizable_localization/00_more_dragon_eggs_loc.txt' 'localization_key = nagga_desc' 'localization_key = MDE_nagga_desc' 1
foreach($file in @('dragonblood_viewer','dragonpit_single_viewer','dragon_move_viewer','dragon_viewer','egg_viewer','kingsguard_viewer','mde_menu_menu','valyrian_steel_viewer')){
    Patch-Script ('gui/custom_gui/mde_gui/'+$file+'.gui') 'raw_text = "Exit."' 'text = "MDE_gui_exit"' 1
}
Patch-Script 'gui/custom_gui/mde_gui/dragonpits_viewer.gui' 'raw_text = "Exit."' 'text = "MDE_gui_exit"' 2
Patch-Script 'gui/custom_gui/mde_gui/dragonpits_viewer.gui' 'raw_text = "Move Outside"' 'text = "MDE_gui_move_outside"' 1
$lawFile='common/laws/02_mde_realm_laws.txt'
$lawText=[IO.File]::ReadAllText((Join-Path $MainModPath $lawFile),$utf8)
$lawMatch=[regex]::Matches($lawText,'(?s)custom_description\s*=\s*\{\s*subject\s*=\s*root\s*text\s*=\s*"NEEDS_ABSOLUTE_CROWN_AUTHORITY"\s*\}\s*has_realm_law\s*=\s*crown_authority_3')
if($lawMatch.Count -ne 1){throw 'Crown-authority tooltip structure changed.'}
$newline=if($lawText.Contains("`r`n")){"`r`n"}else{"`n"}
$lawAfter=@('custom_description = {',"`t`t`t`tsubject = root",'                text = "NEEDS_ABSOLUTE_CROWN_AUTHORITY"',"`t`t`t`thas_realm_law = crown_authority_3","`t`t`t}") -join $newline
Patch-Script $lawFile $lawMatch[0].Value $lawAfter 1

function Format-Loc($Map,[string]$Language){
    $lines=@(('l_'+$Language+':'),' # Generated by tools/Build-MDERusCorrect.ps1. Reviewed corrections and required priority overrides.')
    foreach($key in $Map.Keys | Sort-Object -CaseSensitive){$lines+=' '+$key+':0 "'+$Map[$key]+'"'}
    return ($lines -join "`n")+"`n"
}
$ruOverlay=New-Map
foreach($key in $russian.Keys){if(-not $shadowRussian.ContainsKey($key)){$ruOverlay[$key]=$russian[$key]}}
$outputs['localization/replace/russian/zzzz_mde_rus_correct_l_russian.yml']=Format-Loc $ruOverlay 'russian'
$outputs['localization/replace/english/zzzz_mde_rus_correct_l_english.yml']=Format-Loc $english 'english'

. (Join-Path $PSScriptRoot 'Test-MDEContracts.ps1')
$verification=Test-MDEContracts $outputs $sourceTexts $en $ru $builtin $russian $scriptChanges $roots $genderFixes

$descriptor=@('version="1.0.0"','tags={','    "Translation"','    "Fixes"','}',
    'name="AGOT More Dragon Eggs | Исправления русификатора и совместимости"',
    'supported_version="1.19.0.6"','dependencies={','    "AGOT More Dragon Eggs"','    "AGOT More Dragon Eggs - Русификация"','}') -join "`n"
$outputs['descriptor.mod']=$descriptor+"`n"
$external=$descriptor+"`npath="""+$modRoot.Replace('\','/')+"""`n"
function Write-Or-Check([string]$Path,[string]$Content){
    $expected=$utf8.GetPreamble()+$utf8.GetBytes($Content)
    if($Check){
        if(-not(Test-Path -LiteralPath $Path) -or [Convert]::ToBase64String([IO.File]::ReadAllBytes($Path)) -cne [Convert]::ToBase64String($expected)){throw "Generated file differs: $Path"}
    }else{[IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Path))|Out-Null;[IO.File]::WriteAllText($Path,$Content,$utf8)}
}
$outputHashes=@(foreach($file in $outputs.Keys | Sort-Object -CaseSensitive){
    $path=Join-Path $modRoot $file
    Write-Or-Check $path $outputs[$file]
    [ordered]@{File=$file;SHA256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
})
$externalPath=Join-Path (Split-Path -Parent $modRoot) 'AGOT_More_Dragon_Eggs_RUS_CORRECT.mod'
Write-Or-Check $externalPath $external
$changes=@(foreach($key in $russian.Keys | Sort-Object -CaseSensitive){
    [ordered]@{Key=$key;Reason=$reasons[$key];English=$en[$key];ExternalRussian=$ru[$key];BuiltinRussian=$builtin[$key];After=$russian[$key]}
})
$manifest=[ordered]@{
    MainWorkshopId='3388366564';MainVersion='56';TranslationWorkshopId='3736931686';TranslationVersion='1.1'
    SourceHashesChecked=$baseline.Count;RussianOverlayKeys=$ruOverlay.Count;RussianShadowKeys=$shadowRussian.Count
    EnglishOverlayKeys=$english.Count;LocalizationShadowFiles=$shadows.Count;ScriptOverrideFiles=@($scriptChanges.File|Sort-Object -Unique).Count
    MissingExternalKeysProvided=331;MissingRussianKeysTranslated=257;RenamedKey='MDE_nagga_desc';SyntaxRepairs=@($syntaxRepairs.ToArray())
    CoveredAuditIssues=@('MDE-01','MDE-02','MDE-03','MDE-04','MDE-05','MDE-06','MDE-07','MDE-08','MDE-09','MDE-10')
    Verification=$verification;RussianChanges=$changes;EnglishChanges=$english;ScriptChanges=@($scriptChanges.ToArray());Outputs=$outputHashes
    ExternalDescriptorSHA256=(Get-FileHash -LiteralPath $externalPath -Algorithm SHA256).Hash
}
Write-Or-Check (Join-Path $modRoot 'docs/source-manifest.json') (($manifest|ConvertTo-Json -Depth 9)+"`n")
$actualFiles=@(foreach($folder in @('localization','common','gui','events','gfx','history')){
    $path=Join-Path $modRoot $folder
    if(Test-Path -LiteralPath $path){Get-ChildItem -LiteralPath $path -Recurse -File | ForEach-Object {$_.FullName.Substring($modRoot.Length+1).Replace('\','/')}}
})
$expectedFiles=@($outputs.Keys | Where-Object {$_ -ne 'descriptor.mod'})
if((($actualFiles|Sort-Object -CaseSensitive)-join '|') -cne (($expectedFiles|Sort-Object -CaseSensitive)-join '|')){throw 'Unexpected runtime output files.'}
Write-Output ('Validated MDE: '+($verification|ConvertTo-Json -Compress))
Write-Output $(if($Check){'Generated files and manifest match byte for byte.'}else{'Built AGOT_More_Dragon_Eggs_RUS_CORRECT and repository descriptor; game profile not modified.'})
