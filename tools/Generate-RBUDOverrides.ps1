[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GamePath,

    [string]$ModPath,
    [string]$ManifestPath,
    [string]$PlanPath,
    [string]$LayoutPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$repositoryRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ModPath)) {
    $ModPath = Join-Path $repositoryRoot 'RB_UD'
}
$ModPath = [IO.Path]::GetFullPath($ModPath)
$GamePath = [IO.Path]::GetFullPath($GamePath)
if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
    $ManifestPath = Join-Path $ModPath 'tools\generated\RB_UD_vanilla_manifest.json'
}
if ([string]::IsNullOrWhiteSpace($PlanPath)) {
    $PlanPath = Join-Path $ModPath 'tools\generated\RB_UD_override_plan.json'
}
if ([string]::IsNullOrWhiteSpace($LayoutPath)) {
    $LayoutPath = Join-Path $ModPath 'tools\RB_UD_layouts.json'
}
$ManifestPath = [IO.Path]::GetFullPath($ManifestPath)
$PlanPath = [IO.Path]::GetFullPath($PlanPath)
$LayoutPath = [IO.Path]::GetFullPath($LayoutPath)

function Convert-ToArray {
    param($Value)
    if ($null -eq $Value) { return @() }
    return @($Value)
}

function Get-CodeLine {
    param([string]$Line)
    return ($Line -split '#', 2)[0]
}

function Get-BraceDelta {
    param([string]$Line)
    $code = Get-CodeLine $Line
    return ([regex]::Matches($code, '\{')).Count - ([regex]::Matches($code, '\}')).Count
}

function Get-StringSha256 {
    param([string]$Text)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '')
    }
    finally {
        $sha.Dispose()
    }
}

function Get-FileSha256 {
    param([string]$Path)
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '')
    }
    finally {
        $sha.Dispose()
        $stream.Dispose()
    }
}

function Get-TopLevelBlocks {
    param(
        [string[]]$Lines,
        [string]$SourceFile
    )
    $result = [ordered]@{}
    $depth = 0
    $name = $null
    $buffer = $null
    $startLine = 0
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        $rawLine = $Lines[$index]
        $codeLine = Get-CodeLine $rawLine
        if ($depth -eq 0 -and $codeLine -match '^([A-Za-z0-9_.]+)\s*=\s*\{') {
            $name = $Matches[1]
            $buffer = [Collections.Generic.List[string]]::new()
            $startLine = $index + 1
        }
        if ($null -ne $name) { $buffer.Add($rawLine) }
        $depth += Get-BraceDelta $rawLine
        if ($depth -lt 0) {
            throw "Unbalanced closing brace in $SourceFile at line $($index + 1)."
        }
        if ($null -ne $name -and $depth -eq 0) {
            $result[$name] = [pscustomobject]@{
                Id = $name
                SourceFile = $SourceFile
                StartLine = $startLine
                Lines = $buffer.ToArray()
            }
            $name = $null
            $buffer = $null
        }
    }
    if ($depth -ne 0 -or $null -ne $name) {
        throw "Unbalanced braces while parsing $SourceFile."
    }
    return $result
}

function Get-DirectBlockRange {
    param(
        [string[]]$Lines,
        [string]$Field
    )
    $depth = 0
    $start = -1
    $startDepth = -1
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        $code = Get-CodeLine $Lines[$index]
        if (
            $start -lt 0 -and
            $depth -eq 1 -and
            $code -match ('^\s*' + [regex]::Escape($Field) + '\s*=\s*\{')
        ) {
            $start = $index
            $startDepth = $depth
        }
        $depth += Get-BraceDelta $Lines[$index]
        if ($start -ge 0 -and $depth -eq $startDepth) {
            return [pscustomobject]@{ Start = $start; End = $index }
        }
    }
    return $null
}

function Get-DirectBlock {
    param([string[]]$Lines, [string]$Field)
    $range = Get-DirectBlockRange $Lines $Field
    if ($null -eq $range) { return @() }
    return @($Lines[$range.Start..$range.End])
}

function Replace-LineRange {
    param(
        [string[]]$Lines,
        [int]$Start,
        [int]$End,
        [string[]]$Replacement
    )
    $result = [Collections.Generic.List[string]]::new()
    if ($Start -gt 0) {
        for ($index = 0; $index -lt $Start; $index++) { $result.Add($Lines[$index]) }
    }
    foreach ($line in Convert-ToArray $Replacement) { $result.Add([string]$line) }
    if ($End -lt ($Lines.Count - 1)) {
        for ($index = $End + 1; $index -lt $Lines.Count; $index++) { $result.Add($Lines[$index]) }
    }
    return $result.ToArray()
}

function Replace-DirectBlock {
    param(
        [string[]]$Lines,
        [string]$Field,
        [string[]]$Replacement,
        [switch]$AllowMissing
    )
    $range = Get-DirectBlockRange $Lines $Field
    if ($null -eq $range) {
        if ($AllowMissing) { return $Lines }
        throw "Direct block '$Field' not found in $($Lines[0])."
    }
    return Replace-LineRange $Lines $range.Start $range.End $Replacement
}

