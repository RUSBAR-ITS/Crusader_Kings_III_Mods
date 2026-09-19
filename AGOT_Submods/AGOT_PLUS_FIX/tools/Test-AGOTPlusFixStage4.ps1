# Limited condition model, fed from the actual packaged script blocks.
# It does not execute the game, relations, births or event scheduling.
$s4Setup=Read-Plus 'common/scripted_effects/asoiaf_setup_effects.txt'
$s4Children=Read-Plus 'common/scripted_effects/asoiaf_canon_children_effects.txt'
$s4Invader=Read-Plus 'common/scripted_character_templates/asoiaf_invader_templates.txt'
$s4Original=[IO.File]::ReadAllText((Join-Path $MainPath 'common/scripted_effects/asoiaf_setup_effects.txt'))
$s4Cases=0
function Get-S4OptionalBody($Text,$Key,$Contains='.'){
 $bodies=@(Get-AllBlocks ($Text.Replace($Key+' ?=', $Key+' =')) $Key|Where-Object {$_ -match $Contains})
 if($bodies.Count -ne 1){throw "Ambiguous character body: $Key / $Contains"}
 $bodies[0]
}
function Get-S4Branch($Text,$Effect){
 $branches=@(Get-AllBlocks $Text 'if'|Where-Object {$_ -match $Effect})
 # Keep the innermost branch containing the action, not an enclosing rule gate.
 $branch=$branches|Sort-Object Length|Select-Object -First 1
 if(-not $branch){throw "Missing stage-four action: $Effect"}
 $branch
}
function Test-S4Conditions($Nodes,$Context,$Current){
 foreach($n in $Nodes){
  $ok=$false
  switch -CaseSensitive ($n.Key){
   'NOT' {$ok=-not (Test-S4Conditions $n.Children $Context $Current)}
   'exists' {$ok=$Context.Exists -ccontains $n.Value}
   'current_date' {
    if($n.Operator -cne '>='){throw 'Unexpected date operator'}
    $ok=[version]$Context.Date -ge [version]$n.Value
   }
   'has_game_rule' {$ok=$Context.Rules -ccontains $n.Value}
   'is_married' {$ok=($Context.Spouses.Count -gt 0) -eq ($n.Value -ceq 'yes')}
   'any_spouse' {
    foreach($spouse in $Context.Spouses){if(Test-S4Conditions $n.Children $Context $spouse){$ok=$true;break}}
   }
   'house' {$ok=$Current.House -and $Current.House -ceq $Context.ReferenceHouse}
   'dynasty:dynn_Targaryen' {$ok=Test-S4Conditions $n.Children $Context $Current}
   'any_dynasty_member' {
    foreach($member in $Context.Members){
     if($member.Dynasty -ceq 'dynn_Targaryen' -and (Test-S4Conditions $n.Children $Context $member)){$ok=$true;break}
    }
   }
   'has_inactive_trait' {$ok=$Current.Traits -ccontains $n.Value}
   'is_alive' {$ok=$Current.Alive -eq ($n.Value -ceq 'yes')}
   'has_relation_nemesis' {$ok=$Context.Nemesis}
   'is_landed' {$ok=$Context.Landed -eq ($n.Value -ceq 'yes')}
   'scope:father.player_heir' {$ok=$Context.RhaenyraHeir}
   'has_claim_on' {$ok=$Context.Claims -ccontains $n.Value}
   default {throw "Unmodelled stage-four condition: $($n.Key)"}
  }
  if(-not $ok){return $false}
 }
 return $true
}
function Assert-S4Condition($Nodes,$Context,[bool]$Expected,$Label,$Current=$null){
 if((Test-S4Conditions $Nodes $Context $Current) -ne $Expected){throw "Incorrect stage-four condition: $Label"}
 $script:s4Cases++
}

