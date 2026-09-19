# Loaded after source/byte checks and the stage-two helpers. This interprets only
# the age-transition control flow; it does not emulate CK3 events or education.
$originalSetup=[IO.File]::ReadAllText((Join-Path $MainPath 'common/scripted_effects/asoiaf_setup_effects.txt'))
$ageSource=Get-ScriptBlock $originalSetup 'asoiaf_alternative_ages_effect'
$agePatched=Get-ScriptBlock $setup 'asoiaf_alternative_ages_effect'
$cleanup=Get-ScriptBlock $setup 'asoiaf_alternative_ages_cleanup_effect'
if($cleanup -cne (Get-ScriptBlock $originalSetup 'asoiaf_alternative_ages_cleanup_effect')){throw 'Unrelated adulthood cleanup behavior changed'}
if($agePatched -match '(?<!:)\basoiaf_underaged\s*\?=' -or $agePatched -match 'asoiaf_alternative_ages_cleanup_effect\s*='){throw 'Invalid candidate access or direct cleanup remains'}
$ageEvent=Get-ScriptBlock (Read-Plus 'events/agot_plus_fix_age_events.txt') 'agot_plus_fix_ages.0001'
if($ageEvent -notmatch 'type\s*=\s*character_event' -or $ageEvent -notmatch 'hidden\s*=\s*yes'){throw 'Cleanup must run as a hidden character event'}
$immediate=Get-ScriptBlock $ageEvent 'immediate'
$eventGuard=Get-ScriptBlock $ageEvent 'trigger'
if($eventGuard -notmatch 'is_alive\s*=\s*yes' -or $eventGuard -notmatch 'age\s*>=\s*16'){throw 'Age event guard missing'}
$eventCommands=@([regex]::Matches($immediate,'(?m)^\s*(\w+)\s*=\s*(\w+)\s*$'))
if($eventCommands.Count -ne 10 -or $eventCommands[-1].Groups[1].Value -cne 'asoiaf_alternative_ages_cleanup_effect' -or $eventCommands[-1].Groups[2].Value -cne 'yes'){throw 'Cleanup must be called directly from event ROOT after clearing targets'}
$cleared=@($eventCommands|Where-Object {$_.Groups[1].Value -ceq 'clear_saved_scope'}|ForEach-Object {$_.Groups[2].Value})
foreach($target in @('educator','victim','bully','crush','crushed_crush','root_crush','hostage','education_memory','new_memory')){
 if($cleared -cnotcontains $target){throw "Inherited cleanup scope is not cleared: $target"}
}
# The effective AGOT helper uses ROOT for memories, removing the ward, and house
# relations. Keep calling that helper from the new event rather than cloning it.
$education=Get-ScriptBlock (Read-Agot 'common/scripted_effects/00_education_effects.txt') 'wrap_up_education_effect'
if($education -notmatch 'WARD\s*=\s*root' -or $education -notmatch 'ward\s*=\s*root' -or $education -notmatch 'root\.house'){throw 'AGOT education contract changed'}
$null=Get-ScriptBlock (Read-Agot 'events/education_and_childhood/childhood_events.txt') 'childhood.0999'
$null=Get-ScriptBlock (Read-Agot 'events/dlc/bp2/bp2_hostage_system.txt') 'bp2_hostage_system.0200'