function Remove-DirectBlock {
    param([string[]]$Lines, [string]$Field, [switch]$AllowMissing)
    $range = Get-DirectBlockRange $Lines $Field
    if ($null -eq $range) {
        if ($AllowMissing) { return $Lines }
        throw "Direct block '$Field' not found in $($Lines[0])."
    }
    return Replace-LineRange $Lines $range.Start $range.End @()
}

function Set-DirectScalar {
    param(
        [string[]]$Lines,
        [string]$Field,
        [string]$Value
    )
    $depth = 0
    $found = -1
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        $code = Get-CodeLine $Lines[$index]
        if ($depth -eq 1 -and $code -match ('^\s*' + [regex]::Escape($Field) + '\s*=')) {
            if ($found -ge 0) { throw "Multiple direct '$Field' values in $($Lines[0])." }
            $found = $index
        }
        $depth += Get-BraceDelta $Lines[$index]
    }
    if ($found -ge 0) {
        $indent = ([regex]::Match($Lines[$found], '^\s*')).Value
        $replacement = "$indent$Field = $Value"
        return Replace-LineRange $Lines $found $found @($replacement)
    }
    return Replace-LineRange $Lines 1 0 @("`t$Field = $Value")
}

function Set-DirectInlineValue {
    param([string[]]$Lines, [string]$Field, [string]$Value)
    return Set-DirectScalar $Lines $Field $Value
}

function Get-DirectScalarValue {
    param([string[]]$Lines, [string]$Field)
    $depth = 0
    foreach ($line in $Lines) {
        $code = Get-CodeLine $line
        if (
            $depth -eq 1 -and
            $code -match ('^\s*' + [regex]::Escape($Field) + '\s*=\s*([^\s\{\}]+)')
        ) {
            return $Matches[1].Trim('"')
        }
        $depth += Get-BraceDelta $line
    }
    return $null
}

function Set-CapacityModifier {
    param([string[]]$Lines, [int]$Target)
    $matchIndexes = [Collections.Generic.List[int]]::new()
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        if ((Get-CodeLine $Lines[$index]) -match '^\s*domicile_external_slots_capacity_add\s*=') {
            $matchIndexes.Add($index)
        }
    }
    if ($Target -eq 0) {
        $result = $Lines
        foreach ($lineIndex in @($matchIndexes | Sort-Object -Descending)) {
            $result = Replace-LineRange $result $lineIndex $lineIndex @()
        }
        return $result
    }
    if ($matchIndexes.Count -ne 1) {
        throw "Expected exactly one domicile_external_slots_capacity_add in $($Lines[0]); found $($matchIndexes.Count)."
    }
    $lineIndex = $matchIndexes[0]
    $indent = ([regex]::Match($Lines[$lineIndex], '^\s*')).Value
    return Replace-LineRange $Lines $lineIndex $lineIndex @("${indent}domicile_external_slots_capacity_add = $Target")
}

function Add-ConditionToDirectBlock {
    param(
        [string[]]$Lines,
        [string]$Field,
        [string]$ConditionLine
    )
    $range = Get-DirectBlockRange $Lines $Field
    if ($null -eq $range) {
        throw "Cannot append to missing '$Field' in $($Lines[0])."
    }
    $replacement = [Collections.Generic.List[string]]::new()
    for ($index = $range.Start; $index -lt $range.End; $index++) {
        $replacement.Add($Lines[$index])
    }
    $replacement.Add("`t`t$ConditionLine")
    $replacement.Add($Lines[$range.End])
    return Replace-LineRange $Lines $range.Start $range.End $replacement.ToArray()
}

function Get-AllNamedBlockRanges {
    param([string[]]$Lines, [string]$Field)
    $stack = [Collections.Generic.Stack[object]]::new()
    $result = [Collections.Generic.List[object]]::new()
    $depth = 0
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        $code = Get-CodeLine $Lines[$index]
        if ($code -match ('^\s*' + [regex]::Escape($Field) + '\s*=\s*\{')) {
            $stack.Push([pscustomobject]@{ Start = $index; StartDepth = $depth })
        }
        $depth += Get-BraceDelta $Lines[$index]
        while ($stack.Count -gt 0 -and $depth -eq $stack.Peek().StartDepth) {
            $open = $stack.Pop()
            $result.Add([pscustomobject]@{ Start = $open.Start; End = $index })
        }
    }
    return $result.ToArray()
}

function Remove-ContainingNamedBlock {
    param(
        [string[]]$Lines,
        [string]$Field,
        [string]$RequiredText
    )
    $candidates = @()
    foreach ($range in Get-AllNamedBlockRanges $Lines $Field) {
        $text = $Lines[$range.Start..$range.End] -join "`n"
        if ($text -match [regex]::Escape($RequiredText)) {
            $candidates += $range
        }
    }
    if ($candidates.Count -ne 1) {
        throw "Expected one '$Field' block containing '$RequiredText'; found $($candidates.Count)."
    }
    return Replace-LineRange $Lines $candidates[0].Start $candidates[0].End @()
}

