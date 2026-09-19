# Loaded by Test-AGOTPlusFix.ps1. Interpret the actual bonding control flow only.
# Native AGOT bonding is a checked call boundary, NOT an emulation of CK3.
$s5Sites=@(Import-Csv -LiteralPath (Join-Path $modRoot 'docs/stage5-bond-sites.csv'))
$s5BirthSites=@($s5Sites|Where-Object Kind -eq 'Birth')
$s5YearSites=@($s5Sites|Where-Object Kind -eq 'Yearly retry')
if($s5BirthSites.Count -ne 24 -or $s5YearSites.Count -ne 10){throw 'Bonding audit inventory changed'}
$s5BirthText=Read-Plus 'common/scripted_effects/asoiaf_canon_children_effects.txt'
$s5YearText=Read-Plus 'common/on_action/asoiaf_yearly_on_actions.txt'
foreach($s5Text in @($s5BirthText,$s5YearText)){
 if((Clear-ScriptText $s5Text) -match '\bstart_scheme\s*='){throw 'A scheme launch remains in the canonical birth/yearly files'}
}
$s5Year=Get-ScriptBlock $s5YearText 'asoiaf_canon_children_dragon_bonding_maintenance'
$s5Trigger=@(ConvertTo-AgeNodes (Get-ScriptBlock $s5Year 'trigger'))
$s5Effects=@(ConvertTo-AgeNodes (Get-ScriptBlock $s5Year 'effect'))
$s5EnabledText=[IO.File]::ReadAllText((Join-Path $MainPath 'common/scripted_triggers/asoiaf_canon_children_triggers.txt'))
$s5Enabled=@(ConvertTo-AgeNodes (Get-ScriptBlock $s5EnabledText 'asoiaf_canon_children_enabled_trigger'))
if((Get-ScriptBlock $s5YearText 'random_yearly_everyone_pulse') -notmatch '\basoiaf_canon_children_dragon_bonding_maintenance\b'){throw 'Yearly bonding is disconnected from its pulse'}

