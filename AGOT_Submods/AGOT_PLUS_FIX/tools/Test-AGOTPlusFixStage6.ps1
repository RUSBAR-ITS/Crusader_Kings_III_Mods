
. (Join-Path $PSScriptRoot '../../../tools/RepositoryText.ps1')
# Loaded after the common parser and regression tests. These are source/contract
# checks plus a limited model of crown creation, not execution of CK3 artifacts.
$s6File='common/scripted_effects/asoiaf_scripted_effects_artifacts.txt'
$s6Original=[IO.File]::ReadAllText((Join-Path $MainPath $s6File))
$s6Patched=Read-Plus $s6File
$s6OriginalNodes=@(ConvertTo-AgeNodes $s6Original)
$s6PatchedNodes=@(ConvertTo-AgeNodes $s6Patched)
$s6Names=@('ice','heartsbane','longclaw','oathkeeper','widows_wail','dark_sister')
$s6Counts=@(2,2,2,6,6,3)
$s6Crowns=@('robertI','renly','joffreyI')
$s6Dependencies=[Collections.Generic.List[object]]::new()
function Get-S6Definition([string]$Text,[string]$Key){
 $clean=Clear-ScriptText $Text
 $definitions=[regex]::Matches($clean,'(?m)^'+[regex]::Escape($Key)+'\s*=\s*\{')
 if($definitions.Count -ne 1){throw "Expected one top-level artifact definition: $Key"}
 Get-ScriptBlock ($clean.Substring($definitions[0].Index)) $Key
}
function Read-S6Effective([string]$Relative){
 $providers=@($active|Where-Object {Test-Path -LiteralPath (Join-Path $_ $Relative)})
 if(-not $providers.Count){throw "Missing artifact dependency: $Relative"}
 $path=Join-Path $providers[-1] $Relative
 $s6Dependencies.Add([pscustomobject]@{File=$Relative;Provider=$providers[-1];SHA256=(Get-FileHash -LiteralPath $path).Hash})
 [IO.File]::ReadAllText($path)
}
$s6Templates=Read-S6Effective 'common/artifacts/templates/00_agot_historical_artifacts_equipment.txt'
$s6CrownTemplates=Read-S6Effective 'common/artifacts/templates/00_agot_historical_artifacts_crowns.txt'
$s6Modifiers=Read-S6Effective 'common/modifiers/00_agot_artifact_modifiers.txt'
$s6Culture=Read-S6Effective 'common/culture/cultures/00_agot_cul_andal.txt'
$s6Steel=Get-ScriptBlock $s6Templates 'valyrian_steel_template'
if($s6Steel -cne (Get-ScriptBlock (Read-Agot 'common/artifacts/templates/00_agot_historical_artifacts_equipment.txt') 'valyrian_steel_template')){throw 'Active steel template differs from the reviewed AGOT template'}
if((Get-ScriptBlock $s6Steel 'can_equip').Trim() -cne 'always = yes' -or (Get-ScriptBlock $s6Steel 'can_benefit').Trim() -cne 'is_capable_adult = yes' -or $s6Steel -notmatch '\bunique\s*=\s*yes\b'){throw 'Steel template equipment/benefit/uniqueness contract changed'}
$s6SwordSites=0
for($s6i=0;$s6i -lt $s6Names.Count;$s6i++){
 $name=$s6Names[$s6i];$old='vs_'+$name+'_template'
 $matches=[regex]::Matches((Clear-ScriptText $s6Original),'\btemplate\s*=\s*'+$old+'\b')
 if($matches.Count -ne $s6Counts[$s6i] -or (Clear-ScriptText $s6Patched) -match ('\b'+$old+'\b')){throw "Sword template repair incomplete: $name"}
 $s6SwordSites+=$matches.Count
 $baseFile=if($name -in @('oathkeeper','widows_wail')){'common/scripted_effects/00_agot_artifact_vs_sword_forgeable_effects.txt'}else{'common/scripted_effects/00_agot_artifact_vs_sword_effects.txt'}
 $baseEffect=Get-S6Definition (Read-Agot $baseFile) ('agot_create_artifact_vs_'+$name+'_effect')
 if((Get-ScriptBlock $baseEffect 'create_artifact') -notmatch '\btemplate\s*=\s*valyrian_steel_template\b'){throw "Base AGOT no longer uses this template for $name"}
 $null=Get-ScriptBlock $s6Modifiers ('vs_'+$name+'_modifier')
}
if($s6SwordSites -ne 21){throw 'Expected 21 sword creation branches'}
# Independently check the entire effect file against the tightly scoped migration,
# preserving histories, claims, ownership, visuals and equipment logic. Stage 12
# explicitly comments six unread marker writes; its check also compares every
# remaining active token against the pinned pre-stage-12 artifact file.
foreach($oldNode in $s6OriginalNodes){
 $oldBody=Get-S6Definition $s6Original $oldNode.Key
 $newBody=Get-S6Definition $s6Patched $oldNode.Key
 if($oldNode.Key -cin @($s6Crowns|ForEach-Object {'agot_create_artifact_'+$_+'_crown_effect'})){
  $newBody=$newBody.Replace('$CREATOR$ = { save_scope_as = creator }','').Replace('creator = scope:creator','')
 }else{
  foreach($name in $s6Names){$oldBody=$oldBody.Replace(('template = vs_'+$name+'_template'),'template = valyrian_steel_template')}
 }
 if($manifest.Revision -ge 12){
  $oldBody=[regex]::Replace($oldBody,'\bset_variable\s*=\s*\{\s*name\s*=\s*(asoiaf_is_krakenfall|asoiaf_is_needle|asoiaf_is_red_vipers_spear|dark_sister_artifact)\s+value\s*=\s*yes\s*\}','')
 }
 if(($oldBody -replace '\s+','') -cne ($newBody -replace '\s+','')){throw "Unrelated artifact behavior changed: $($oldNode.Key)"}
}

