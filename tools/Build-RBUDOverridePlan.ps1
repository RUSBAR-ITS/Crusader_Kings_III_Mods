[CmdletBinding()]
param(
    [string]$ManifestPath,
    [string]$ModPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
    $ManifestPath = Join-Path $repositoryRoot 'RB_UD\tools\generated\RB_UD_vanilla_manifest.json'
}
if ([string]::IsNullOrWhiteSpace($ModPath)) {
    $ModPath = Join-Path $repositoryRoot 'RB_UD'
}

$ManifestPath = [IO.Path]::GetFullPath($ManifestPath)
$ModPath = [IO.Path]::GetFullPath($ModPath)
$jsonOutputPath = Join-Path $ModPath 'tools\generated\RB_UD_override_plan.json'
$markdownOutputPath = Join-Path $ModPath 'docs\generated\RB_UD_OVERRIDE_PLAN.md'

function Convert-ToArray {
    param($Value)
    if ($null -eq $Value) { return @() }
    return @($Value)
}

function Get-Sha256 {
    param([Parameter(Mandatory = $true)][string]$Text)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '')
    }
    finally {
        $sha.Dispose()
    }
}

function Escape-MarkdownCell {
    param($Value)
    if ($null -eq $Value) { return '' }
    return ([string]$Value).Replace('|', '\|').Replace("`r", ' ').Replace("`n", '<br>')
}

function Add-MarkdownRow {
    param(
        [Collections.Generic.List[string]]$Lines,
        [Parameter(Mandatory = $true)][object[]]$Cells
    )
    $escaped = @($Cells | ForEach-Object { Escape-MarkdownCell $_ })
    $Lines.Add('| ' + ($escaped -join ' | ') + ' |')
}

function Get-AllowedDomicileId {
    param($Building)
    return @(Convert-ToArray $Building.AllowedDomicileTypes) | Select-Object -First 1
}

function Get-LinearAnchorMembers {
    param(
        [Parameter(Mandatory = $true)][string]$RootId,
        [Parameter(Mandatory = $true)][string]$DomicileId,
        [Parameter(Mandatory = $true)]$BuildingById,
        [Parameter(Mandatory = $true)]$ChildrenByParent
    )

    $members = [Collections.Generic.List[string]]::new()
    $currentId = $RootId
    $visited = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    while (-not [string]::IsNullOrWhiteSpace($currentId)) {
        if (-not $visited.Add($currentId)) {
            throw "Cycle encountered while resolving anchor track $RootId at $currentId."
        }
        if (-not $BuildingById.ContainsKey($currentId)) {
            throw "Unknown building $currentId while resolving anchor track $RootId."
        }

        $current = $BuildingById[$currentId]
        $members.Add($currentId)
        $children = @()
        if ($ChildrenByParent.ContainsKey($currentId)) {
            $children = @(
                $ChildrenByParent[$currentId] |
                    Where-Object {
                        $_.SlotType -eq $current.SlotType -and
                        (Get-AllowedDomicileId $_) -eq $DomicileId
                    } |
                    Sort-Object Tier, Id
            )
        }
        if ($children.Count -ne 1) { break }
        $currentId = $children[0].Id
    }
    return @($members)
}

if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    throw "Manifest not found: $ManifestPath"
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ([int]$manifest.SchemaVersion -lt 2) {
    throw "Manifest schema v2 or newer is required; got $($manifest.SchemaVersion)."
}

$fatalDiagnostics = @(
    @(Convert-ToArray $manifest.Diagnostics.GraphCycles).Count,
    @(Convert-ToArray $manifest.Diagnostics.DuplicateBuildingDefinitions).Count,
    @(Convert-ToArray $manifest.Diagnostics.DuplicateTypeDefinitions).Count,
    @(Convert-ToArray $manifest.Diagnostics.Transformation.SpecializationsMissingRootIcons).Count,
    @(Convert-ToArray $manifest.Diagnostics.Transformation.SpecializationsMissingRootTextures).Count,
    @(Convert-ToArray $manifest.Diagnostics.Transformation.UnclassifiedSameSlotBranchPoints).Count,
    @(Convert-ToArray $manifest.Diagnostics.Availability.UnresolvedScriptedTriggerReferences).Count,
    @(Convert-ToArray $manifest.Diagnostics.Availability.UnclassifiedConditionTracks).Count
)
if (($fatalDiagnostics | Measure-Object -Sum).Sum -ne 0) {
    throw 'The vanilla manifest contains unresolved diagnostics. Regenerate or fix Stage 1 before building the override plan.'
}
foreach ($domicile in $manifest.Domiciles) {
    if (@(Convert-ToArray $domicile.UnresolvedParents).Count -ne 0) {
        throw "Domicile $($domicile.Type.Id) contains unresolved previous_building references."
    }
}

$buildingById = @{}
$childrenByParent = @{}
foreach ($building in $manifest.Buildings) {
    $buildingById[$building.Id] = $building
    if (-not [string]::IsNullOrWhiteSpace([string]$building.PreviousBuilding)) {
        if (-not $childrenByParent.ContainsKey($building.PreviousBuilding)) {
            $childrenByParent[$building.PreviousBuilding] = [Collections.Generic.List[object]]::new()
        }
        $childrenByParent[$building.PreviousBuilding].Add($building)
    }
}