function Find-S5Nodes($Nodes,[string]$Key){
 foreach($n in $Nodes){if($n.Key -ceq $Key){$n};if($n.Children.Count){Find-S5Nodes $n.Children $Key}}
}
function New-S5Character([string]$Id,[string]$Marker=''){
 [pscustomobject]@{Id=$Id;Alive=$true;Bound=$false;Dragon=$false;Watch=$false;Marker=$Marker;Pair=$null}
}
function New-S5State {
 @{
  Characters=@{};Scopes=@{};Root=$null
  Dynasties=@{
   'dynasty:dynn_Targaryen'=[pscustomobject]@{Members=@()}
   'dynasty:dynn_Velaryon'=[pscustomobject]@{Members=@()}
  }
  Rules=@('agot_canon_children_disabled','asoiaf_canon_children_rule_on_traits','asoiaf_canon_children_dragon_bonding_rule_on')
  Bonds=[Collections.Generic.List[object]]::new();Toasts=[Collections.Generic.List[object]]::new()
 }
}
function Resolve-S5Scope([string]$Reference,$Current,$State){
 if($Reference -ceq 'this'){return $Current}
 if($Reference -ceq 'root'){return $State.Root}
 if($Reference.StartsWith('scope:')){return $State.Scopes[$Reference.Substring(6)]}
 if($Reference.StartsWith('character:')){return $State.Characters[$Reference]}
 if($Reference.StartsWith('dynasty:')){return $State.Dynasties[$Reference]}
 throw "Unknown bonding scope: $Reference"
}
function Test-S5Conditions($Nodes,$Current,$State){
 foreach($n in $Nodes){
  if($n.Operator -cne '='){throw "Unexpected bonding condition operator: $($n.Operator)"}
  $ok=switch -CaseSensitive ($n.Key){
   'exists' {$null -ne (Resolve-S5Scope $n.Value $Current $State)}
   'is_alive' {$Current.Alive -eq ($n.Value -ceq 'yes')}
   'agot_has_relationship_dragon' {$Current.Bound -eq ($n.Value -ceq 'yes')}
   'has_inactive_trait' {$Current.Marker -ceq $n.Value}
   'has_trait' {
    switch -CaseSensitive ($n.Value){'dragon' {$Current.Dragon};'nightswatch' {$Current.Watch};default {throw 'Unknown bonding trait'}}
   }
   'this' {[object]::ReferenceEquals($Current,(Resolve-S5Scope $n.Value $Current $State))}
   'has_game_rule' {$State.Rules -ccontains $n.Value}
   'asoiaf_canon_children_enabled_trigger' {
    if($n.Value -cne 'yes'){throw 'Unexpected enabled-trigger use'}
    Test-S5Conditions $s5Enabled $Current $State
   }
   'AND' {Test-S5Conditions $n.Children $Current $State}
   'NOT' {-not (Test-S5Conditions $n.Children $Current $State)}
   'OR' {
    $any=$false
    foreach($child in $n.Children){if(Test-S5Conditions @($child) $Current $State){$any=$true;break}}
    $any
   }
   default {
    $target=Resolve-S5Scope $n.Key $Current $State
    if($null -eq $target){throw "Unguarded scope in bonding conditions: $($n.Key)"}
    Test-S5Conditions $n.Children $target $State
   }
  }
  if(-not $ok){return $false}
 }
 return $true
}
function Invoke-S5Nodes($Nodes,$Current,$State){
 foreach($n in $Nodes){
  if($n.Operator -cne '='){throw "Unexpected bonding effect operator: $($n.Operator)"}
  switch -CaseSensitive ($n.Key){
   'if' {
    $limits=@($n.Children|Where-Object Key -ceq 'limit')
    if($limits.Count -ne 1){throw 'Bond branch must have exactly one limit'}
    if(Test-S5Conditions $limits[0].Children $Current $State){Invoke-S5Nodes @($n.Children|Where-Object Key -cne 'limit') $Current $State}
   }
   'every_dynasty_member' {
    $limits=@($n.Children|Where-Object Key -ceq 'limit')
    if($limits.Count -ne 1){throw 'Candidate selection must have one limit'}
    foreach($member in $Current.Members){
     if(Test-S5Conditions $limits[0].Children $member $State){Invoke-S5Nodes @($n.Children|Where-Object Key -cne 'limit') $member $State}
    }
   }
   'clear_saved_scope' {$State.Scopes.Remove($n.Value)}
   'save_scope_as' {$State.Scopes[$n.Value]=$Current}
   'agot_bond_dragon_relation_effect' {
    if(($n.Children.Key -join '|') -cne 'ACTOR|DRAGON'){throw 'Native bond parameters changed'}
    $actor=Resolve-S5Scope $n.Children[0].Value $Current $State
    $dragon=Resolve-S5Scope $n.Children[1].Value $Current $State
    if($null -eq $actor -or $null -eq $dragon -or -not $actor.Alive -or -not $dragon.Alive -or -not $dragon.Dragon -or $actor.Bound -or $dragon.Bound){throw 'Unsafe call to the native bonding effect'}
    if(-not [object]::ReferenceEquals($actor,$Current)){throw 'Native bond called outside the selected actor scope'}
    $State.Bonds.Add([pscustomobject]@{Actor=$actor.Id;Dragon=$dragon.Id})
    # Only the relation's existence is modeled, so a repeated call can be tested.
    $actor.Bound=$true;$dragon.Bound=$true;$actor.Pair=$dragon.Id;$dragon.Pair=$actor.Id
   }
   'send_interface_toast' {
    if(($n.Children.Key -join '|') -cne 'title|left_icon|right_icon' -or $n.Children[0].Value -cne 'bond_dragon_notification'){throw 'Unexpected bonding toast payload'}
    $actor=Resolve-S5Scope $n.Children[1].Value $Current $State
    $dragon=Resolve-S5Scope $n.Children[2].Value $Current $State
    if(-not [object]::ReferenceEquals($Current,$actor) -or $null -eq $actor -or $actor.Pair -cne $dragon.Id -or $State.Bonds.Count -eq 0){throw 'Toast has the wrong recipient or precedes a successful bond'}
    $State.Toasts.Add([pscustomobject]@{Actor=$actor.Id;Dragon=$dragon.Id})
   }
   default {
    $target=Resolve-S5Scope $n.Key $Current $State
    if($null -eq $target){throw "Unguarded scope in bonding effects: $($n.Key)"}
    Invoke-S5Nodes $n.Children $target $State
   }
  }
 }
}
function Invoke-S5Year($State){
 if(Test-S5Conditions $s5Trigger $State.Root $State){Invoke-S5Nodes $s5Effects $State.Root $State}
}
function Assert-S5Result($State,[int]$Count,[string]$Actor='',[string]$Dragon=''){
 if($State.Bonds.Count -ne $Count -or $State.Toasts.Count -ne $Count){throw "Unexpected bond/toast count: expected $Count, got $($State.Bonds.Count)/$($State.Toasts.Count)"}
 if($Count -eq 1 -and ($State.Bonds[0].Actor -cne $Actor -or $State.Bonds[0].Dragon -cne $Dragon)){throw 'Bond paired the wrong actor or dragon'}
 foreach($site in $s5YearSites){if($State.Scopes.ContainsKey($site.Actor.Substring(6))){throw 'Yearly candidate scope leaked'}}
}
function Add-S5Dragon($State,[string]$Id,[string]$Status){
 if($Status -ceq 'missing'){return}
 $d=New-S5Character $Id;$d.Dragon=$true
 if($Status -ceq 'dead'){$d.Alive=$false}
 if($Status -ceq 'bound'){$d.Bound=$true}
 if($Status -ceq 'not-dragon'){$d.Dragon=$false}
 $State.Characters[$Id]=$d
}
function Get-S5Dynasty($Site){
 if($Site.IdentityTrait.StartsWith('asoiaf_Velaryon_')){'dynasty:dynn_Velaryon'}else{'dynasty:dynn_Targaryen'}
}
$s5BirthCases=0;$s5YearCases=0;$s5ExtraCases=0;$s5BirthBlocks=@{}
foreach($s5Site in $s5BirthSites){
 $birth=Get-ScriptBlock $s5BirthText $s5Site.Function
 $creation=Get-ScriptBlock $birth 'create_character'
 if($creation -notmatch '(?m)^\s*age\s*=\s*0\s*$' -or $creation -notmatch ('\b'+$s5Site.IdentityTrait+'\b')){throw 'Newborn age/identity changed'}
 $after=@(ConvertTo-AgeNodes (Get-ScriptBlock $creation 'after_creation'))
 $gates=@($after|Where-Object {$_.Key -ceq 'if' -and @($_.Children|Where-Object {$_.Key -ceq 'limit' -and @($_.Children|Where-Object {$_.Key -ceq 'has_game_rule' -and $_.Value -ceq 'asoiaf_canon_children_dragon_bonding_rule_on'}).Count}).Count})
 if($gates.Count -ne 1 -or (Find-S5Nodes $gates 'agot_bond_dragon_relation_effect').Children[1].Value -cne $s5Site.Dragon){throw 'Birth bonding gate/pair changed'}
 $s5BirthBlocks[$s5Site.Function]=$gates
 foreach($enabled in @($true,$false)){
  foreach($dragonStatus in @('free','missing','dead','bound','not-dragon')){
   foreach($actorStatus in @('free','dead','bound')){
    foreach($scopeStatus in @('valid','missing','stale')){
     $state=New-S5State;$child=New-S5Character 'newborn' $s5Site.IdentityTrait;$state.Root=New-S5Character 'parent'
     if(-not $enabled){$state.Rules=@()}
     if($actorStatus -ceq 'dead'){$child.Alive=$false}
     if($actorStatus -ceq 'bound'){$child.Bound=$true}
     if($scopeStatus -ceq 'valid'){$state.Scopes.child=$child}
     if($scopeStatus -ceq 'stale'){$state.Scopes.child=New-S5Character 'previous-child'}
     Add-S5Dragon $state $s5Site.Dragon $dragonStatus
     $expected=[int]($enabled -and $dragonStatus -ceq 'free' -and $actorStatus -ceq 'free' -and $scopeStatus -ceq 'valid')
     Invoke-S5Nodes $gates $child $state
     Assert-S5Result $state $expected 'newborn' $s5Site.Dragon
     Invoke-S5Nodes $gates $child $state
     Assert-S5Result $state $expected 'newborn' $s5Site.Dragon
     $s5BirthCases++
    }
   }
  }
 }
}
# The full yearly body is interpreted in order, including all ten clear/select/bond blocks.
$s5YearCalls=@(Find-S5Nodes $s5Effects 'agot_bond_dragon_relation_effect')
if($s5YearCalls.Count -ne 10){throw 'Yearly bond call inventory changed'}
for($s5i=0;$s5i -lt 10;$s5i++){
 if($s5YearCalls[$s5i].Children[0].Value -cne $s5YearSites[$s5i].Actor -or $s5YearCalls[$s5i].Children[1].Value -cne $s5YearSites[$s5i].Dragon){throw 'Yearly pair priority changed from the audited upstream source'}
}
foreach($s5Site in $s5YearSites){
 foreach($enabled in @($true,$false)){
  foreach($dragonStatus in @('free','missing','dead','bound','not-dragon')){
   foreach($actorStatus in @('free','dead','bound','watch','wrong-trait','wrong-dynasty','missing')){
    $state=New-S5State;$state.Root=New-S5Character 'pulse-root' $s5Site.IdentityTrait
    $candidate=New-S5Character 'candidate' $s5Site.IdentityTrait
    if(-not $enabled){$state.Rules=@()}
    if($actorStatus -ceq 'dead'){$candidate.Alive=$false}
    if($actorStatus -ceq 'bound'){$candidate.Bound=$true}
    if($actorStatus -ceq 'watch'){$candidate.Watch=$true}
    if($actorStatus -ceq 'wrong-trait'){$candidate.Marker='other'}
    if($actorStatus -cnotin @('missing','wrong-dynasty')){$state.Dynasties[(Get-S5Dynasty $s5Site)].Members=@($candidate)}
    if($actorStatus -ceq 'wrong-dynasty'){
     $wrong=if((Get-S5Dynasty $s5Site) -ceq 'dynasty:dynn_Targaryen'){'dynasty:dynn_Velaryon'}else{'dynasty:dynn_Targaryen'}
     $state.Dynasties[$wrong].Members=@($candidate)
    }
    # Seed every candidate scope with an eligible-looking but unrelated object.
    # When disabled, the whole on_action does nothing, including no scope cleanup.
    if($enabled){foreach($site in $s5YearSites){$state.Scopes[$site.Actor.Substring(6)]=New-S5Character 'stale-candidate'}}
    Add-S5Dragon $state $s5Site.Dragon $dragonStatus
    $expected=[int]($enabled -and $dragonStatus -ceq 'free' -and $actorStatus -ceq 'free')
    Invoke-S5Year $state
    Assert-S5Result $state $expected 'candidate' $s5Site.Dragon
    Invoke-S5Year $state
    Assert-S5Result $state $expected 'candidate' $s5Site.Dragon
    $s5YearCases++
   }
  }
 }
 # An ineligible member after a valid one must not overwrite the selection.
 $state=New-S5State;$state.Root=New-S5Character 'pulse-root' $s5Site.IdentityTrait
 $members=@(New-S5Character 'eligible-first' $s5Site.IdentityTrait;New-S5Character 'eligible-last' $s5Site.IdentityTrait)
 foreach($status in @('dead','watch','bound','wrong-trait')){
  $c=New-S5Character $status $s5Site.IdentityTrait
  switch($status){'dead' {$c.Alive=$false};'watch' {$c.Watch=$true};'bound' {$c.Bound=$true};'wrong-trait' {$c.Marker='other'}}
  $members+=,$c
 }
 $state.Dynasties[(Get-S5Dynasty $s5Site)].Members=$members
 Add-S5Dragon $state $s5Site.Dragon 'free'
 Invoke-S5Year $state
 Assert-S5Result $state 1 'eligible-last' $s5Site.Dragon
 $s5ExtraCases++
 # Missing on the first pulse, the canonical dragon becomes available later.
 $state=New-S5State;$state.Root=New-S5Character 'pulse-root' $s5Site.IdentityTrait
 $state.Dynasties[(Get-S5Dynasty $s5Site)].Members=@(New-S5Character 'candidate' $s5Site.IdentityTrait)
 Invoke-S5Year $state;Assert-S5Result $state 0
 Add-S5Dragon $state $s5Site.Dragon 'free'
 Invoke-S5Year $state;Assert-S5Result $state 1 'candidate' $s5Site.Dragon
 $s5ExtraCases++
}
# Distinct children rules, and Aerea as the only identity capable of firing the pulse.
foreach($plusRule in @('asoiaf_canon_children_rule_on_traits','asoiaf_canon_children_rule_on','disabled')){
 foreach($baseDisabled in @($true,$false)){
  foreach($auto in @($true,$false)){
   $state=New-S5State;$aerea=New-S5Character 'aerea' 'asoiaf_Targaryen_41_trait';$state.Root=$aerea
   $state.Dynasties['dynasty:dynn_Targaryen'].Members=@($aerea);$state.Rules=@($plusRule)
   if($baseDisabled){$state.Rules+='agot_canon_children_disabled'}
   if($auto){$state.Rules+='asoiaf_canon_children_dragon_bonding_rule_on'}
   Add-S5Dragon $state 'character:dragon_balerion' 'free'
   Invoke-S5Year $state
   Assert-S5Result $state ([int]($plusRule -cne 'disabled' -and $baseDisabled -and $auto)) 'aerea' 'character:dragon_balerion'
   $s5ExtraCases++
  }
 }
}
# Shared-dragon competition: preserve branch priority, then allow later claimants
# only after the previous relation has gone. The model does not simulate death cleanup.
$state=New-S5State;$state.Root=New-S5Character 'pulse-root' 'asoiaf_Targaryen_41_trait'
foreach($site in $s5YearSites){
 $candidate=New-S5Character $site.Actor $site.IdentityTrait
 $state.Dynasties[(Get-S5Dynasty $site)].Members+=,$candidate
 Add-S5Dragon $state $site.Dragon 'free'
}
Invoke-S5Year $state;Assert-S5Result $state 6
$expectedFirst=@(0,1,4,6,7,8|ForEach-Object {$s5YearSites[$_].Actor}) -join '|'
if(($state.Bonds.Actor -join '|') -cne $expectedFirst){throw 'First-claim priority changed'}
Invoke-S5Year $state;Assert-S5Result $state 6
foreach($idx in @(0,1,8)){
 $site=$s5YearSites[$idx]
 $candidate=$state.Dynasties[(Get-S5Dynasty $site)].Members|Where-Object Id -ceq $site.Actor
 $candidate.Alive=$false
 $state.Characters[$site.Dragon].Bound=$false
}
Invoke-S5Year $state;Assert-S5Result $state 9
if((@($state.Bonds|Select-Object -Skip 6).Actor -join '|') -cne ((@(2,3,9|ForEach-Object {$s5YearSites[$_].Actor})) -join '|')){throw 'Successor priority changed'}
$aerea=$state.Dynasties['dynasty:dynn_Targaryen'].Members|Where-Object Id -ceq $s5YearSites[3].Actor
$aerea.Alive=$false;$state.Characters['character:dragon_balerion'].Bound=$false
Invoke-S5Year $state;Assert-S5Result $state 10
if($state.Bonds[9].Actor -cne $s5YearSites[5].Actor){throw 'Viserys did not receive the next free Balerion opportunity'}
$s5ExtraCases++
$state=New-S5State;$state.Root=New-S5Character 'unrelated-root'
$state.Dynasties['dynasty:dynn_Targaryen'].Members=@(New-S5Character 'aerea' 'asoiaf_Targaryen_41_trait')
Add-S5Dragon $state 'character:dragon_balerion' 'free'
Invoke-S5Year $state;Assert-S5Result $state 0;$s5ExtraCases++