function Get-DirectPositionY {
    param([string[]]$Lines)
    foreach ($line in $Lines) {
        if ((Get-CodeLine $line) -match '^\s*position\s*=\s*\{\s*[0-9.]+%\s+([0-9.]+)%') {
            return [double]$Matches[1]
        }
    }
    return 0.0
}

function Get-SourceBlocks {
    param([string]$RelativePath)
    if (-not $script:SourceBlockCache.ContainsKey($RelativePath)) {
        $fullPath = Join-Path $GamePath $RelativePath
        if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
            throw "Vanilla source file not found: $fullPath"
        }
        $lines = Get-Content -LiteralPath $fullPath -Encoding UTF8
        $script:SourceBlockCache[$RelativePath] = Get-TopLevelBlocks $lines $RelativePath
    }
    return $script:SourceBlockCache[$RelativePath]
}

function Get-VanillaObjectLines {
    param([string]$RelativePath, [string]$ObjectId)
    $blocks = Get-SourceBlocks $RelativePath
    if (-not $blocks.Contains($ObjectId)) {
        throw "Object '$ObjectId' not found in '$RelativePath'."
    }
    return @($blocks[$ObjectId].Lines)
}

function Get-RelativeSourceFromLocation {
    param([string]$Location)
    return ($Location -replace ':\d+$', '')
}

