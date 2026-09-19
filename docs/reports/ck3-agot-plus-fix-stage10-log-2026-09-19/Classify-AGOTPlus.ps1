$ErrorActionPreference = 'Stop'
$entries = @(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'classified-entries.csv'))
$mods = @(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'active-mods.csv'))
$plus = $mods | Where-Object Name -eq 'AGOT+'
$fix = $mods | Where-Object Descriptor -eq 'mod/AGOT_PLUS_FIX.mod'
$traitDefinitions = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
$traitSources = @(Get-ChildItem -LiteralPath (Join-Path $plus.Path 'common/traits') -File -Filter '*.txt')
foreach ($source in $traitSources) {
    foreach ($match in [regex]::Matches([IO.File]::ReadAllText($source.FullName), '(?m)^\s*(asoiaf_\w+_trait)\s*=\s*\{')) {
        $traitDefinitions[$match.Groups[1].Value] = 'common/traits/' + $source.Name
    }
}

# Conservative attribution: a resolved source file belongs to AGOT+ or its
# same-path corrective shadow, or a missing trait name has a verified definition.
# Ownerless history links and other diagnostics remain outside this lower bound.
$selected = [Collections.Generic.List[object]]::new()
$graphics = [Collections.Generic.List[object]]::new()
foreach ($entry in $entries) {
    if ($entry.Key) { continue }
    $direct = $entry.Owner -eq $plus.Name -or $entry.Owner -eq $fix.Name
    $trait = ''
    if ($entry.Message -match '^Unrecognized loc key trait_(asoiaf_\w+_trait)\.') {
        $trait = $Matches[1]
        if (-not $traitDefinitions.ContainsKey($trait)) { throw "Missing trait source: $trait" }
    }
    if (-not $direct -and -not $trait) { continue }
    if ($entry.Category -eq 'Graphics / portrait source error') {
        $graphics.Add($entry)
        continue
    }
    $group = if ($entry.Category -eq 'Localization / dynamic text error') { 'Localization' }
    elseif ($entry.Component -match '^lexer\.' -and $entry.Message -match 'utf8-bom') { 'Encoding_warnings' }
    elseif ($entry.Message -match '^PostValidate of (effect|trigger)') { 'Secondary_PostValidate' }
    elseif ($entry.Message -match 'Error: create_character effect') { 'Character_creation' }
    elseif ($entry.Message -match 'Error: start_scheme effect' -or $entry.Component -eq 'jomini_effect.cpp:914') { 'Dragon_schemes' }
    elseif ($entry.Message -match 'Invalid artifact template|unknown arguments: CREATOR') { 'Artifact_templates_and_arguments' }
    elseif ($entry.Files -match '^history/' -or $entry.Component -match '^history\.') { 'Character_history' }
    elseif ($entry.Component -match '^jomini_onaction\.') { 'On_action_structure' }
    elseif ($entry.Component -match '^(pdx_persistent_reader|jomini_eventtarget)\.') { 'Triggers_effects_and_syntax' }
    elseif ($entry.Component -match '^(jomini_script_system|faith_links|title_links)\.') { 'Database_references' }
    else { throw "Unclassified direct entry at line $($entry.Line): $($entry.Component)" }
    $selected.Add([pscustomobject]@{
        IssueClass = $group
        Attribution = $(if ($trait) { 'Verified trait definition' } else { 'Resolved source path' })
        Evidence = $(if ($trait) { $traitDefinitions[$trait] + ': ' + $trait } else { $entry.Files })
        LogLine = [int]$entry.Line
        Component = $entry.Component
        Owner = $entry.Owner
        Message = $entry.Message
    })
}
$selected | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'agot-plus-remaining.csv') -NoTypeInformation -Encoding UTF8
$summary = @($selected | Group-Object IssueClass | Sort-Object Name | ForEach-Object {
    [pscustomobject]@{ IssueClass = $_.Name; Messages = $_.Count }
})
$summary | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'agot-plus-classes.csv') -NoTypeInformation -Encoding UTF8
$details = [ordered]@{
    Scope = 'Conservative source-attributed lower bound; counts are diagnostics, not independent bugs.'
    NonGraphicsMessages = $selected.Count
    DirectNonGraphicsMessages = @($selected | Where-Object Attribution -eq 'Resolved source path').Count
    VerifiedMissingTraitNames = @($selected | Where-Object Attribution -eq 'Verified trait definition').Count
    DirectGraphicsExcluded = $graphics.Count
    TraitSources = @($traitSources | ForEach-Object { [pscustomobject]@{ Path = $_.FullName; SHA256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash } })
    Classes = $summary
    CharacterLocationEmployerConflict = @($selected | Where-Object Message -match 'Cannot specify both location and employer').Count
    CharacterMissingLocationEmployer = @($selected | Where-Object Message -match 'Invalid/missing location or employer').Count
    UnderagedTriggerMessages = @($selected | Where-Object Message -match 'Unknown trigger: asoiaf_underaged').Count
    UnattributedCharacterLinkMessages = @($entries | Where-Object { -not $_.Owner -and $_.Component -eq 'history.cpp:644' }).Count
}
$details | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'agot-plus-summary.json') -Encoding UTF8
$details | ConvertTo-Json -Depth 5