function Read-AgeNodes([string[]]$Tokens,[ref]$Index){
 $nodes=[Collections.Generic.List[object]]::new()
 while($Index.Value -lt $Tokens.Count -and $Tokens[$Index.Value] -cne '}'){
  $key=$Tokens[$Index.Value];$Index.Value++
  $operator=$Tokens[$Index.Value];$Index.Value++
  if($operator -notin @('=','?=','<','>','>=','<=','!=')){throw "Unknown age operator: $operator"}
  $value=$Tokens[$Index.Value];$Index.Value++
  $children=@()
  if($value -ceq '{'){
   $children=@(Read-AgeNodes $Tokens $Index)
   if($Index.Value -ge $Tokens.Count -or $Tokens[$Index.Value] -cne '}'){throw 'Unclosed age AST'}
   $Index.Value++
   $value=$null
  }
  $nodes.Add([pscustomobject]@{Key=$key;Operator=$operator;Value=$value;Children=$children})
 }
 $nodes.ToArray()
}
function ConvertTo-AgeNodes([string]$Text){
 $tokens=@([regex]::Matches((Clear-ScriptText $Text),'\?=|>=|<=|!=|[{}=<>]|[^{}\s=<>!?]+')|ForEach-Object Value)
 $cursor=0
 $nodes=@(Read-AgeNodes $tokens ([ref]$cursor))
 if($cursor -ne $tokens.Count){throw 'Unconsumed age AST tokens'}
 $nodes
}
function Test-AgeConditions($Nodes,$Character,$State){
 foreach($node in $Nodes){
  switch -CaseSensitive ($node.Key){
   'age' {
    $valid=switch($node.Operator){
     '<' {$Character.Age -lt [int]$node.Value}
     '>=' {$Character.Age -ge [int]$node.Value}
     default {throw 'Unsupported age comparison'}
    }
    if(-not $valid){return $false}
   }
   'exists' {if(-not $State.Scopes.ContainsKey($node.Value.Substring(6))){return $false}}
   'this' {
    if($node.Operator -cne '=' -or $node.Value -cne 'scope:asoiaf_underaged'){throw 'Unexpected candidate identity comparison'}
    if(-not [object]::ReferenceEquals($Character,$State.Scopes['asoiaf_underaged'])){return $false}
   }
   'is_alive' {if($Character.Alive -ne ($node.Value -ceq 'yes')){return $false}}
   default {throw "Unexpected age condition: $($node.Key)"}
  }
 }
 return $true
}
function Invoke-AgeNodes($Nodes,$Character,$State){
 foreach($node in $Nodes){
  switch -CaseSensitive ($node.Key){
   'if' {
    $limits=@($node.Children|Where-Object Key -ceq 'limit')
    if($limits.Count -ne 1){throw 'Age branch must have one limit'}
    if(Test-AgeConditions $limits[0].Children $Character $State){Invoke-AgeNodes @($node.Children|Where-Object Key -cne 'limit') $Character $State}
   }
   'clear_saved_scope' {$State.Scopes.Remove($node.Value)}
   'save_scope_as' {$State.Scopes[$node.Value]=$Character}
   'change_age' {$Character.Age += [int]$node.Value}
   'set_mother' {} # Verified unchanged against source below; irrelevant to age gate.
   'set_father' {}
   'trigger_event' {
    if($node.Children.Count -ne 1 -or $node.Children[0].Key -cne 'id' -or $node.Children[0].Value -cne 'agot_plus_fix_ages.0001'){throw 'Unexpected event or delay in age transition'}
    $State.Events.Add($Character.Id)
   }
   default {throw "Unexpected age effect: $($node.Key)"}
  }
 }
}
$originalNodes=@(ConvertTo-AgeNodes $ageSource)
$patchedNodes=@(ConvertTo-AgeNodes $agePatched)
if($patchedNodes.Count -ne 107 -or $originalNodes.Count -ne 107){throw 'Expected 107 character age adjustments'}
$cases=0
$state=@{Scopes=@{};Events=[Collections.Generic.List[string]]::new()}
for($i=0;$i -lt $patchedNodes.Count;$i++){
 $original=$originalNodes[$i];$patched=$patchedNodes[$i]
 if($patched.Key -cne $original.Key -or $patched.Key -notmatch '^character:' -or $patched.Operator -cne '?='){throw 'Age character/order changed'}
 $originalDirect=@($original.Children|Where-Object Key -in @('change_age','set_mother','set_father'))
 $patchedDirect=@($patched.Children|Where-Object Key -in @('change_age','set_mother','set_father'))
 if(($originalDirect|ConvertTo-Json -Compress -Depth 5) -cne ($patchedDirect|ConvertTo-Json -Compress -Depth 5)){throw "Age or parentage changed: $($patched.Key)"}
 $delta=[int](@($originalDirect|Where-Object Key -ceq 'change_age')[0].Value)
 $ages=@(@(0,1,14,15,16,17,25,80,(15-$delta),(16-$delta),(17-$delta))|Where-Object {$_ -ge 0}|Sort-Object -Unique)
 foreach($before in $ages){foreach($alive in @($true,$false)){
  # Seed a stale candidate to expose cross-character leaks independently of
  # the previous case. Keep the same state across all 107 character blocks.
  $state.Scopes['asoiaf_underaged']=[pscustomobject]@{Id='previous_character';Age=35;Alive=$true}
  $character=[pscustomobject]@{Id=$patched.Key;Age=$before;Alive=$alive}
  $eventCount=$state.Events.Count
  Invoke-AgeNodes $patched.Children $character $state
  $expected=[int]($alive -and $before -lt 16 -and ($before+$delta) -ge 16)
  if($character.Age -ne $before+$delta -or $state.Events.Count-$eventCount -ne $expected){throw "Incorrect transition for $($patched.Key): $before, delta $delta, alive $alive"}
  if($expected -eq 1 -and $state.Events[-1] -cne $character.Id){throw 'Cleanup dispatched to another character'}
  if($state.Scopes.ContainsKey('asoiaf_underaged')){throw 'Candidate leaks to the next character'}
  $cases++
 }}
}
$diagnostics=@(Import-Csv (Join-Path $modRoot 'docs/stage3-targeted-log-messages.csv'))
if($diagnostics.Count -ne 107 -or @($diagnostics|Where-Object Message -notmatch 'Unknown trigger: asoiaf_underaged,').Count){throw 'Unexpected stage-three log baseline'}
Write-Output "PASS: $cases age-control-flow cases from all 107 actual blocks; threshold boundaries, adults, minors, dead characters and stale candidates."
Write-Output 'PASS: original age deltas/parentage/order; hidden character event ROOT; inherited cleanup targets cleared; AGOT education dependencies.'