function Convert-ToGeneratedPath {
    param([string]$PlanPathValue)
    return Join-Path $ModPath ($PlanPathValue -replace '/', '\')
}

function Write-GeneratedText {
    param([string]$Path, [string]$Text, [bool]$Bom)
    [IO.Directory]::CreateDirectory((Split-Path -Parent $Path)) | Out-Null
    $encoding = [Text.UTF8Encoding]::new($Bom)
    [IO.File]::WriteAllText($Path, $Text, $encoding)
}

foreach ($requiredPath in @($ManifestPath, $PlanPath, $LayoutPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required input not found: $requiredPath"
    }
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$planWrapper = Get-Content -LiteralPath $PlanPath -Raw -Encoding UTF8 | ConvertFrom-Json
$layoutConfig = Get-Content -LiteralPath $LayoutPath -Raw -Encoding UTF8 | ConvertFrom-Json
$plan = $planWrapper.Plan

$computedPlanHash = Get-StringSha256 ($plan | ConvertTo-Json -Depth 100 -Compress)
if ($computedPlanHash -ne $planWrapper.PlanSha256) {
    throw "Override plan signature mismatch: stored $($planWrapper.PlanSha256), computed $computedPlanHash."
}
if ($plan.SourceManifest.GameVersion -ne $manifest.GameVersion) {
    throw 'Plan and manifest target different CK3 versions.'
}
foreach ($signatureName in @('StructureSha256', 'AvailabilitySha256', 'AssetsSha256', 'ExplicitRemovalSha256')) {
    if ($plan.SourceManifest.VanillaSignatures.$signatureName -ne $manifest.VanillaSignatures.$signatureName) {
        throw "Plan/manifest vanilla signature mismatch for $signatureName."
    }
}

Write-Output "Validating $(@(Convert-ToArray $manifest.InputFiles).Count) vanilla input hashes..."
foreach ($input in Convert-ToArray $manifest.InputFiles) {
    $fullPath = Join-Path $GamePath $input.Path
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) {
        throw "Vanilla input is missing: $($input.Path)"
    }
    $actualHash = Get-FileSha256 $fullPath
    if ($actualHash -ne $input.Sha256) {
        throw "Vanilla input changed since analysis: $($input.Path). Expected $($input.Sha256), got $actualHash."
    }
}

$script:SourceBlockCache = @{}
$buildingRecordById = @{}
foreach ($building in $manifest.Buildings) { $buildingRecordById[$building.Id] = $building }
$buildingLines = @{}
$originalBuildingText = @{}
foreach ($buildingId in Convert-ToArray $plan.ObjectInventory.AffectedVanillaBuildingIds) {
    if (-not $buildingRecordById.ContainsKey($buildingId)) {
        throw "Plan references unknown building '$buildingId'."
    }
    $record = $buildingRecordById[$buildingId]
    $lines = Get-VanillaObjectLines $record.SourceFile $buildingId
    $buildingLines[$buildingId] = $lines
    $originalBuildingText[$buildingId] = $lines -join "`n"
}

# External capacity is moved to the first main-building level.
foreach ($domicileOverride in Convert-ToArray $plan.DomicileTypeOverrides) {
    foreach ($change in Convert-ToArray $domicileOverride.MainTrackCapacityChanges) {
        $buildingLines[$change.Building] = Set-CapacityModifier `
            $buildingLines[$change.Building] `
            ([int]$change.TargetCapacityAdd)
    }
}

# Every anchor level receives enough internal slots for all parallel tracks.
foreach ($slotOverride in Convert-ToArray $plan.InternalSlotOverrides) {
    foreach ($change in Convert-ToArray $slotOverride.BuildingChanges) {
        $buildingLines[$change.Building] = Set-DirectScalar `
            $buildingLines[$change.Building] `
            'internal_slots' `
            ([string]$change.TargetInternalSlots)
    }
}

# Terminal external specializations become independent internal tracks.
foreach ($branch in Convert-ToArray $plan.ExternalBranchOverrides) {
    foreach ($buildingId in Convert-ToArray $branch.BuildingsChangingSlotType) {
        $buildingLines[$buildingId] = Set-DirectScalar $buildingLines[$buildingId] 'slot_type' 'internal'
    }
}

# The shared estate library remains a prerequisite track. Its two final
# specializations are re-anchored to the estate main building.
foreach ($branch in Convert-ToArray $plan.InternalBranchOverrides) {
    foreach ($specialization in Convert-ToArray $branch.Specializations) {
        $rootId = $specialization.Root
        $buildingLines[$rootId] = Set-DirectScalar `
            $buildingLines[$rootId] `
            'previous_building' `
            ([string]$specialization.ReplacePreviousBuilding.To)
        $buildingLines[$rootId] = Add-ConditionToDirectBlock `
            $buildingLines[$rootId] `
            'can_construct' `
            ([string]$specialization.AddConstructionPrerequisite)
    }
}

# Purpose-specific camp buildings retain no purpose gate. The generator only
# accepts buildings whose analyzed construction dependency is that one flag.
foreach ($purpose in Convert-ToArray $plan.ConditionalOverrides.CampPurpose) {
    foreach ($buildingId in Convert-ToArray $purpose.Buildings) {
        $record = $buildingRecordById[$buildingId]
        $dependencies = @()
        if ($null -ne $record.Availability.CanConstruct) {
            $resolved = $record.Availability.CanConstruct.ResolvedDependencies
            foreach ($property in $resolved.PSObject.Properties) {
                if (@(Convert-ToArray $property.Value).Count -gt 0) {
                    $dependencies += $property.Name
                }
            }
        }
        if ($dependencies.Count -ne 1 -or $dependencies[0] -ne 'RealmLawFlags') {
            throw "Camp-purpose building '$buildingId' has unexpected extra construction dependencies: $($dependencies -join ', ')."
        }
        $buildingLines[$buildingId] = Remove-DirectBlock $buildingLines[$buildingId] 'can_construct'
    }
}

# Access-gate rewrite. The only conditions retained from these reviewed tracks
# are main-domicile progression and the elephant-meal temporary state check.
$accessGatePattern = '(?i)(innovation_war_camels|innovation_elephantry|innovation_champa_rice|innovation_fire_medicine|innovation_lacquered_armor|can_recruit_archer_cavalry_trigger|ep3_unlocked_silk|unlocks_silk_buildings_parameter|hosts_chariot_races|_internal_yurt_unlock|any_held_county|num_of_known_languages|geographical_region\s*=\s*world_innovation_elephants)'
$rewrittenAccessBuildings = [Collections.Generic.List[string]]::new()
foreach ($track in Convert-ToArray $plan.ConditionalOverrides.CultureTerritoryAndSpecialAccess) {
    if ($track.Decision -ne 'targeted_remove_specialization_access_gate') { continue }
    foreach ($profile in Convert-ToArray $track.BuildingProfiles) {
        $field = $null
        $scriptText = $null
        if (-not [string]::IsNullOrWhiteSpace([string]$profile.ExistingCanConstruct)) {
            $field = 'can_construct'
            $scriptText = [string]$profile.ExistingCanConstruct
        }
        elseif (-not [string]::IsNullOrWhiteSpace([string]$profile.ExistingCanConstructPotential)) {
            $field = 'can_construct_potential'
            $scriptText = [string]$profile.ExistingCanConstructPotential
        }
        if ($null -eq $field -or $scriptText -notmatch $accessGatePattern) { continue }

        $buildingId = $profile.Building
        $replacement = @()
        $mainRequirement = [regex]::Match(
            $scriptText,
            'has_domicile_building_or_higher\s*=\s*([A-Za-z0-9_]+)'
        )
        if ($buildingId -eq 'proving_grounds_elephantry_reserve') {
            $replacement = @(
                "`tcan_construct = {",
                "`t`tcustom_tooltip = {",
                "`t`t`ttext = proving_grounds_elephantry_reserve.tt.ate_elephants",
                "`t`t`tNOT = { has_character_flag = recently_ate_elephants }",
                "`t`t}",
                "`t}"
            )
        }
        elseif ($mainRequirement.Success) {
            $mainBuilding = $mainRequirement.Groups[1].Value
            $replacement = @(
                "`t$field = {",
                "`t`tdomicile ?= { has_domicile_building_or_higher = $mainBuilding }",
                "`t}"
            )
        }

        if ($replacement.Count -eq 0) {
            $buildingLines[$buildingId] = Remove-DirectBlock $buildingLines[$buildingId] $field
        }
        else {
            $buildingLines[$buildingId] = Replace-DirectBlock $buildingLines[$buildingId] $field $replacement
        }
        $rewrittenAccessBuildings.Add($buildingId)
    }
}