$targetExternalSlots = [ordered]@{
    camp = 7
    estate = 16
    yurt = 7
    east_asian_estate = 15
    japanese_manor = 12
}
$buildingOverrideFiles = [ordered]@{
    camp = 'common\domiciles\buildings\zzz_RB_UD_camp_<family>.txt'
    estate = 'common\domiciles\buildings\zzz_RB_UD_estate_<family>.txt'
    yurt = 'common\domiciles\buildings\zzz_RB_UD_yurt_<family>.txt'
    east_asian_estate = 'common\domiciles\buildings\zzz_RB_UD_east_asian_estate_<family>.txt'
    japanese_manor = 'common\domiciles\buildings\zzz_RB_UD_japanese_manor_<family>.txt'
}
$scriptedEffectOverrideFile = 'common\scripted_effects\zzz_RB_UD_domicile_effects.txt'

$domicileTypeOverrides = [Collections.Generic.List[object]]::new()
foreach ($domicile in $manifest.Domiciles) {
    $domicileId = $domicile.Type.Id
    if (-not $targetExternalSlots.Contains($domicileId)) {
        throw "No target external slot policy for domicile type $domicileId."
    }
    $target = [int]$targetExternalSlots[$domicileId]
    $base = [int]$domicile.Type.BaseExternalSlots
    $mainBuildings = @(
        $manifest.Buildings |
            Where-Object {
                $_.SlotType -eq 'main' -and
                (Get-AllowedDomicileId $_) -eq $domicileId
            } |
            Sort-Object Tier, Id
    )
    if ($mainBuildings.Count -eq 0) {
        throw "No main building track found for $domicileId."
    }

    $capacityChanges = [Collections.Generic.List[object]]::new()
    for ($index = 0; $index -lt $mainBuildings.Count; $index++) {
        $building = $mainBuildings[$index]
        $currentAdds = @(
            Convert-ToArray $building.ExternalCapacityAdds |
                ForEach-Object { [ordered]@{ Raw = $_.Raw; Numeric = $_.Numeric } }
        )
        $capacityChanges.Add([ordered]@{
            Building = $building.Id
            CurrentCapacityAdds = $currentAdds
            # base_external_slots is a pre-main-building fallback, not an
            # additive bonus on top of the inherited main-track capacity.
            # The first main level therefore receives the complete target.
            TargetCapacityAdd = $(if ($index -eq 0) { $target } else { 0 })
            Operation = $(if ($index -eq 0) { 'replace_with_full_capacity' } else { 'remove_later_capacity_additions' })
        })
    }

    $visualSlots = @()
    for ($slot = 1; $slot -le $target; $slot++) {
        $visualSlots += "external_slot_$slot"
    }
    $domicileTypeOverrides.Add([ordered]@{
        DomicileType = $domicileId
        VanillaSource = "$($domicile.Type.SourceFile):$($domicile.Type.StartLine)"
        TargetOverrideFile = 'common\domiciles\types\zzz_RB_UD_domicile_types.txt'
        CurrentVisualExternalSlots = [int]$domicile.CurrentVisualExternalSlots
        CurrentMaximumExternalCapacity = [int]$domicile.CurrentMaximumExternalCapacity
        TargetVisualExternalSlots = $target
        TargetMaximumExternalCapacity = $target
        BaseExternalSlots = $base
        TargetVisualSlotNames = $visualSlots
        LayoutStrategy = 'preserve_existing_slots_and_generate_balanced_additional_slots_then_validate_in_game'
        CapacityStrategy = 'grant_full_external_capacity_from_first_main_building'
        MainTrackCapacityChanges = @($capacityChanges)
        Preserve = @('main-building costs', 'effects', 'main progression requirements')
    })
}

