# Loaded by Test-AGOTPlusFix.ps1 after source hash, inventory and byte checks.
function Get-AllBlocks([string]$Text,[string]$Key){
    $clean=Clear-ScriptText $Text
    foreach($match in [regex]::Matches($clean,'(?m)(?<!\S)'+[regex]::Escape($Key)+'\s*=\s*\{')){
        $start=$match.Index+$match.Length
        $depth=1
        for($i=$start;$i -lt $clean.Length;$i++){
            if($clean[$i] -eq '{'){$depth++}elseif($clean[$i] -eq '}'){$depth--}
            if($depth -eq 0){$clean.Substring($start,$i-$start);break}
        }
        if($depth -ne 0){throw "Unclosed $Key block"}
    }
}
$children=Read-Plus 'common/scripted_effects/asoiaf_canon_children_effects.txt'
$births=@(Get-AllBlocks $children 'create_character')
if($births.Count -ne 202){throw 'Canon child creation inventory changed'}
$secondTwins=0
foreach($birth in $births){
    $after=Get-ScriptBlock $birth 'after_creation'
    if($birth -match '(?m)^\s*employer\s*=' -or $birth -notmatch '\blocation\s*=\s*scope:mother\.location\b'){throw 'Invalid or lost newborn placement'}
    if([regex]::Matches($after,'\bagot_plus_fix_place_newborn_effect\s*=\s*yes\b').Count -ne 1){throw 'Newborn placement must run exactly once'}
    if($after.IndexOf('agot_plus_fix_place_newborn_effect') -gt $after.IndexOf('asoiaf_canon_children_parentage_assignment_effect') -or $after.IndexOf('agot_plus_fix_place_newborn_effect') -gt $after.IndexOf('asoiaf_canon_children_join_travel_plan_effect')){throw 'Court assignment must precede original parentage and travel handling'}
    if($birth -match '\bsave_scope_as\s*=\s*child_2\b'){$secondTwins++}
}
if($secondTwins -ne 7){throw 'Second twin inventory changed'}
$placement=Get-ScriptBlock (Read-Plus 'common/scripted_effects/zz_agot_plus_fix_child_effects.txt') 'agot_plus_fix_place_newborn_effect'
if($placement -notmatch '^\s*save_scope_as\s*=\s*agot_plus_fix_newborn\b' -or $placement -match 'scope:child\b|scope:child_2\b|\.liege\b'){throw 'Court transfer must use the newborn scope, not a twin or maternal liege'}
$ruler=Get-ScriptBlock $placement 'if'
$courtier=Get-ScriptBlock $placement 'else_if'
if($ruler -notmatch 'scope:mother\s*=\s*\{\s*is_ruler\s*=\s*yes\s*\}' -or $ruler -notmatch 'scope:mother\s*=\s*\{\s*add_courtier\s*=\s*scope:agot_plus_fix_newborn\s*\}') {throw 'Ruling mother must retain the newborn at her own court'}
if($courtier -notmatch 'exists\s*=\s*scope:mother\.employer' -or $courtier -notmatch 'scope:mother\.employer\s*=\s*\{\s*add_courtier\s*=\s*scope:agot_plus_fix_newborn\s*\}') {throw 'Maternal employer access must be guarded'}
if($placement -notmatch 'set_location\s*=\s*scope:mother\.location\s*$'){throw 'Final location must follow court transfer for travelling mothers'}
$referenceBirths=Read-Agot 'common/scripted_effects/00_agot_canon_children_effects.txt'
foreach($id in @('agot_canon_children_backup_girl_twin','agot_canon_children_backup_boy_twin')){
    $sample=Get-ScriptBlock $referenceBirths $id
    if($sample -notmatch 'location\s*=\s*scope:child\.mother\.location' -or $sample -notmatch 'add_courtier\s*=\s*scope:new_baby'){throw 'AGOT newborn reference behavior changed'}
}
$parents=@(Get-AllBlocks (Read-Plus 'events/asoiaf_young_griff_landing_events.txt') 'create_character')
if(@($parents|Where-Object {$_ -match '\blocation\s*=\s*scope:faegon\.location\b'}).Count -ne 2){throw 'Griff parents still lack placement'}

$traits=Read-Agot 'common/traits/00_traits.txt'
foreach($id in @('august','tourney_participant','lifestyle_blademaster','lifestyle_hunter','lifestyle_reveler','bossy')){$null=Get-ScriptBlock $traits $id}
$null=Get-ScriptBlock (Read-Agot 'common/focuses/00_education_focuses.txt') 'education_stewardship'
$null=Get-ScriptBlock (Read-Agot 'common/nicknames/00_agot_generic_nicknames.txt') 'nick_agot_the_imp'
$null=Get-ScriptBlock (Read-Agot 'common/nicknames/00_agot_historical_nicknames.txt') 'nick_agot_historical_ironrod'
$null=Get-ScriptBlock (Read-Agot 'common/nicknames/00_agot_historical_nicknames.txt') 'nick_agot_historical_bittersteel'
$rhllor=Read-Agot 'common/religion/religion_types/00_agot_the_rhllor.txt'
$null=Get-ScriptBlock $rhllor 'the_rhllor_religion'
$null=Get-ScriptBlock $rhllor 'rhllor_fots'
$river=Get-ScriptBlock (Read-Agot 'common/culture/cultures/00_agot_cul_andal.txt') 'riverman_main'
if((Get-ScriptBlock $river 'clothing_gfx') -notmatch '\briverlander_clothing_gfx\b'){throw 'Riverlander clothing flag is not defined by the reference culture'}
$null=Get-ScriptBlock (Read-Agot 'common/activities/activity_types/coronation.txt') 'activity_coronation'
$plusTraits=[IO.File]::ReadAllText((Join-Path $MainPath 'common/traits/asoiaf_canon_children_traits.txt'))
$null=Get-ScriptBlock $plusTraits 'asoiaf_Baratheon_2_1_trait'
$clear=Get-ScriptBlock (Read-Plus 'common/scripted_effects/asoiaf_clear_traits_effects.txt') 'asoiaf_clear_lifestyle_traits_effect'
foreach($id in @('lifestyle_hunter','lifestyle_blademaster','lifestyle_reveler')){if($clear -notmatch ('remove_trait\s*=\s*'+$id+'\b')){throw "Modern cleanup removed: $id"}}
if($clear -match '_history\b'){throw 'Obsolete historical lifestyle trait cleanup remains'}