# Title and death predicates retain their operands and Boolean structure.
if((Clear-ScriptText ($s4Setup+$s4Invader)) -match '\b(has_claim|is_dead)\s*='){throw 'Obsolete predicate remains'}
$claimTargets=@([regex]::Matches($s4Original,'\bhas_claim\s*=\s*(\S+)')|ForEach-Object {$_.Groups[1].Value})
$fixedTargets=@([regex]::Matches($s4Setup,'\bhas_claim_on\s*=\s*(\S+)')|ForEach-Object {$_.Groups[1].Value})
if($claimTargets.Count -ne 15 -or ($claimTargets -join '|') -cne ($fixedTargets -join '|')){throw 'Claim targets/order changed'}
$florent=Get-S4OptionalBody $s4Setup 'dynasty:dynn_Florent.dynast'
$florentNodes=@(ConvertTo-AgeNodes (Get-ScriptBlock (Get-ScriptBlock $florent 'if') 'limit'))
foreach($alive in @($false,$true)){foreach($reach in @($false,$true)){foreach($mander in @($false,$true)){
 $claims=@();if($reach){$claims+='title:e_the_reach'};if($mander){$claims+='title:k_the_mander'}
 Assert-S4Condition $florentNodes @{Claims=$claims} ($alive -and $reach -and $mander) 'Florent needs both claims and life' @{Alive=$alive}
}}}
$loras=Get-ScriptBlock $s4Children 'asoiaf_canon_children_Tyrell_13_birth_effect'
$lorasAfter=Get-ScriptBlock (Get-ScriptBlock $loras 'create_character') 'after_creation'
if($lorasAfter -notmatch '(?m)^\s*add_trait = beauty_good_3\s*$' -or $lorasAfter -match '(?m)^\s*trait = beauty_good_3'){throw 'Loras beauty is not an after_creation effect'}
$null=Get-ScriptBlock (Read-Agot 'common/traits/00_traits.txt') 'beauty_good_3'