# Expanding external capacity must not make vanilla history/setup effects fill
# every new slot. Preserve the number of buildings that vanilla would create at
# each main-building level by shifting the free-slot threshold by the capacity
# increase at that level. Every generated while loop also receives a hard cap.
$fillEffectPolicies = [ordered]@{
    fill_external_estate_building_effect = [ordered]@{
        DomicileType = 'estate'
        CalledEffect = 'add_random_external_estate_building'
    }
    fill_external_east_asian_estate_building_effect = [ordered]@{
        DomicileType = 'east_asian_estate'
        CalledEffect = 'add_random_external_east_asian_estate_building'
    }
    fill_external_japanese_manor_building_effect = [ordered]@{
        DomicileType = 'japanese_manor'
        CalledEffect = 'add_random_external_japanese_manor_building'
    }
}
$initialFillEffectOverrides = [Collections.Generic.List[object]]::new()
foreach ($fillEffect in Convert-ToArray $manifest.FillEffects) {
    if (-not $fillEffectPolicies.Contains($fillEffect.Id)) {
        throw "No RB_UD initial-fill policy for $($fillEffect.Id)."
    }
    $policy = $fillEffectPolicies[$fillEffect.Id]
    $typeOverride = @(
        $domicileTypeOverrides |
            Where-Object { $_.DomicileType -eq $policy.DomicileType }
    ) | Select-Object -First 1
    if ($null -eq $typeOverride) {
        throw "No domicile capacity plan for fill effect $($fillEffect.Id)."
    }

    $thresholds = @(Convert-ToArray $fillEffect.FreeSlotThresholds)
    $mainChanges = @(Convert-ToArray $typeOverride.MainTrackCapacityChanges)
    if ($thresholds.Count -gt $mainChanges.Count) {
        throw "Fill effect $($fillEffect.Id) has more branches than its main track."
    }

    $capacityByBuilding = @{}
    $currentCapacity = 0
    foreach ($change in $mainChanges) {
        $currentAdd = 0
        foreach ($add in Convert-ToArray $change.CurrentCapacityAdds) {
            if ($null -ne $add.Numeric) { $currentAdd += [int]$add.Numeric }
        }
        $currentCapacity += $currentAdd
        $capacityByBuilding[$change.Building] = [Math]::Max(
            [int]$typeOverride.BaseExternalSlots,
            $currentCapacity
        )
    }

    # Vanilla switches list the highest handled main tier first. The analyzer
    # records thresholds in that same order, while capacity changes are sorted
    # from the first main tier upwards.
    $handledMainChanges = @($mainChanges | Select-Object -First $thresholds.Count)
    [array]::Reverse($handledMainChanges)
    $branches = [Collections.Generic.List[object]]::new()
    for ($index = 0; $index -lt $thresholds.Count; $index++) {
        $thresholdText = [string]$thresholds[$index]
        if ($thresholdText -notmatch '>=\s*([0-9]+)') {
            throw "Unsupported free-slot threshold '$thresholdText' in $($fillEffect.Id)."
        }
        $originalThreshold = [int]$Matches[1]
        $mainBuilding = [string]$handledMainChanges[$index].Building
        $originalCapacity = [int]$capacityByBuilding[$mainBuilding]
        $targetCapacity = [int]$typeOverride.TargetMaximumExternalCapacity
        $branches.Add([ordered]@{
            MainBuilding = $mainBuilding
            OriginalCapacity = $originalCapacity
            TargetCapacity = $targetCapacity
            OriginalFreeSlotThreshold = $originalThreshold
            TargetFreeSlotThreshold = $originalThreshold + ($targetCapacity - $originalCapacity)
            MaximumIterations = $targetCapacity
        })
    }

    $initialFillEffectOverrides.Add([ordered]@{
        Effect = $fillEffect.Id
        DomicileType = $policy.DomicileType
        VanillaSource = "$($fillEffect.SourceFile):$($fillEffect.StartLine)"
        TargetOverrideFile = $scriptedEffectOverrideFile
        CalledEffect = $policy.CalledEffect
        Branches = @($branches)
        Strategy = 'preserve_vanilla_initial_building_count_after_capacity_expansion'
    })
}

$slotTargets = @{}
foreach ($domicile in $manifest.Domiciles) {
    $domicileId = $domicile.Type.Id
    foreach ($requirement in Convert-ToArray $domicile.InternalAnchorRequirements) {
        $key = "$domicileId|$($requirement.AnchorTrack)"
        $slotTargets[$key] = [ordered]@{
            DomicileType = $domicileId
            AnchorTrack = $requirement.AnchorTrack
            TargetInternalSlots = [int]$requirement.RequiredSlotsForAllBranches
            Reasons = [Collections.Generic.List[string]]::new()
        }
        $slotTargets[$key].Reasons.Add('all_existing_internal_tracks_can_coexist')
    }
    foreach ($group in Convert-ToArray $domicile.ExternalBranchGroups) {
        $key = "$domicileId|$($group.AnchorTrack)"
        if (-not $slotTargets.ContainsKey($key)) {
            $slotTargets[$key] = [ordered]@{
                DomicileType = $domicileId
                AnchorTrack = $group.AnchorTrack
                TargetInternalSlots = 0
                Reasons = [Collections.Generic.List[string]]::new()
            }
        }
        $slotTargets[$key].TargetInternalSlots = [Math]::Max(
            [int]$slotTargets[$key].TargetInternalSlots,
            [int]$group.RequiredInternalSlotsAfterTransformation
        )
        $slotTargets[$key].Reasons.Add("internalize_external_branch_at_$($group.CommonBuilding)")
    }
}

# The estate library has one shared prerequisite line plus two specialization
# lines. Keeping the shared line avoids duplicating its effects and needs one
# more slot than a simple leaf count.
$estateMainKey = 'estate|estate_main_01'
if (-not $slotTargets.ContainsKey($estateMainKey)) {
    throw 'The estate main internal-slot anchor is missing from the manifest.'
}
$slotTargets[$estateMainKey].TargetInternalSlots = [int]$slotTargets[$estateMainKey].TargetInternalSlots + 1
$slotTargets[$estateMainKey].Reasons.Add('keep_library_shared_prefix_plus_two_parallel_specializations')