# Build the five domicile-type overrides from vanilla objects and a separate,
# hand-tunable layout preset. Empty/construction asset blocks are cloned from
# existing vanilla slots; only slot name, position, and size are changed.
$generatedTypeBlocks = [Collections.Generic.List[object]]::new()
foreach ($typeOverride in Convert-ToArray $plan.DomicileTypeOverrides) {
    $domicileId = $typeOverride.DomicileType
    $sourcePath = Get-RelativeSourceFromLocation $typeOverride.VanillaSource
    $typeLines = Get-VanillaObjectLines $sourcePath $domicileId
    $slotsBlock = Get-DirectBlock $typeLines 'domicile_building_slots'
    if ($slotsBlock.Count -eq 0) { throw "No domicile_building_slots block for $domicileId." }
    $mainSlot = Get-DirectBlock $slotsBlock 'main_slot'
    if ($mainSlot.Count -eq 0) { throw "No main_slot block for $domicileId." }

    $sourceSlots = @{}
    for ($slot = 1; $slot -le [int]$typeOverride.CurrentVisualExternalSlots; $slot++) {
        $sourceBlock = Get-DirectBlock $slotsBlock "external_slot_$slot"
        if ($sourceBlock.Count -eq 0) { throw "Missing vanilla external_slot_$slot for $domicileId." }
        $sourceSlots[$slot] = $sourceBlock
    }

    $layoutProperty = $layoutConfig.Layouts.PSObject.Properties[$domicileId]
    if ($null -eq $layoutProperty) { throw "No layout preset for $domicileId." }
    $layoutSlots = @(Convert-ToArray $layoutProperty.Value.Slots | Sort-Object Id)
    if ($layoutSlots.Count -ne [int]$typeOverride.TargetVisualExternalSlots) {
        throw "Layout $domicileId has $($layoutSlots.Count) slots; plan requires $($typeOverride.TargetVisualExternalSlots)."
    }

    $renderItems = [Collections.Generic.List[object]]::new()
    $renderItems.Add([pscustomobject]@{
        SortY = Get-DirectPositionY $mainSlot
        SortX = 50.0
        Lines = $mainSlot
    })
    foreach ($layoutSlot in $layoutSlots) {
        $slotId = [int]$layoutSlot.Id
        if ($slotId -lt 1 -or $slotId -gt $layoutSlots.Count) {
            throw "Invalid slot ID $slotId in layout $domicileId."
        }
        $sourceAssetSlot = [int]$layoutSlot.SourceAssetSlot
        if (-not $sourceSlots.ContainsKey($sourceAssetSlot)) {
            throw "Layout $domicileId slot $slotId references missing vanilla asset slot $sourceAssetSlot."
        }
        $clone = @($sourceSlots[$sourceAssetSlot])
        $clone[0] = [regex]::Replace(
            $clone[0],
            'external_slot_[0-9]+',
            "external_slot_$slotId",
            1
        )
        $clone = Set-DirectInlineValue $clone 'position' "{ $($layoutSlot.X)% $($layoutSlot.Y)% }"
        $clone = Set-DirectInlineValue $clone 'size' "{ $($layoutSlot.Width)% $($layoutSlot.Height)% }"
        $renderItems.Add([pscustomobject]@{
            SortY = [double]$layoutSlot.Y
            SortX = [double]$layoutSlot.X
            Lines = $clone
        })
    }

    $newSlots = [Collections.Generic.List[string]]::new()
    $newSlots.Add("`tdomicile_building_slots = {")
    $orderedItems = @($renderItems | Sort-Object SortY, SortX)
    for ($index = 0; $index -lt $orderedItems.Count; $index++) {
        foreach ($line in $orderedItems[$index].Lines) { $newSlots.Add($line) }
        if ($index -lt ($orderedItems.Count - 1)) { $newSlots.Add('') }
    }
    $newSlots.Add("`t}")
    $typeLines = Replace-DirectBlock $typeLines 'domicile_building_slots' $newSlots.ToArray()
    $validationSlotsBlock = Get-DirectBlock $typeLines 'domicile_building_slots'
    for ($slot = 1; $slot -le $layoutSlots.Count; $slot++) {
        if (@(Get-DirectBlock $validationSlotsBlock "external_slot_$slot").Count -eq 0) {
            throw "Generated type $domicileId is missing external_slot_$slot."
        }
    }
    if (@(Get-DirectBlock $validationSlotsBlock "external_slot_$($layoutSlots.Count + 1)").Count -ne 0) {
        throw "Generated type $domicileId has an unexpected extra external slot."
    }
    $generatedTypeBlocks.Add([pscustomobject]@{
        Id = $domicileId
        SourceFile = $sourcePath
        StartLine = [int]($typeOverride.VanillaSource -replace '^.*:', '')
        Lines = $typeLines
        TargetFile = $typeOverride.TargetOverrideFile
    })
}

