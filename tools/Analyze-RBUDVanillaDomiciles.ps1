param(
    [Parameter(Mandatory = $true)]
    [string]$GamePath,

    [string]$ModPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$script:ScriptedTriggerBlocks = @{}

if ([string]::IsNullOrWhiteSpace($ModPath)) {
    $ModPath = Join-Path $PSScriptRoot '..\RB_UD'
}

function Get-CodeLine {
    param([string]$Line)

    # CK3 comments begin with #. None of the audited database keys use # in a
    # quoted scalar, so removing the comment is safe for structural parsing.
    return ($Line -split '#', 2)[0]
}

function Get-BraceDelta {
    param([string]$Line)

    $codeLine = Get-CodeLine $Line
    return ([regex]::Matches($codeLine, '\{')).Count -
        ([regex]::Matches($codeLine, '\}')).Count
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

    if ($null -eq $Lines) {
        return $result
    }

    for ($index = 0; $index -lt $Lines.Count; $index++) {
        $rawLine = $Lines[$index]
        $codeLine = Get-CodeLine $rawLine

        if ($depth -eq 0 -and $codeLine -match '^([A-Za-z0-9_]+)\s*=\s*\{') {
            $name = $Matches[1]
            $buffer = [System.Collections.Generic.List[string]]::new()
            $startLine = $index + 1
        }

        if ($null -ne $name) {
            $buffer.Add($rawLine)
        }

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
            $startLine = 0
        }
    }

    if ($depth -ne 0 -or $null -ne $name) {
        throw "Unbalanced braces while parsing $SourceFile. Final depth: $depth."
    }

    return $result
}

function Get-DatabaseBlocks {
    param([string]$Directory)

    $database = @{}
    $duplicates = [System.Collections.Generic.List[object]]::new()

    Get-ChildItem -LiteralPath $Directory -Filter '*.txt' -File |
        Where-Object { -not $_.Name.StartsWith('_') } |
        Sort-Object Name |
        ForEach-Object {
            $relativePath = Get-GameRelativePath $_.FullName
            $blocks = Get-TopLevelBlocks `
                -Lines (Get-Content -LiteralPath $_.FullName -Encoding UTF8) `
                -SourceFile $relativePath

            foreach ($key in $blocks.Keys) {
                if ($database.ContainsKey($key)) {
                    $duplicates.Add([pscustomobject]@{
                        Id = $key
                        PreviousSource = $database[$key].SourceFile
                        WinningSource = $relativePath
                    })
                }
                $database[$key] = $blocks[$key]
            }
        }

    return [pscustomobject]@{
        Blocks = $database
        Duplicates = $duplicates.ToArray()
    }
}

function Get-ChildBlock {
    param(
        [string[]]$Lines,
        [string]$Field
    )

    $depth = 0
    $capturing = $false
    $startDepth = 0
    $buffer = $null

    foreach ($rawLine in $Lines) {
        $codeLine = Get-CodeLine $rawLine

        if (
            -not $capturing -and
            $depth -eq 1 -and
            $codeLine -match ('^\s*' + [regex]::Escape($Field) + '\s*=\s*\{')
        ) {
            $capturing = $true
            $startDepth = $depth
            $buffer = [System.Collections.Generic.List[string]]::new()
        }

        if ($capturing) {
            $buffer.Add($rawLine)
        }

        $depth += Get-BraceDelta $rawLine

        if ($capturing -and $depth -eq $startDepth) {
            return $buffer.ToArray()
        }
    }

    return @()
}

function Get-DirectScalar {
    param(
        [string[]]$Lines,
        [string]$Field
    )

    $depth = 0
    foreach ($rawLine in $Lines) {
        $codeLine = Get-CodeLine $rawLine
        if (
            $depth -eq 1 -and
            $codeLine -match ('^\s*' + [regex]::Escape($Field) + '\s*=\s*([^\s\{\}]+)')
        ) {
            return $Matches[1].Trim('"')
        }
        $depth += Get-BraceDelta $rawLine
    }

    return $null
}

function Get-DirectInlineList {
    param(
        [string[]]$Lines,
        [string]$Field
    )

    $depth = 0
    foreach ($rawLine in $Lines) {
        $codeLine = Get-CodeLine $rawLine
        if (
            $depth -eq 1 -and
            $codeLine -match ('^\s*' + [regex]::Escape($Field) + '\s*=\s*\{([^}]*)\}')
        ) {
            return @(
                [regex]::Matches($Matches[1], '[A-Za-z0-9_]+') |
                    ForEach-Object { $_.Value }
            )
        }
        $depth += Get-BraceDelta $rawLine
    }

    return @()
}

function Get-ChildObjectNames {
    param([string[]]$Lines)

    $result = [System.Collections.Generic.List[string]]::new()
    $depth = 0

    foreach ($rawLine in $Lines) {
        $codeLine = Get-CodeLine $rawLine
        if ($depth -eq 1 -and $codeLine -match '^\s*([A-Za-z0-9_]+)\s*=\s*\{') {
            $result.Add($Matches[1])
        }
        $depth += Get-BraceDelta $rawLine
    }

    return $result.ToArray()
}

function Get-BlockText {
    param([string[]]$Lines)

    if ($null -eq $Lines -or $Lines.Count -eq 0) {
        return ''
    }
    return $Lines -join "`n"
}

function Convert-ToNullableInt {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $parsed = 0
    if ([int]::TryParse([string]$Value, [ref]$parsed)) {
        return $parsed
    }
    return $null
}

function Get-StringSha256 {
    param([string]$Text)

    $sha256 = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($Text)
        return ([BitConverter]::ToString($sha256.ComputeHash($bytes))).Replace('-', '')
    }
    finally {
        $sha256.Dispose()
    }
}

function Get-RestrictionAnalysis {
    param([string]$Text)

    $categories = [System.Collections.Generic.List[string]]::new()
    $realmLawFlags = @(
        [regex]::Matches(
            $Text,
            '(?m)has_realm_law(?:_flag)?\s*=\s*([A-Za-z0-9_]+)'
        ) | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
    )
    $campPurposeLawFlags = @(
        $realmLawFlags | Where-Object { $_ -match '^unlocks_' }
    )
    $otherRealmLawFlags = @(
        $realmLawFlags | Where-Object { $_ -notmatch '^unlocks_' }
    )

    if ($campPurposeLawFlags.Count -gt 0 -or $Text -match '(?i)camp_purpose|uses_camp_purpose|_camp_purpose') {
        $categories.Add('camp_purpose')
    }
    if ($otherRealmLawFlags.Count -gt 0) {
        $categories.Add('realm_law')
    }
    if ($Text -match '(?i)\bculture\b|heritage|language|graphical_|has_cultural_parameter|has_tradition') {
        $categories.Add('culture_or_language')
    }
    if ($Text -match '(?i)\bterrain\b|geographical_region|\bregion\b|\bprovince\b|\bcounty\b|coastal|river|island') {
        $categories.Add('territory')
    }
    if ($Text -match '(?i)has_innovation|has_era|domicile_building_or_higher|num_domicile_buildings|main_0[1-9]') {
        $categories.Add('progression')
    }
    if ($Text -match '(?i)government|administrative|nomad|landless|ruler|title|vassal_contract|is_governor|top_liege') {
        $categories.Add('government_or_status')
    }
    if ($Text -match '(?i)faith|religion|doctrine|holy_site|piety') {
        $categories.Add('faith')
    }
    if ($Text -match '(?m)^\s*[A-Za-z0-9_]+_trigger\s*=\s*(?:yes|\{)') {
        $categories.Add('scripted_trigger')
    }
    if ($Text -match '(?i)has_dynasty_perk|house_aspiration|dynasty|\bhouse\b|any_relation|has_character_flag|has_trait|is_adult|is_alive|is_landed|is_ruler|is_ai') {
        $categories.Add('character_dynasty_or_house')
    }
    if ($Text -match '(?i)has_domicile_building_parameter|has_domicile_parameter|has_variable|has_dlc_feature|has_game_rule|has_perk|has_lifestyle|is_any_movement_leader|any_character_situation|situation_type|number_maa_regiments') {
        $categories.Add('state_or_feature')
    }

    return [pscustomobject]@{
        Categories = $categories.ToArray()
        RealmLawFlags = $realmLawFlags
    }
}

function Resolve-ScriptedTriggerReferences {
    param([string]$Text)

    $referencePattern = '(?m)^\s*([A-Za-z0-9_]+_trigger)\s*=\s*(?:yes|\{)'
    $pending = [System.Collections.Generic.Queue[string]]::new()
    foreach ($name in @(
        [regex]::Matches($Text, $referencePattern) |
            ForEach-Object { $_.Groups[1].Value } |
            Sort-Object -Unique
    )) {
        $pending.Enqueue($name)
    }

    $visited = [System.Collections.Generic.HashSet[string]]::new()
    $resolved = [System.Collections.Generic.List[object]]::new()
    $unresolved = [System.Collections.Generic.List[string]]::new()
    $expandedTexts = [System.Collections.Generic.List[string]]::new()

    while ($pending.Count -gt 0) {
        $name = $pending.Dequeue()
        if ($visited.Contains($name)) {
            continue
        }
        $null = $visited.Add($name)
        if (-not $script:ScriptedTriggerBlocks.ContainsKey($name)) {
            $unresolved.Add($name)
            continue
        }

        $block = $script:ScriptedTriggerBlocks[$name]
        $blockText = Get-BlockText $block.Lines
        $expandedTexts.Add($blockText)
        $resolved.Add([pscustomobject]@{
            Id = $name
            SourceFile = $block.SourceFile
            StartLine = $block.StartLine
        })
        foreach ($nestedName in @(
            [regex]::Matches($blockText, $referencePattern) |
                ForEach-Object { $_.Groups[1].Value } |
                Sort-Object -Unique
        )) {
            if (-not $visited.Contains($nestedName)) {
                $pending.Enqueue($nestedName)
            }
        }
    }

    return [pscustomobject]@{
        AnalysisText = @($Text, $expandedTexts.ToArray()) -join "`n"
        Resolved = @($resolved.ToArray() | Sort-Object Id)
        Unresolved = @($unresolved.ToArray() | Sort-Object -Unique)
    }
}