# Check the helpers actually supplied by this playset, including More Dragon Eggs.
# No ownership, memory, dragonrider, or taming implementation is copied into this fix.
$s5Dependencies=@(foreach($spec in @(
 @('common/scripted_effects/00_agot_dragon_effects.txt','agot_bond_dragon_relation_effect','agot_set_as_owned_dragon'),
 @('common/scripted_triggers/00_agot_dragon_triggers.txt','agot_has_relationship_dragon'),
 @('common/scripted_triggers/asoiaf_canon_children_triggers.txt','asoiaf_canon_children_enabled_trigger')
)){
 $providers=@($active|Where-Object {Test-Path -LiteralPath (Join-Path $_ $spec[0])})
 if(-not $providers.Count){throw "Missing active dependency: $($spec[0])"}
 $path=Join-Path $providers[-1] $spec[0];$effective=[IO.File]::ReadAllText($path)
 $reference=if($spec[0] -like '*asoiaf*'){$s5EnabledText}else{Read-Agot $spec[0]}
 foreach($key in $spec|Select-Object -Skip 1){
  if((Get-ScriptBlock $effective $key) -cne (Get-ScriptBlock $reference $key)){throw "Active bonding dependency diverged: $key in $path"}
 }
 [pscustomobject]@{File=$spec[0];Provider=$providers[-1];SHA256=(Get-FileHash -LiteralPath $path).Hash;Helpers=@($spec|Select-Object -Skip 1)}
})
$s5Targets=@(Import-Csv -LiteralPath (Join-Path $modRoot 'docs/stage5-targeted-log-messages.csv'))
if($s5Targets.Count -ne 102){throw 'Historical bonding diagnostic inventory changed'}
$s5Result=[ordered]@{
 Revision=5;Status='PASS';GameExecutionChecked=$false
 Verification='Actual script control flow interpreted; native AGOT calls stubbed at the validated helper boundary. Not a CK3 runtime test.'
 BirthSites=24;YearlySites=10;RemovedSchemeLaunches=34
 BirthScenarios=$s5BirthCases;YearlyScenarios=$s5YearCases;AdditionalScenarios=$s5ExtraCases
 RepeatedCallsChecked=$true;HistoricalDiagnosticTargets=$s5Targets.Count;FreshLogChecked=$false
 NativeDependencies=$s5Dependencies
 ManifestSHA256=(Get-FileHash -LiteralPath (Join-Path $modRoot 'docs/source-manifest.json')).Hash
}
if($manifest.Revision -eq 5){
 [IO.File]::WriteAllText((Join-Path $modRoot 'docs/stage5-validation.json'),($s5Result|ConvertTo-Json -Depth 7)+"`n",$utf8)
}
Write-Output "PASS: bonding: $s5BirthCases birth, $s5YearCases yearly and $s5ExtraCases additional control-flow scenarios; repeat calls, scope cleanup, actor notification and pair priorities."
Write-Output 'PASS: all 34 contradictory scheme launches removed; effective native bond/ownership/relation helpers and original yearly pulse checked. CK3 runtime not exercised.'