$externalBranchOverrides = [Collections.Generic.List[object]]::new()
foreach ($domicile in $manifest.Domiciles) {
    $domicileId = $domicile.Type.Id
    foreach ($group in Convert-ToArray $domicile.ExternalBranchGroups) {
        $specializationBuildings = @(
            Convert-ToArray $group.Specializations |
                ForEach-Object { Convert-ToArray $_.Buildings } |
                Sort-Object -Unique
        )
        $externalBranchOverrides.Add([ordered]@{
            DomicileType = $domicileId
            VanillaSource = "$($group.SourceFile):$($group.StartLine)"
            TargetOverrideFile = $buildingOverrideFiles[$domicileId]
            AnchorTrack = $group.AnchorTrack
            CommonBuilding = $group.CommonBuilding
            CommonExternalPrefix = @(Convert-ToArray $group.CommonExternalPrefix)
            SpecializationRoots = @(Convert-ToArray $group.Specializations | ForEach-Object { $_.Root })
            RootPreviousBuilding = [string](Convert-ToArray $group.CommonExternalPrefix)[0]
            RequiredCommonBuilding = [string]$group.CommonBuilding
            RootConstructionPrerequisite = "domicile ?= { has_domicile_building_or_higher = $($group.CommonBuilding) }"
            BuildingsChangingSlotType = $specializationBuildings
            Change = 'set slot_type = internal on every specialization-tail building'
            PreviousBuildingPolicy = 'reanchor specialization roots to the first common external building; preserve the former common tier as a construction prerequisite; descendants retain their upgrade chain'
            RemoveInternalSlotsFromConvertedBuildings = $true
            RequiredInternalSlotsOnAnchor = [int]$group.RequiredInternalSlotsAfterTransformation
            Preserve = @('building IDs', 'icons', 'panorama textures', 'costs', 'effects', 'upgrade order', 'non-exclusivity prerequisites')
        })
    }
}

$internalBranchOverrides = [Collections.Generic.List[object]]::new()
foreach ($domicile in $manifest.Domiciles) {
    foreach ($group in Convert-ToArray $domicile.InternalBranchGroups) {
        $specializationChanges = @()
        foreach ($specialization in Convert-ToArray $group.Specializations) {
            $specializationChanges += [ordered]@{
                Root = $specialization.Root
                Buildings = @(Convert-ToArray $specialization.Buildings)
                ReplacePreviousBuilding = [ordered]@{
                    From = $group.CommonBuilding
                    To = $group.AnchorBuilding
                }
                AddConstructionPrerequisite = "domicile ?= { has_domicile_building_or_higher = $($group.CommonBuilding) }"
            }
        }
        $internalBranchOverrides.Add([ordered]@{
            DomicileType = $domicile.Type.Id
            VanillaSource = "$($group.SourceFile):$($group.StartLine)"
            TargetOverrideFile = $buildingOverrideFiles[$domicile.Type.Id]
            Strategy = 'preserve_shared_prefix_as_prerequisite_and_reanchor_specializations_in_parallel'
            AnchorBuilding = $group.AnchorBuilding
            SharedPrefix = @(Convert-ToArray $group.SharedInternalPrefix)
            SharedPrefixPolicy = 'keep as one separately buildable internal track with unchanged effects'
            Specializations = $specializationChanges
            RequiredInternalSlotsOnAnchor = [int]$slotTargets["$($domicile.Type.Id)|$($group.AnchorBuilding)"].TargetInternalSlots
        })
    }
}

$internalSlotOverrides = [Collections.Generic.List[object]]::new()
foreach ($key in @($slotTargets.Keys | Sort-Object)) {
    $entry = $slotTargets[$key]
    $domicile = $manifest.Domiciles | Where-Object { $_.Type.Id -eq $entry.DomicileType } | Select-Object -First 1
    $branchGroup = @(
        Convert-ToArray $domicile.ExternalBranchGroups |
            Where-Object { $_.AnchorTrack -eq $entry.AnchorTrack }
    ) | Select-Object -First 1
    if ($null -ne $branchGroup) {
        $members = @(Convert-ToArray $branchGroup.CommonExternalPrefix)
    }
    else {
        $members = @(Get-LinearAnchorMembers $entry.AnchorTrack $entry.DomicileType $buildingById $childrenByParent)
    }

    $memberChanges = @()
    foreach ($memberId in $members) {
        $building = $buildingById[$memberId]
        $memberChanges += [ordered]@{
            Building = $memberId
            CurrentInternalSlots = $building.InternalSlots
            TargetInternalSlots = [int]$entry.TargetInternalSlots
        }
    }
    $internalSlotOverrides.Add([ordered]@{
        DomicileType = $entry.DomicileType
        TargetOverrideFile = $buildingOverrideFiles[$entry.DomicileType]
        AnchorTrack = $entry.AnchorTrack
        AnchorMembers = $members
        TargetInternalSlotsAtEveryAnchorLevel = [int]$entry.TargetInternalSlots
        BuildingChanges = $memberChanges
        Reasons = @($entry.Reasons | Sort-Object -Unique)
        Strategy = 'grant_complete_internal_capacity_on_every_level_of_the_anchor_line'
    })
}