# Remove only the 23 purpose-change cleanup blocks from the vanilla event.
$eventReference = @(
    Convert-ToArray $manifest.DomicileRemovalReferences |
        Where-Object { $_.Category -eq 'camp_purpose_change_cleanup' }
) | Select-Object -First 1
if ($null -eq $eventReference) { throw 'No camp-purpose cleanup event reference in manifest.' }
$eventLines = Get-VanillaObjectLines $eventReference.SourceFile $plan.RemovalOverrides.Suppress.TargetEvent
foreach ($purpose in Convert-ToArray $plan.ConditionalOverrides.CampPurpose) {
    foreach ($buildingId in Convert-ToArray $purpose.Buildings) {
        $eventLines = Remove-ContainingNamedBlock `
            $eventLines `
            'if' `
            "remove_domicile_building = $buildingId"
    }
}

# Semantic post-transform validation. These checks intentionally repeat the
# plan from the generated in-memory objects, so a future generator regression
# cannot silently produce syntactically valid but functionally wrong output.
foreach ($domicileOverride in Convert-ToArray $plan.DomicileTypeOverrides) {
    foreach ($change in Convert-ToArray $domicileOverride.MainTrackCapacityChanges) {
        $text = $buildingLines[$change.Building] -join "`n"
        $values = @(
            [regex]::Matches($text, '(?m)^\s*domicile_external_slots_capacity_add\s*=\s*([^\s#]+)') |
                ForEach-Object { $_.Groups[1].Value }
        )
        if ([int]$change.TargetCapacityAdd -eq 0) {
            if ($values.Count -ne 0) {
                throw "Capacity modifier remains on $($change.Building)."
            }
        }
        elseif ($values.Count -ne 1 -or [int]$values[0] -ne [int]$change.TargetCapacityAdd) {
            throw "Wrong generated capacity modifier on $($change.Building)."
        }
    }
}
foreach ($slotOverride in Convert-ToArray $plan.InternalSlotOverrides) {
    foreach ($change in Convert-ToArray $slotOverride.BuildingChanges) {
        $actual = Get-DirectScalarValue $buildingLines[$change.Building] 'internal_slots'
        if ([int]$actual -ne [int]$change.TargetInternalSlots) {
            throw "Wrong generated internal_slots on $($change.Building): $actual."
        }
    }
}
foreach ($branch in Convert-ToArray $plan.ExternalBranchOverrides) {
    foreach ($buildingId in Convert-ToArray $branch.BuildingsChangingSlotType) {
        if ((Get-DirectScalarValue $buildingLines[$buildingId] 'slot_type') -ne 'internal') {
            throw "External specialization '$buildingId' was not converted to internal."
        }
    }
}
foreach ($branch in Convert-ToArray $plan.InternalBranchOverrides) {
    foreach ($specialization in Convert-ToArray $branch.Specializations) {
        $rootId = $specialization.Root
        if ((Get-DirectScalarValue $buildingLines[$rootId] 'previous_building') -ne $specialization.ReplacePreviousBuilding.To) {
            throw "Internal specialization '$rootId' has the wrong new anchor."
        }
        $conditionText = (Get-DirectBlock $buildingLines[$rootId] 'can_construct') -join "`n"
        if ($conditionText -notmatch ('has_domicile_building_or_higher\s*=\s*' + [regex]::Escape($branch.SharedPrefix[-1]))) {
            throw "Internal specialization '$rootId' lost its shared-prefix prerequisite."
        }
    }
}
foreach ($purpose in Convert-ToArray $plan.ConditionalOverrides.CampPurpose) {
    foreach ($buildingId in Convert-ToArray $purpose.Buildings) {
        if (@(Get-DirectBlock $buildingLines[$buildingId] 'can_construct').Count -ne 0) {
            throw "Camp-purpose gate remains on '$buildingId'."
        }
    }
}
foreach ($track in Convert-ToArray $plan.ConditionalOverrides.CultureTerritoryAndSpecialAccess) {
    if ($track.Decision -ne 'targeted_remove_specialization_access_gate') { continue }
    foreach ($profile in Convert-ToArray $track.BuildingProfiles) {
        $sourceCondition = $null
        $field = $null
        if (-not [string]::IsNullOrWhiteSpace([string]$profile.ExistingCanConstruct)) {
            $sourceCondition = [string]$profile.ExistingCanConstruct
            $field = 'can_construct'
        }
        elseif (-not [string]::IsNullOrWhiteSpace([string]$profile.ExistingCanConstructPotential)) {
            $sourceCondition = [string]$profile.ExistingCanConstructPotential
            $field = 'can_construct_potential'
        }
        if ($null -eq $sourceCondition -or $sourceCondition -notmatch $accessGatePattern) { continue }
        $generatedCondition = (Get-DirectBlock $buildingLines[$profile.Building] $field) -join "`n"
        if ($generatedCondition -match $accessGatePattern) {
            throw "Special access gate remains on '$($profile.Building)'."
        }
        $sourceMainRequirement = [regex]::Match(
            $sourceCondition,
            'has_domicile_building_or_higher\s*=\s*([A-Za-z0-9_]+)'
        )
        if (
            $sourceMainRequirement.Success -and
            $generatedCondition -notmatch (
                'has_domicile_building_or_higher\s*=\s*' +
                [regex]::Escape($sourceMainRequirement.Groups[1].Value)
            )
        ) {
            throw "Main-building progression was lost on '$($profile.Building)'."
        }
    }
}
if (
    ((Get-DirectBlock $buildingLines['proving_grounds_elephantry_reserve'] 'can_construct') -join "`n") -notmatch
    'has_character_flag\s*=\s*recently_ate_elephants'
) {
    throw 'The elephant-reserve temporary character-state restriction was lost.'
}
foreach ($purpose in Convert-ToArray $plan.ConditionalOverrides.CampPurpose) {
    foreach ($buildingId in Convert-ToArray $purpose.Buildings) {
        if (($eventLines -join "`n") -match ('remove_domicile_building\s*=\s*' + [regex]::Escape($buildingId))) {
            throw "Purpose cleanup for '$buildingId' remains in generated event."
        }
    }
}