$newModifiers=Read-Plus 'common/modifiers/zz_agot_plus_fix_modifiers.txt'
$sourceModifiers=[IO.File]::ReadAllText((Join-Path $MainPath 'common/modifiers/asoiaf_canon_children_modifiers.txt'))
foreach($pair in @(@('asoiaf_Targaryen_95_modifier','asoiaf_Targaryen_94_modifier'),@('asoiaf_Greyjoy_13_alt_modifier','asoiaf_Greyjoy_13_modifier'))){
    if((Get-ScriptBlock $newModifiers $pair[0]) -cne (Get-ScriptBlock $sourceModifiers $pair[1])){throw "Canonical modifier bonuses changed: $($pair[0])"}
}
$marriage=Get-ScriptBlock (Read-Plus 'common/on_action/asoiaf_marriage_concubinage_on_actions.txt') 'asoiaf_rhaenyra_personal_coa_marriage'
$originalMarriage=Get-ScriptBlock ([IO.File]::ReadAllText((Join-Path $MainPath 'common/on_action/asoiaf_marriage_concubinage_on_actions.txt'))) 'asoiaf_rhaenyra_personal_coa_marriage'
if((Get-ScriptBlock $marriage 'trigger') -cne (Get-ScriptBlock $originalMarriage 'trigger')){throw 'Rhaenyra marriage eligibility changed'}
if([regex]::Matches($marriage,'COA_KEY\s*=\s*rhaenrya_personal_coa\b').Count -ne 2 -or $marriage -match 'has_game_rule|personal_coa_alt'){throw 'Wrong default heraldry behavior'}
$null=Get-ScriptBlock ([IO.File]::ReadAllText((Join-Path $MainPath 'common/coat_of_arms/coat_of_arms/test_personal_coas.txt'))) 'rhaenrya_personal_coa'

# Effective active paths matter: reject later mods hiding the new shadow files,
# a newly installed AOTK integration, or the reappearance of removed definitions.
$profile=Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Paradox Interactive/Crusader Kings III'
$load=Get-Content -LiteralPath (Join-Path $profile 'dlc_load.json') -Raw -Encoding UTF8|ConvertFrom-Json
$active=@(foreach($descriptorFile in $load.enabled_mods){
    $descriptorText=[IO.File]::ReadAllText((Join-Path $profile $descriptorFile))
    $activePath=[regex]::Match($descriptorText,'(?m)^\s*path\s*=\s*"([^"]+)"').Groups[1].Value
    if($activePath){[IO.Path]::GetFullPath($activePath)}
})
foreach($item in $manifest.Files){
    $providers=@($active|Where-Object {[IO.File]::Exists((Get-NativePath (Join-Path $_ $item.File)))})
    if($providers.Count -eq 0 -or $providers[-1] -ine $modRoot){throw "Patch is not the final active provider: $($item.File)"}
}
$ruleSources=@(foreach($root in $active){$rules=Join-Path $root 'common/game_rules';if(Test-Path -LiteralPath $rules){Get-ChildItem -LiteralPath $rules -Recurse -File -Filter '*.txt'}})
foreach($file in $ruleSources){
    $text=Clear-ScriptText ([IO.File]::ReadAllText($file.FullName))
    if($text -match '\b(show_armor_enabled|asoiaf_alternative_arryn_sigil_rule_(on|off))\s*='){throw 'Optional game-rule definitions reappeared; restore/review the integration before using this revision'}
}
foreach($addition in $additions|Where-Object File -like '*.yml'){
    $lines=$addition.Text -split '\r?\n'
    foreach($line in $lines|Select-Object -Skip 1){if($line.Trim() -and $line -notmatch '^ [A-Za-z0-9_]+:0 "(?:[^"\\]|\\.)*"$'){throw "Malformed added localization: $line"}}
}
foreach($key in @('Aegor','nick_agot_historical_bittersteel','asoiaf_Greyjoy_13_alt_modifier','asoiaf_Greyjoy_13_alt_modifier_desc')){
    foreach($language in @('english','russian')){
        $found=$false
        foreach($root in $active){
            $loc=Join-Path $root 'localization'
            if(-not(Test-Path -LiteralPath $loc)){continue}
            foreach($file in Get-ChildItem -LiteralPath $loc -Recurse -File -Filter ('*_l_'+$language+'.yml')){
                if([regex]::IsMatch([IO.File]::ReadAllText($file.FullName),'(?m)^\s*'+[regex]::Escape($key)+':')){$found=$true;break}
            }
            if($found){break}
        }
        if(-not $found){throw "Missing $language localization dependency: $key"}
    }
}
Write-Output 'PASS: 202 newborn placements, including seven second twins; ruler/courtier/no-employer branches; original parentage and travel order.'
Write-Output 'PASS: current trait/focus/nickname/faith/activity/gfx references; real modifier bonuses; default heraldry and localization dependencies.'
Write-Output 'PASS: active VFS providers and absence of unsupported optional game rules.'