$campPurposeOverrides = [Collections.Generic.List[object]]::new()
foreach ($item in Convert-ToArray $manifest.CampPurposeCompatibility) {
    $campPurposeOverrides.Add([ordered]@{
        RealmLawFlag = $item.RealmLawFlag
        Buildings = @(Convert-ToArray $item.Buildings)
        AffectedTracks = @(Convert-ToArray $item.AffectedTracks)
        BuildingAction = 'remove only the matching camp-purpose realm-law gate'
        CleanupContainers = @(Convert-ToArray $item.CleanupContainers)
        CleanupAction = 'disable the dedicated purpose-change cleanup scripted effect; do not override its event ID'
        Preserve = @('all other building prerequisites', 'all other event commands', 'full camp liquidation', 'targeted gameplay removals')
    })
}

$manualConditionOverrides = [Collections.Generic.List[object]]::new()
foreach ($domicile in $manifest.Domiciles) {
    foreach ($track in @(Convert-ToArray $domicile.ConditionalAvailability.Tracks | Where-Object { $_.RequiresManualReview })) {
        $notes = [Collections.Generic.List[string]]::new()
        $notes.Add('Keep every vanilla can_construct and can_construct_potential prerequisite unchanged.')
        $notes.Add('Mutual exclusivity is removed structurally by parallelizing branch tracks, not by weakening their availability rules.')
        $notes.Add('Culture, innovation, terrain, region, character-state, language-count, main-tier and other independent requirements remain mandatory.')

        $dependencySummary = [ordered]@{}
        foreach ($property in $track.Dependencies.PSObject.Properties) {
            $values = @(Convert-ToArray $property.Value)
            if ($values.Count -gt 0) {
                $dependencySummary[$property.Name] = $values
            }
        }
        $profiles = @()
        foreach ($profile in Convert-ToArray $track.BuildingProfiles) {
            $building = $buildingById[$profile.Building]
            $profiles += [ordered]@{
                Building = $profile.Building
                VanillaSource = "$($profile.SourceFile):$($profile.StartLine)"
                ExistingCanConstruct = $(if ($null -ne $building.Availability.CanConstruct) { $building.Availability.CanConstruct.Script } else { $null })
                ExistingCanConstructPotential = $(if ($null -ne $building.Availability.CanConstructPotential) { $building.Availability.CanConstructPotential.Script } else { $null })
            }
        }
        $manualConditionOverrides.Add([ordered]@{
            DomicileType = $domicile.Type.Id
            TargetOverrideFile = $buildingOverrideFiles[$domicile.Type.Id]
            TrackRoot = $track.TrackRoot
            SlotType = $track.SlotType
            AnchorTrack = $track.AnchorTrack
            Decision = 'preserve_entire_vanilla_condition'
            RemoveCategories = @()
            PreserveCategories = @(Convert-ToArray $track.RestrictionCategories)
            Dependencies = $dependencySummary
            ConditionalBuildings = @(Convert-ToArray $track.ConditionalBuildings)
            BuildingProfiles = $profiles
            Notes = @($notes)
        })
    }
}

$preservedRemovalCategories = @(
    Convert-ToArray $manifest.RemovalSummary |
        Where-Object { $_.Category -ne 'camp_purpose_change_cleanup' } |
        ForEach-Object {
            [ordered]@{
                Category = $_.Category
                ReferenceCount = $_.ReferenceCount
                UniqueBuildingCount = $_.UniqueBuildingCount
                Containers = @(Convert-ToArray $_.Containers)
                Policy = 'preserve unchanged'
            }
        }
)

$affectedBuildingIds = @(
    @($domicileTypeOverrides | ForEach-Object { $_.MainTrackCapacityChanges.Building }) +
    @($internalSlotOverrides | ForEach-Object { $_.BuildingChanges.Building }) +
    @($externalBranchOverrides | ForEach-Object { $_.BuildingsChangingSlotType }) +
    @($internalBranchOverrides | ForEach-Object { $_.Specializations.Buildings }) +
    @($campPurposeOverrides | ForEach-Object { $_.Buildings }) +
    @($manualConditionOverrides | Where-Object { $_.Decision -ne 'preserve_entire_vanilla_condition' } | ForEach-Object { $_.ConditionalBuildings }) |
        Sort-Object -Unique
)