$headerLines = @(
    '############################################################',
    '# GENERATED FILE - DO NOT EDIT BY HAND',
    '# Generator: tools/Generate-RBUDOverrides.ps1',
    "# CK3: $($manifest.GameVersion)",
    "# Plan SHA-256: $($planWrapper.PlanSha256)",
    '############################################################',
    ''
)

$generatedFiles = [Collections.Generic.List[object]]::new()

# Write domicile types.
$typeGroups = $generatedTypeBlocks | Group-Object TargetFile
foreach ($group in $typeGroups) {
    $content = [Collections.Generic.List[string]]::new()
    foreach ($line in $headerLines) { $content.Add($line) }
    $objects = @($group.Group | Sort-Object SourceFile, StartLine, Id)
    for ($index = 0; $index -lt $objects.Count; $index++) {
        foreach ($line in $objects[$index].Lines) { $content.Add($line) }
        if ($index -lt ($objects.Count - 1)) { $content.Add('') }
    }
    $targetPath = Convert-ToGeneratedPath $group.Name
    $text = ($content -join "`r`n") + "`r`n"
    Write-GeneratedText $targetPath $text $false
    $generatedFiles.Add([pscustomobject]@{
        Path = $group.Name
        ObjectCount = $objects.Count
        Sha256 = Get-StringSha256 $text
    })
}

# Write only building objects whose text actually changed.
$changedBuildingObjects = [Collections.Generic.List[object]]::new()
foreach ($buildingId in @($buildingLines.Keys | Sort-Object)) {
    $newText = $buildingLines[$buildingId] -join "`n"
    if ($newText -eq $originalBuildingText[$buildingId]) { continue }
    $record = $buildingRecordById[$buildingId]
    $domicileId = @(Convert-ToArray $record.AllowedDomicileTypes) | Select-Object -First 1
    $targetOverride = $plan.DomicileTypeOverrides |
        Where-Object { $_.DomicileType -eq $domicileId } |
        Select-Object -First 1
    if ($null -eq $targetOverride) { throw "No target type override for building $buildingId." }
    $targetFile = $plan.TargetFiles.DomicileBuildings |
        Where-Object { $_ -match ([regex]::Escape($domicileId)) } |
        Select-Object -First 1
    if ($null -eq $targetFile) {
        $targetFile = $plan.ExternalBranchOverrides |
            Where-Object { $_.DomicileType -eq $domicileId } |
            Select-Object -First 1 -ExpandProperty TargetOverrideFile
    }
    if ($null -eq $targetFile) {
        # Camp/yurt/Japanese may have no external branch; use the deterministic
        # target file declared by an internal-slot or condition override.
        $candidate = @(
            $plan.InternalSlotOverrides |
                Where-Object { $_.DomicileType -eq $domicileId } |
                Select-Object -First 1
        )
        if ($candidate.Count -gt 0) { $targetFile = $candidate[0].TargetOverrideFile }
    }
    if ($null -eq $targetFile) { throw "Cannot resolve output file for building $buildingId ($domicileId)." }
    $changedBuildingObjects.Add([pscustomobject]@{
        Id = $buildingId
        SourceFile = $record.SourceFile
        StartLine = [int]$record.StartLine
        Lines = $buildingLines[$buildingId]
        TargetFile = $targetFile
    })
}

foreach ($group in ($changedBuildingObjects | Group-Object TargetFile)) {
    $content = [Collections.Generic.List[string]]::new()
    foreach ($line in $headerLines) { $content.Add($line) }
    $objects = @($group.Group | Sort-Object SourceFile, StartLine, Id)
    for ($index = 0; $index -lt $objects.Count; $index++) {
        foreach ($line in $objects[$index].Lines) { $content.Add($line) }
        if ($index -lt ($objects.Count - 1)) { $content.Add('') }
    }
    $targetPath = Convert-ToGeneratedPath $group.Name
    $text = ($content -join "`r`n") + "`r`n"
    Write-GeneratedText $targetPath $text $false
    $generatedFiles.Add([pscustomobject]@{
        Path = $group.Name
        ObjectCount = $objects.Count
        Sha256 = Get-StringSha256 $text
    })
}

