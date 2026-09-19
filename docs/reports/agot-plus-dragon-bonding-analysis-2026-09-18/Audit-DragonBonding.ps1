
. (Join-Path $PSScriptRoot '../../../tools/RepositoryText.ps1')
# Read-only audit of runtime scripts; writes report artifacts in this directory.
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$modRoot=Join-Path $repo 'AGOT_Submods/AGOT_PLUS_FIX'
$previous=Join-Path $PSScriptRoot '../ck3-agot-plus-fix-stage4-log-2026-09-18'
$mods=Import-Csv -LiteralPath (Join-Path $previous 'active-mods.csv')
$diagnostics=@(Import-Csv -LiteralPath (Join-Path $previous 'agot-plus-remaining.csv')|Where-Object IssueClass -ceq 'Dragon_schemes')
if($diagnostics.Count -ne 102){throw 'Expected 102 dragon scheme diagnostics'}
$utf8=[Text.UTF8Encoding]::new($false,$true)
function Mask-Script([string]$Text){
 [regex]::Replace($Text,'"(?:\\.|[^"\\])*"|#[^\r\n]*',{param($m) [regex]::Replace($m.Value,'[^\r\n]',' ')})
}
function Get-Blocks([string]$Text,[string]$Key){
 $clean=Mask-Script $Text
 foreach($m in [regex]::Matches($clean,'(?m)(?<!\S)'+[regex]::Escape($Key)+'\s*(?:\?=|=)\s*\{')){
  $depth=1;$start=$m.Index+$m.Length
  for($i=$start;$i -lt $clean.Length;$i++){
   if($clean[$i] -ceq '{'){$depth++}elseif($clean[$i] -ceq '}'){$depth--}
   if($depth -eq 0){break}
  }
  if($depth){throw "Unclosed block: $Key"}
  [pscustomobject]@{Index=$m.Index;End=$i;Line=1+[regex]::Matches($Text.Substring(0,$m.Index),'\n').Count;Body=$Text.Substring($start,$i-$start);Text=$Text.Substring($m.Index,$i+1-$m.Index)}
 }
}
function Read-Field($Text,$Key){
 [regex]::Match((Mask-Script $Text),'\b'+[regex]::Escape($Key)+'\s*=\s*([^\s{}]+)').Groups[1].Value
}
function Find-Parent($Blocks,$Child){
 $found=$Blocks|Where-Object {$_.Index -lt $Child.Index -and $_.End -gt $Child.End}|Sort-Object Index -Descending|Select-Object -First 1
 if(-not $found){throw 'Missing parent block'}
 $found
}
$sites=[Collections.Generic.List[object]]::new()
$inputs=[Collections.Generic.List[object]]::new()
foreach($relative in @('common/on_action/asoiaf_yearly_on_actions.txt','common/scripted_effects/asoiaf_canon_children_effects.txt')){
 $path=Join-Path $modRoot $relative
 $body=[IO.File]::ReadAllText($path)
 $inputs.Add([pscustomobject]@{Kind='Audited runtime';Path=$path;SHA256=(Get-FileHash -LiteralPath $path).Hash})
 $functions=[regex]::Matches($body,'(?m)^(\w+)\s*=\s*\{[^\r\n]*')
 $ifs=@(Get-Blocks $body 'if')
 $toasts=@(Get-Blocks $body 'send_interface_toast')
 $creations=@(Get-Blocks $body 'create_character')
 foreach($scheme in Get-Blocks $body 'start_scheme'){
  if((Read-Field $scheme.Body 'type') -cne 'bond_with_dragon_scheme'){continue}
  $branch=Find-Parent $ifs $scheme
  $toast=Find-Parent $toasts $scheme
  $bonds=@(Get-Blocks $branch.Text 'agot_bond_dragon_relation_effect')
  if($bonds.Count -ne 1){throw 'Expected one direct bond before each scheme'}
  $bond=$bonds[0]
  $function=$functions|Where-Object Index -lt $scheme.Index|Select-Object -Last 1
  $actor=Read-Field $bond.Body 'ACTOR'
  $dragon=Read-Field $bond.Body 'DRAGON'
  $target=Read-Field $scheme.Body 'target'
  $limit=@(Get-Blocks $branch.Text 'limit')[0].Body
  $birth=$relative -like '*canon_children_effects.txt'
  $creation=if($birth){Find-Parent $creations $scheme}else{$null}
  $name=if($birth){[regex]::Match($creation.Body,'\bname\s*=\s*"([^"]+)"').Groups[1].Value}else{''}
  $targetLine=$scheme.Line+[regex]::Matches($scheme.Text.Substring(0,$scheme.Text.IndexOf('target =')),'\n').Count
  $messages=@($diagnostics|Where-Object {
   $_.Evidence -ceq $relative -and $_.Message -match 'line: (\d+)' -and [int]$Matches[1] -in @($scheme.Line,$targetLine)
  })
  if($messages.Count -ne 3){throw "Expected three diagnostics at $relative line $($scheme.Line), found $($messages.Count)"}
  $candidate=if(-not $birth){@(Get-Blocks $branch.Text 'every_dynasty_member')[0]}else{$null}
  $eligibility=if(-not $birth){@(Get-Blocks $branch.Text 'any_dynasty_member')[0]}else{$null}
  $candidateTrait=if($candidate){Read-Field $candidate.Body 'has_inactive_trait'}else{Read-Field $creation.Body 'make_trait_inactive'}
  $sites.Add([pscustomobject][ordered]@{
   File=$relative;Function=$function.Groups[1].Value;FunctionHeader=$function.Value.Trim();Kind=$(if($birth){'Birth'}else{'Yearly retry'})
   SchemeLine=$scheme.Line;TargetLine=$targetLine;DiagnosticCount=$messages.Count;LogLines=($messages.LogLine -join ',')
   Actor=$actor;Dragon=$dragon;Target=$target;DragonMatchesTarget=($dragon -ceq $target)
   DirectBondPrecedesScheme=($branch.Index+$bond.Index -lt $scheme.Index)
   ToastActor=Read-Field $toast.Body 'left_icon';ToastDragon=Read-Field $toast.Body 'right_icon'
   CurrentCharacter=$(if($birth){'after_creation newborn'}else{'yearly pulse ROOT, not selected ACTOR'})
   ChildName=$name;ChildAge=$(if($birth){Read-Field $creation.Body 'age'}else{''});IdentityTrait=$candidateTrait
   OptionalDragonGuard=($limit -match ([regex]::Escape($dragon)+'\s*\?=\s*\{'))
   ExplicitDragonExists=($limit -match ('\bexists\s*=\s*'+[regex]::Escape($dragon)+'\b'))
   CandidateAliveGuard=$(if($candidate){$candidate.Body -match '\bis_alive\s*=\s*yes'}else{$null})
   CandidateNightswatchGuard=$(if($candidate){$candidate.Body -match '\bhas_trait\s*=\s*nightswatch'}else{$null})
   EligibilityNightswatchGuard=$(if($eligibility){$eligibility.Body -match '\bhas_trait\s*=\s*nightswatch'}else{$null})
  })
 }
}
if($sites.Count -ne 34 -or @($sites|Where-Object {-not $_.DragonMatchesTarget -or -not $_.DirectBondPrecedesScheme}).Count){throw 'Unexpected scheme pattern'}
$sites|Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'scheme-sites.csv') -NoTypeInformation -Encoding UTF8
$diagnostics|Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'targeted-log-messages.csv') -NoTypeInformation -Encoding UTF8
$yearly=[IO.File]::ReadAllText((Join-Path $modRoot 'common/on_action/asoiaf_yearly_on_actions.txt'))
$maintenance=@(Get-Blocks $yearly 'asoiaf_canon_children_dragon_bonding_maintenance')[0]
$trigger=@(Get-Blocks $maintenance.Text 'trigger')[0]
$rootTraits=@([regex]::Matches($trigger.Body,'has_inactive_trait\s*=\s*(\w+)')|ForEach-Object {$_.Groups[1].Value})
$retry=$sites|Where-Object Kind -ceq 'Yearly retry'
$missing=@($retry|Where-Object {$rootTraits -cnotcontains $_.IdentityTrait}|Select-Object IdentityTrait,Actor,Dragon)
$evidence=@(
 @('AGOT','2962333032','common/scripted_effects/00_agot_dragon_effects.txt'),
 @('More Dragon Eggs','3388366564','common/scripted_effects/00_agot_dragon_effects.txt'),
 @('AGOT','2962333032','common/scripted_triggers/00_agot_dragon_triggers.txt'),
 @('More Dragon Eggs','3388366564','common/scripted_triggers/00_agot_dragon_triggers.txt'),
 @('AGOT','2962333032','common/schemes/scheme_types/agot_bond_with_dragon_scheme.txt'),
 @('Valyrian Steel','2962713441','common/schemes/scheme_types/bond_with_dragon_scheme.txt'),
 @('AGOT','2962333032','events/agot_events/agot_dragon_maintenance_events.txt'),
 @('AGOT','2962333032','common/character_interactions/00_agot_dragon_bond_interactions.txt'),
 @('AGOT','2962333032','common/scripted_relations/00_agot_scripted_relations.txt'),
 @('AGOT+','2950245430','common/game_rules/asoiaf_game_rules.txt'),
 @('AGOT+','2950245430','localization/english/asoiaf_game_rules_l_english.yml')
)
foreach($item in $evidence){
 $path='E:/SteamLibrary/steamapps/workshop/content/1158310/'+$item[1]+'/'+$item[2]
 $inputs.Add([pscustomobject]@{Kind=$item[0];Path=$path;SHA256=(Get-FileHash -LiteralPath $path).Hash})
}
# Both effective MDE helpers retain the relevant AGOT contract.
foreach($key in @('agot_bond_dragon_relation_effect','agot_set_as_owned_dragon')){
 $base=@(Get-Blocks ([IO.File]::ReadAllText('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032/common/scripted_effects/00_agot_dragon_effects.txt')) $key)[0].Body
 $effective=@(Get-Blocks ([IO.File]::ReadAllText('E:/SteamLibrary/steamapps/workshop/content/1158310/3388366564/common/scripted_effects/00_agot_dragon_effects.txt')) $key)[0].Body
 if((Mask-Script $base) -cne (Mask-Script $effective)){throw "Effective MDE helper differs: $key"}
}
foreach($key in @('agot_has_relationship_dragon','can_use_bond_with_dragon_scheme')){
 $base=@(Get-Blocks ([IO.File]::ReadAllText('E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032/common/scripted_triggers/00_agot_dragon_triggers.txt')) $key)[0].Body
 $effective=@(Get-Blocks ([IO.File]::ReadAllText('E:/SteamLibrary/steamapps/workshop/content/1158310/3388366564/common/scripted_triggers/00_agot_dragon_triggers.txt')) $key)[0].Body
 if((Mask-Script $base) -cne (Mask-Script $effective)){throw "Effective MDE trigger differs: $key"}
}
foreach($relative in @('2962333032/common/schemes/scheme_types/agot_bond_with_dragon_scheme.txt','2962713441/common/schemes/scheme_types/bond_with_dragon_scheme.txt')){
 $text=[IO.File]::ReadAllText('E:/SteamLibrary/steamapps/workshop/content/1158310/'+$relative)
 $valid=@(Get-Blocks $text 'valid')[0].Body
 foreach($key in @('scope:owner','scope:target')){
  $scopeBody=@(Get-Blocks $valid $key)[0].Body
  if((Mask-Script $scopeBody) -notmatch 'any_relation\s*=\s*\{\s*type\s*=\s*agot_dragon\s*count\s*=\s*0\s*\}') {throw 'Scheme no-bond requirement changed'}
 }
 if(@([regex]::Matches(@(Get-Blocks $text 'allow')[0].Body,'age >= 6')).Count -ne 2){throw 'Scheme age requirements changed'}
}
$inputs|Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'source-hashes.csv') -NoTypeInformation -Encoding UTF8
$sourceConflicts='C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III/logs/database_conflicts.log'
$conflictText=[IO.File]::ReadAllText($sourceConflicts)
$conflictLines=@($conflictText -split '\r?\n'|Where-Object {$_ -match "Overriding entry 'bond_with_dragon_scheme'"})
[RepositoryText]::WriteAllText((Join-Path $PSScriptRoot 'scheme-override-evidence.log'),($conflictLines -join [Environment]::NewLine)+[Environment]::NewLine,$utf8)
$summary=[ordered]@{
 CapturedAt=[DateTimeOffset]::Now.ToString('o');AnalysisOnly=$true;RuntimeFilesChanged=$false
 TargetMessages=$diagnostics.Count;SchemeSites=$sites.Count;BirthSites=@($sites|Where-Object Kind -ceq 'Birth').Count;YearlySites=@($retry).Count
 DiagnosticComponents=@($diagnostics|Group-Object Component|Select-Object Name,Count)
 DirectBondBeforeEveryScheme=$true;AllBirthActorsAreNewborns=(@($sites|Where-Object {$_.Kind -ceq 'Birth' -and $_.ChildAge -cne '0'}).Count -eq 0)
 RootTriggerIdentityTraits=$rootTraits.Count;RetryBranches=@($retry).Count;MissingRootTriggerIdentities=$missing
 OptionalDragonGuards=@($sites|Where-Object OptionalDragonGuard).Count;ExplicitDragonExistenceGuards=@($sites|Where-Object ExplicitDragonExists).Count
 SelectedCandidateAliveGuards=@($retry|Where-Object CandidateAliveGuard).Count;SelectedCandidateNightswatchGuards=@($retry|Where-Object CandidateNightswatchGuard).Count
 BaseAndEffectiveBondAndOwnershipHelpersEqual=$true;SchemeOverrideLogLines=$conflictLines.Count
 BaseAndEffectiveBondTriggersEqual=$true;BothSchemeDefinitionsRequireUnbondedPairAndAgeSix=$true
 BaselineErrorLogSHA256=(Get-FileHash -LiteralPath (Join-Path $previous 'snapshot/error.log')).Hash
 PatchManifestSHA256=(Get-FileHash -LiteralPath (Join-Path $modRoot 'docs/source-manifest.json')).Hash
 RecommendedPolicy='Retain canonical automatic bonding, remove all 34 redundant scheme launches, harden target/candidate guards and yearly recipient handling; preserve pair priority.'
 EngineExecutionChecked=$false
}
[RepositoryText]::WriteAllText((Join-Path $PSScriptRoot 'summary.json'),($summary|ConvertTo-Json -Depth 6)+[Environment]::NewLine,$utf8)
$summary|ConvertTo-Json -Depth 6