$validation = [ordered]@{
    ManifestHasNoFatalDiagnostics = $true
    ExpectedDomicileTypes = $targetExternalSlots.Count
    PlannedDomicileTypes = $domicileTypeOverrides.Count
    ExpectedInitialFillEffects = $fillEffectPolicies.Count
    PlannedInitialFillEffects = $initialFillEffectOverrides.Count
    ExpectedExternalBranchGroups = [int]$manifest.TransformationSummary.ExternalBranchGroupCount
    PlannedExternalBranchGroups = $externalBranchOverrides.Count
    ExpectedInternalBranchGroups = [int]$manifest.TransformationSummary.InternalBranchGroupCount
    PlannedInternalBranchGroups = $internalBranchOverrides.Count
    ExpectedCampPurposeFlags = @(Convert-ToArray $manifest.CampPurposeFlags).Count
    PlannedCampPurposeFlags = $campPurposeOverrides.Count
    ExpectedManualConditionTracks = [int]$manifest.ConditionalCompatibilitySummary.ManualReviewTrackCount
    PlannedManualConditionTracks = $manualConditionOverrides.Count
    PreservedManualConditionTracks = @($manualConditionOverrides | Where-Object { $_.Decision -eq 'preserve_entire_vanilla_condition' }).Count
    RewrittenManualConditionTracks = @($manualConditionOverrides | Where-Object { $_.Decision -ne 'preserve_entire_vanilla_condition' }).Count
}
if ($validation.ExpectedDomicileTypes -ne $validation.PlannedDomicileTypes -or
    $validation.ExpectedInitialFillEffects -ne $validation.PlannedInitialFillEffects -or
    $validation.ExpectedExternalBranchGroups -ne $validation.PlannedExternalBranchGroups -or
    $validation.ExpectedInternalBranchGroups -ne $validation.PlannedInternalBranchGroups -or
    $validation.ExpectedCampPurposeFlags -ne $validation.PlannedCampPurposeFlags -or
    $validation.ExpectedManualConditionTracks -ne $validation.PlannedManualConditionTracks) {
    throw 'Override plan coverage validation failed.'
}

$planCore = [ordered]@{
    SchemaVersion = 2
    Status = 'generation_ready'
    SourceManifest = [ordered]@{
        Path = 'tools/generated/RB_UD_vanilla_manifest.json'
        SchemaVersion = $manifest.SchemaVersion
        GameVersion = $manifest.GameVersion
        VanillaSignatures = $manifest.VanillaSignatures
    }
    Principles = @(
        'Mirror all vanilla domicile-building objects; never use replace_path.',
        'Emit one generated file per vanilla root family and exactly one copy of every vanilla building.',
        'Vanilla objects retain vanilla IDs; new helper objects use the RB_UD_ prefix.',
        'Preserve vanilla construction time through generated file-local RB_UD_ @ constants because this database field rejects global script values.',
        'Preserve vanilla costs, effects, upgrade order, culture, innovation, territory, terrain and all other independent prerequisites.',
        'Remove branch mutual exclusivity structurally; remove only camp-purpose gates and their targeted purpose-change cleanup.',
        'Grant complete slot capacity from the first main or anchor level; base_external_slots is a pre-main fallback and is not subtracted from that target.',
        'No mass-build action and no construction-speed modifier are part of this mod.'
    )
    TargetFiles = [ordered]@{
        DomicileTypes = 'common/domiciles/types/zzz_RB_UD_domicile_types.txt'
        DomicileBuildings = @($buildingOverrideFiles.Values)
        ScriptedEffects = $scriptedEffectOverrideFile
        ReplacePath = $false
    }
    DomicileTypeOverrides = @($domicileTypeOverrides)
    InitialFillEffectOverrides = @($initialFillEffectOverrides)
    InternalSlotOverrides = @($internalSlotOverrides)
    ExternalBranchOverrides = @($externalBranchOverrides)
    InternalBranchOverrides = @($internalBranchOverrides)
    ConditionalOverrides = [ordered]@{
        CampPurpose = @($campPurposeOverrides)
        CultureTerritoryAndSpecialAccess = @($manualConditionOverrides)
        DefaultPolicyForAllOtherConditions = 'preserve unchanged'
    }
    RemovalOverrides = [ordered]@{
        Suppress = [ordered]@{
            Category = 'camp_purpose_change_cleanup'
            TargetScriptedEffect = 'laamp_clear_inappropriate_buildings_effect'
            VanillaSource = 'common\scripted_effects\00_laamp_effects.txt:765'
            ReferenceCount = @(Convert-ToArray $manifest.DomicileRemovalReferences | Where-Object { $_.Category -eq 'camp_purpose_change_cleanup' }).Count
            Policy = 'override the dedicated cleanup scripted effect with an empty effect; preserve ep3_laamps.1021 for all other callers'
        }
        Preserve = $preservedRemovalCategories
    }
    ObjectInventory = [ordered]@{
        OverriddenDomicileTypeIds = @($targetExternalSlots.Keys)
        AffectedVanillaBuildingCount = $affectedBuildingIds.Count
        AffectedVanillaBuildingIds = $affectedBuildingIds
        MirroredVanillaBuildingCount = @(Convert-ToArray $manifest.Buildings).Count
        OverriddenVanillaEventIds = @()
        OverriddenVanillaScriptedEffectIds = @(
            @($initialFillEffectOverrides | ForEach-Object { $_.Effect }) +
            @('laamp_clear_inappropriate_buildings_effect')
        )
        PlannedNewHelperObjects = @()
    }
    Validation = $validation
    RemainingImplementationChecks = @(
        'Visually test all five generated domicile windows after gameplay generation.',
        'Verify construction time and every split specialization family in game.',
        'Run CK3 with error.log and debug.log checks after each domicile family is enabled.',
        'Regenerate Stage 1 and this plan after every supported CK3 update; signatures must be reviewed before code regeneration.'
    )
}