# Write event override.
$eventContent = [Collections.Generic.List[string]]::new()
foreach ($line in $headerLines) { $eventContent.Add($line) }
$eventContent.Add('namespace = ep3_laamps')
$eventContent.Add('')
foreach ($line in $eventLines) { $eventContent.Add($line) }
$eventTargetPath = Convert-ToGeneratedPath $plan.TargetFiles.CampPurposeEvent
$eventText = ($eventContent -join "`r`n") + "`r`n"
Write-GeneratedText $eventTargetPath $eventText $false
$generatedFiles.Add([pscustomobject]@{
    Path = $plan.TargetFiles.CampPurposeEvent
    ObjectCount = 1
    Sha256 = Get-StringSha256 $eventText
})

# Parse every emitted database/event file again. This catches broken braces and
# duplicate objects inside a generated file before the game sees it.
foreach ($generatedFile in $generatedFiles) {
    $fullPath = Convert-ToGeneratedPath $generatedFile.Path
    $parsed = Get-TopLevelBlocks (Get-Content -LiteralPath $fullPath -Encoding UTF8) $generatedFile.Path
    if ($parsed.Count -ne [int]$generatedFile.ObjectCount) {
        throw "Generated object-count mismatch in $($generatedFile.Path): expected $($generatedFile.ObjectCount), parsed $($parsed.Count)."
    }
}

$generationManifest = [ordered]@{
    SchemaVersion = 1
    GeneratedAtUtc = [DateTime]::UtcNow.ToString('o')
    GameVersion = $manifest.GameVersion
    PlanSha256 = $planWrapper.PlanSha256
    VanillaSignatures = $manifest.VanillaSignatures
    InputHashValidation = 'passed'
    LayoutSchemaVersion = $layoutConfig.SchemaVersion
    GeneratedFiles = @($generatedFiles | Sort-Object Path)
    GeneratedDomicileTypeCount = $generatedTypeBlocks.Count
    GeneratedBuildingObjectCount = $changedBuildingObjects.Count
    RewrittenSpecialAccessBuildingCount = @($rewrittenAccessBuildings | Sort-Object -Unique).Count
    RemovedCampPurposeCleanupCount = @(Convert-ToArray $plan.ConditionalOverrides.CampPurpose).Count
    Validation = [ordered]@{
        BracesAndObjectCounts = 'passed'
        PlanSignature = 'passed'
        VanillaInputHashes = 'passed'
        ManualVisualValidationRequired = $true
    }
}
$generationManifestPath = Join-Path $ModPath 'tools\generated\RB_UD_generation_manifest.json'
$generationManifestText = $generationManifest | ConvertTo-Json -Depth 20 -Compress
Write-GeneratedText $generationManifestPath $generationManifestText $false

$report = [Collections.Generic.List[string]]::new()
$report.Add('# RB_UD generation report')
$report.Add('')
$report.Add("- CK3: **$($manifest.GameVersion)**")
$report.Add("- Plan: ``$($planWrapper.PlanSha256)``")
$report.Add('- Vanilla input hashes: **passed**')
$report.Add("- Generated domicile types: **$($generatedTypeBlocks.Count)**")
$report.Add("- Generated changed building objects: **$($changedBuildingObjects.Count)**")
$report.Add("- Rewritten specialization-access buildings: **$(@($rewrittenAccessBuildings | Sort-Object -Unique).Count)**")
$report.Add("- Disabled camp-purpose cleanup pairs: **$(@(Convert-ToArray $plan.ConditionalOverrides.CampPurpose).Count)**")
$report.Add('')
$report.Add('## Files')
$report.Add('')
$report.Add('| File | Objects | SHA-256 |')
$report.Add('|---|---:|---|')
foreach ($file in @($generatedFiles | Sort-Object Path)) {
    $report.Add("| ``$($file.Path)`` | $($file.ObjectCount) | ``$($file.Sha256)`` |")
}
$report.Add('')
$report.Add('## Required manual check')
$report.Add('')
$report.Add('The five domicile windows must be opened in game. Slot positions are deliberately stored in `tools/RB_UD_layouts.json`, so visual adjustments do not require changing the generator.')
$reportPath = Join-Path $ModPath 'docs\generated\RB_UD_GENERATION_REPORT.md'
Write-GeneratedText $reportPath (($report -join "`r`n") + "`r`n") $true

Write-Output "RB_UD gameplay overrides generated for CK3 $($manifest.GameVersion)."
Write-Output "Domicile types: $($generatedTypeBlocks.Count)"
Write-Output "Changed building objects: $($changedBuildingObjects.Count)"
Write-Output "Special-access rewrites: $(@($rewrittenAccessBuildings | Sort-Object -Unique).Count)"
Write-Output "Camp cleanup removals disabled: $(@(Convert-ToArray $plan.ConditionalOverrides.CampPurpose).Count)"
Write-Output "Generation manifest: $generationManifestPath"
Write-Output "Generation report:   $reportPath"
