param(
    [string]$MainPath='E:\SteamLibrary\steamapps\workshop\content\1158310\2950245430',
    [string]$AgotPath='E:\SteamLibrary\steamapps\workshop\content\1158310\2962333032'
)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'NativeFiles.ps1')
$modRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$utf8=[Text.UTF8Encoding]::new($false,$true)
$roots=@{AGOT_PLUS=$MainPath;AGOT=$AgotPath}
$baseline=Get-Content -LiteralPath (Join-Path $modRoot 'docs/source-baseline.json') -Raw -Encoding UTF8|ConvertFrom-Json
$fixes=Get-Content -LiteralPath (Join-Path $modRoot 'docs/fixes.json') -Raw -Encoding UTF8|ConvertFrom-Json
$additions=Get-Content -LiteralPath (Join-Path $modRoot 'docs/additions.json') -Raw -Encoding UTF8|ConvertFrom-Json
$manifest=Get-Content -LiteralPath (Join-Path $modRoot 'docs/source-manifest.json') -Raw -Encoding UTF8|ConvertFrom-Json
$binaryFixes=Get-Content -LiteralPath (Join-Path $modRoot 'docs/binary-fixes.json') -Raw -Encoding UTF8|ConvertFrom-Json
function Read-Plus([string]$File){[IO.File]::ReadAllText((Get-NativePath (Join-Path $modRoot $File)),$utf8)}
function Read-Agot([string]$File){[IO.File]::ReadAllText((Join-Path $AgotPath $File),$utf8)}
function Clear-ScriptText([string]$Text){
    [regex]::Replace($Text,'"(?:\\.|[^"\\])*"|#[^\r\n]*',{param($m) if($m.Value.StartsWith('#')){''}else{'""'}})
}
function Get-ScriptBlock([string]$Text,[string]$Key){
    $clean=Clear-ScriptText $Text
    $match=[regex]::Match($clean,'(?m)(?<!\S)'+[regex]::Escape($Key)+'\s*=\s*\{')
    if(-not $match.Success){throw "Missing script block: $Key"}
    $start=$match.Index+$match.Length
    $depth=1
    for($i=$start;$i -lt $clean.Length;$i++){
        if($clean[$i] -eq '{'){$depth++}
        if($clean[$i] -eq '}'){$depth--}
        if($depth -eq 0){return $clean.Substring($start,$i-$start)}
    }
    throw "Unclosed script block: $Key"
}
function Test-Braces([string]$Text,[string]$File){
    $depth=0
    foreach($m in [regex]::Matches((Clear-ScriptText $Text),'[{}]')){
        if($m.Value -eq '{'){$depth++}else{$depth--}
        if($depth -lt 0){throw "Unexpected closing brace: $File"}
    }
    if($depth -ne 0){throw "Unclosed braces: $File"}
}
foreach($source in $baseline){
    $path=Join-Path $roots[$source.Catalog] $source.File
    if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -cne $source.SHA256){throw "Upstream file changed: $path"}
}
$currentPlan=Get-Content -LiteralPath (Join-Path $modRoot 'docs/stage12-plan.json') -Raw -Encoding UTF8|ConvertFrom-Json
if($manifest.Revision -ne 12 -or $manifest.Files.Count -ne ($currentPlan.Shadows+$currentPlan.Additions) -or $manifest.ShadowFiles -ne $currentPlan.Shadows -or $manifest.AddedFiles -ne $currentPlan.Additions -or $manifest.FixGroups -ne $currentPlan.FixGroups -or $manifest.ReplacementOccurrences -ne $currentPlan.Occurrences -or $fixes.Count -ne $currentPlan.Rules -or $manifest.BinaryShadowFiles -ne 1 -or $manifest.BinaryBytesRemoved -ne 8){throw 'Unexpected stage-twelve repair inventory.'}
$nativeRoot=Get-NativePath $modRoot
$packaged=@(foreach($dir in @('common','gfx','events','localization','history')){[IO.Directory]::EnumerateFiles((Get-NativePath (Join-Path $modRoot $dir)),'*',[IO.SearchOption]::AllDirectories)|ForEach-Object {$_.Substring($nativeRoot.Length+1).Replace('\','/')}})
if((($packaged|Sort-Object)-join '|') -cne (($manifest.Files.File|Sort-Object)-join '|')){throw 'Unexpected runtime files in package.'}
$applied=0
foreach($item in $manifest.Files){
    $path=Join-Path $modRoot $item.File
    if($item.Kind -eq 'BinaryShadow'){
        $rules=@($binaryFixes|Where-Object File -CEQ $item.File)
        if($rules.Count -ne 1 -or $item.Changes.Count -ne 1){throw 'Unexpected binary recipe count.'}
        $rule=$rules[0]
        if(($item.Changes[0]|ConvertTo-Json -Depth 4 -Compress) -cne ($rule|ConvertTo-Json -Depth 4 -Compress)){throw 'Binary manifest recipe mismatch.'}
        [byte[]]$binaryExpectedBytes=Get-RepairedBinary (Join-Path $roots[$rule.Catalog] $rule.File) $rule
        if([Convert]::ToBase64String($binaryExpectedBytes) -cne [Convert]::ToBase64String([IO.File]::ReadAllBytes((Get-NativePath $path)))){throw 'Unrecorded binary edit.'}
        if((Get-NativeSHA256 $path) -cne $item.PatchedSHA256 -or $item.SourceSHA256 -cne $rule.SourceSHA256){throw 'Binary manifest hash mismatch.'}
        continue
    }
    if($item.Kind -eq 'Addition'){
        $addition=@($additions|Where-Object File -CEQ $item.File)
        if($addition.Count -ne 1 -or (Read-Plus $item.File) -cne $addition[0].Text){throw "Unrecorded addition: $($item.File)"}
        $encoding=[Text.UTF8Encoding]::new($addition[0].UTF8BOM,$true)
        [byte[]]$expectedBytes=$encoding.GetPreamble()+$encoding.GetBytes($addition[0].Text)
        if([Convert]::ToBase64String($expectedBytes) -cne [Convert]::ToBase64String([IO.File]::ReadAllBytes($path))){throw "Addition encoding changed: $($item.File)"}
        if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -cne $item.PatchedSHA256){throw "Addition manifest mismatch: $($item.File)"}
        if($item.File.EndsWith('.txt')){Test-Braces $addition[0].Text $item.File}
        continue
    }
    $catalog=if($item.Catalog){$item.Catalog}else{'AGOT_PLUS'}
    if(-not $roots.ContainsKey($catalog)){throw "Unknown source catalog: $catalog"}
    $source=Join-Path $roots[$catalog] $item.File
    $original=[IO.File]::ReadAllText($source,$utf8)
    $expected=$original
    $rules=@($fixes|Where-Object File -CEQ $item.File)
    if($rules.Count -ne $item.Changes.Count){throw 'Manifest repair inventory mismatch.'}
    foreach($fix in $rules){
        $record=@($item.Changes|Where-Object Id -CEQ $fix.Id)
        if($record.Count -ne 1 -or $record[0].Before -cne $fix.Before -or $record[0].After -cne $fix.After -or $record[0].Occurrences -ne $fix.ExpectedCount){throw "Unexpected repair record: $($fix.Id)"}
        $sourceBefore=if($fix.SourceBefore){$fix.SourceBefore}else{$fix.Before}
        if([regex]::Matches($original,[regex]::Escape($sourceBefore)).Count -ne $fix.ExpectedCount){throw "Wrong upstream occurrences: $($fix.Id)"}
        if($fix.SourceBefore -and $record[0].SourceBefore -cne $fix.SourceBefore){throw "Upstream guard differs from manifest: $($fix.Id)"}
        if([regex]::Matches($expected,[regex]::Escape($fix.Before)).Count -ne $fix.ExpectedCount){throw "Wrong source occurrences: $($fix.Id)"}
        $expected=$expected.Replace($fix.Before,$fix.After)
        $applied+=$fix.ExpectedCount
    }
    $actual=Read-Plus $item.File
    if($actual -cne $expected){throw "Unrecorded edit in $($item.File)"}
    if((Get-NativeSHA256 $path) -cne $item.PatchedSHA256 -or (Get-NativeSHA256 $source) -cne $item.SourceSHA256){throw 'Source/output manifest hash mismatch.'}
    $encoded=[Text.UTF8Encoding]::new($item.UTF8BOM,$true)
    [byte[]]$expectedBytes=$encoded.GetPreamble()+$encoded.GetBytes($expected)
    if([Convert]::ToBase64String($expectedBytes) -cne [Convert]::ToBase64String([IO.File]::ReadAllBytes((Get-NativePath $path)))){throw 'Unrecorded encoding or newline change.'}
    Test-Braces $actual $item.File
    $beforeDefinitions=([regex]::Matches((Clear-ScriptText $original),'(?m)^([A-Za-z_0-9.]+)\s*=\s*\{')|ForEach-Object {$_.Groups[1].Value})-join '|'
    $afterDefinitions=([regex]::Matches((Clear-ScriptText $actual),'(?m)^([A-Za-z_0-9.]+)\s*=\s*\{')|ForEach-Object {$_.Groups[1].Value})-join '|'
    $plannedDefinitions=($currentPlan.ShadowDefinitions.PSObject.Properties[$item.File].Value)-join '|'
    if($plannedDefinitions -cne $afterDefinitions){throw "Unplanned definition inventory change: $($item.File)"}
}
if($applied -ne $currentPlan.Occurrences){throw 'Unexpected applied replacement count.'}

# Resolve actual database objects, rather than accepting text replacement alone.
$null=Get-ScriptBlock (Read-Agot 'common/nicknames/00_agot_event_nicknames.txt') 'nick_agot_young_griff'
foreach($file in @('common/scripted_character_templates/asoiaf_invader_templates.txt')){
    $text=Read-Plus $file
    if($text -match '\bgive_nickname\s*=\s*nick_young_griff\b' -or $text -notmatch '\bgive_nickname\s*=\s*nick_agot_young_griff\b'){throw 'Young Griff nickname still unresolved.'}
}
$null=Get-ScriptBlock (Read-Agot 'common/landed_titles/01_agot_landed_titles.txt') 'c_darry'
$setup=Read-Plus 'common/scripted_effects/asoiaf_setup_effects.txt'
if($setup -match '\bhas_title\s*\?=' -or $setup -notmatch '\bhas_title\s*=\s*title:c_darry\b'){throw 'Invalid has_title operator remains.'}
$interaction=Get-ScriptBlock (Read-Plus 'common/character_interactions/asoiaf_character_interactions.txt') 'asoiaf_dismiss_kingsguard_interaction'
$players=Get-ScriptBlock $interaction 'every_player'
$limit=Get-ScriptBlock $players 'limit'
if($limit -notmatch 'NOT\s*=\s*\{\s*this\s*=\s*scope:actor\s*\}' -or $limit -notmatch 'is_vassal_or_below_of\s*=\s*scope:asoiaf_dismissing_monarch'){throw 'Notification recipient conditions changed.'}
$null=Get-ScriptBlock (Read-Agot 'common/dynasty_houses/00_agot_dynasty_houses.txt') 'house_BaratheonKL'
$artifact=Get-ScriptBlock (Read-Plus 'common/artifacts/templates/asoiaf_artifacts_templates.txt') 'asoiaf_krakenfall_template'
if($artifact -notmatch '\bhouse\s*=\s*house:house_BaratheonKL\b' -or $artifact -notmatch 'add\s*=\s*-100\b'){throw 'Artifact preference rule changed.'}
$giant=Get-ScriptBlock (Read-Agot 'common/men_at_arms_types/00_agot_innovation_maa_types.txt') 'giant_regiment'
$mance=Get-ScriptBlock (Read-Plus 'common/on_action/asoiaf_yearly_on_actions.txt') 'asoiaf_mance_rayder_desertion'
$unit=Get-ScriptBlock (Get-ScriptBlock $mance 'spawn_army') 'men_at_arms'
if($giant -notmatch '\bstack\s*=\s*5\b' -or $unit -notmatch '\btype\s*=\s*giant_regiment\b' -or $unit -notmatch '\bstacks\s*=\s*20\b'){throw 'Giant army no longer matches the intended 100 soldiers.'}
$null=Get-ScriptBlock (Read-Agot 'common/culture/cultures/00_agot_cul_ancient_races.txt') 'dragon_culture'
$null=Get-ScriptBlock (Read-Agot 'common/religion/religion_types/00_agot_the_flames.txt') 'valyrian_pan_freehold'
$dragonSource=Read-Agot 'common/scripted_effects/00_agot_dragon_canon_dragons_effects.txt'
foreach($id in @('agot_spawn_vermax_effect','agot_spawn_drogon_effect','agot_spawn_rhaegal_effect','agot_spawn_viserion_effect')){
    $create=Get-ScriptBlock (Get-ScriptBlock $dragonSource $id) 'create_character'
    if($create -notmatch '\bculture\s*=\s*culture:dragon_culture\b' -or $create -notmatch '\bfaith\s*=\s*faith:valyrian_pan_freehold\b'){throw "AGOT changed its canonical dragon identifiers: $id"}
}
$dragons=Read-Plus 'common/scripted_effects/asoiaf_agot_overwrite_effects.txt'
foreach($id in @('agot_spawn_vermax_effect','agot_spawn_drogon_effect','agot_spawn_adult_drogon_effect','agot_spawn_rhaegal_effect','agot_spawn_adult_rhaegal_effect','agot_spawn_viserion_effect','agot_spawn_adult_viserion_effect')){
    $create=Get-ScriptBlock (Get-ScriptBlock $dragons $id) 'create_character'
    if($create -notmatch '\bculture\s*=\s*culture:dragon_culture\b' -or $create -notmatch '\bfaith\s*=\s*faith:valyrian_pan_freehold\b'){throw "Dragon identifiers not fixed: $id"}
}
$roles=Read-Plus 'gfx/court_scene/character_roles/asoiaf_default_roles.txt'
foreach($id in @('asoiaf_kingsguard','asoiaf_gold_cloak','asoiaf_gold_cloak_commander')){
    $vassal=Get-ScriptBlock (Get-ScriptBlock $roles $id) 'any_vassal'
    if($vassal.TrimStart() -match '^limit\s*=' -or $vassal -notmatch '\bhas_court_position\s*=\s*goldcloaks_court_position\b' -or $vassal -notmatch '\bname\s*=\s*agot_goldcloaks_founded\b'){throw "Court role conditions damaged: $id"}
}
$descriptor=Read-Plus 'descriptor.mod'
$external=[IO.File]::ReadAllText((Join-Path $modRoot '../AGOT_PLUS_FIX.mod'),$utf8)
if($descriptor -match '\breplace_path\s*=' -or $external -match '\breplace_path\s*='){throw 'Patch must not discard upstream directories.'}
$path=[regex]::Match($external,'(?m)^path="([^"]+)"').Groups[1].Value
if([IO.Path]::GetFullPath($path) -ine $modRoot){throw 'External descriptor points to the wrong directory.'}
. (Join-Path $PSScriptRoot 'Test-AGOTPlusFixStage2.ps1')
. (Join-Path $PSScriptRoot 'Test-AGOTPlusFixStage3.ps1')
. (Join-Path $PSScriptRoot 'Test-AGOTPlusFixStage4.ps1')
. (Join-Path $PSScriptRoot 'Test-AGOTPlusFixStage5.ps1')
. (Join-Path $PSScriptRoot 'Test-AGOTPlusFixStage6.ps1')
& python (Join-Path $PSScriptRoot 'Appearance-Stage7.py') check --plus $MainPath --agot $AgotPath
if($LASTEXITCODE -ne 0){throw 'Stage-seven appearance validation failed.'}
& python (Join-Path $PSScriptRoot 'Test-Scripts-Stage8.py')
if($LASTEXITCODE -ne 0){throw 'Stage-eight script validation failed.'}
& python (Join-Path $PSScriptRoot 'DNA-Stage9.py') check --before-stage10
if($LASTEXITCODE -ne 0){throw 'Archived stage-nine DNA validation failed.'}
& python (Join-Path $PSScriptRoot 'DNA-Stage10.py') check
if($LASTEXITCODE -ne 0){throw 'Stage-ten DNA validation failed.'}
& python (Join-Path $PSScriptRoot 'Portraits-Stage11.py') check
if($LASTEXITCODE -ne 0){throw 'Stage-eleven portrait/model validation failed.'}
& python (Join-Path $PSScriptRoot 'Variables-Stage12.py') check
if($LASTEXITCODE -ne 0){throw 'Stage-twelve variable validation failed.'}
Write-Output "PASS: $($baseline.Count) source hashes; $($manifest.ShadowFiles) exact file shadows and $($manifest.AddedFiles) additions; $applied replacements in $($manifest.FixGroups) groups."
Write-Output 'PASS: script braces and definition inventory; source/output bytes reconstruct exactly.'
Write-Output 'PASS: real nickname, house, title, giant unit, dragon culture/faith and court role contracts.'
Write-Output 'Static checks passed. CK3 execution was not performed; engine behavior and a fresh game log are unverified.'
