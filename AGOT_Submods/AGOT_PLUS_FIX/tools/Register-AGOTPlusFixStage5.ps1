# Register reviewed replacements against the upstream source, then use Build/Test.
param([string]$MainPath='E:\SteamLibrary\steamapps\workshop\content\1158310\2950245430',
      [string]$AgotPath='E:\SteamLibrary\steamapps\workshop\content\1158310\2962333032')
$ErrorActionPreference='Stop'
$modRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$reportRoot=[IO.Path]::GetFullPath((Join-Path $modRoot '../../docs/reports/agot-plus-dragon-bonding-analysis-2026-09-18'))
$utf8=[Text.UTF8Encoding]::new($false,$true)
$fixPath=Join-Path $modRoot 'docs/fixes.json'
$fixes=Get-Content -LiteralPath $fixPath -Raw -Encoding UTF8|ConvertFrom-Json
if(@($fixes|Where-Object Group -eq 'F17').Count){throw 'Stage five is already registered; run Build and Test instead.'}
function Mask-Source($Text){[regex]::Replace($Text,'"(?:\\.|[^"\\])*"|#[^\r\n]*',{param($m) [regex]::Replace($m.Value,'[^\r\n]',' ')})}
function Find-Blocks($Text,$Key){
 $clean=Mask-Source $Text
 foreach($m in [regex]::Matches($clean,'(?<!\S)'+[regex]::Escape($Key)+'\s*(?:\?=|=)\s*\{')){
  $start=$m.Index+$m.Length;$depth=1
  for($i=$start;$i -lt $clean.Length;$i++){
   if($clean[$i] -eq '{'){$depth++}elseif($clean[$i] -eq '}'){$depth--}
   if(-not $depth){break}
  }
  if($depth){throw "Unclosed source block: $Key"}
  [pscustomobject]@{Index=$m.Index;End=$i;Text=$Text.Substring($m.Index,$i+1-$m.Index)}
 }
}
function Indent-Fragment($Text,$Indent){
 ($Text.Trim() -split '\r?\n') -join ("`r`n"+$Indent)
}
$pending=[Collections.Generic.List[object]]::new()
foreach($relative in @('common/scripted_effects/asoiaf_canon_children_effects.txt','common/on_action/asoiaf_yearly_on_actions.txt')){
 $text=[IO.File]::ReadAllText((Join-Path $MainPath $relative))
 $ifs=@(Find-Blocks $text 'if')
 foreach($scheme in Find-Blocks $text 'start_scheme'){
  if($scheme.Text -notmatch 'type\s*=\s*bond_with_dragon_scheme\b'){continue}
  $branch=$ifs|Where-Object {$_.Index -lt $scheme.Index -and $_.End -gt $scheme.End}|Sort-Object Index -Descending|Select-Object -First 1
  $dragon=[regex]::Match($scheme.Text,'target\s*=\s*(character:\w+)').Groups[1].Value
  if(-not $branch -or -not $dragon){throw 'Unrecognized bond branch'}
  $indent=[regex]::Match($text.Substring(0,$branch.Index),'[\t ]+\z').Value
  if($relative -like '*canon_children_effects.txt'){
   # This fragment remains under the original game-rule if and after_creation.
   $after=@'
if = {
	limit = {
		exists = __DRAGON__
		exists = scope:child
	}
	if = {
		limit = {
			is_alive = yes
			this = scope:child
			agot_has_relationship_dragon = no
			__DRAGON__ = {
				is_alive = yes
				has_trait = dragon
				agot_has_relationship_dragon = no
			}
		}
		agot_bond_dragon_relation_effect = {
			ACTOR = scope:child
			DRAGON = __DRAGON__
		}
		send_interface_toast = {
			title = bond_dragon_notification
			left_icon = scope:child
			right_icon = __DRAGON__
		}
	}
}
'@
   $after=$after.Replace('__DRAGON__',$dragon)
   $id='dragon-bond-birth-'+$dragon.Substring(10)
   $reason='Preserve the direct newborn bond; guard both references and the living free pair before calling AGOT. Remove the contradictory scheme; retain the newborn toast and rule gate.'
  }else{
   $name=[regex]::Match($branch.Text,'save_scope_as\s*=\s*(\w+)').Groups[1].Value
   $trait=[regex]::Match($branch.Text,'has_inactive_trait\s*=\s*(\w+)').Groups[1].Value
   $dynasty=[regex]::Match($branch.Text,'dynasty:(\w+)').Groups[1].Value
   if(-not $name -or -not $trait -or -not $dynasty){throw 'Unrecognized yearly candidate'}
   $after=@'
clear_saved_scope = __NAME__
if = { # __TRAIT__ -> __DRAGON__; preserve the original branch order.
	limit = { exists = __DRAGON__ }
	if = {
		limit = {
			__DRAGON__ = {
				is_alive = yes
				has_trait = dragon
				agot_has_relationship_dragon = no
			}
		}
		dynasty:__DYNASTY__ = {
			every_dynasty_member = {
				limit = {
					has_inactive_trait = __TRAIT__
					is_alive = yes
					agot_has_relationship_dragon = no
					NOT = { has_trait = nightswatch }
				}
				save_scope_as = __NAME__
			}
		}
		if = {
			limit = { exists = scope:__NAME__ }
			scope:__NAME__ = {
				agot_bond_dragon_relation_effect = {
					ACTOR = scope:__NAME__
					DRAGON = __DRAGON__
				}
				send_interface_toast = {
					title = bond_dragon_notification
					left_icon = scope:__NAME__
					right_icon = __DRAGON__
				}
			}
		}
	}
}
clear_saved_scope = __NAME__
'@
   $after=$after.Replace('__NAME__',$name).Replace('__TRAIT__',$trait).Replace('__DYNASTY__',$dynasty).Replace('__DRAGON__',$dragon)
   $id='dragon-bond-yearly-'+$name
   $reason='Choose once with matching living/free/not-Nights-Watch conditions; clear stale candidates before and after; notify the selected actor. Preserve the pair, dynasty, last eligible member selection and branch priority.'
  }
  $pending.Add([pscustomobject]@{Id=$id;Group='F17';File=$relative;Before=$branch.Text;After=(Indent-Fragment $after $indent);ExpectedCount=1;Reason=$reason})
 }
}
if($pending.Count -ne 34){throw "Expected 34 source sites, got $($pending.Count)"}
# Identical newborn fragments can occur for successive riders of the same dragon.
$newRules=@(foreach($g in $pending|Group-Object Before){
 $rule=$g.Group[0]
 if(@($g.Group|Where-Object {$_.After -cne $rule.After -or $_.File -cne $rule.File}).Count){throw 'Ambiguous grouped replacement'}
 $rule.ExpectedCount=$g.Count
 $rule
})
$old="`t`t`t`thas_inactive_trait = asoiaf_Targaryen_33_trait #Aegon Targaryen (son of Aenys)"
$newRules+=[pscustomobject]@{Id='dragon-bond-aerea-pulse';Group='F17';File='common/on_action/asoiaf_yearly_on_actions.txt';Before=$old;After=($old+"`r`n`t`t`t`thas_inactive_trait = asoiaf_Targaryen_41_trait #Aerea Targaryen (daughter of Aegon)");ExpectedCount=1;Reason='Allow Aerea to trigger the existing yearly retry even when no other canonical candidate is alive.'}
$all=@($fixes)+@($newRules)
# Match both raw upstream and sequentially patched text, as the builder requires.
foreach($g in $all|Group-Object File){
 $original=[IO.File]::ReadAllText((Join-Path $MainPath $g.Name));$body=$original
 foreach($fix in $g.Group){
  if([regex]::Matches($original,[regex]::Escape($fix.Before)).Count -ne $fix.ExpectedCount -or [regex]::Matches($body,[regex]::Escape($fix.Before)).Count -ne $fix.ExpectedCount){throw "Unexpected replacement count: $($fix.Id)"}
  $body=$body.Replace($fix.Before,$fix.After)
 }
}
[IO.File]::WriteAllText($fixPath,($all|ConvertTo-Json -Depth 8)+"`n",$utf8)
# Pin the base relation helpers, plus the active override in the stage-five test.
$basePath=Join-Path $modRoot 'docs/source-baseline.json'
$baseline=Get-Content -LiteralPath $basePath -Raw -Encoding UTF8|ConvertFrom-Json
foreach($file in @('common/scripted_effects/00_agot_dragon_effects.txt','common/scripted_triggers/00_agot_dragon_triggers.txt')){
 if(-not @($baseline|Where-Object {$_.Catalog -eq 'AGOT' -and $_.File -eq $file}).Count){
  $baseline+=[pscustomobject]@{Catalog='AGOT';File=$file;SHA256=(Get-FileHash -LiteralPath (Join-Path $AgotPath $file)).Hash}
 }
}
[IO.File]::WriteAllText($basePath,($baseline|ConvertTo-Json -Depth 5)+"`n",$utf8)
[IO.File]::WriteAllText((Join-Path $modRoot 'docs/stage5-targeted-log-messages.csv'),[IO.File]::ReadAllText((Join-Path $reportRoot 'targeted-log-messages.csv')),$utf8)
[IO.File]::WriteAllText((Join-Path $modRoot 'docs/stage5-bond-sites.csv'),[IO.File]::ReadAllText((Join-Path $reportRoot 'scheme-sites.csv')),$utf8)
Write-Output "Registered $($newRules.Count) stage-five rules / 35 replacements; total $($all.Count) rules / 753 replacements."
