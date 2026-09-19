# One-time registration against reviewed upstream files; normal rebuilds use Build/Test.
param([string]$MainPath='E:\SteamLibrary\steamapps\workshop\content\1158310\2950245430',
      [string]$AgotPath='E:\SteamLibrary\steamapps\workshop\content\1158310\2962333032')
$ErrorActionPreference='Stop'
$modRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$utf8=[Text.UTF8Encoding]::new($false,$true)
$fixPath=Join-Path $modRoot 'docs/fixes.json'
$basePath=Join-Path $modRoot 'docs/source-baseline.json'
$fixes=Get-Content -LiteralPath $fixPath -Raw -Encoding UTF8|ConvertFrom-Json
$baseline=Get-Content -LiteralPath $basePath -Raw -Encoding UTF8|ConvertFrom-Json
if(@($fixes|Where-Object Group -in @('F18','F19','F20')).Count){throw 'Stage six is already registered; use Build/Test.'}
$roots=@{AGOT_PLUS=$MainPath;AGOT=$AgotPath}
foreach($source in $baseline){
 if((Get-FileHash -LiteralPath (Join-Path $roots[$source.Catalog] $source.File)).Hash -cne $source.SHA256){throw "Changed baseline: $($source.File)"}
}
function Get-S6OriginalBlock([string]$Text,[string]$Key){
 $clean=[regex]::Replace($Text,'"(?:\\.|[^"\\])*"|#[^\r\n]*',{param($m) [regex]::Replace($m.Value,'[^\r\n]',' ')})
 $matches=[regex]::Matches($clean,'(?m)^'+[regex]::Escape($Key)+'\s*=\s*\{')
 if($matches.Count -ne 1){throw "Expected one definition: $Key"}
 $m=$matches[0];$depth=1
 for($i=$m.Index+$m.Length;$i -lt $clean.Length;$i++){
  if($clean[$i] -eq '{'){$depth++}elseif($clean[$i] -eq '}'){$depth--}
  if(-not $depth){return $Text.Substring($m.Index,$i+1-$m.Index)}
 }
 throw "Unclosed definition: $Key"
}
$effectFile='common/scripted_effects/asoiaf_scripted_effects_artifacts.txt'
$sourceText=[IO.File]::ReadAllText((Join-Path $MainPath $effectFile))
$newRules=[Collections.Generic.List[object]]::new()
foreach($entry in @(@('ice',2),@('heartsbane',2),@('longclaw',2),@('oathkeeper',6),@('widows_wail',6),@('dark_sister',3))){
 $newRules.Add([pscustomobject]@{
  Id=('artifact-template-'+$entry[0]);Group='F18';File=$effectFile
  Before=('template = vs_'+$entry[0]+'_template');After='template = valyrian_steel_template';ExpectedCount=$entry[1]
  Reason='Use the template used by the same sword in current AGOT. Keep every individual modifier, visual, history, flag, owner and claim unchanged.'
 })
}
foreach($name in @('robertI','renly','joffreyI')){
 $key='agot_create_artifact_'+$name+'_crown_effect'
 $before=Get-S6OriginalBlock $sourceText $key
 $owner='$OWNER$ = { save_scope_as = owner }'
 $after=$before.Replace($owner,($owner+"`r`n`t"+'$CREATOR$ = { save_scope_as = creator }'))
 $saved="`t`t`tsave_scope_as = newly_created_artifact"
 if([regex]::Matches($after,[regex]::Escape($saved)).Count -ne 2){throw 'Expected two aesthetic branches'}
 $after=$after.Replace($saved,($saved+"`r`n`t`t`tcreator = scope:creator"))
 $newRules.Add([pscustomobject]@{
  Id=('crown-creator-'+$name);Group='F19';File=$effectFile;Before=$before;After=$after;ExpectedCount=1
  Reason='Restore current AGOT OWNER/CREATOR signature and record the passed creator in both aesthetic branches; preserve all other crown behavior.'
 })
 $newRules.Add([pscustomobject]@{
  Id=('crown-inheritance-creator-'+$name);Group='F19';File='common/on_action/agot_on_actions/test_title_on_actions.txt'
  Before=($key+' = { OWNER = this }');After=($key+' = { OWNER = this CREATOR = this }');ExpectedCount=1
  Reason='The automatic title-inheritance grant has no smith. Explicitly credit the receiving monarch as creator instead of inheriting an unrelated saved creator; keep owner, trigger and delayed equip event unchanged.'
 })
}
$newRules.Add([pscustomobject]@{
 Id='oathkeeper-westerman-opinion';Group='F20';File='common/modifiers/asoiaf_artifact_modifiers.txt'
 Before='westerman_opinion = 20';After='westerman_main_opinion = 20';ExpectedCount=1
 Reason='Resolve the existing +20 opinion modifier against the current westerman_main culture. Preserve the definition and all other bonuses.'
})
$all=@($fixes)+$newRules.ToArray()
foreach($group in $all|Group-Object File){
 $original=[IO.File]::ReadAllText((Join-Path $MainPath $group.Name));$body=$original
 foreach($rule in $group.Group){
  if([regex]::Matches($original,[regex]::Escape($rule.Before)).Count -ne $rule.ExpectedCount -or [regex]::Matches($body,[regex]::Escape($rule.Before)).Count -ne $rule.ExpectedCount){throw "Unexpected replacement count: $($rule.Id)"}
  $body=$body.Replace($rule.Before,$rule.After)
 }
}
foreach($entry in @(
 @('AGOT_PLUS',$effectFile),
 @('AGOT_PLUS','common/modifiers/asoiaf_artifact_modifiers.txt'),
 @('AGOT','common/artifacts/templates/00_agot_historical_artifacts_equipment.txt'),
 @('AGOT','common/artifacts/templates/00_agot_historical_artifacts_crowns.txt'),
 @('AGOT','common/scripted_effects/00_agot_artifact_vs_sword_effects.txt'),
 @('AGOT','common/scripted_effects/00_agot_artifact_vs_sword_forgeable_effects.txt'),
 @('AGOT','common/scripted_effects/00_agot_artifact_crowns_effects.txt'),
 @('AGOT','common/modifiers/00_agot_artifact_modifiers.txt')
)){
 if(-not @($baseline|Where-Object {$_.Catalog -ceq $entry[0] -and $_.File -ceq $entry[1]}).Count){
  $baseline+=[pscustomobject]@{Catalog=$entry[0];File=$entry[1];SHA256=(Get-FileHash -LiteralPath (Join-Path $roots[$entry[0]] $entry[1])).Hash}
 }
}
$reportPath=Join-Path $modRoot '../../docs/reports/ck3-agot-plus-fix-stage4-log-2026-09-18/agot-plus-without-portraits.csv'
$targets=@(Import-Csv -LiteralPath $reportPath|Where-Object {$_.IssueClass -ceq 'Artifact_templates_and_arguments' -or $_.Message -match 'Unexpected token: westerman_opinion'})
if($targets.Count -ne 49){throw 'Expected 49 historical diagnostic targets'}
[IO.File]::WriteAllText($fixPath,($all|ConvertTo-Json -Depth 8)+"`n",$utf8)
[IO.File]::WriteAllText($basePath,($baseline|ConvertTo-Json -Depth 5)+"`n",$utf8)
[IO.File]::WriteAllText((Join-Path $modRoot 'docs/stage6-targeted-log-messages.csv'),(($targets|ConvertTo-Csv -NoTypeInformation)-join "`r`n")+"`r`n",$utf8)
Write-Output "Registered $($newRules.Count) rules / 28 replacements; $($baseline.Count) baseline hashes; 49 historical targets."