# Optional historical characters and action-local guards.
$characterSetup=Get-ScriptBlock $s4Setup 'asoiaf_setup_characters_effect'
foreach($id in @('Lannister_1','Lannister_135')){
 if($characterSetup -notmatch ('character:'+ $id +'\s*\?=\s*\{')){throw "Unguarded character: $id"}
}
if($characterSetup -match '(?m)^\texists\s*='){throw 'A top-level exists is still used as an effect'}
$rhaegar=Get-S4OptionalBody $characterSetup 'character:Targaryen_3' 'set_relation_soulmate'
$rhaegarNodes=@(ConvertTo-AgeNodes $rhaegar)
if(@($rhaegarNodes|Where-Object {$_.Key -ceq 'add_martial_skill' -and $_.Value -ceq '5'}).Count -ne 1){throw 'Rhaegar skill gain became dependent on Lyanna'}
$stannis=Get-S4OptionalBody $characterSetup 'character:Baratheon_3' 'add_pressed_claim'
$stannisClaim=Get-S4Branch $stannis '\badd_pressed_claim = title:h_the_iron_throne\b'
if((Get-ScriptBlock $stannisClaim 'limit').Trim() -cne 'current_date >= 8283.6.1'){throw 'Stannis claim gained an unrelated existence condition'}
foreach($spec in @(
 @($rhaegar,'set_relation_soulmate = character:Stark_5','character:Stark_5','8282.6.14','8282.6.15'),
 @($stannis,'set_relation_friend = character:Seaworth_1','character:Seaworth_1','8282.12.31','8283.1.1'),
 @($stannis,'set_relation_lover = character:Melisandre_1','character:Melisandre_1','8299.12.31','8300.1.1')
)){
 $nodes=@(ConvertTo-AgeNodes (Get-ScriptBlock (Get-S4Branch $spec[0] $spec[1]) 'limit'))
 foreach($exists in @($false,$true)){foreach($after in @($false,$true)){
  $known=@();if($exists){$known+= $spec[2]}
  $date=if($after){$spec[4]}else{$spec[3]}
  Assert-S4Condition $nodes @{Exists=$known;Date=$date} ($exists -and $after) $spec[1]
 }}
}
$margaery=Get-S4OptionalBody $characterSetup 'character:Tyrell_14'
$friendLimits=@{}
foreach($id in @('Redwyne_2','Tyrell_13')){
 $friendLimits[$id]=@(ConvertTo-AgeNodes (Get-ScriptBlock (Get-S4Branch $margaery ('set_relation_friend = character:'+$id)) 'limit'))
}
foreach($olenna in @($false,$true)){foreach($lorasExists in @($false,$true)){
 $known=@();if($olenna){$known+='character:Redwyne_2'};if($lorasExists){$known+='character:Tyrell_13'}
 Assert-S4Condition $friendLimits.Redwyne_2 @{Exists=$known} $olenna 'Olenna independent of Loras'
 Assert-S4Condition $friendLimits.Tyrell_13 @{Exists=$known} $lorasExists 'Loras independent of Olenna'
}}
foreach($spec in @(
 @($characterSetup,'set_real_father = character:Strong_30','character:Strong_30'),
 @($characterSetup,'set_relation_best_friend = character:Baratheon_4','character:Baratheon_4'),
 @((Get-ScriptBlock $s4Setup 'asoiaf_new_dnas_effect'),'set_mother = character:Saan_asoiaf_2_mother','character:Saan_asoiaf_2_mother')
)){
 $nodes=@(ConvertTo-AgeNodes (Get-ScriptBlock (Get-S4Branch $spec[0] $spec[1]) 'limit'))
 foreach($exists in @($false,$true)){
  $known=@();if($exists){$known+=$spec[2]}
  Assert-S4Condition $nodes @{Exists=$known} $exists $spec[1]
 }
}
$salladhor=Get-S4OptionalBody (Get-ScriptBlock $s4Setup 'asoiaf_new_dnas_effect') 'character:Saan_2'
$salladhorNodes=@(ConvertTo-AgeNodes $salladhor)
if(@($salladhorNodes|Where-Object {$_.Key -ceq 'copy_inheritable_appearance_from' -and $_.Value -ceq 'character:Saan_asoiaf_2'}).Count -ne 1){throw 'Salladhor appearance depends on mother'}
$motherBranch=Get-S4Branch $salladhor 'set_mother = character:Saan_asoiaf_2_mother'
foreach($trait in @('wild_oat','fornicator','adulterer')){if($motherBranch -notmatch ('add_trait\s*=\s*'+$trait+'\b')){throw 'Parentage traits escaped mother guard'}}

# All six dead-child lookups are existential. Valid effect iterators stay effects.
$deathLookups=@(Get-AllBlocks $s4Children 'any_dynasty_member'|Where-Object {$_ -match 'has_inactive_trait = asoiaf_Targaryen_(65|67)_trait' -and $_ -match 'is_alive = no'})
if($deathLookups.Count -ne 6){throw 'Expected six dead canonical child lookups'}
foreach($childId in @('67','68')){
 $birth=Get-ScriptBlock $s4Children ('asoiaf_canon_children_Targaryen_'+$childId+'_birth_effect')
 $hiddenBlocks=@(Get-AllBlocks $birth 'hidden_effect'|Where-Object {$_ -match 'id = asoiaf_maintenance_events\.0012'})
 if($hiddenBlocks.Count -ne 1){throw 'Ambiguous post-birth rivalry block'}
 $hidden=$hiddenBlocks[0]
 foreach($parent in @('mother','father')){
  $effect=if($parent -ceq 'mother'){'id = asoiaf_maintenance_events\.0012'}else{'clear_designated_heir = yes'}
  $parentBody=Get-S4OptionalBody $hidden ('scope:'+$parent) $effect
  $branch=Get-S4Branch $parentBody $effect
  $limit=Get-ScriptBlock $branch 'limit'
  if($limit -match 'every_dynasty_member|\blimit\s*='){throw 'Effect syntax remains inside death conditions'}
  $nodes=@(ConvertTo-AgeNodes $limit)
  foreach($aegon in @('absent','alive','dead')){foreach($aemond in @('absent','alive','dead')){foreach($blocked in @($false,$true)){
   $members=@()
   foreach($spec in @(@('65',$aegon),@('67',$aemond))){
    if($spec[1] -cne 'absent'){$members+=@{Dynasty='dynn_Targaryen';Traits=@('asoiaf_Targaryen_'+$spec[0]+'_trait');Alive=($spec[1] -ceq 'alive')}}
   }
   # Wrong dynasties and other dead Targaryens must not satisfy identity checks.
   $members+=@{Dynasty='dynn_Other';Traits=@('asoiaf_Targaryen_65_trait','asoiaf_Targaryen_67_trait');Alive=$false}
   $members+=@{Dynasty='dynn_Targaryen';Traits=@('unrelated_trait');Alive=$false}
   $ctx=@{Members=$members;Nemesis=$blocked;Landed=(-not $blocked);RhaenyraHeir=$true;Exists=@('character:Targaryen_63')}
   $expected=$aegon -ceq 'dead' -and ($childId -ceq '67' -or $aemond -ceq 'dead') -and -not $blocked
   Assert-S4Condition $nodes $ctx $expected "$childId/$parent/$aegon/$aemond/$blocked"
  }}}
  if($parent -ceq 'mother' -and $branch -notmatch 'days = 730'){throw 'Rivalry delay changed'}
  if($parent -ceq 'father' -and $branch -notmatch 'id = agot_scenario_trp\.1036 days = 1'){throw 'Heir event/delay changed'}
 }
}