# Inspect every effective call site in common/events/history from the actual
# playset. A source file hidden by a later mod must not be counted as active.
$s6Pattern='agot_create_artifact_(robertI|renly|joffreyI)_crown_effect\s*='
$s6RelativeFiles=@{}
foreach($rootPath in $active){
 $searchPaths=@(foreach($part in @('common','events','history')){$p=Join-Path $rootPath $part;if(Test-Path -LiteralPath $p){$p}})
 if(-not $searchPaths.Count){continue}
 $hits=@(& rg -l $s6Pattern @searchPaths -g '*.txt')
 if($LASTEXITCODE -gt 1){throw "Artifact caller scan failed: $rootPath"}
 foreach($hit in $hits){$relative=[IO.Path]::GetFullPath($hit).Substring($rootPath.TrimEnd('\','/').Length+1).Replace('\','/');$s6RelativeFiles[$relative]=$true}
}
$s6Calls=[Collections.Generic.List[object]]::new()
$s6Definitions=[Collections.Generic.List[object]]::new()
foreach($relative in $s6RelativeFiles.Keys|Sort-Object){
 $providers=@($active|Where-Object {Test-Path -LiteralPath (Join-Path $_ $relative)})
 $effectivePath=Join-Path $providers[-1] $relative;$effective=[IO.File]::ReadAllText($effectivePath)
 foreach($name in $s6Crowns){
  $key='agot_create_artifact_'+$name+'_crown_effect'
  if((Clear-ScriptText $effective) -match ('\b'+$key+'\s*=\s*yes\b')){throw "Crown call without parameters: $effectivePath"}
  foreach($body in @(Get-AllBlocks $effective $key)){
   $nodes=@(ConvertTo-AgeNodes $body)
   if($nodes[0].Key -ceq '$OWNER$'){
    $s6Definitions.Add([pscustomobject]@{Effect=$key;File=$relative;Provider=$providers[-1]})
    continue
   }
   if((($nodes.Key|Sort-Object) -join '|') -cne 'CREATOR|OWNER' -or @($nodes|Where-Object {$_.Children.Count -or $_.Operator -cne '='}).Count){throw "Incompatible crown call: $effectivePath / $key"}
   $s6Calls.Add([pscustomobject]@{Effect=$key;File=$relative;Provider=$providers[-1];OWNER=($nodes|Where-Object Key -ceq 'OWNER').Value;CREATOR=($nodes|Where-Object Key -ceq 'CREATOR').Value})
  }
 }
}
foreach($name in $s6Crowns){
 $key='agot_create_artifact_'+$name+'_crown_effect'
 $definitions=@($s6Definitions|Where-Object Effect -ceq $key)
 if($definitions.Count -ne 2 -or @($definitions|Where-Object {$_.File -ceq $s6File -and $_.Provider -ieq $modRoot}).Count -ne 1 -or @($definitions|Where-Object {$_.File -ceq 'common/scripted_effects/00_agot_artifact_crowns_effects.txt' -and $_.Provider -ieq $AgotPath}).Count -ne 1){throw "Unexpected active crown effect override: $key"}
 $body=Get-S6Definition $s6Patched $key
 $parameters=@([regex]::Matches($body,'\$([A-Z_]+)\$')|ForEach-Object {$_.Groups[1].Value}|Sort-Object -Unique)
 if(($parameters -join '|') -cne 'CREATOR|OWNER'){throw 'Patched crown macro parameters differ from current AGOT'}
 $baseCrown=Get-S6Definition (Read-Agot 'common/scripted_effects/00_agot_artifact_crowns_effects.txt') $key
 if($baseCrown -notmatch '\$CREATOR\$\s*=\s*\{\s*save_scope_as\s*=\s*creator\s*\}' -or (Get-ScriptBlock $baseCrown 'create_artifact') -notmatch '\bcreator\s*=\s*scope:creator\b'){throw 'Native creator contract changed'}
 $null=Get-ScriptBlock $s6CrownTemplates ($name+'_crown_template')
 $null=Get-ScriptBlock $s6Modifiers ($name+'_crown_modifier')
 $inheritance=@($s6Calls|Where-Object {$_.Effect -ceq $key -and $_.File -ceq 'common/on_action/agot_on_actions/test_title_on_actions.txt'})
 if($inheritance.Count -ne 1 -or $inheritance[0].OWNER -cne 'this' -or $inheritance[0].CREATOR -cne 'this'){throw 'Automatic crown grant is missing its explicit creator'}
 if(-not @($s6Calls|Where-Object {$_.Effect -ceq $key -and $_.CREATOR -ceq 'scope:smith'}).Count){throw 'No active commissioned crown caller was checked'}
}

function Resolve-S6Character($Reference,$State){
 if($Reference -ceq 'this'){return $State.Current}
 if($Reference -cmatch '^scope:(\w+)$'){
  $target=$State.Scopes[$Matches[1]]
  if($null -eq $target){throw "Unresolved artifact character: $Reference"}
  return $target
 }
 throw "Unknown character reference in crown model: $Reference"
}
function Invoke-S6Creation($Nodes,$State,$Current=$State.Current){
 $taken=$false
 foreach($node in $Nodes){
  switch -CaseSensitive ($node.Key){
   '$OWNER$' {Invoke-S6Creation $node.Children $State (Resolve-S6Character $State.Arguments.OWNER $State)}
   '$CREATOR$' {Invoke-S6Creation $node.Children $State (Resolve-S6Character $State.Arguments.CREATOR $State)}
   'save_scope_as' {$State.Scopes[$node.Value]=$Current}
   'set_artifact_rarity_illustrious' {if($node.Value -cne 'yes'){throw 'Crown rarity changed'}}
   'if' {
    $limit=@($node.Children|Where-Object Key -ceq 'limit')
    if($limit.Count -ne 1 -or $limit[0].Children.Count -ne 1 -or $limit[0].Children[0].Key -cne 'has_game_rule'){throw 'Unexpected crown creation condition'}
    $taken=$State.Rules -ccontains $limit[0].Children[0].Value
    if($taken){Invoke-S6Creation @($node.Children|Where-Object Key -cne 'limit') $State}
   }
   'else' {if(-not $taken){Invoke-S6Creation $node.Children $State}}
   'create_artifact' {
    $fields=@{}
    foreach($field in $node.Children){if($field.Children.Count){throw 'Unexpected new crown creation block'};$fields[$field.Key]=$field.Value}
    if(-not $fields.ContainsKey('creator')){throw 'Crown lost its creator'}
    $State.Created.Add([pscustomobject]@{Owner=$State.Scopes.owner;Creator=(Resolve-S6Character $fields.creator $State);Fields=$fields})
   }
   default {throw "Unsupported crown creation command: $($node.Key)"}
  }
 }
}
$s6Cases=0
foreach($name in $s6Crowns){
 $key='agot_create_artifact_'+$name+'_crown_effect'
 $body=Get-S6Definition $s6Patched $key
 # Stop at artifact post-processing, which is proven unchanged above.
 $creationPrefix=$body.Substring(0,$body.IndexOf('scope:newly_created_artifact'))
 foreach($style in @($true,$false)){
  foreach($call in @($s6Calls|Where-Object Effect -ceq $key|Sort-Object OWNER,CREATOR -Unique)){
   $state=@{Current='caller';Scopes=@{artifact_recipient='recipient';smith='smith';creator='stale-creator'};Rules=@();Created=[Collections.Generic.List[object]]::new();Arguments=$call}
   if($style){$state.Rules=@('asoiaf_new_clothes_stormlands_rule_on','asoiaf_new_clothes_crownlands_rule_on')}
   $owner=Resolve-S6Character $call.OWNER $state;$creator=Resolve-S6Character $call.CREATOR $state
   # Execute the real parameter scope changes and save_scope_as commands.
   # Owner, creator and the calling character may be three different people.
   $nodes=@(ConvertTo-AgeNodes $creationPrefix)
   if($nodes[0].Key -cne '$OWNER$' -or $nodes[1].Key -cne '$CREATOR$'){throw 'Crown creator must be set before creation'}
   Invoke-S6Creation $nodes $state
   if($state.Created.Count -ne 1){throw 'Crown branch created zero or multiple artifacts'}
   $result=$state.Created[0]
   if($result.Owner -cne $owner -or $result.Creator -cne $creator -or $result.Creator -ceq 'stale-creator'){throw 'Crown attributed to the wrong owner/creator'}
   $visual=if($style){switch($name){'robertI' {'asoiaf_robert_I_crown_visuals'};'joffreyI' {'asoiaf_joffrey_I_crown_visuals'};'renly' {'asoiaf_renly_crown_visuals'}}}else{$name+'_crown_visuals'}
   if($result.Fields.visuals -cne $visual -or $result.Fields.template -cne ($name+'_crown_template') -or $result.Fields.modifier -cne ($name+'_crown_modifier') -or $result.Fields.decaying -cne 'no'){throw 'Crown presentation/properties changed'}
   $s6Cases++
  }
 }
}
$null=Get-ScriptBlock $s6Culture 'westerman_main'
if((Clear-ScriptText $s6Culture) -match '(?m)^westerman\s*='){throw 'Obsolete westerman culture returned; review the modifier migration'}
$s6ModifierFile='common/modifiers/asoiaf_artifact_modifiers.txt'
$s6OldModifier=[RepositoryText]::Normalize([IO.File]::ReadAllText((Join-Path $MainPath $s6ModifierFile)))
$s6CurrentModifier=Read-Plus $s6ModifierFile
if($manifest.Revision -in @(14,15)){
 # Stage14 explicitly archives the unused Oathkeeper definition. Its validator
 # proves the new delta; retain this older contract on the pinned prior file.
 $s6Stage14Plan=Get-Content -LiteralPath (Join-Path $modRoot 'docs/stage14-plan.json') -Raw -Encoding UTF8 | ConvertFrom-Json
 $s6Archive=$s6Stage14Plan.Archives.PSObject.Properties[$s6ModifierFile].Value
 if(-not $s6Archive){throw 'Missing stage-fourteen modifier archive'}
 $s6CurrentModifier=[IO.File]::ReadAllText((Join-Path $modRoot ('docs/'+$s6Archive)))
}
if($s6CurrentModifier -cne $s6OldModifier.Replace('westerman_opinion = 20','westerman_main_opinion = 20')){throw 'Other artifact bonuses changed'}
if((Clear-ScriptText $s6Modifiers) -notmatch '\bwesterman_main_opinion\s*='){throw 'Current AGOT does not corroborate the culture opinion key'}
$s6Targets=@(Import-Csv -LiteralPath (Join-Path $modRoot 'docs/stage6-targeted-log-messages.csv'))
if($s6Targets.Count -ne 49 -or @($s6Targets|Where-Object IssueClass -ceq 'Artifact_templates_and_arguments').Count -ne 48){throw 'Stage-six diagnostic inventory changed'}
$s6Result=[ordered]@{
 Revision=6;Status='PASS';GameExecutionChecked=$false;FreshLogChecked=$false
 HistoricalDiagnosticTargets=49;SwordTemplateSites=$s6SwordSites;CrownCreationBranches=6;CrownScenarios=$s6Cases
 ActiveCrownCalls=$s6Calls.Count;Calls=$s6Calls.ToArray();Dependencies=$s6Dependencies.ToArray()
 Verification='Source/argument/active-provider contracts and a limited crown-creation model; CK3 artifact creation, display and history were not executed.'
 PreviousRegressionChecksPassed=$true;DragonBondingScenarios=($s5BirthCases+$s5YearCases+$s5ExtraCases)
 SourceHashes=$baseline.Count;ManifestSHA256=(Get-FileHash -LiteralPath (Join-Path $modRoot 'docs/source-manifest.json')).Hash
}
[RepositoryText]::WriteAllText((Join-Path $modRoot 'docs/stage6-validation.json'),($s6Result|ConvertTo-Json -Depth 8)+"`n",$utf8)
Write-Output "PASS: artifact contracts: 21 sword templates; six crown branches; $s6Cases crown creation scenarios; $($s6Calls.Count) effective calls; current culture opinion key."
Write-Output 'PASS: artifact histories/claims/modifiers/visual choices preserved; only approved unused marker writes excluded; 49 historical diagnostic targets. CK3 runtime not exercised.'
