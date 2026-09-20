$ErrorActionPreference='Stop'
$repoRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
. (Join-Path $repoRoot 'AGOT_Submods/AGOT_More_Dragon_Eggs_RUS_CORRECT/tools/Build-MDERusCorrect.ps1') -Check

# Mutations are in memory only. These cases reproduce the namespace regression
# and make sure duplicate cleanup cannot silently remove the unique labels.
function Assert-Rejected([string]$File,[string]$Mutated,[string]$ExpectedError){
    $original=$outputs[$File]
    try {
        $outputs[$File]=$Mutated
        $failure=$null
        try { Test-MDEContracts $outputs $sourceTexts $en $ru $builtin $russian $scriptChanges $roots $genderFixes | Out-Null }
        catch { $failure=$_.Exception.Message }
        if(-not $failure -or $failure -notmatch $ExpectedError){throw "Mutation was not rejected as expected: $File / $failure"}
        Write-Output "Rejected: $File / $failure"
    } finally { $outputs[$File]=$original }
}
$file='localization/russian/mde_artifacts_l_russian.yml'
Assert-Rejected $file $sourceTexts['Translation:'+$file] 'Conflicting MDE travel-key declaration'
$file='localization/replace/english/agot/agot_artifacts/mde_artifacts_l_english.yml'
Assert-Rejected $file ($outputs[$file].Replace(' MDE_nagga_desc:',' nagga_desc:')) 'Conflicting MDE travel-key declaration'
$file='localization/russian/dp_artifacts_l_russian.yml'
Assert-Rejected $file $sourceTexts['Translation:'+$file] 'Duplicate external Russian declaration'
$missingParent=$outputs[$file] -creplace '(?m)^([ \t]*mde_dragon_egg_gen_parent:.*)$','# removed: $1'
Assert-Rejected $file $missingParent 'Expected 1044|Unique artifact parent label lost'
$file='common/customizable_localization/00_more_dragon_eggs_loc.txt'
Assert-Rejected $file ($outputs[$file].Replace('localization_key = MDE_nagga_desc','localization_key = nagga_desc')) 'Nagga artifact selector'
Write-Output 'Five regression mutations rejected; disk files untouched.'