# Same-house spouse prevents suppression; single/widowed and unresolved reference
# do not count as an incompatible marriage. Cadet houses remain distinct.
$joffrey=Get-ScriptBlock $s4Children 'asoiaf_canon_children_Targaryen_77_birth_effect'
$hiddenBlocks=@(Get-AllBlocks $joffrey 'hidden_effect'|Where-Object {$_ -match '\bany_spouse\s*='})
if($hiddenBlocks.Count -ne 1){throw 'Ambiguous spouse-dependent pregnancy block'}
$mother=Get-ScriptBlock $hiddenBlocks[0] 'scope:mother'
$pregnancy=Get-S4Branch $mother 'add_character_modifier = asoiaf_canon_children_pregnancy_negation_modifier'
$nodes=@(ConvertTo-AgeNodes (Get-ScriptBlock $pregnancy 'limit'))
foreach($rule in @($false,$true)){foreach($reference in @($false,$true)){foreach($scenario in @('none','same','other','mixed','cadet','lowborn')){
 $spouses=switch($scenario){
  'none' {@()};'same' {@{House='Targaryen'}};'other' {@{House='Velaryon'}}
  'mixed' {@{House='Velaryon'};@{House='Targaryen'}};'cadet' {@{House='Cadet'}};'lowborn' {@{House=$null}}
 }
 $known=@();if($reference){$known+='character:Targaryen_13.house'}
 $rulesOn=@();if($rule){$rulesOn+='asoiaf_canon_children_pregnancy_negation_rule_on'}
 $ctx=@{Exists=$known;Rules=$rulesOn;Spouses=@($spouses);ReferenceHouse='Targaryen'}
 Assert-S4Condition $nodes $ctx ($rule -and $reference -and $scenario -in @('other','cadet','lowborn')) "pregnancy/$rule/$reference/$scenario"
}}}
if($s4Children -match '\bany_spouse\.house\b'){throw 'Invalid spouse scope remains'}
$diagnostics=@(Import-Csv (Join-Path $modRoot 'docs/stage4-targeted-log-messages.csv'))
if($diagnostics.Count -ne 33){throw 'Stage-four baseline must contain 33 engine messages'}
Write-Output "PASS: $s4Cases stage-four condition cases; relation-target guards, unchanged independent actions, both Florent claims, dead-child identities and spouse-house edge cases."
Write-Output 'PASS: 33 diagnostic targets; optional character scopes; Loras after_creation trait; original event IDs/delays.'