function Get-ConstraintDependencyAnalysis {
    param([string]$Text)

    $definitions = @(
        [pscustomobject]@{ Name = 'RealmLawFlags'; Pattern = '\bhas_realm_law(?:_flag)?\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'CulturalParameters'; Pattern = '\bhas_cultural_parameter\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'CulturalTraditions'; Pattern = '\bhas_(?:cultural_)?tradition\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'Innovations'; Pattern = '\bhas_innovation\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'Eras'; Pattern = '\bhas_era\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'Terrains'; Pattern = '(?m)^\s*terrain\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'Regions'; Pattern = '\b(?:geographical_region|region)\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'GovernmentFlags'; Pattern = '\bgovernment_has_flag\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'Governments'; Pattern = '(?m)^\s*(?:government|government_type)\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'FaithDoctrines'; Pattern = '\bhas_doctrine\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'Faiths'; Pattern = '(?m)^\s*faith\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'Religions'; Pattern = '(?m)^\s*religion\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'DynastyPerks'; Pattern = '\bhas_dynasty_perk\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'HouseAspirationParameters'; Pattern = '\bhas_house_aspiration_parameter\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'CharacterFlags'; Pattern = '\bhas_character_flag\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'Traits'; Pattern = '\bhas_trait\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'Relations'; Pattern = '\btype\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'DomicileBuildingParameters'; Pattern = '\bhas_domicile_building_parameter\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'DomicileParameters'; Pattern = '\bhas_domicile_parameter\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'DlcFeatures'; Pattern = '\bhas_dlc_feature\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'GameRules'; Pattern = '\bhas_game_rule\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'SituationTypes'; Pattern = '\bsituation_type\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'MenAtArmsBaseTypes'; Pattern = '\bnumber_maa_regiments_of_base_type:([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'RequiredDomicileBuildings'; Pattern = '\bhas_domicile_building_or_higher\s*=\s*([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'RequiredDomicileBuildingCounts'; Pattern = '\bnum_domicile_buildings\s*[^\r\n}]*?([A-Za-z0-9_]+)' },
        [pscustomobject]@{ Name = 'ScriptedTriggers'; Pattern = '(?m)^\s*([A-Za-z0-9_]+_trigger)\s*=\s*(?:yes|\{)' }
    )

    $result = [ordered]@{}
    foreach ($definition in $definitions) {
        $result[$definition.Name] = @(
            [regex]::Matches($Text, $definition.Pattern) |
                ForEach-Object { $_.Groups[1].Value } |
                Sort-Object -Unique
        )
    }
    return [pscustomobject]$result
}

function Get-AvailabilityPolicy {
    param(
        [string[]]$Categories,
        [bool]$HasConditions
    )

    $exclusivityCandidates = @(
        $Categories |
            Where-Object { $_ -in @('camp_purpose', 'culture_or_language', 'territory') } |
            Sort-Object -Unique
    )
    $preservedPrerequisites = @(
        $Categories |
            Where-Object {
                $_ -in @(
                    'progression',
                    'government_or_status',
                    'faith',
                    'realm_law',
                    'scripted_trigger',
                    'character_dynasty_or_house',
                    'state_or_feature'
                )
            } |
            Sort-Object -Unique
    )
    $actions = [System.Collections.Generic.List[string]]::new()
    if ($exclusivityCandidates -contains 'camp_purpose') {
        $actions.Add('remove_camp_purpose_gate_and_disable_corresponding_cleanup')
    }
    if ($exclusivityCandidates -contains 'culture_or_language') {
        $actions.Add('review_culture_condition_and_remove_only_track_exclusivity')
    }
    if ($exclusivityCandidates -contains 'territory') {
        $actions.Add('review_territory_condition_and_remove_only_track_exclusivity')
    }
    if ($preservedPrerequisites.Count -gt 0) {
        $actions.Add('preserve_unrelated_vanilla_prerequisites')
    }
    if ($actions.Count -eq 0 -and $HasConditions) {
        $actions.Add('preserve_until_manually_classified')
    }

    $disposition = 'unrestricted'
    if ($exclusivityCandidates.Count -gt 0) {
        if (
            $exclusivityCandidates -contains 'culture_or_language' -or
            $exclusivityCandidates -contains 'territory'
        ) {
            $disposition = 'manual_review_required'
        }
        else {
            $disposition = 'split_exclusivity_from_prerequisites'
        }
    }
    elseif ($Categories.Count -gt 0) {
        $disposition = 'preserve_vanilla_prerequisites'
    }
    elseif ($HasConditions) {
        $disposition = 'unclassified_conditions'
    }

    return [pscustomobject]@{
        Disposition = $disposition
        ExclusivityCandidateCategories = $exclusivityCandidates
        PreservedPrerequisiteCategories = $preservedPrerequisites
        RecommendedActions = $actions.ToArray()
        RequiresManualReview = $disposition -eq 'manual_review_required'
    }
}

function Get-AvailabilityBlockRecord {
    param([string[]]$Lines)

    $text = Get-BlockText $Lines
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }
    $substantiveLines = @(
        for ($index = 1; $index -lt ($Lines.Count - 1); $index++) {
            $codeLine = (Get-CodeLine $Lines[$index]).Trim()
            if (-not [string]::IsNullOrWhiteSpace($codeLine)) {
                $codeLine
            }
        }
    )
    if ($substantiveLines.Count -eq 0) {
        return $null
    }
    $resolution = Resolve-ScriptedTriggerReferences $text
    $restrictionAnalysis = Get-RestrictionAnalysis $resolution.AnalysisText
    return [pscustomobject]@{
        Script = $text
        DirectDependencies = Get-ConstraintDependencyAnalysis $text
        ResolvedDependencies = Get-ConstraintDependencyAnalysis $resolution.AnalysisText
        RestrictionCategories = @($restrictionAnalysis.Categories)
        ResolvedScriptedTriggers = @($resolution.Resolved)
        UnresolvedScriptedTriggers = @($resolution.Unresolved)
    }
}

function Get-ExternalCapacityAdds {
    param([string[]]$Lines)

    $result = [System.Collections.Generic.List[object]]::new()
    foreach ($match in [regex]::Matches(
        (Get-BlockText $Lines),
        '(?m)^\s*domicile_external_slots_capacity_add\s*=\s*([^\s#\}]+)'
    )) {
        $rawValue = $match.Groups[1].Value
        $result.Add([pscustomobject]@{
            Raw = $rawValue
            Numeric = Convert-ToNullableInt $rawValue
        })
    }
    return $result.ToArray()
}

function Get-GameRelativePath {
    param([string]$Path)

    $fullPath = [IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($script:ResolvedGamePath, [StringComparison]::OrdinalIgnoreCase)) {
        return $fullPath
    }
    return $fullPath.Substring($script:ResolvedGamePath.Length).TrimStart('\', '/')
}

function Get-BuildingRecord {
    param([object]$Block)

    $declaredSlotType = Get-DirectScalar $Block.Lines 'slot_type'
    $slotType = $declaredSlotType
    if ([string]::IsNullOrWhiteSpace($slotType)) {
        $slotType = 'external'
    }

    $canConstruct = @(Get-ChildBlock $Block.Lines 'can_construct')
    $canConstructPotential = @(Get-ChildBlock $Block.Lines 'can_construct_potential')
    $canConstructRecord = Get-AvailabilityBlockRecord $canConstruct
    $canConstructPotentialRecord = Get-AvailabilityBlockRecord $canConstructPotential
    $restrictionCategories = @(
        @($canConstructRecord, $canConstructPotentialRecord) |
            Where-Object { $null -ne $_ } |
            ForEach-Object { $_.RestrictionCategories } |
            Sort-Object -Unique
    )
    $realmLawFlags = @(
        @($canConstructRecord, $canConstructPotentialRecord) |
            Where-Object { $null -ne $_ } |
            ForEach-Object { $_.ResolvedDependencies.RealmLawFlags } |
            Sort-Object -Unique
    )
    $availabilityPolicy = Get-AvailabilityPolicy `
        $restrictionCategories `
        ($null -ne $canConstructRecord -or $null -ne $canConstructPotentialRecord)
    $blockText = Get-BlockText $Block.Lines
    $icons = @(
        [regex]::Matches($blockText, '(?m)^\s*icon\s*=\s*"([^"]+)"') |
            ForEach-Object { $_.Groups[1].Value } |
            Sort-Object -Unique
    )
    $textures = @(
        [regex]::Matches($blockText, '(?m)^\s*texture\s*=\s*"([^"]+)"') |
            ForEach-Object { $_.Groups[1].Value } |
            Sort-Object -Unique
    )

    return [pscustomobject]@{
        Id = $Block.Id
        SourceFile = $Block.SourceFile
        StartLine = $Block.StartLine
        Tier = Get-BuildingTier $Block.Id
        AllowedDomicileTypes = @(Get-DirectInlineList $Block.Lines 'allowed_domicile_types')
        SlotType = $slotType
        DeclaredSlotType = $declaredSlotType
        HasExplicitSlotType = -not [string]::IsNullOrWhiteSpace($declaredSlotType)
        PreviousBuilding = Get-DirectScalar $Block.Lines 'previous_building'
        InternalSlotsRaw = Get-DirectScalar $Block.Lines 'internal_slots'
        InternalSlots = Convert-ToNullableInt (Get-DirectScalar $Block.Lines 'internal_slots')
        ConstructionTime = Get-DirectScalar $Block.Lines 'construction_time'
        ExternalCapacityAdds = @(Get-ExternalCapacityAdds $Block.Lines)
        RestrictionCategories = $restrictionCategories
        RealmLawFlags = $realmLawFlags
        HasCanConstruct = $null -ne $canConstructRecord
        HasCanConstructPotential = $null -ne $canConstructPotentialRecord
        Availability = [pscustomobject]@{
            CanConstruct = $canConstructRecord
            CanConstructPotential = $canConstructPotentialRecord
            Policy = $availabilityPolicy
        }
        Icons = $icons
        Textures = $textures
    }
}

function Get-TypeRecord {
    param([object]$Block)

    $slotsBlock = @(Get-ChildBlock $Block.Lines 'domicile_building_slots')
    $slotNames = @(Get-ChildObjectNames $slotsBlock)
    $externalSlotNames = @($slotNames | Where-Object { $_ -match '^external_slot_' })

    return [pscustomobject]@{
        Id = $Block.Id
        SourceFile = $Block.SourceFile
        StartLine = $Block.StartLine
        BaseExternalSlotsRaw = Get-DirectScalar $Block.Lines 'base_external_slots'
        BaseExternalSlots = Convert-ToNullableInt (Get-DirectScalar $Block.Lines 'base_external_slots')
        MainSlotNames = @($slotNames | Where-Object { $_ -eq 'main_slot' })
        ExternalSlotNames = $externalSlotNames
        VisualExternalSlotCount = $externalSlotNames.Count
    }
}

function Get-SameSlotChildren {
    param(
        [string]$BuildingId,
        [string]$SlotType,
        [hashtable]$BuildingById,
        [hashtable]$ChildrenByParent
    )

    if (-not $ChildrenByParent.ContainsKey($BuildingId)) {
        return @()
    }

    return @(
        $ChildrenByParent[$BuildingId] |
            Where-Object {
                $BuildingById.ContainsKey($_) -and
                $BuildingById[$_].SlotType -eq $SlotType
            }
    )
}

function Get-SameSlotDescendantIds {
    param(
        [string]$BuildingId,
        [string]$SlotType,
        [hashtable]$BuildingById,
        [hashtable]$ChildrenByParent,
        [switch]$IncludeSelf
    )

    $result = [System.Collections.Generic.HashSet[string]]::new()
    $pending = [System.Collections.Generic.Stack[string]]::new()
    $pending.Push($BuildingId)

    while ($pending.Count -gt 0) {
        $currentId = $pending.Pop()
        if ($result.Contains($currentId)) {
            $script:GraphCycles.Add($currentId)
            continue
        }
        $null = $result.Add($currentId)
        foreach ($child in @(
            Get-SameSlotChildren $currentId $SlotType $BuildingById $ChildrenByParent
        )) {
            $pending.Push($child)
        }
    }

    if (-not $IncludeSelf) {
        $null = $result.Remove($BuildingId)
    }
    return @($result | Sort-Object)
}

function Get-SameSlotPathToRoot {
    param(
        [string]$BuildingId,
        [string]$SlotType,
        [hashtable]$BuildingById
    )

    $path = [System.Collections.Generic.List[string]]::new()
    $visited = [System.Collections.Generic.HashSet[string]]::new()
    $currentId = $BuildingId

    while ($BuildingById.ContainsKey($currentId)) {
        if ($visited.Contains($currentId)) {
            $script:GraphCycles.Add($currentId)
            break
        }
        $null = $visited.Add($currentId)
        $path.Add($currentId)

        $parentId = $BuildingById[$currentId].PreviousBuilding
        if (
            [string]::IsNullOrWhiteSpace($parentId) -or
            -not $BuildingById.ContainsKey($parentId) -or
            $BuildingById[$parentId].SlotType -ne $SlotType
        ) {
            break
        }
        $currentId = $parentId
    }

    $array = $path.ToArray()
    [array]::Reverse($array)
    return $array
}

function Get-BuildingTier {
    param([string]$BuildingId)

    if ($BuildingId -match '_(\d+)$') {
        return [int]$Matches[1]
    }
    return $null
}

function Test-IdenticalStringSets {
    param([object[]]$Sets)

    if ($Sets.Count -lt 2) {
        return $false
    }
    $normalized = @(
        $Sets | ForEach-Object {
            @($_ | Sort-Object -Unique) -join "`n"
        }
    )
    if (@($normalized | Where-Object { [string]::IsNullOrWhiteSpace($_) }).Count -gt 0) {
        return $false
    }
    return @($normalized | Sort-Object -Unique).Count -eq 1
}

function Test-DistinctStringSets {
    param([object[]]$Sets)

    if ($Sets.Count -lt 2) {
        return $false
    }
    $normalized = @(
        $Sets | ForEach-Object {
            @($_ | Sort-Object -Unique) -join "`n"
        }
    )
    if (@($normalized | Where-Object { [string]::IsNullOrWhiteSpace($_) }).Count -gt 0) {
        return $false
    }
    return @($normalized | Sort-Object -Unique).Count -eq $normalized.Count
}

function Get-LeafIds {
    param(
        [string]$BuildingId,
        [string]$SlotType,
        [hashtable]$BuildingById,
        [hashtable]$ChildrenByParent,
        [System.Collections.Generic.HashSet[string]]$Visiting
    )

    if ($Visiting.Contains($BuildingId)) {
        $script:GraphCycles.Add($BuildingId)
        return @()
    }

    $null = $Visiting.Add($BuildingId)
    $children = @(Get-SameSlotChildren $BuildingId $SlotType $BuildingById $ChildrenByParent)
    if ($children.Count -eq 0) {
        $null = $Visiting.Remove($BuildingId)
        return @($BuildingId)
    }

    $leaves = [System.Collections.Generic.List[string]]::new()
    foreach ($child in $children) {
        foreach ($leaf in @(Get-LeafIds $child $SlotType $BuildingById $ChildrenByParent $Visiting)) {
            $leaves.Add($leaf)
        }
    }
    $null = $Visiting.Remove($BuildingId)
    return @($leaves.ToArray() | Sort-Object -Unique)
}

function Get-TrackRootId {
    param(
        [string]$BuildingId,
        [string]$SlotType,
        [hashtable]$BuildingById
    )

    $currentId = $BuildingId
    $visited = [System.Collections.Generic.HashSet[string]]::new()

    while ($BuildingById.ContainsKey($currentId)) {
        if ($visited.Contains($currentId)) {
            $script:GraphCycles.Add($currentId)
            break
        }
        $null = $visited.Add($currentId)

        $current = $BuildingById[$currentId]
        $parentId = $current.PreviousBuilding
        if (
            [string]::IsNullOrWhiteSpace($parentId) -or
            -not $BuildingById.ContainsKey($parentId) -or
            $BuildingById[$parentId].SlotType -ne $SlotType
        ) {
            break
        }
        $currentId = $parentId
    }

    return $currentId
}

function Get-CumulativeCapacity {
    param(
        [string]$BuildingId,
        [hashtable]$BuildingById
    )

    $currentId = $BuildingId
    $visited = [System.Collections.Generic.HashSet[string]]::new()
    $sum = 0
    $unknown = [System.Collections.Generic.List[string]]::new()

    while ($BuildingById.ContainsKey($currentId)) {
        if ($visited.Contains($currentId)) {
            $script:GraphCycles.Add($currentId)
            break
        }
        $null = $visited.Add($currentId)

        $current = $BuildingById[$currentId]
        foreach ($addition in @($current.ExternalCapacityAdds)) {
            if ($null -eq $addition.Numeric) {
                $unknown.Add($addition.Raw)
            }
            else {
                $sum += $addition.Numeric
            }
        }

        if ([string]::IsNullOrWhiteSpace($current.PreviousBuilding)) {
            break
        }
        $currentId = $current.PreviousBuilding
    }

    return [pscustomobject]@{
        Numeric = $sum
        UnknownValues = @($unknown.ToArray() | Sort-Object -Unique)
    }
}

function Get-DomicileAnalysis {
    param(
        [object]$TypeRecord,
        [object[]]$AllBuildings
    )

    $selected = @(
        $AllBuildings |
            Where-Object { $_.AllowedDomicileTypes -contains $TypeRecord.Id }
    )
    $buildingById = @{}
    foreach ($building in $selected) {
        $buildingById[$building.Id] = $building
    }

    $childrenByParent = @{}
    foreach ($building in $selected) {
        if ([string]::IsNullOrWhiteSpace($building.PreviousBuilding)) {
            continue
        }
        if (-not $childrenByParent.ContainsKey($building.PreviousBuilding)) {
            $childrenByParent[$building.PreviousBuilding] = [System.Collections.Generic.List[string]]::new()
        }
        $childrenByParent[$building.PreviousBuilding].Add($building.Id)
    }

    $unresolvedParents = @(
        $selected |
            Where-Object {
                -not [string]::IsNullOrWhiteSpace($_.PreviousBuilding) -and
                -not $script:AllBuildingById.ContainsKey($_.PreviousBuilding)
            } |
            ForEach-Object {
                [pscustomobject]@{
                    Building = $_.Id
                    MissingPreviousBuilding = $_.PreviousBuilding
                }
            }
    )

    $externalBuildings = @($selected | Where-Object { $_.SlotType -eq 'external' })
    $mainBuildings = @($selected | Where-Object { $_.SlotType -eq 'main' })
    $internalBuildings = @($selected | Where-Object { $_.SlotType -eq 'internal' })

    $externalRoots = @(
        $externalBuildings |
            Where-Object {
                [string]::IsNullOrWhiteSpace($_.PreviousBuilding) -or
                -not $buildingById.ContainsKey($_.PreviousBuilding) -or
                $buildingById[$_.PreviousBuilding].SlotType -ne 'external'
            } |
            Sort-Object Id
    )
    $internalRoots = @(
        $internalBuildings |
            Where-Object {
                [string]::IsNullOrWhiteSpace($_.PreviousBuilding) -or
                -not $buildingById.ContainsKey($_.PreviousBuilding) -or
                $buildingById[$_.PreviousBuilding].SlotType -ne 'internal'
            } |
            Sort-Object Id
    )

    $externalTrackAnalysis = [System.Collections.Generic.List[object]]::new()
    $requiredExternalSlots = 0
    foreach ($root in $externalRoots) {
        $leaves = @(Get-LeafIds `
            -BuildingId $root.Id `
            -SlotType 'external' `
            -BuildingById $buildingById `
            -ChildrenByParent $childrenByParent `
            -Visiting ([System.Collections.Generic.HashSet[string]]::new()))
        $copies = [Math]::Max(1, $leaves.Count)
        $requiredExternalSlots += $copies
        $externalTrackAnalysis.Add([pscustomobject]@{
            Root = $root.Id
            RequiredCopiesForAllBranches = $copies
            Leaves = $leaves
            RestrictionCategories = @($root.RestrictionCategories)
        })
    }

    $internalTrackAnalysis = [System.Collections.Generic.List[object]]::new()
    $internalRequirementsByAnchor = @{}
    foreach ($root in $internalRoots) {
        $leaves = @(Get-LeafIds `
            -BuildingId $root.Id `
            -SlotType 'internal' `
            -BuildingById $buildingById `
            -ChildrenByParent $childrenByParent `
            -Visiting ([System.Collections.Generic.HashSet[string]]::new()))
        $copies = [Math]::Max(1, $leaves.Count)

        $anchor = $root.PreviousBuilding
        if (-not [string]::IsNullOrWhiteSpace($anchor) -and $buildingById.ContainsKey($anchor)) {
            $anchorSlotType = $buildingById[$anchor].SlotType
            $anchor = Get-TrackRootId $anchor $anchorSlotType $buildingById
        }
        if ([string]::IsNullOrWhiteSpace($anchor)) {
            $anchor = '<unresolved>'
        }

        if (-not $internalRequirementsByAnchor.ContainsKey($anchor)) {
            $internalRequirementsByAnchor[$anchor] = 0
        }
        $internalRequirementsByAnchor[$anchor] += $copies

        $internalTrackAnalysis.Add([pscustomobject]@{
            Root = $root.Id
            AnchorTrack = $anchor
            RequiredCopiesForAllBranches = $copies
            Leaves = $leaves
            RestrictionCategories = @($root.RestrictionCategories)
            RealmLawFlags = @($root.RealmLawFlags)
        })
    }

    $branchPoints = [System.Collections.Generic.List[object]]::new()
    foreach ($building in $selected) {
        $sameSlotChildren = @(
            Get-SameSlotChildren $building.Id $building.SlotType $buildingById $childrenByParent
        )
        if ($sameSlotChildren.Count -gt 1) {
            $branchPoints.Add([pscustomobject]@{
                Building = $building.Id
                SlotType = $building.SlotType
                Children = @($sameSlotChildren | Sort-Object)
            })
        }
    }

    $externalBranchGroups = [System.Collections.Generic.List[object]]::new()
    $internalBranchGroups = [System.Collections.Generic.List[object]]::new()
    foreach ($branchPoint in $branchPoints) {
        $commonBuilding = $buildingById[$branchPoint.Building]
        $specializations = [System.Collections.Generic.List[object]]::new()
        foreach ($childId in @($branchPoint.Children | Sort-Object)) {
            $child = $buildingById[$childId]
            $descendantIds = @(
                Get-SameSlotDescendantIds `
                    -BuildingId $childId `
                    -SlotType $branchPoint.SlotType `
                    -BuildingById $buildingById `
                    -ChildrenByParent $childrenByParent `
                    -IncludeSelf
            )
            $leaves = @(Get-LeafIds `
                -BuildingId $childId `
                -SlotType $branchPoint.SlotType `
                -BuildingById $buildingById `
                -ChildrenByParent $childrenByParent `
                -Visiting ([System.Collections.Generic.HashSet[string]]::new()))
            $allIcons = @(
                $descendantIds |
                    ForEach-Object { $buildingById[$_].Icons } |
                    Sort-Object -Unique
            )
            $allTextures = @(
                $descendantIds |
                    ForEach-Object { $buildingById[$_].Textures } |
                    Sort-Object -Unique
            )
            $specializations.Add([pscustomobject]@{
                Root = $childId
                StartTier = Get-BuildingTier $childId
                Leaves = $leaves
                RequiredParallelTracks = [Math]::Max(1, $leaves.Count)
                Buildings = $descendantIds
                RootIcons = @($child.Icons)
                RootTextures = @($child.Textures)
                AllIcons = $allIcons
                AllTextures = $allTextures
                SourceFile = $child.SourceFile
                StartLine = $child.StartLine
            })
        }

        $specializationArray = $specializations.ToArray()
        $requiredParallelTracks = @(
            $specializationArray |
                Measure-Object -Property RequiredParallelTracks -Sum
        )[0].Sum
        if ($null -eq $requiredParallelTracks) {
            $requiredParallelTracks = 0
        }

        if ($branchPoint.SlotType -eq 'external') {
            $existingDirectInternalSlots = 0
            foreach ($internalRoot in @(
                $internalRoots | Where-Object { $_.PreviousBuilding -eq $branchPoint.Building }
            )) {
                $existingLeaves = @(Get-LeafIds `
                    -BuildingId $internalRoot.Id `
                    -SlotType 'internal' `
                    -BuildingById $buildingById `
                    -ChildrenByParent $childrenByParent `
                    -Visiting ([System.Collections.Generic.HashSet[string]]::new()))
                $existingDirectInternalSlots += [Math]::Max(1, $existingLeaves.Count)
            }

            $externalBranchGroups.Add([pscustomobject]@{
                CommonBuilding = $branchPoint.Building
                CommonTier = Get-BuildingTier $branchPoint.Building
                CommonExternalPrefix = @(
                    Get-SameSlotPathToRoot $branchPoint.Building 'external' $buildingById
                )
                Specializations = $specializationArray
                SpecializationCount = $specializationArray.Count
                RequiredNewInternalSlots = $requiredParallelTracks
                ExistingDirectInternalSlots = $existingDirectInternalSlots
                RequiredInternalSlotsAtCommonBuilding = (
                    $requiredParallelTracks + $existingDirectInternalSlots
                )
                CurrentInternalSlotsAtCommonBuilding = $(
                    if ($null -eq $commonBuilding.InternalSlots) { 0 }
                    else { $commonBuilding.InternalSlots }
                )
                UniqueSpecializationRootIcons = Test-DistinctStringSets @(
                    $specializationArray | ForEach-Object { ,@($_.RootIcons) }
                )
                SharedSpecializationRootTextures = Test-IdenticalStringSets @(
                    $specializationArray | ForEach-Object { ,@($_.RootTextures) }
                )
                RecommendedStrategy = 'internalize_external_specialization_tails'
                SourceFile = $commonBuilding.SourceFile
                StartLine = $commonBuilding.StartLine
            })
        }
        elseif ($branchPoint.SlotType -eq 'internal') {
            $commonPrefix = @(
                Get-SameSlotPathToRoot $branchPoint.Building 'internal' $buildingById
            )
            $internalRootId = $commonPrefix[0]
            $anchorBuilding = $buildingById[$internalRootId].PreviousBuilding
            $internalBranchGroups.Add([pscustomobject]@{
                CommonBuilding = $branchPoint.Building
                CommonTier = Get-BuildingTier $branchPoint.Building
                AnchorBuilding = $anchorBuilding
                SharedInternalPrefix = $commonPrefix
                Specializations = $specializationArray
                SpecializationCount = $specializationArray.Count
                RequiredParallelInternalSlots = $requiredParallelTracks
                RecommendedStrategy = 'split_shared_internal_prefix_into_parallel_tracks'
                SourceFile = $commonBuilding.SourceFile
                StartLine = $commonBuilding.StartLine
            })
        }
    }

    $mainLeaves = @(
        $mainBuildings |
            Where-Object {
                @(Get-SameSlotChildren $_.Id 'main' $buildingById $childrenByParent).Count -eq 0
            }
    )
    $maxCapacityAddition = 0
    $unknownCapacityValues = [System.Collections.Generic.List[string]]::new()
    foreach ($leaf in $mainLeaves) {
        $capacity = Get-CumulativeCapacity $leaf.Id $buildingById
        if ($capacity.Numeric -gt $maxCapacityAddition) {
            $maxCapacityAddition = $capacity.Numeric
        }
        foreach ($unknown in @($capacity.UnknownValues)) {
            $unknownCapacityValues.Add($unknown)
        }
    }

    $currentCapacity = $null
    if ($null -ne $TypeRecord.BaseExternalSlots) {
        $currentCapacity = $TypeRecord.BaseExternalSlots + $maxCapacityAddition
    }

    $visualSlotDeficit = [Math]::Max(
        0,
        $requiredExternalSlots - $TypeRecord.VisualExternalSlotCount
    )
    $recommendedVisualSlotDeficit = [Math]::Max(
        0,
        $externalRoots.Count - $TypeRecord.VisualExternalSlotCount
    )
    $capacityDeficit = $null
    $capacityVisualMismatch = $null
    if ($null -ne $currentCapacity) {
        $capacityDeficit = [Math]::Max(0, $requiredExternalSlots - $currentCapacity)
        $capacityVisualMismatch = $currentCapacity - $TypeRecord.VisualExternalSlotCount
    }
    $recommendedCapacityDeficit = $null
    if ($null -ne $currentCapacity) {
        $recommendedCapacityDeficit = [Math]::Max(
            0,
            $externalRoots.Count - $currentCapacity
        )
    }

    $restrictionSummary = [ordered]@{}
    foreach ($category in @(
        'camp_purpose',
        'realm_law',
        'culture_or_language',
        'territory',
        'progression',
        'government_or_status',
        'faith',
        'scripted_trigger',
        'character_dynasty_or_house',
        'state_or_feature'
    )) {
        $matching = @(
            $selected |
                Where-Object { $_.RestrictionCategories -contains $category } |
                Select-Object -ExpandProperty Id |
                Sort-Object -Unique
        )
        $restrictionSummary[$category] = $matching
    }

    $internalAnchorSummary = [System.Collections.Generic.List[object]]::new()
    foreach ($anchor in @($internalRequirementsByAnchor.Keys | Sort-Object)) {
        $currentTrackMaximum = 0
        if ($anchor -ne '<unresolved>' -and $buildingById.ContainsKey($anchor)) {
            $anchorSlotType = $buildingById[$anchor].SlotType
            $trackMembers = @(
                $selected |
                    Where-Object {
                        $_.SlotType -eq $anchorSlotType -and
                        (Get-TrackRootId $_.Id $_.SlotType $buildingById) -eq $anchor
                    }
            )
            $slotValues = @(
                $trackMembers |
                    Where-Object { $null -ne $_.InternalSlots } |
                    Select-Object -ExpandProperty InternalSlots
            )
            if ($slotValues.Count -gt 0) {
                $currentTrackMaximum = ($slotValues | Measure-Object -Maximum).Maximum
            }
        }

        $internalAnchorSummary.Add([pscustomobject]@{
            AnchorTrack = $anchor
            RequiredSlotsForAllBranches = $internalRequirementsByAnchor[$anchor]
            CurrentMaximumSlots = $currentTrackMaximum
            Deficit = [Math]::Max(
                0,
                $internalRequirementsByAnchor[$anchor] - $currentTrackMaximum
            )
        })
    }

    foreach ($group in $externalBranchGroups) {
        $anchorTrack = Get-TrackRootId `
            $group.CommonBuilding `
            'external' `
            $buildingById
        $existingTrackRequirement = @(
            $internalAnchorSummary |
                Where-Object { $_.AnchorTrack -eq $anchorTrack }
        ) | Select-Object -First 1
        $existingSlotsOnAnchorTrack = 0
        if ($null -ne $existingTrackRequirement) {
            $existingSlotsOnAnchorTrack = $existingTrackRequirement.RequiredSlotsForAllBranches
        }
        $group | Add-Member -NotePropertyName AnchorTrack -NotePropertyValue $anchorTrack
        $group | Add-Member `
            -NotePropertyName ExistingInternalSlotsOnAnchorTrack `
            -NotePropertyValue $existingSlotsOnAnchorTrack
        $group | Add-Member `
            -NotePropertyName RequiredInternalSlotsAfterTransformation `
            -NotePropertyValue ($existingSlotsOnAnchorTrack + $group.RequiredNewInternalSlots)
    }

    $conditionalTrackBuilders = @{}
    foreach ($building in @(
        $selected | Where-Object { $_.HasCanConstruct -or $_.HasCanConstructPotential }
    )) {
        $trackRoot = Get-TrackRootId $building.Id $building.SlotType $buildingById
        $trackKey = "$($building.SlotType)|$trackRoot"
        if (-not $conditionalTrackBuilders.ContainsKey($trackKey)) {
            $conditionalTrackBuilders[$trackKey] = [System.Collections.Generic.List[object]]::new()
        }
        $conditionalTrackBuilders[$trackKey].Add($building)
    }

    $dependencyNames = @(
        'RealmLawFlags',
        'CulturalParameters',
        'CulturalTraditions',
        'Innovations',
        'Eras',
        'Terrains',
        'Regions',
        'GovernmentFlags',
        'Governments',
        'FaithDoctrines',
        'Faiths',
        'Religions',
        'DynastyPerks',
        'HouseAspirationParameters',
        'CharacterFlags',
        'Traits',
        'Relations',
        'DomicileBuildingParameters',
        'DomicileParameters',
        'DlcFeatures',
        'GameRules',
        'SituationTypes',
        'MenAtArmsBaseTypes',
        'RequiredDomicileBuildings',
        'RequiredDomicileBuildingCounts',
        'ScriptedTriggers'
    )
    $conditionalTracks = [System.Collections.Generic.List[object]]::new()
    foreach ($trackKey in @($conditionalTrackBuilders.Keys | Sort-Object)) {
        $members = @($conditionalTrackBuilders[$trackKey].ToArray() | Sort-Object Id)
        $slotType = $members[0].SlotType
        $trackRoot = Get-TrackRootId $members[0].Id $slotType $buildingById
        $anchorTrack = $trackRoot
        if ($slotType -eq 'internal') {
            $parentId = $buildingById[$trackRoot].PreviousBuilding
            if (-not [string]::IsNullOrWhiteSpace($parentId) -and $buildingById.ContainsKey($parentId)) {
                $anchorTrack = Get-TrackRootId `
                    $parentId `
                    $buildingById[$parentId].SlotType `
                    $buildingById
            }
        }

        $categories = @(
            $members |
                ForEach-Object { $_.RestrictionCategories } |
                Sort-Object -Unique
        )
        $dependencySummary = [ordered]@{}
        foreach ($dependencyName in $dependencyNames) {
            $values = [System.Collections.Generic.List[string]]::new()
            foreach ($member in $members) {
                foreach ($blockName in @('CanConstruct', 'CanConstructPotential')) {
                    $availabilityBlock = $member.Availability.$blockName
                    if ($null -eq $availabilityBlock) {
                        continue
                    }
                    foreach ($value in @($availabilityBlock.ResolvedDependencies.$dependencyName)) {
                        $values.Add($value)
                    }
                }
            }
            $dependencySummary[$dependencyName] = @($values.ToArray() | Sort-Object -Unique)
        }

        $allTrackBuildings = @(
            $selected |
                Where-Object {
                    $_.SlotType -eq $slotType -and
                    (Get-TrackRootId $_.Id $_.SlotType $buildingById) -eq $trackRoot
                } |
                Select-Object -ExpandProperty Id |
                Sort-Object
        )
        $profiles = @(
            $members | ForEach-Object {
                [pscustomobject]@{
                    Building = $_.Id
                    Categories = @($_.RestrictionCategories)
                    Disposition = $_.Availability.Policy.Disposition
                    RecommendedActions = @($_.Availability.Policy.RecommendedActions)
                    SourceFile = $_.SourceFile
                    StartLine = $_.StartLine
                }
            }
        )
        $exclusivityCandidateCategories = @(
            $members |
                ForEach-Object { $_.Availability.Policy.ExclusivityCandidateCategories } |
                Sort-Object -Unique
        )
        $conditionalTracks.Add([pscustomobject]@{
            TrackRoot = $trackRoot
            SlotType = $slotType
            AnchorTrack = $anchorTrack
            AllTrackBuildings = $allTrackBuildings
            ConditionalBuildings = @($members.Id)
            RestrictionCategories = $categories
            Dependencies = [pscustomobject]$dependencySummary
            ExclusivityCandidateCategories = $exclusivityCandidateCategories
            PreservedPrerequisiteCategories = @(
                $members |
                    ForEach-Object { $_.Availability.Policy.PreservedPrerequisiteCategories } |
                    Sort-Object -Unique
            )
            RecommendedActions = @(
                $members |
                    ForEach-Object { $_.Availability.Policy.RecommendedActions } |
                    Sort-Object -Unique
            )
            PossibleMutualExclusion = $exclusivityCandidateCategories.Count -gt 0
            RequiresManualReview = @(
                $members | Where-Object { $_.Availability.Policy.RequiresManualReview }
            ).Count -gt 0
            ContainsUnclassifiedConditions = @(
                $members | Where-Object {
                    $_.Availability.Policy.Disposition -eq 'unclassified_conditions'
                }
            ).Count -gt 0
            BuildingProfiles = $profiles
        })
    }

    $conditionalTrackArray = @($conditionalTracks.ToArray() | Sort-Object SlotType, TrackRoot)

    return [pscustomobject]@{
        Type = $TypeRecord
        BuildingCount = $selected.Count
        MainBuildingCount = $mainBuildings.Count
        ExternalBuildingCount = $externalBuildings.Count
        InternalBuildingCount = $internalBuildings.Count
        ExternalRootCount = $externalRoots.Count
        RequiredExternalSlotsForAllBranches = $requiredExternalSlots
        CurrentVisualExternalSlots = $TypeRecord.VisualExternalSlotCount
        CurrentMaximumExternalCapacity = $currentCapacity
        ExternalVisualSlotDeficit = $visualSlotDeficit
        ExternalCapacityDeficit = $capacityDeficit
        ExternalCapacityVisualMismatch = $capacityVisualMismatch
        ExternalSlotDemand = [pscustomobject]@{
            PhysicalRootTracks = $externalRoots.Count
            AllLeafSpecializationsIfKeptExternal = $requiredExternalSlots
            RecommendedExternalSlots = $externalRoots.Count
            RecommendedPolicy = 'one_external_slot_per_physical_root_track'
            CurrentVisualExternalSlots = $TypeRecord.VisualExternalSlotCount
            CurrentMaximumExternalCapacity = $currentCapacity
            RecommendedVisualSlotDeficit = $recommendedVisualSlotDeficit
            RecommendedCapacityDeficit = $recommendedCapacityDeficit
            LeafModeVisualSlotDeficit = $visualSlotDeficit
            LeafModeCapacityDeficit = $capacityDeficit
        }
        UnknownCapacityValues = @($unknownCapacityValues.ToArray() | Sort-Object -Unique)
        ExternalTracks = $externalTrackAnalysis.ToArray()
        InternalTracks = $internalTrackAnalysis.ToArray()
        InternalAnchorRequirements = $internalAnchorSummary.ToArray()
        BranchPoints = @($branchPoints.ToArray() | Sort-Object Building)
        ExternalBranchGroups = @($externalBranchGroups.ToArray() | Sort-Object CommonBuilding)
        InternalBranchGroups = @($internalBranchGroups.ToArray() | Sort-Object CommonBuilding)
        RecommendedTransformationPlan = [pscustomobject]@{
            ExternalSlots = $externalRoots.Count
            ExternalSpecializationGroupsToInternalize = $externalBranchGroups.Count
            ExistingInternalBranchGroupsToSplit = $internalBranchGroups.Count
            Strategy = 'preserve_physical_external_roots_and_materialize_specializations_as_parallel_internal_tracks'
        }
        ConditionalAvailability = [pscustomobject]@{
            ConditionalBuildingCount = @(
                $selected | Where-Object { $_.HasCanConstruct -or $_.HasCanConstructPotential }
            ).Count
            ConditionalTrackCount = $conditionalTrackArray.Count
            PossibleMutualExclusionTrackCount = @(
                $conditionalTrackArray | Where-Object { $_.PossibleMutualExclusion }
            ).Count
            ManualReviewTrackCount = @(
                $conditionalTrackArray | Where-Object { $_.RequiresManualReview }
            ).Count
            UnclassifiedConditionTrackCount = @(
                $conditionalTrackArray | Where-Object { $_.ContainsUnclassifiedConditions }
            ).Count
            Tracks = $conditionalTrackArray
        }
        Restrictions = $restrictionSummary
        RealmLawFlags = @(
            $selected |
                ForEach-Object { $_.RealmLawFlags } |
                Sort-Object -Unique
        )
        UnresolvedParents = $unresolvedParents
    }
}

function Get-TopLevelRanges {
    param([string[]]$Lines)

    $result = [System.Collections.Generic.List[object]]::new()
    if ($null -eq $Lines) {
        return $result.ToArray()
    }

    $depth = 0
    $name = $null
    $startLine = 0
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        $codeLine = Get-CodeLine $Lines[$index]
        if ($depth -eq 0 -and $codeLine -match '^\s*([A-Za-z0-9_.:-]+)\s*=\s*\{') {
            $name = $Matches[1]
            $startLine = $index + 1
        }

        $depth += Get-BraceDelta $Lines[$index]
        if ($null -ne $name -and $depth -eq 0) {
            $result.Add([pscustomobject]@{
                Id = $name
                StartLine = $startLine
                EndLine = $index + 1
            })
            $name = $null
            $startLine = 0
        }
    }

    return $result.ToArray()
}

function Get-RemovalReferences {
    param(
        [string[]]$BuildingIds,
        [string[]]$SearchRoots,
        [hashtable]$BuildingTypesById
    )

    $idLookup = @{}
    foreach ($id in $BuildingIds) {
        $idLookup[$id] = $true
    }

    $foundReferences = [System.Collections.Generic.List[object]]::new()
    $pattern = '(?<![A-Za-z0-9_])(remove_domicile_building(?:_no_refund)?|lower_domicile_building_no_refund)\s*=\s*([A-Za-z0-9_]+)'

    $candidateFiles = @(
        foreach ($searchRoot in $SearchRoots) {
            if (Test-Path -LiteralPath $searchRoot -PathType Container) {
                Get-ChildItem -LiteralPath $searchRoot -Filter '*.txt' -File -Recurse
            }
        }
    )
    foreach ($matchInfo in @(
        Select-String -LiteralPath $candidateFiles.FullName -Pattern $pattern
    )) {
        if ((Get-CodeLine $matchInfo.Line) -notmatch $pattern) {
            continue
        }
        $target = $Matches[2]
        if ($idLookup.ContainsKey($target)) {
            $foundReferences.Add([pscustomobject]@{
                AbsolutePath = $matchInfo.Path
                Effect = $Matches[1]
                Building = $target
                SourceFile = Get-GameRelativePath $matchInfo.Path
                Line = $matchInfo.LineNumber
            })
        }
    }

    $result = [System.Collections.Generic.List[object]]::new()
    foreach ($fileGroup in @($foundReferences.ToArray() | Group-Object AbsolutePath)) {
        $ranges = @(
            Get-TopLevelRanges (
                Get-Content -LiteralPath $fileGroup.Name -Encoding UTF8
            )
        )
        foreach ($reference in $fileGroup.Group) {
            $container = @(
                $ranges | Where-Object {
                    $_.StartLine -le $reference.Line -and $_.EndLine -ge $reference.Line
                }
            ) | Select-Object -First 1
            $containerId = $(
                if ($null -eq $container) { '<top-level>' }
                else { $container.Id }
            )
            $category = switch ($containerId) {
                'laamp_clear_domicile_buildings_effect' { 'full_domicile_liquidation'; break }
                'tgp_wipe_domicile_effect' { 'domicile_type_conversion'; break }
                'ep3_laamps.1021' { 'camp_purpose_change_cleanup'; break }
                default { 'targeted_gameplay_action' }
            }
            $result.Add([pscustomobject]@{
                Category = $category
                Container = $containerId
                Effect = $reference.Effect
                Building = $reference.Building
                DomicileTypes = @(
                    if ($BuildingTypesById.ContainsKey($reference.Building)) {
                        $BuildingTypesById[$reference.Building]
                    }
                )
                SourceFile = $reference.SourceFile
                Line = $reference.Line
            })
        }
    }

    return $result.ToArray()
}

function Get-RemovalSummary {
    param([object[]]$References)

    $summary = [System.Collections.Generic.List[object]]::new()
    foreach ($group in @($References | Group-Object Category | Sort-Object Name)) {
        $summary.Add([pscustomobject]@{
            Category = $group.Name
            ReferenceCount = $group.Count
            UniqueBuildingCount = @(
                $group.Group.Building | Sort-Object -Unique
            ).Count
            DomicileTypes = @(
                $group.Group |
                    ForEach-Object { $_.DomicileTypes } |
                    Sort-Object -Unique
            )
            Containers = @(
                $group.Group.Container | Sort-Object -Unique
            )
        })
    }
    return $summary.ToArray()
}

function Get-FillEffects {
    param([string]$ScriptedEffectsDirectory)

    $result = [System.Collections.Generic.List[object]]::new()
    Get-ChildItem -LiteralPath $ScriptedEffectsDirectory -Filter '*.txt' -File |
        Sort-Object Name |
        ForEach-Object {
            $sourceFile = Get-GameRelativePath $_.FullName
            $blocks = Get-TopLevelBlocks `
                -Lines (Get-Content -LiteralPath $_.FullName -Encoding UTF8) `
                -SourceFile $sourceFile
            foreach ($key in $blocks.Keys) {
                if ($key -notmatch '^fill_external_.*building_effect$') {
                    continue
                }
                $text = Get-BlockText $blocks[$key].Lines
                $thresholds = @(
                    [regex]::Matches(
                        $text,
                        '(?m)^\s*limit\s*=\s*\{\s*free_external_domicile_building_slots\s*([^}]*)\}'
                    ) | ForEach-Object { $_.Groups[1].Value.Trim() }
                )
                $calledEffects = @(
                    [regex]::Matches(
                        $text,
                        '(?m)^\s*(add_random_external_[A-Za-z0-9_]+)\s*=\s*yes'
                    ) | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
                )
                $result.Add([pscustomobject]@{
                    Id = $key
                    SourceFile = $sourceFile
                    StartLine = $blocks[$key].StartLine
                    FreeSlotThresholds = $thresholds
                    CalledEffects = $calledEffects
                })
            }
        }

    return $result.ToArray()
}

function Add-MarkdownTableRow {
    param(
        [System.Collections.Generic.List[string]]$Output,
        [object[]]$Cells
    )

    $escaped = @(
        $Cells | ForEach-Object {
            ([string]$_).Replace('|', '\|').Replace("`r", ' ').Replace("`n", '<br>')
        }
    )
    $Output.Add('| ' + ($escaped -join ' | ') + ' |')
}

function Format-DependencySummary {
    param([object]$Dependencies)

    $labels = [ordered]@{
        RealmLawFlags = 'laws'
        CulturalParameters = 'culture_parameters'
        CulturalTraditions = 'traditions'
        Innovations = 'innovations'
        Eras = 'eras'
        Terrains = 'terrains'
        Regions = 'regions'
        GovernmentFlags = 'government_flags'
        Governments = 'governments'
        FaithDoctrines = 'doctrines'
        Faiths = 'faiths'
        Religions = 'religions'
        DynastyPerks = 'dynasty_perks'
        HouseAspirationParameters = 'house_aspirations'
        CharacterFlags = 'character_flags'
        Traits = 'traits'
        Relations = 'relations'
        DomicileBuildingParameters = 'domicile_building_parameters'
        DomicileParameters = 'domicile_parameters'
        DlcFeatures = 'dlc_features'
        GameRules = 'game_rules'
        SituationTypes = 'situation_types'
        MenAtArmsBaseTypes = 'men_at_arms_base_types'
        RequiredDomicileBuildings = 'domicile_buildings'
        RequiredDomicileBuildingCounts = 'domicile_building_counts'
        ScriptedTriggers = 'scripted_triggers'
    }
    $parts = [System.Collections.Generic.List[string]]::new()
    foreach ($name in $labels.Keys) {
        $values = @($Dependencies.$name)
        if ($values.Count -gt 0) {
            $parts.Add("$($labels[$name]): " + ($values -join ', '))
        }
    }
    return $parts -join '; '
}

function Write-MarkdownReport {
    param(
        [string]$Path,
        [object]$Manifest
    )

    $output = [System.Collections.Generic.List[string]]::new()
    $output.Add('# Аудит ванильных домицилей для Unlimited Domiciles')
    $output.Add('')
    $output.Add("- Версия схемы отчёта: ``$($Manifest.SchemaVersion)``")
    $output.Add("- Версия CK3: ``$($Manifest.GameVersion)``")
    $output.Add("- Время анализа (UTC): ``$($Manifest.GeneratedAtUtc)``")
    $output.Add("- Корень ванили: ``$($Manifest.GamePath)``")
    $output.Add('- Отчёт только описывает ванильные данные и ничего в них не изменяет.')
    $output.Add('')
    $output.Add('## Сводка')
    $output.Add('')
    $output.Add('| Домицилий | Зданий | Физические внешние линии | Конечные специализации при старой модели | Рекомендовано внешних ячеек | Нарисовано | Вместимость | Дефицит интерфейса | Дефицит вместимости | Внешних развилок | Внутренних развилок |')
    $output.Add('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    foreach ($analysis in $Manifest.Domiciles) {
        Add-MarkdownTableRow $output @(
            $analysis.Type.Id,
            $analysis.BuildingCount,
            $analysis.ExternalSlotDemand.PhysicalRootTracks,
            $analysis.ExternalSlotDemand.AllLeafSpecializationsIfKeptExternal,
            $analysis.ExternalSlotDemand.RecommendedExternalSlots,
            $analysis.ExternalSlotDemand.CurrentVisualExternalSlots,
            $(if ($null -eq $analysis.ExternalSlotDemand.CurrentMaximumExternalCapacity) { '?' } else { $analysis.ExternalSlotDemand.CurrentMaximumExternalCapacity }),
            $analysis.ExternalSlotDemand.RecommendedVisualSlotDeficit,
            $(if ($null -eq $analysis.ExternalSlotDemand.RecommendedCapacityDeficit) { '?' } else { $analysis.ExternalSlotDemand.RecommendedCapacityDeficit }),
            $analysis.ExternalBranchGroups.Count,
            $analysis.InternalBranchGroups.Count
        )
    }
    $output.Add('')
    $output.Add('> Политика RB_UD: одна физическая корневая линия занимает одну внешнюю ячейку. Взаимоисключающие внешние специализации после общей части переводятся в параллельные внутренние треки. Поэтому рекомендуемое число внешних ячеек равно числу физических корневых линий, а не числу всех конечных листьев графа.')
    $output.Add('')
    $output.Add('> Уже внутренние развилки нельзя исправить простой сменой `slot_type`: для их одновременного существования общую внутреннюю начальную часть необходимо расщепить на независимые параллельные линии. Теоретическая вместимость внешних ячеек равна `base_external_slots` плюс унаследованная сумма `domicile_external_slots_capacity_add` по главной линии.')
    $output.Add('')
    $output.Add('### Масштаб планируемого преобразования')
    $output.Add('')
    $output.Add("- Внешних групп специализаций: $($Manifest.TransformationSummary.ExternalBranchGroupCount).")
    $output.Add("- Независимых специализационных треков: $($Manifest.TransformationSummary.ExternalSpecializationTrackCount).")
    $output.Add("- Ванильных зданий, чьи определения потребуется перевести во внутренний тип: $($Manifest.TransformationSummary.BuildingsToInternalizeCount).")
    $output.Add("- Уже внутренних развилок с общей начальной частью: $($Manifest.TransformationSummary.InternalBranchGroupCount).")
    $output.Add("- Домицилии с внешними развилками: ``$($Manifest.TransformationSummary.DomicilesWithExternalBranches -join '`, `')``.")
    $output.Add("- Домицилии с внутренними развилками: ``$($Manifest.TransformationSummary.DomicilesWithInternalBranches -join '`, `')``.")
    $output.Add('')
    $output.Add('### Политика условной совместимости')
    $output.Add('')
    $output.Add("- Всего зданий с условиями доступности: $($Manifest.ConditionalCompatibilitySummary.ConditionalBuildingCount).")
    $output.Add("- Линий-кандидатов на условное взаимоисключение: $($Manifest.ConditionalCompatibilitySummary.PossibleMutualExclusionTrackCount).")
    $output.Add("- Линий, требующих ручной проверки: $($Manifest.ConditionalCompatibilitySummary.ManualReviewTrackCount).")
    $output.Add("- Линий с не классифицированными автоматически условиями: $($Manifest.ConditionalCompatibilitySummary.UnclassifiedConditionTrackCount).")
    $output.Add("- Раскрыто определений scripted triggers: $($Manifest.ConditionalCompatibilitySummary.ResolvedScriptedTriggerDefinitionCount).")
    $output.Add("- Неразрешённых ссылок на scripted triggers: $($Manifest.ConditionalCompatibilitySummary.UnresolvedScriptedTriggerReferenceCount).")
    $output.Add('')
    $output.Add('| Категория | Политика |')
    $output.Add('|---|---|')
    foreach ($property in $Manifest.ConditionalCompatibilitySummary.Policy.PSObject.Properties) {
        Add-MarkdownTableRow $output @($property.Name, $property.Value)
    }
    $output.Add('')
    $output.Add('### Сигнатуры ванильных данных')
    $output.Add('')
    $output.Add('Эти стабильные SHA-256 позволяют после обновления CK3 отличить изменение графа, условий, ассетов или сценариев удаления. Обычный `git diff` перегенерированного JSON покажет, какая именно часть изменилась.')
    $output.Add('')
    $output.Add('| Область | SHA-256 |')
    $output.Add('|---|---|')
    $output.Add("| Структура | ``$($Manifest.VanillaSignatures.StructureSha256)`` |")
    $output.Add("| Условная доступность | ``$($Manifest.VanillaSignatures.AvailabilitySha256)`` |")
    $output.Add("| Иконки и панорамы | ``$($Manifest.VanillaSignatures.AssetsSha256)`` |")
    $output.Add("| Явные удаления | ``$($Manifest.VanillaSignatures.ExplicitRemovalSha256)`` |")
    $output.Add('')

    foreach ($analysis in $Manifest.Domiciles) {
        $output.Add("## ``$($analysis.Type.Id)``")
        $output.Add('')
        $output.Add("Источник типа: ``$($analysis.Type.SourceFile):$($analysis.Type.StartLine)``")
        $output.Add('')
        $output.Add('### Физические внешние линии')
        $output.Add('')
        $output.Add('| Корневое здание | Конечных специализаций | Конечные здания | Ограничения корня |')
        $output.Add('|---|---:|---|---|')
        foreach ($track in $analysis.ExternalTracks) {
            Add-MarkdownTableRow $output @(
                $track.Root,
                $track.RequiredCopiesForAllBranches,
                ($track.Leaves -join ', '),
                ($track.RestrictionCategories -join ', ')
            )
        }
        $output.Add('')

        $output.Add('### Внешние развилки, переводимые во внутренние треки')
        $output.Add('')
        $output.Add('| Общая внешняя часть | Опорная линия | Уровень развилки | Специализации | Существующих внутренних ячеек | Новых внутренних ячеек | Итого после преобразования | Иконки различаются | Панорамы совпадают | Стратегия | Источник |')
        $output.Add('|---|---|---:|---|---:|---:|---:|---|---|---|---|')
        foreach ($group in $analysis.ExternalBranchGroups) {
            Add-MarkdownTableRow $output @(
                $group.CommonBuilding,
                $group.AnchorTrack,
                $group.CommonTier,
                ($group.Specializations.Root -join ', '),
                $group.ExistingInternalSlotsOnAnchorTrack,
                $group.RequiredNewInternalSlots,
                $group.RequiredInternalSlotsAfterTransformation,
                $(if ($group.UniqueSpecializationRootIcons) { 'да' } else { 'нет/не определено' }),
                $(if ($group.SharedSpecializationRootTextures) { 'да' } else { 'нет/не определено' }),
                $group.RecommendedStrategy,
                "$($group.SourceFile):$($group.StartLine)"
            )
        }
        if ($analysis.ExternalBranchGroups.Count -eq 0) {
            $output.Add('| — | — | — | — | 0 | 0 | 0 | — | — | — | — |')
        }
        $output.Add('')

        foreach ($group in $analysis.ExternalBranchGroups) {
            $output.Add("#### Специализации после ``$($group.CommonBuilding)``")
            $output.Add('')
            $output.Add('| Корень специализации | Стартовый уровень | Здания, переводимые во внутренний тип | Листья | Иконки корня | Панорамы корня |')
            $output.Add('|---|---:|---|---|---|---|')
            foreach ($specialization in $group.Specializations) {
                Add-MarkdownTableRow $output @(
                    $specialization.Root,
                    $specialization.StartTier,
                    ($specialization.Buildings -join ', '),
                    ($specialization.Leaves -join ', '),
                    ($specialization.RootIcons -join ', '),
                    ($specialization.RootTextures -join ', ')
                )
            }
            $output.Add('')
        }

        $output.Add('### Уже внутренние развилки, требующие расщепления общей части')
        $output.Add('')
        $output.Add('| Общая внутренняя часть | Родитель | Общий префикс | Специализации | Нужно параллельных ячеек | Стратегия | Источник |')
        $output.Add('|---|---|---|---|---:|---|---|')
        foreach ($group in $analysis.InternalBranchGroups) {
            Add-MarkdownTableRow $output @(
                $group.CommonBuilding,
                $group.AnchorBuilding,
                ($group.SharedInternalPrefix -join ' → '),
                ($group.Specializations.Root -join ', '),
                $group.RequiredParallelInternalSlots,
                $group.RecommendedStrategy,
                "$($group.SourceFile):$($group.StartLine)"
            )
        }
        if ($analysis.InternalBranchGroups.Count -eq 0) {
            $output.Add('| — | — | — | — | 0 | — | — |')
        }
        $output.Add('')

        $output.Add('### Существующие требования внутренних ячеек')
        $output.Add('')
        $output.Add('| Родительская линия | Нужно для всех ветвей | Текущий максимум | Дефицит |')
        $output.Add('|---|---:|---:|---:|')
        foreach ($requirement in $analysis.InternalAnchorRequirements) {
            Add-MarkdownTableRow $output @(
                $requirement.AnchorTrack,
                $requirement.RequiredSlotsForAllBranches,
                $requirement.CurrentMaximumSlots,
                $requirement.Deficit
            )
        }
        if ($analysis.InternalAnchorRequirements.Count -eq 0) {
            $output.Add('| — | 0 | 0 | 0 |')
        }
        $output.Add('')

        $output.Add('### Все исходные точки ветвления')
        $output.Add('')
        $output.Add('| Здание | Тип ячейки | Дочерние ветви |')
        $output.Add('|---|---|---|')
        foreach ($branch in $analysis.BranchPoints) {
            Add-MarkdownTableRow $output @(
                $branch.Building,
                $branch.SlotType,
                ($branch.Children -join ', ')
            )
        }
        if ($analysis.BranchPoints.Count -eq 0) {
            $output.Add('| — | — | — |')
        }
        $output.Add('')

        $output.Add('### Условная доступность и кандидаты на взаимоисключение')
        $output.Add('')
        $output.Add('- Зданий с `can_construct`/`can_construct_potential`: ' + $analysis.ConditionalAvailability.ConditionalBuildingCount + '.')
        $output.Add("- Затронутых линий: $($analysis.ConditionalAvailability.ConditionalTrackCount).")
        $output.Add("- Линий с возможным взаимоисключением: $($analysis.ConditionalAvailability.PossibleMutualExclusionTrackCount).")
        $output.Add("- Линий, требующих ручной проверки культурных или территориальных условий: $($analysis.ConditionalAvailability.ManualReviewTrackCount).")
        $output.Add("- Линий с пока не классифицированными условиями: $($analysis.ConditionalAvailability.UnclassifiedConditionTrackCount).")
        $output.Add('')
        $output.Add('| Линия | Тип | Внешняя опора | Категории-кандидаты | Условные здания | Извлечённые зависимости | Рекомендуемые действия | Ручная проверка |')
        $output.Add('|---|---|---|---|---|---|---|---|')
        $candidateTracks = @(
            $analysis.ConditionalAvailability.Tracks |
                Where-Object {
                    $_.PossibleMutualExclusion -or $_.ContainsUnclassifiedConditions
                }
        )
        foreach ($track in $candidateTracks) {
            Add-MarkdownTableRow $output @(
                $track.TrackRoot,
                $track.SlotType,
                $track.AnchorTrack,
                ($track.ExclusivityCandidateCategories -join ', '),
                ($track.ConditionalBuildings -join ', '),
                (Format-DependencySummary $track.Dependencies),
                ($track.RecommendedActions -join ', '),
                $(if ($track.RequiresManualReview) { 'да' } else { 'нет' })
            )
        }
        if ($candidateTracks.Count -eq 0) {
            $output.Add('| — | — | — | — | — | — | — | — |')
        }
        $output.Add('')
        $output.Add('Полные исходные блоки условий и поключевые профили зданий сохранены в JSON. Культурные и территориальные совпадения являются кандидатами, а не автоматически удаляемыми ограничениями: сначала следует отделить взаимоисключение специализаций от обычных требований прогресса.')
        $output.Add('')

        $output.Add('### Классифицированные ограничения')
        $output.Add('')
        $output.Add('| Категория | Количество | Здания |')
        $output.Add('|---|---:|---|')
        foreach ($category in $analysis.Restrictions.Keys) {
            $ids = @($analysis.Restrictions.$category)
            Add-MarkdownTableRow $output @($category, $ids.Count, ($ids -join ', '))
        }
        $output.Add('')

        if ($analysis.UnresolvedParents.Count -gt 0) {
            $output.Add('### Неразрешённые родительские связи')
            $output.Add('')
            foreach ($item in $analysis.UnresolvedParents) {
                $output.Add("- ``$($item.Building)`` → ``$($item.MissingPreviousBuilding)``")
            }
            $output.Add('')
        }
    }

    $output.Add('## Флаги назначения лагеря')
    $output.Add('')
    $output.Add('| Флаг закона | Здания | Линии | Удалений при смене назначения | Контейнеры очистки | Политика RB_UD |')
    $output.Add('|---|---|---|---:|---|---|')
    foreach ($item in $Manifest.CampPurposeCompatibility) {
        Add-MarkdownTableRow $output @(
            $item.RealmLawFlag,
            ($item.Buildings -join ', '),
            ($item.AffectedTracks -join ', '),
            $item.CleanupReferenceCount,
            ($item.CleanupContainers -join ', '),
            $item.RecommendedPolicy
        )
    }
    if ($Manifest.CampPurposeCompatibility.Count -eq 0) {
        $output.Add('| — | — | — | 0 | — | — |')
        $output.Add('Флаги назначения лагеря в ограничениях зданий не обнаружены.')
    }
    $output.Add('')

    $output.Add('## Явные удаления и понижения зданий домицилей')
    $output.Add('')
    $output.Add('Анализ охватывает явные эффекты `remove_domicile_building`, `remove_domicile_building_no_refund` и `lower_domicile_building_no_refund`. Уничтожение целого объекта домиция движковыми командами без перечисления ID зданий в эту таблицу не входит.')
    $output.Add('')
    $output.Add('| Категория | Ссылок | Уникальных зданий | Домицилии | Контейнеры |')
    $output.Add('|---|---:|---:|---|---|')
    foreach ($summary in $Manifest.RemovalSummary) {
        Add-MarkdownTableRow $output @(
            $summary.Category,
            $summary.ReferenceCount,
            $summary.UniqueBuildingCount,
            ($summary.DomicileTypes -join ', '),
            ($summary.Containers -join ', ')
        )
    }
    if ($Manifest.RemovalSummary.Count -eq 0) {
        $output.Add('| — | 0 | 0 | — | — |')
    }
    $output.Add('')

    $output.Add('### Точечные игровые удаления')
    $output.Add('')
    $output.Add('| Контейнер | Эффект | Здание | Домицилий | Источник |')
    $output.Add('|---|---|---|---|---|')
    $targetedReferences = @(
        $Manifest.DomicileRemovalReferences |
            Where-Object { $_.Category -eq 'targeted_gameplay_action' }
    )
    foreach ($reference in $targetedReferences) {
        Add-MarkdownTableRow $output @(
            $reference.Container,
            $reference.Effect,
            $reference.Building,
            ($reference.DomicileTypes -join ', '),
            "$($reference.SourceFile):$($reference.Line)"
        )
    }
    if ($targetedReferences.Count -eq 0) {
        $output.Add('| — | — | — | — | — |')
    }
    $output.Add('')
    $output.Add('Полный поключевой список ссылок хранится в JSON-манифесте в поле `DomicileRemovalReferences`. Массовые очистки при смене назначения лагеря, полной ликвидации и преобразовании типа домиция сохраняются как отдельные категории и не должны автоматически отключаться модом.')
    $output.Add('')

    $output.Add('## Эффекты начального заполнения внешних ячеек')
    $output.Add('')
    $output.Add('| Эффект | Порог свободных ячеек | Вызываемые эффекты | Источник |')
    $output.Add('|---|---|---|---|')
    foreach ($effect in $Manifest.FillEffects) {
        Add-MarkdownTableRow $output @(
            $effect.Id,
            ($effect.FreeSlotThresholds -join ', '),
            ($effect.CalledEffects -join ', '),
            "$($effect.SourceFile):$($effect.StartLine)"
        )
    }
    $output.Add('')

    $output.Add('## Диагностика графа')
    $output.Add('')
    $output.Add("- Циклические ссылки: $($Manifest.Diagnostics.GraphCycles.Count)")
    $output.Add("- Повторно определённые ID зданий в ванильной базе: $($Manifest.Diagnostics.DuplicateBuildingDefinitions.Count)")
    $output.Add("- Повторно определённые ID типов домицилей: $($Manifest.Diagnostics.DuplicateTypeDefinitions.Count)")
    $output.Add("- Повторно определённые scripted triggers: $($Manifest.Diagnostics.DuplicateScriptedTriggerDefinitions.Count)")
    $output.Add("- Специализации без корневых иконок: $($Manifest.Diagnostics.Transformation.SpecializationsMissingRootIcons.Count)")
    $output.Add("- Специализации без корневых панорам: $($Manifest.Diagnostics.Transformation.SpecializationsMissingRootTextures.Count)")
    $output.Add("- Не классифицированные типы структурных развилок: $($Manifest.Diagnostics.Transformation.UnclassifiedSameSlotBranchPoints.Count)")
    $output.Add("- Условные линии, требующие ручной проверки: $($Manifest.Diagnostics.Availability.ManualReviewTracks.Count)")
    $output.Add("- Условные линии без автоматической классификации: $($Manifest.Diagnostics.Availability.UnclassifiedConditionTracks.Count)")
    $output.Add("- Неразрешённые ссылки на scripted triggers: $($Manifest.Diagnostics.Availability.UnresolvedScriptedTriggerReferences.Count)")
    if ($Manifest.Diagnostics.GraphCycles.Count -gt 0) {
        $output.Add('- Циклы: ' + ($Manifest.Diagnostics.GraphCycles -join ', '))
    }
    $output.Add('')

    $output.Add('## Входные файлы')
    $output.Add('')
    $output.Add('| Файл | SHA-256 |')
    $output.Add('|---|---|')
    foreach ($input in $Manifest.InputFiles) {
        Add-MarkdownTableRow $output @($input.Path, $input.Sha256)
    }
    $output.Add('')

    [IO.File]::WriteAllLines($Path, $output, [Text.UTF8Encoding]::new($true))
}

$script:ResolvedGamePath = [IO.Path]::GetFullPath($GamePath).TrimEnd('\', '/')
$resolvedModPath = [IO.Path]::GetFullPath($ModPath).TrimEnd('\', '/')

$domicileBuildingDirectory = Join-Path $script:ResolvedGamePath 'common\domiciles\buildings'
$domicileTypeDirectory = Join-Path $script:ResolvedGamePath 'common\domiciles\types'
$scriptedEffectsDirectory = Join-Path $script:ResolvedGamePath 'common\scripted_effects'
$scriptedTriggersDirectory = Join-Path $script:ResolvedGamePath 'common\scripted_triggers'
$commonDirectory = Join-Path $script:ResolvedGamePath 'common'
$eventsDirectory = Join-Path $script:ResolvedGamePath 'events'

foreach ($requiredDirectory in @(
    $domicileBuildingDirectory,
    $domicileTypeDirectory,
    $scriptedEffectsDirectory,
    $scriptedTriggersDirectory
)) {
    if (-not (Test-Path -LiteralPath $requiredDirectory -PathType Container)) {
        throw "Required vanilla directory was not found: $requiredDirectory"
    }
}
if (-not (Test-Path -LiteralPath $resolvedModPath -PathType Container)) {
    throw "Unlimited Domiciles mod directory was not found: $resolvedModPath"
}

$launcherSettingsPath = Join-Path (Split-Path $script:ResolvedGamePath -Parent) 'launcher\launcher-settings.json'
$gameVersion = 'unknown'
if (Test-Path -LiteralPath $launcherSettingsPath -PathType Leaf) {
    try {
        $launcherSettings = Get-Content -LiteralPath $launcherSettingsPath -Raw -Encoding UTF8 |
            ConvertFrom-Json
        if ($null -ne $launcherSettings.rawVersion) {
            $gameVersion = [string]$launcherSettings.rawVersion
        }
    }
    catch {
        Write-Warning "Could not read CK3 version from $launcherSettingsPath`: $($_.Exception.Message)"
    }
}

Write-Host "Reading vanilla domicile types from $domicileTypeDirectory"
$typeDatabase = Get-DatabaseBlocks $domicileTypeDirectory
Write-Host "Reading vanilla domicile buildings from $domicileBuildingDirectory"
$buildingDatabase = Get-DatabaseBlocks $domicileBuildingDirectory
Write-Host "Reading vanilla scripted triggers from $scriptedTriggersDirectory"
$scriptedTriggerDatabase = Get-DatabaseBlocks $scriptedTriggersDirectory
$script:ScriptedTriggerBlocks = $scriptedTriggerDatabase.Blocks

$typeIds = @('camp', 'estate', 'yurt', 'east_asian_estate', 'japanese_manor')
$typeRecords = [System.Collections.Generic.List[object]]::new()
foreach ($typeId in $typeIds) {
    if (-not $typeDatabase.Blocks.ContainsKey($typeId)) {
        throw "Expected vanilla domicile type was not found: $typeId"
    }
    $typeRecords.Add((Get-TypeRecord $typeDatabase.Blocks[$typeId]))
}

$buildingRecords = [System.Collections.Generic.List[object]]::new()
foreach ($buildingId in @($buildingDatabase.Blocks.Keys | Sort-Object)) {
    $buildingRecords.Add((Get-BuildingRecord $buildingDatabase.Blocks[$buildingId]))
}

$script:AllBuildingById = @{}
foreach ($building in $buildingRecords) {
    $script:AllBuildingById[$building.Id] = $building
}
$script:GraphCycles = [System.Collections.Generic.HashSet[string]]::new()

$domicileAnalyses = [System.Collections.Generic.List[object]]::new()
foreach ($typeRecord in $typeRecords) {
    Write-Host "Analyzing $($typeRecord.Id)..."
    $domicileAnalyses.Add((Get-DomicileAnalysis $typeRecord $buildingRecords.ToArray()))
}

$campAnalysis = @($domicileAnalyses.ToArray() | Where-Object { $_.Type.Id -eq 'camp' })[0]
$buildingTypesById = @{}
foreach ($building in $buildingRecords) {
    $buildingTypesById[$building.Id] = @($building.AllowedDomicileTypes)
}
Write-Host 'Scanning vanilla scripts for explicit domicile building removal effects...'
$domicileRemovalReferences = @(
    Get-RemovalReferences `
        -BuildingIds @($buildingRecords | Select-Object -ExpandProperty Id) `
        -SearchRoots @($commonDirectory, $eventsDirectory) `
        -BuildingTypesById $buildingTypesById
)
$removalSummary = @(Get-RemovalSummary $domicileRemovalReferences)

Write-Host 'Reading vanilla domicile fill effects...'
$fillEffects = @(Get-FillEffects $scriptedEffectsDirectory)

$inputFiles = [System.Collections.Generic.List[object]]::new()
foreach ($directory in @($domicileTypeDirectory, $domicileBuildingDirectory)) {
    Get-ChildItem -LiteralPath $directory -Filter '*.txt' -File |
        Where-Object { -not $_.Name.StartsWith('_') } |
        Sort-Object FullName |
        ForEach-Object {
            $inputFiles.Add([pscustomobject]@{
                Path = Get-GameRelativePath $_.FullName
                Sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
            })
        }
}
$extraInputPaths = [System.Collections.Generic.HashSet[string]]::new(
    [StringComparer]::OrdinalIgnoreCase
)
$null = $extraInputPaths.Add(
    (Join-Path $script:ResolvedGamePath 'common\laws\00_realm_laws.txt')
)
foreach ($relativePath in @(
    $domicileRemovalReferences | Select-Object -ExpandProperty SourceFile
    $fillEffects | Select-Object -ExpandProperty SourceFile
    $buildingRecords |
        ForEach-Object {
            @($_.Availability.CanConstruct, $_.Availability.CanConstructPotential) |
                Where-Object { $null -ne $_ } |
                ForEach-Object {
                    $_.ResolvedScriptedTriggers |
                        ForEach-Object { $_.SourceFile }
                }
        }
)) {
    $null = $extraInputPaths.Add((Join-Path $script:ResolvedGamePath $relativePath))
}
foreach ($extraInput in @($extraInputPaths | Sort-Object)) {
    if (Test-Path -LiteralPath $extraInput -PathType Leaf) {
        $inputFiles.Add([pscustomobject]@{
            Path = Get-GameRelativePath $extraInput
            Sha256 = (Get-FileHash -LiteralPath $extraInput -Algorithm SHA256).Hash
        })
    }
}

$allExternalBranchGroups = @(
    $domicileAnalyses | ForEach-Object { $_.ExternalBranchGroups }
)
$allInternalBranchGroups = @(
    $domicileAnalyses | ForEach-Object { $_.InternalBranchGroups }
)
$externalSpecializationTracks = @(
    $allExternalBranchGroups | ForEach-Object { $_.Specializations }
)
$internalSpecializationTracks = @(
    $allInternalBranchGroups | ForEach-Object { $_.Specializations }
)
$buildingsToInternalize = @(
    $externalSpecializationTracks |
        ForEach-Object { $_.Buildings } |
        Sort-Object -Unique
)
$sharedInternalPrefixBuildings = @(
    $allInternalBranchGroups |
        ForEach-Object { $_.SharedInternalPrefix } |
        Sort-Object -Unique
)
$campPurposeFlags = @(
    $campAnalysis.RealmLawFlags | Where-Object { $_ -match '^unlocks_' }
)
$campPurposeCompatibility = [System.Collections.Generic.List[object]]::new()
foreach ($flag in @($campPurposeFlags | Sort-Object)) {
    $affectedBuildings = @(
        $buildingRecords |
            Where-Object {
                $_.AllowedDomicileTypes -contains 'camp' -and
                $_.RealmLawFlags -contains $flag
            } |
            Sort-Object Id
    )
    $affectedIds = @($affectedBuildings.Id)
    $cleanupReferences = @(
        $domicileRemovalReferences |
            Where-Object {
                $_.Category -eq 'camp_purpose_change_cleanup' -and
                $affectedIds -contains $_.Building
            }
    )
    $campPurposeCompatibility.Add([pscustomobject]@{
        RealmLawFlag = $flag
        Buildings = $affectedIds
        AffectedTracks = @(
            $campAnalysis.ConditionalAvailability.Tracks |
                Where-Object { $_.Dependencies.RealmLawFlags -contains $flag } |
                Select-Object -ExpandProperty TrackRoot |
                Sort-Object -Unique
        )
        CleanupReferenceCount = $cleanupReferences.Count
        CleanupContainers = @($cleanupReferences.Container | Sort-Object -Unique)
        RecommendedPolicy = 'remove_gate_and_disable_only_purpose_change_cleanup'
    })
}

$structureSignatureLines = [System.Collections.Generic.List[string]]::new()
$availabilitySignatureLines = [System.Collections.Generic.List[string]]::new()
$assetSignatureLines = [System.Collections.Generic.List[string]]::new()
foreach ($building in @($buildingRecords | Sort-Object Id)) {
    $capacityText = @(
        $building.ExternalCapacityAdds |
            ForEach-Object { $_.Raw }
    ) -join ','
    $structureSignatureLines.Add(@(
        $building.Id,
        ($building.AllowedDomicileTypes -join ','),
        $building.SlotType,
        $building.PreviousBuilding,
        $building.InternalSlotsRaw,
        $capacityText
    ) -join '|')

    $canConstructScript = ''
    $canConstructPotentialScript = ''
    $resolvedTriggerIds = [System.Collections.Generic.List[string]]::new()
    if ($null -ne $building.Availability.CanConstruct) {
        $canConstructScript = $building.Availability.CanConstruct.Script
        foreach ($item in @($building.Availability.CanConstruct.ResolvedScriptedTriggers)) {
            $resolvedTriggerIds.Add($item.Id)
        }
    }
    if ($null -ne $building.Availability.CanConstructPotential) {
        $canConstructPotentialScript = $building.Availability.CanConstructPotential.Script
        foreach ($item in @($building.Availability.CanConstructPotential.ResolvedScriptedTriggers)) {
            $resolvedTriggerIds.Add($item.Id)
        }
    }
    $availabilitySignatureLines.Add(@(
        $building.Id,
        $canConstructScript,
        $canConstructPotentialScript,
        (@($resolvedTriggerIds.ToArray() | Sort-Object -Unique) -join ',')
    ) -join '|')
    $assetSignatureLines.Add(@(
        $building.Id,
        ($building.Icons -join ','),
        ($building.Textures -join ',')
    ) -join '|')
}
$removalSignatureLines = @(
    $domicileRemovalReferences |
        Sort-Object SourceFile, Line, Effect, Building |
        ForEach-Object {
            @($_.Category, $_.Container, $_.Effect, $_.Building, $_.SourceFile, $_.Line) -join '|'
        }
)
$resolvedAvailabilityTriggerIds = @(
    $buildingRecords |
        ForEach-Object {
            @($_.Availability.CanConstruct, $_.Availability.CanConstructPotential) |
                Where-Object { $null -ne $_ } |
                ForEach-Object {
                    $_.ResolvedScriptedTriggers |
                        ForEach-Object { $_.Id }
                }
        } |
        Sort-Object -Unique
)
$unresolvedAvailabilityTriggerIds = @(
    $buildingRecords |
        ForEach-Object {
            @($_.Availability.CanConstruct, $_.Availability.CanConstructPotential) |
                Where-Object { $null -ne $_ } |
                ForEach-Object { $_.UnresolvedScriptedTriggers }
        } |
        Sort-Object -Unique
)

$manifest = [pscustomobject]@{
    SchemaVersion = 2
    GeneratedAtUtc = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    GameVersion = $gameVersion
    GamePath = $script:ResolvedGamePath
    DomicileTypeIds = $typeIds
    Domiciles = $domicileAnalyses.ToArray()
    Buildings = $buildingRecords.ToArray()
    VanillaSignatures = [pscustomobject]@{
        StructureSha256 = Get-StringSha256 ($structureSignatureLines -join "`n")
        AvailabilitySha256 = Get-StringSha256 ($availabilitySignatureLines -join "`n")
        AssetsSha256 = Get-StringSha256 ($assetSignatureLines -join "`n")
        ExplicitRemovalSha256 = Get-StringSha256 ($removalSignatureLines -join "`n")
        Purpose = 'stable fingerprints for detecting relevant vanilla changes between regenerated manifests'
    }
    TransformationSummary = [pscustomobject]@{
        Policy = 'preserve_physical_external_roots_and_materialize_specializations_as_parallel_internal_tracks'
        RecommendedExternalSlotsTotal = @(
            $domicileAnalyses |
                Measure-Object -Property ExternalRootCount -Sum
        )[0].Sum
        ExternalBranchGroupCount = $allExternalBranchGroups.Count
        ExternalSpecializationTrackCount = $externalSpecializationTracks.Count
        BuildingsToInternalizeCount = $buildingsToInternalize.Count
        BuildingsToInternalize = $buildingsToInternalize
        InternalBranchGroupCount = $allInternalBranchGroups.Count
        InternalSpecializationTrackCount = $internalSpecializationTracks.Count
        SharedInternalPrefixBuildingCount = $sharedInternalPrefixBuildings.Count
        SharedInternalPrefixBuildings = $sharedInternalPrefixBuildings
        DomicilesWithExternalBranches = @(
            $domicileAnalyses |
                Where-Object { $_.ExternalBranchGroups.Count -gt 0 } |
                ForEach-Object { $_.Type.Id }
        )
        DomicilesWithInternalBranches = @(
            $domicileAnalyses |
                Where-Object { $_.InternalBranchGroups.Count -gt 0 } |
                ForEach-Object { $_.Type.Id }
        )
    }
    ConditionalCompatibilitySummary = [pscustomobject]@{
        ConditionalBuildingCount = @(
            $buildingRecords |
                Where-Object { $_.HasCanConstruct -or $_.HasCanConstructPotential }
        ).Count
        PossibleMutualExclusionTrackCount = @(
            $domicileAnalyses |
                ForEach-Object { $_.ConditionalAvailability.Tracks } |
                Where-Object { $_.PossibleMutualExclusion }
        ).Count
        ManualReviewTrackCount = @(
            $domicileAnalyses |
                ForEach-Object { $_.ConditionalAvailability.Tracks } |
                Where-Object { $_.RequiresManualReview }
        ).Count
        UnclassifiedConditionTrackCount = @(
            $domicileAnalyses |
                ForEach-Object { $_.ConditionalAvailability.Tracks } |
                Where-Object { $_.ContainsUnclassifiedConditions }
        ).Count
        ResolvedScriptedTriggerDefinitionCount = $resolvedAvailabilityTriggerIds.Count
        ResolvedScriptedTriggerDefinitions = $resolvedAvailabilityTriggerIds
        UnresolvedScriptedTriggerReferenceCount = $unresolvedAvailabilityTriggerIds.Count
        UnresolvedScriptedTriggerReferences = $unresolvedAvailabilityTriggerIds
        Policy = [pscustomobject]@{
            CampPurpose = 'remove_gate_and_disable_only_corresponding_purpose_change_cleanup'
            CultureOrLanguage = 'manual_review_remove_only_mutual_exclusivity'
            Territory = 'manual_review_remove_only_mutual_exclusivity'
            Progression = 'preserve_vanilla_prerequisite'
            GovernmentOrStatus = 'preserve_vanilla_prerequisite'
            Faith = 'preserve_vanilla_prerequisite'
            OtherRealmLaw = 'preserve_vanilla_prerequisite'
            ScriptedTrigger = 'resolve_definition_then_preserve_unrelated_prerequisite'
            CharacterDynastyOrHouse = 'preserve_vanilla_prerequisite'
            StateOrFeature = 'preserve_vanilla_prerequisite'
            Unclassified = 'preserve_until_manually_classified'
        }
    }
    CampPurposeFlags = $campPurposeFlags
    CampPurposeCompatibility = $campPurposeCompatibility.ToArray()
    DomicileRemovalReferences = $domicileRemovalReferences
    RemovalSummary = $removalSummary
    FillEffects = $fillEffects
    Diagnostics = [pscustomobject]@{
        GraphCycles = @($script:GraphCycles | Sort-Object)
        DuplicateBuildingDefinitions = @($buildingDatabase.Duplicates)
        DuplicateTypeDefinitions = @($typeDatabase.Duplicates)
        DuplicateScriptedTriggerDefinitions = @($scriptedTriggerDatabase.Duplicates)
        Transformation = [pscustomobject]@{
            SpecializationsMissingRootIcons = @(
                @($externalSpecializationTracks + $internalSpecializationTracks) |
                    Where-Object { $_.RootIcons.Count -eq 0 } |
                    Select-Object -ExpandProperty Root |
                    Sort-Object -Unique
            )
            SpecializationsMissingRootTextures = @(
                @($externalSpecializationTracks + $internalSpecializationTracks) |
                    Where-Object { $_.RootTextures.Count -eq 0 } |
                    Select-Object -ExpandProperty Root |
                    Sort-Object -Unique
            )
            UnclassifiedSameSlotBranchPoints = @(
                $domicileAnalyses |
                    ForEach-Object { $_.BranchPoints } |
                    Where-Object { $_.SlotType -notin @('external', 'internal') }
            )
        }
        Availability = [pscustomobject]@{
            UnresolvedScriptedTriggerReferences = $unresolvedAvailabilityTriggerIds
            UnclassifiedConditionTracks = @(
                $domicileAnalyses |
                    ForEach-Object { $_.ConditionalAvailability.Tracks } |
                    Where-Object { $_.ContainsUnclassifiedConditions } |
                    ForEach-Object {
                        [pscustomobject]@{
                            TrackRoot = $_.TrackRoot
                            SlotType = $_.SlotType
                            ConditionalBuildings = $_.ConditionalBuildings
                            ScriptedTriggers = $_.Dependencies.ScriptedTriggers
                        }
                    }
            )
            ManualReviewTracks = @(
                $domicileAnalyses |
                    ForEach-Object { $_.ConditionalAvailability.Tracks } |
                    Where-Object { $_.RequiresManualReview } |
                    ForEach-Object {
                        [pscustomobject]@{
                            TrackRoot = $_.TrackRoot
                            SlotType = $_.SlotType
                            Categories = $_.ExclusivityCandidateCategories
                            ConditionalBuildings = $_.ConditionalBuildings
                        }
                    }
            )
        }
    }
    InputFiles = @($inputFiles.ToArray() | Sort-Object Path)
}

$reportDirectory = Join-Path $resolvedModPath 'docs\generated'
$manifestDirectory = Join-Path $resolvedModPath 'tools\generated'
$null = New-Item -ItemType Directory -Path $reportDirectory -Force
$null = New-Item -ItemType Directory -Path $manifestDirectory -Force

$manifestPath = Join-Path $manifestDirectory 'RB_UD_vanilla_manifest.json'
$reportPath = Join-Path $reportDirectory 'RB_UD_VANILLA_AUDIT.md'

$manifestJson = $manifest | ConvertTo-Json -Depth 100 -Compress
[IO.File]::WriteAllText($manifestPath, $manifestJson + "`n", [Text.UTF8Encoding]::new($false))
Write-MarkdownReport -Path $reportPath -Manifest $manifest

$unresolvedCount = @(
    $manifest.Domiciles | ForEach-Object { $_.UnresolvedParents }
).Count

Write-Host ''
Write-Host "Vanilla domicile audit completed for CK3 $gameVersion."
Write-Host "Manifest: $manifestPath"
Write-Host "Report:   $reportPath"
Write-Host "Graph cycles: $($manifest.Diagnostics.GraphCycles.Count)"
Write-Host "Unresolved previous_building references: $unresolvedCount"

if ($manifest.Diagnostics.GraphCycles.Count -gt 0 -or $unresolvedCount -gt 0) {
    throw 'Vanilla domicile graph validation failed. Inspect the generated report.'
}