$coreJson = $planCore | ConvertTo-Json -Depth 100 -Compress
$planSignature = Get-Sha256 $coreJson
$plan = [ordered]@{
    GeneratedAtUtc = [DateTime]::UtcNow.ToString('o')
    PlanSha256 = $planSignature
    Plan = $planCore
}

$jsonDirectory = Split-Path -Parent $jsonOutputPath
$markdownDirectory = Split-Path -Parent $markdownOutputPath
[IO.Directory]::CreateDirectory($jsonDirectory) | Out-Null
[IO.Directory]::CreateDirectory($markdownDirectory) | Out-Null
$utf8NoBom = [Text.UTF8Encoding]::new($false)
$utf8Bom = [Text.UTF8Encoding]::new($true)
[IO.File]::WriteAllText($jsonOutputPath, ($plan | ConvertTo-Json -Depth 100 -Compress), $utf8NoBom)

$lines = [Collections.Generic.List[string]]::new()
$lines.Add('# RB_UD — план переопределений ванильных домицилей')
$lines.Add('')
$lines.Add("Версия CK3: **$($manifest.GameVersion)**. Сигнатура плана: ``$planSignature``.")
$lines.Add('')
$lines.Add('Документ определяет точные объекты и преобразования, которые затем воспроизводимо применяет генератор `tools/Generate-RBUDOverrides.ps1`.')
$lines.Add('')
$lines.Add('## Принципы')
$lines.Add('')
foreach ($principle in $planCore.Principles) { $lines.Add("- $principle") }
$lines.Add('')
$lines.Add('## Типы домицилей и внешняя ёмкость')
$lines.Add('')
$lines.Add('| Тип | Видимых сейчас | Максимум сейчас | Цель | Добавка на первом главном здании | Последующие добавки |')
$lines.Add('|---|---:|---:|---:|---:|---|')
foreach ($entry in $domicileTypeOverrides) {
    Add-MarkdownRow $lines @(
        $entry.DomicileType,
        $entry.CurrentVisualExternalSlots,
        $entry.CurrentMaximumExternalCapacity,
        $entry.TargetVisualExternalSlots,
        $entry.MainTrackCapacityChanges[0].TargetCapacityAdd,
        'обнулить'
    )
}
$lines.Add('')
$lines.Add('Полная внешняя ёмкость доступна с первого уровня главного здания. Это не открывает более высокие уровни построек: их ванильная прогрессия сохраняется.')
$lines.Add('')
$lines.Add('## Стартовое заполнение внешних ячеек')
$lines.Add('')
$lines.Add('Расширенная ёмкость не должна заставлять ванильные эффекты начальной генерации заполнять все новые ячейки. Пороги сдвигаются так, чтобы на каждом уровне главного здания создавалось прежнее число построек; каждый цикл получает жёсткий лимит итераций.')
$lines.Add('')
$lines.Add('| Эффект | Тип | Главный уровень | Было мест | Стало мест | Старый порог | Новый порог | Лимит |')
$lines.Add('|---|---|---|---:|---:|---:|---:|---:|')
foreach ($entry in $initialFillEffectOverrides) {
    foreach ($branch in Convert-ToArray $entry.Branches) {
        Add-MarkdownRow $lines @(
            $entry.Effect,
            $entry.DomicileType,
            $branch.MainBuilding,
            $branch.OriginalCapacity,
            $branch.TargetCapacity,
            $branch.OriginalFreeSlotThreshold,
            $branch.TargetFreeSlotThreshold,
            $branch.MaximumIterations
        )
    }
}
$lines.Add('')
$lines.Add('## Внутренние ячейки')
$lines.Add('')
$lines.Add('| Тип | Опорная линия | Цель на каждом уровне линии | Причина |')
$lines.Add('|---|---|---:|---|')
foreach ($entry in $internalSlotOverrides) {
    Add-MarkdownRow $lines @($entry.DomicileType, $entry.AnchorTrack, $entry.TargetInternalSlotsAtEveryAnchorLevel, ($entry.Reasons -join ', '))
}
$lines.Add('')
$lines.Add('## Внешние развилки, переводимые во внутренние линии')
$lines.Add('')
$lines.Add('| Тип | Общая внешняя часть | Опорная линия | Внутренних линий | Новая ёмкость | Переводимые здания |')
$lines.Add('|---|---|---|---:|---:|---|')
foreach ($entry in $externalBranchOverrides) {
    Add-MarkdownRow $lines @(
        $entry.DomicileType,
        $entry.CommonBuilding,
        $entry.AnchorTrack,
        $entry.SpecializationRoots.Count,
        $entry.RequiredInternalSlotsOnAnchor,
        ($entry.BuildingsChangingSlotType -join ', ')
    )
}
$lines.Add('')
$lines.Add('## Внутренняя развилка библиотеки поместья')
$lines.Add('')
foreach ($entry in $internalBranchOverrides) {
    $lines.Add("- Общая линия ``$($entry.SharedPrefix -join ' -> ')`` сохраняется отдельной.")
    $lines.Add("- Специализации ``$($entry.Specializations.Root -join '`` и ``')`` привязываются к ``$($entry.AnchorBuilding)``.")
    $lines.Add("- Каждая специализация дополнительно требует уже построенную ``$($entry.SharedPrefix[-1])``.")
    $lines.Add("- Итоговая ёмкость главной линии: **$($entry.RequiredInternalSlotsOnAnchor)** внутренних ячеек.")
}
$lines.Add('')
$lines.Add('## Условные ограничения')
$lines.Add('')
$lines.Add("### Темы лагеря — $($campPurposeOverrides.Count) точечных пар")
$lines.Add('')
$lines.Add('Для каждой пары снимается соответствующий `has_realm_law_flag`. Специализированный эффект `laamp_clear_inappropriate_buildings_effect`, вызываемый при смене темы лагеря, отключается целиком; ванильное событие `ep3_laamps.1021` не переопределяется и остаётся доступным другим механикам.')
$lines.Add('')
$lines.Add('| Флаг | Здание | Очистка |')
$lines.Add('|---|---|---|')
foreach ($entry in $campPurposeOverrides) {
    Add-MarkdownRow $lines @($entry.RealmLawFlag, ($entry.Buildings -join ', '), ($entry.CleanupContainers -join ', '))
}
$lines.Add('')
$lines.Add('### Культура, территория и специальные способы доступа')
$lines.Add('')
$lines.Add('| Тип | Линия | Решение | Затронутые здания | Зависимости |')
$lines.Add('|---|---|---|---|---|')
foreach ($entry in $manualConditionOverrides) {
    $dependencyText = @(
        $entry.Dependencies.Keys |
            ForEach-Object { "${_}: $($entry.Dependencies[$_] -join ', ')" }
    ) -join '; '
    Add-MarkdownRow $lines @(
        $entry.DomicileType,
        $entry.TrackRoot,
        $entry.Decision,
        ($entry.ConditionalBuildings -join ', '),
        $dependencyText
    )
}
$lines.Add('')
$lines.Add('Три главные линии (`estate_main_01`, `east_asian_estate_main_01`, `japanese_manor_main_01`) сохраняются без изменений: культура там является только областью проверки универсальных инноваций, а не взаимоисключением.')
$lines.Add('')
$lines.Add('## Файлы реализации')
$lines.Add('')
$lines.Add('- `common/domiciles/types/zzz_RB_UD_domicile_types.txt` — пять точечных переопределений типов.')
foreach ($file in $buildingOverrideFiles.Values) { $lines.Add("- ``$file`` — переопределения соответствующего семейства зданий.") }
$lines.Add("- ``$scriptedEffectOverrideFile`` — безопасные стартовые fill-циклы и отключение очистки построек при смене темы лагеря.")
$lines.Add('- `replace_path` не используется.')
$lines.Add('')
$lines.Add('## Покрытие и проверки')
$lines.Add('')
$lines.Add("- Типы домицилей: $($validation.PlannedDomicileTypes)/$($validation.ExpectedDomicileTypes).")
$lines.Add("- Эффекты стартового заполнения: $($validation.PlannedInitialFillEffects)/$($validation.ExpectedInitialFillEffects).")
$lines.Add("- Внешние развилки: $($validation.PlannedExternalBranchGroups)/$($validation.ExpectedExternalBranchGroups).")
$lines.Add("- Внутренние развилки: $($validation.PlannedInternalBranchGroups)/$($validation.ExpectedInternalBranchGroups).")
$lines.Add("- Флаги тем лагеря: $($validation.PlannedCampPurposeFlags)/$($validation.ExpectedCampPurposeFlags).")
$lines.Add("- Ручные условные линии: $($validation.PlannedManualConditionTracks)/$($validation.ExpectedManualConditionTracks); переписать $($validation.RewrittenManualConditionTracks), сохранить $($validation.PreservedManualConditionTracks).")
$lines.Add("- Полностью зеркалируемых ванильных зданий: $(@(Convert-ToArray $manifest.Buildings).Count).")
$lines.Add("- Из них структурно изменяемых зданий: $($affectedBuildingIds.Count).")
$lines.Add('- Неизвестные условия, циклы и потерянные родители: 0.')
$lines.Add('')
$lines.Add('## Что остаётся перед генерацией кода')
$lines.Add('')
foreach ($check in $planCore.RemainingImplementationChecks) { $lines.Add("- $check") }

[IO.File]::WriteAllText($markdownOutputPath, ($lines -join "`r`n") + "`r`n", $utf8Bom)

Write-Output "RB_UD override plan completed for CK3 $($manifest.GameVersion)."
Write-Output "Plan:   $jsonOutputPath"
Write-Output "Report: $markdownOutputPath"
Write-Output "Plan SHA-256: $planSignature"
Write-Output "Affected vanilla buildings: $($affectedBuildingIds.Count)"
Write-Output "External branch groups: $($externalBranchOverrides.Count)"
Write-Output "Manual condition tracks: $($manualConditionOverrides.Count)"
