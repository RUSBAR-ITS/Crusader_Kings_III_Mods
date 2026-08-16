[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GamePath,

    [string]$ModPath,
    [string]$ManifestPath,
    [string]$PlanPath,
    [string]$LayoutPath,
    [string]$SettingsPath
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
if ([string]::IsNullOrWhiteSpace($SettingsPath)) {
    $SettingsPath = Join-Path $ModPath 'tools\RB_UD_generation_settings.json'
}
$ManifestPath = [IO.Path]::GetFullPath($ManifestPath)
$PlanPath = [IO.Path]::GetFullPath($PlanPath)
$LayoutPath = [IO.Path]::GetFullPath($LayoutPath)
$SettingsPath = [IO.Path]::GetFullPath($SettingsPath)

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

function Remove-DirectScalar {
    param([string[]]$Lines, [string]$Field, [switch]$AllowMissing)
    $depth = 0
    $found = [Collections.Generic.List[int]]::new()
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        $code = Get-CodeLine $Lines[$index]
        if ($depth -eq 1 -and $code -match ('^\s*' + [regex]::Escape($Field) + '\s*=')) {
            $found.Add($index)
        }
        $depth += Get-BraceDelta $Lines[$index]
    }
    if ($found.Count -eq 0) {
        if ($AllowMissing) { return $Lines }
        throw "Direct scalar '$Field' not found in $($Lines[0])."
    }
    $result = $Lines
    foreach ($lineIndex in @($found | Sort-Object -Descending)) {
        $result = Replace-LineRange $result $lineIndex $lineIndex @()
    }
    return $result
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

function Add-OrCreateConditionInDirectBlock {
    param(
        [string[]]$Lines,
        [string]$Field,
        [string]$ConditionLine
    )
    $range = Get-DirectBlockRange $Lines $Field
    if ($null -ne $range) {
        return Add-ConditionToDirectBlock $Lines $Field $ConditionLine
    }
    return Replace-LineRange $Lines 1 0 @(
        "`t$Field = {",
        "`t`t$ConditionLine",
        "`t}"
    )
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

function Test-Utf8Bom {
    param([string]$Path)
    $bytes = [IO.File]::ReadAllBytes($Path)
    return (
        $bytes.Length -ge 3 -and
        $bytes[0] -eq 0xEF -and
        $bytes[1] -eq 0xBB -and
        $bytes[2] -eq 0xBF
    )
}

function Get-RequiredConstantDefinitionLines {
    param([object[]]$Objects)
    $tokens = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($object in Convert-ToArray $Objects) {
        foreach ($line in Convert-ToArray $object.Lines) {
            $code = Get-CodeLine ([string]$line)
            foreach ($match in [regex]::Matches($code, '@[A-Za-z0-9_]+')) {
                [void]$tokens.Add($match.Value)
            }
        }
    }
    $definitions = [Collections.Generic.List[string]]::new()
    foreach ($token in @($tokens | Sort-Object)) {
        if ($script:CustomConstantDefinitions.ContainsKey($token)) {
            $definitions.Add("$token = $($script:CustomConstantDefinitions[$token])")
            continue
        }
        if ($script:VanillaConstantDefinitions.ContainsKey($token)) {
            $definitions.Add("$token = $($script:VanillaConstantDefinitions[$token])")
            continue
        }
        throw "No validated definition found for generated constant $token."
    }
    return $definitions.ToArray()
}

function Get-CostConstantId {
    param([string]$Resource, [string]$NumericValue)
    $suffix = $NumericValue.Trim()
    if ($suffix.StartsWith('-')) {
        $suffix = 'neg_' + $suffix.Substring(1)
    }
    $suffix = $suffix.Replace('.', '_')
    return "RB_UD_cost_${Resource}_${suffix}_value"
}

function Convert-DirectNumericCostsToScriptValues {
    param([string[]]$Lines)
    $range = Get-DirectBlockRange $Lines 'cost'
    if ($null -eq $range) { return $Lines }

    $result = @($Lines)
    $pattern = '(?<![A-Za-z0-9_])(' + $script:CostResourcePattern + ')\s*=\s*(-?[0-9]+(?:\.[0-9]+)?)(?=\s*(?:#|\}|$))'
    for ($index = $range.Start; $index -le $range.End; $index++) {
        $result[$index] = [regex]::Replace(
            $result[$index],
            $pattern,
            {
                param($match)
                $resource = $match.Groups[1].Value
                $numericValue = $match.Groups[2].Value
                $constantId = Get-CostConstantId $resource $numericValue
                if (
                    $script:GeneratedCostConstantDefinitions.ContainsKey($constantId) -and
                    $script:GeneratedCostConstantDefinitions[$constantId] -ne $numericValue
                ) {
                    throw "Conflicting generated cost value for $constantId."
                }
                $script:GeneratedCostConstantDefinitions[$constantId] = $numericValue
                return "$resource = $constantId"
            }
        )
    }
    return $result
}

function Get-BuildingFamilyRootId {
    param([string]$BuildingId, [hashtable]$RecordsById)
    $visited = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    $currentId = $BuildingId
    while ($true) {
        if (-not $visited.Add($currentId)) {
            throw "Cycle detected in vanilla domicile-building chain at '$currentId'."
        }
        if (-not $RecordsById.ContainsKey($currentId)) {
            throw "Unknown domicile-building chain member '$currentId'."
        }
        $previousId = [string]$RecordsById[$currentId].PreviousBuilding
        if ([string]::IsNullOrWhiteSpace($previousId)) { return $currentId }
        if (-not $RecordsById.ContainsKey($previousId)) {
            throw "Building '$currentId' references missing previous building '$previousId'."
        }
        $currentId = $previousId
    }
}

function Get-FamilyTargetRelativePath {
    param([string]$DomicileType, [string]$FamilyRootId)
    $familyName = $FamilyRootId -replace '_01$', ''
    $typePrefix = "${DomicileType}_"
    if ($familyName.StartsWith($typePrefix, [StringComparison]::Ordinal)) {
        $familyName = $familyName.Substring($typePrefix.Length)
    }
    elseif ($DomicileType -eq 'japanese_manor' -and $familyName.StartsWith('japanese_', [StringComparison]::Ordinal)) {
        $familyName = $familyName.Substring('japanese_'.Length)
    }
    if ($DomicileType -eq 'yurt' -and $familyName.EndsWith('_yurt', [StringComparison]::Ordinal)) {
        $familyName = $familyName.Substring(0, $familyName.Length - '_yurt'.Length)
    }
    $safeType = $DomicileType -replace '[^A-Za-z0-9_]', '_'
    $safeFamily = $familyName -replace '[^A-Za-z0-9_]', '_'
    return "common\domiciles\buildings\zzz_RB_UD_${safeType}_${safeFamily}.txt"
}

foreach ($requiredPath in @($ManifestPath, $PlanPath, $LayoutPath, $SettingsPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required input not found: $requiredPath"
    }
}

$manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$planWrapper = Get-Content -LiteralPath $PlanPath -Raw -Encoding UTF8 | ConvertFrom-Json
$layoutConfig = Get-Content -LiteralPath $LayoutPath -Raw -Encoding UTF8 | ConvertFrom-Json
$generationSettings = Get-Content -LiteralPath $SettingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
$plan = $planWrapper.Plan

if ([int]$generationSettings.SchemaVersion -ne 1) {
    throw "Unsupported generation-settings schema $($generationSettings.SchemaVersion)."
}
if ([string]$generationSettings.OutputGrouping -ne 'vanilla_root_family') {
    throw "Unsupported output grouping '$($generationSettings.OutputGrouping)'."
}
$constructionTimeDays = [int]$generationSettings.ConstructionTime.DefaultDays
if ($constructionTimeDays -lt 1) {
    throw 'ConstructionTime.DefaultDays must be a positive integer.'
}
$constructionTimeToken = [string]$generationSettings.ConstructionTime.LocalConstant
if ($constructionTimeToken -notmatch '^@[A-Za-z0-9_]+$') {
    throw "Invalid local construction-time constant '$constructionTimeToken'."
}
$costResources = @(
    Convert-ToArray $generationSettings.Costs.ReplaceDirectNumericResources |
        ForEach-Object { [string]$_ }
)
if ($costResources.Count -eq 0 -or @($costResources | Where-Object { $_ -notmatch '^[A-Za-z0-9_]+$' }).Count -gt 0) {
    throw 'Costs.ReplaceDirectNumericResources must contain valid database field names.'
}
$script:CostResourcePattern = ($costResources | ForEach-Object { [regex]::Escape($_) }) -join '|'

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
$script:VanillaConstantDefinitions = @{}
$script:CustomConstantDefinitions = @{}
$script:GeneratedCostConstantDefinitions = @{}
$script:CustomConstantDefinitions[$constructionTimeToken] = [string]$constructionTimeDays
foreach ($input in Convert-ToArray $manifest.InputFiles) {
    $normalizedInputPath = ([string]$input.Path) -replace '/', '\'
    if ($normalizedInputPath -notmatch '^common\\domiciles\\buildings\\.*\.txt$') { continue }
    $fullPath = Join-Path $GamePath $input.Path
    foreach ($line in Get-Content -LiteralPath $fullPath -Encoding UTF8) {
        $code = Get-CodeLine $line
        if ($code -notmatch '^\s*(@[A-Za-z0-9_]+)\s*=\s*(.*?)\s*$') { continue }
        $token = $Matches[1]
        $value = $Matches[2].Trim()
        if (
            $script:VanillaConstantDefinitions.ContainsKey($token) -and
            $script:VanillaConstantDefinitions[$token] -ne $value
        ) {
            throw "Conflicting validated vanilla definitions for $token."
        }
        $script:VanillaConstantDefinitions[$token] = $value
    }
}
$buildingRecordById = @{}
foreach ($building in $manifest.Buildings) { $buildingRecordById[$building.Id] = $building }
$buildingLines = @{}
$originalBuildingText = @{}
foreach ($buildingId in @($buildingRecordById.Keys | Sort-Object)) {
    $record = $buildingRecordById[$buildingId]
    $lines = Get-VanillaObjectLines $record.SourceFile $buildingId
    $buildingLines[$buildingId] = $lines
    $originalBuildingText[$buildingId] = $lines -join "`n"
}
$expectedBuildingCount = @(Convert-ToArray $manifest.Buildings).Count
if ($buildingLines.Count -ne $expectedBuildingCount) {
    throw "Full building inventory mismatch: expected $expectedBuildingCount, loaded $($buildingLines.Count)."
}

$familyRootByBuildingId = @{}
foreach ($buildingId in @($buildingRecordById.Keys | Sort-Object)) {
    $familyRootByBuildingId[$buildingId] = Get-BuildingFamilyRootId $buildingId $buildingRecordById
}
$familyRoots = @($familyRootByBuildingId.Values | Sort-Object -Unique)
$expectedCoverage = $generationSettings.ExpectedCoverage
if ($expectedBuildingCount -ne [int]$expectedCoverage.BuildingCount) {
    throw "Configured building coverage is $($expectedCoverage.BuildingCount), but the manifest contains $expectedBuildingCount."
}
foreach ($expectedFamilyProperty in $expectedCoverage.FamiliesByDomicileType.PSObject.Properties) {
    $domicileType = $expectedFamilyProperty.Name
    $actualFamilyCount = @(
        $buildingRecordById.Values |
            Where-Object { $_.AllowedDomicileTypes -contains $domicileType } |
            ForEach-Object { $familyRootByBuildingId[$_.Id] } |
            Sort-Object -Unique
    ).Count
    if ($actualFamilyCount -ne [int]$expectedFamilyProperty.Value) {
        throw "Family coverage mismatch for '$domicileType': expected $($expectedFamilyProperty.Value), got $actualFamilyCount."
    }
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

# Terminal external specializations become independent internal tracks. Their
# roots must point to an external base building (not a higher external tier),
# while the former tier remains an explicit construction prerequisite. Direct
# internal_slots values on converted buildings are invalid engine data and are
# therefore removed; capacity belongs to the external anchor line instead.
foreach ($branch in Convert-ToArray $plan.ExternalBranchOverrides) {
    foreach ($buildingId in Convert-ToArray $branch.BuildingsChangingSlotType) {
        $buildingLines[$buildingId] = Set-DirectScalar $buildingLines[$buildingId] 'slot_type' 'internal'
        $buildingLines[$buildingId] = Remove-DirectScalar `
            $buildingLines[$buildingId] `
            'internal_slots' `
            -AllowMissing
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

# Apply external-branch reanchoring after access-gate rewrites so the explicit
# common-tier prerequisite cannot be discarded by a replacement condition.
foreach ($branch in Convert-ToArray $plan.ExternalBranchOverrides) {
    foreach ($rootId in Convert-ToArray $branch.SpecializationRoots) {
        $buildingLines[$rootId] = Set-DirectScalar `
            $buildingLines[$rootId] `
            'previous_building' `
            ([string]$branch.RootPreviousBuilding)
        $conditionText = (Get-DirectBlock $buildingLines[$rootId] 'can_construct') -join "`n"
        if ($conditionText -notmatch ('has_domicile_building_or_higher\s*=\s*' + [regex]::Escape([string]$branch.RequiredCommonBuilding))) {
            $buildingLines[$rootId] = Add-OrCreateConditionInDirectBlock `
                $buildingLines[$rootId] `
                'can_construct' `
                ([string]$branch.RootConstructionPrerequisite)
        }
    }
}

# Full-mirror scalar normalization. construction_time is an integer database
# field and therefore uses a file-local @ constant. Direct numeric resource
# costs are moved to generated global script values; existing vanilla script
# values remain intact.
foreach ($buildingId in @($buildingLines.Keys | Sort-Object)) {
    $buildingLines[$buildingId] = Set-DirectScalar `
        $buildingLines[$buildingId] `
        'construction_time' `
        $constructionTimeToken
    $buildingLines[$buildingId] = Convert-DirectNumericCostsToScriptValues $buildingLines[$buildingId]
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

# Safe scripted-effect overrides. The fill effects retain vanilla's number of
# initially generated external buildings despite RB_UD's larger capacity. The
# camp-purpose cleanup is disabled at its dedicated caller instead of
# duplicating the vanilla event ID used to perform demolition.
$scriptedEffectObjects = [Collections.Generic.List[object]]::new()
foreach ($fillOverride in Convert-ToArray $plan.InitialFillEffectOverrides) {
    $lines = [Collections.Generic.List[string]]::new()
    $lines.Add("$($fillOverride.Effect) = {")
    $lines.Add("`tswitch = {")
    $lines.Add("`t`ttrigger = has_domicile_building_or_higher")
    foreach ($branch in Convert-ToArray $fillOverride.Branches) {
        $lines.Add("`t`t$($branch.MainBuilding) = {")
        $lines.Add("`t`t`twhile = {")
        $lines.Add("`t`t`t`tcount = $($branch.MaximumIterations)")
        $lines.Add("`t`t`t`tlimit = { free_external_domicile_building_slots >= $($branch.TargetFreeSlotThreshold) }")
        $lines.Add("`t`t`t`t$($fillOverride.CalledEffect) = yes")
        $lines.Add("`t`t`t}")
        $lines.Add("`t`t}")
    }
    $lines.Add("`t}")
    $lines.Add('}')
    $scriptedEffectObjects.Add([pscustomobject]@{
        Id = $fillOverride.Effect
        SourceFile = Get-RelativeSourceFromLocation $fillOverride.VanillaSource
        StartLine = [int]($fillOverride.VanillaSource -replace '^.*:', '')
        Lines = $lines.ToArray()
        TargetFile = $fillOverride.TargetOverrideFile
    })
}
$cleanupEffectId = [string]$plan.RemovalOverrides.Suppress.TargetScriptedEffect
$scriptedEffectObjects.Add([pscustomobject]@{
    Id = $cleanupEffectId
    SourceFile = Get-RelativeSourceFromLocation $plan.RemovalOverrides.Suppress.VanillaSource
    StartLine = [int]($plan.RemovalOverrides.Suppress.VanillaSource -replace '^.*:', '')
    Lines = @(
        "$cleanupEffectId = {",
        "`t# RB_UD: purpose-specific camp buildings are intentionally retained.",
        '}'
    )
    TargetFile = $plan.TargetFiles.ScriptedEffects
})

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
        if ($null -ne (Get-DirectScalarValue $buildingLines[$buildingId] 'internal_slots')) {
            throw "Converted internal specialization '$buildingId' still grants nested internal slots."
        }
    }
    foreach ($rootId in Convert-ToArray $branch.SpecializationRoots) {
        if ((Get-DirectScalarValue $buildingLines[$rootId] 'previous_building') -ne $branch.RootPreviousBuilding) {
            throw "Converted specialization root '$rootId' has an invalid previous building."
        }
        $conditionText = (Get-DirectBlock $buildingLines[$rootId] 'can_construct') -join "`n"
        if ($conditionText -notmatch ('has_domicile_building_or_higher\s*=\s*' + [regex]::Escape($branch.RequiredCommonBuilding))) {
            throw "Converted specialization root '$rootId' lost its common-tier prerequisite."
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
foreach ($buildingId in @($buildingLines.Keys | Sort-Object)) {
    $actualConstructionTime = Get-DirectScalarValue $buildingLines[$buildingId] 'construction_time'
    if ($actualConstructionTime -ne $constructionTimeToken) {
        throw "Building '$buildingId' was not normalized to $constructionTimeToken."
    }
    $generatedPreviousBuilding = Get-DirectScalarValue $buildingLines[$buildingId] 'previous_building'
    if (
        -not [string]::IsNullOrWhiteSpace([string]$generatedPreviousBuilding) -and
        -not $buildingLines.ContainsKey($generatedPreviousBuilding)
    ) {
        throw "Generated building '$buildingId' references missing previous building '$generatedPreviousBuilding'."
    }
    $buildingCostText = (Get-DirectBlock $buildingLines[$buildingId] 'cost') -join "`n"
    $remainingNumericCost = [regex]::Match(
        $buildingCostText,
        '(?<![A-Za-z0-9_])(' + $script:CostResourcePattern + ')\s*=\s*-?[0-9]+(?:\.[0-9]+)?(?=\s*(?:#|\}|$))'
    )
    if ($remainingNumericCost.Success) {
        throw "Generated building '$buildingId' retains direct numeric cost '$($remainingNumericCost.Value)'."
    }
}
foreach ($fillOverride in Convert-ToArray $plan.InitialFillEffectOverrides) {
    $generatedEffect = @($scriptedEffectObjects | Where-Object { $_.Id -eq $fillOverride.Effect }) | Select-Object -First 1
    if ($null -eq $generatedEffect) { throw "Missing generated fill effect $($fillOverride.Effect)." }
    $effectText = $generatedEffect.Lines -join "`n"
    foreach ($branch in Convert-ToArray $fillOverride.Branches) {
        $expected = 'count\s*=\s*' + [regex]::Escape([string]$branch.MaximumIterations) +
            '.*?free_external_domicile_building_slots\s*>=\s*' + [regex]::Escape([string]$branch.TargetFreeSlotThreshold)
        if ($effectText -notmatch "(?s)$expected") {
            throw "Generated fill effect $($fillOverride.Effect) lost its cap or threshold for $($branch.MainBuilding)."
        }
    }
    if ($effectText -notmatch ([regex]::Escape([string]$fillOverride.CalledEffect) + '\s*=\s*yes')) {
        throw "Generated fill effect $($fillOverride.Effect) calls the wrong random-building effect."
    }
}
$cleanupEffect = @($scriptedEffectObjects | Where-Object { $_.Id -eq $cleanupEffectId }) | Select-Object -First 1
if ($null -eq $cleanupEffect -or ($cleanupEffect.Lines -join "`n") -match 'trigger_event|remove_domicile_building') {
    throw 'Camp-purpose cleanup scripted effect was not safely disabled.'
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
    Write-GeneratedText $targetPath $text $true
    $generatedFiles.Add([pscustomobject]@{
        Path = $group.Name
        ObjectCount = $objects.Count
        Sha256 = Get-StringSha256 $text
    })
}

# Write every vanilla domicile building. Each output file owns one vanilla
# root family (main or external anchor) together with all of its descendants.
$generatedBuildingObjects = [Collections.Generic.List[object]]::new()
foreach ($buildingId in @($buildingLines.Keys | Sort-Object)) {
    $record = $buildingRecordById[$buildingId]
    $domicileId = @(Convert-ToArray $record.AllowedDomicileTypes) | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace([string]$domicileId)) {
        throw "Building '$buildingId' has no allowed domicile type."
    }
    $familyRootId = [string]$familyRootByBuildingId[$buildingId]
    $targetFile = Get-FamilyTargetRelativePath $domicileId $familyRootId
    $generatedBuildingObjects.Add([pscustomobject]@{
        Id = $buildingId
        SourceFile = $record.SourceFile
        StartLine = [int]$record.StartLine
        Lines = $buildingLines[$buildingId]
        TargetFile = $targetFile
        DomicileType = $domicileId
        FamilyRootId = $familyRootId
    })
}

if ($generatedBuildingObjects.Count -ne $expectedBuildingCount) {
    throw "Generated building inventory mismatch: expected $expectedBuildingCount, got $($generatedBuildingObjects.Count)."
}
if (@($generatedBuildingObjects | Group-Object Id | Where-Object Count -ne 1).Count -ne 0) {
    throw 'A domicile building was emitted more than once.'
}

foreach ($group in ($generatedBuildingObjects | Group-Object TargetFile)) {
    $content = [Collections.Generic.List[string]]::new()
    foreach ($line in $headerLines) { $content.Add($line) }
    $objects = @($group.Group | Sort-Object SourceFile, StartLine, Id)
    $rootsInFile = @($objects.FamilyRootId | Sort-Object -Unique)
    if ($rootsInFile.Count -ne 1) {
        throw "Generated family file '$($group.Name)' contains multiple roots: $($rootsInFile -join ', ')."
    }
    $constantDefinitions = @(Get-RequiredConstantDefinitionLines $objects)
    foreach ($definition in $constantDefinitions) { $content.Add($definition) }
    if ($constantDefinitions.Count -gt 0) { $content.Add('') }
    for ($index = 0; $index -lt $objects.Count; $index++) {
        foreach ($line in $objects[$index].Lines) { $content.Add($line) }
        if ($index -lt ($objects.Count - 1)) { $content.Add('') }
    }
    $targetPath = Convert-ToGeneratedPath $group.Name
    $text = ($content -join "`r`n") + "`r`n"
    Write-GeneratedText $targetPath $text $true
    $generatedFiles.Add([pscustomobject]@{
        Path = $group.Name
        ObjectCount = $objects.Count
        Sha256 = Get-StringSha256 $text
    })
}

# Generate the small set of numeric resource costs that were literal in
# vanilla. Most domicile costs already reference vanilla global script values.
$costValueRelativePath = [string]$generationSettings.Costs.GeneratedScriptValuesFile
$costValueObjects = [Collections.Generic.List[object]]::new()
foreach ($constantId in @($script:GeneratedCostConstantDefinitions.Keys | Sort-Object)) {
    $numericValue = $script:GeneratedCostConstantDefinitions[$constantId]
    $costValueObjects.Add([pscustomobject]@{
        Id = $constantId
        Lines = @(
            "$constantId = {",
            "`tvalue = $numericValue",
            '}'
        )
    })
}
if ($costValueObjects.Count -gt 0) {
    $content = [Collections.Generic.List[string]]::new()
    foreach ($line in $headerLines) { $content.Add($line) }
    for ($index = 0; $index -lt $costValueObjects.Count; $index++) {
        foreach ($line in $costValueObjects[$index].Lines) { $content.Add($line) }
        if ($index -lt ($costValueObjects.Count - 1)) { $content.Add('') }
    }
    $targetPath = Convert-ToGeneratedPath $costValueRelativePath
    $text = ($content -join "`r`n") + "`r`n"
    Write-GeneratedText $targetPath $text $true
    $generatedFiles.Add([pscustomobject]@{
        Path = $costValueRelativePath
        ObjectCount = $costValueObjects.Count
        Sha256 = Get-StringSha256 $text
    })
}

# Write scripted-effect overrides.
foreach ($group in ($scriptedEffectObjects | Group-Object TargetFile)) {
    $content = [Collections.Generic.List[string]]::new()
    foreach ($line in $headerLines) { $content.Add($line) }
    $objects = @($group.Group | Sort-Object SourceFile, StartLine, Id)
    for ($index = 0; $index -lt $objects.Count; $index++) {
        foreach ($line in $objects[$index].Lines) { $content.Add($line) }
        if ($index -lt ($objects.Count - 1)) { $content.Add('') }
    }
    $targetPath = Convert-ToGeneratedPath $group.Name
    $text = ($content -join "`r`n") + "`r`n"
    Write-GeneratedText $targetPath $text $true
    $generatedFiles.Add([pscustomobject]@{
        Path = $group.Name
        ObjectCount = $objects.Count
        Sha256 = Get-StringSha256 $text
    })
}

# Stage 3 previously generated an event override with a duplicated vanilla ID.
# It is obsolete now that the dedicated cleanup caller is overridden.
$legacyEventRelativePath = 'events/zzz_RB_UD_camp_purpose_events.txt'
$legacyEventPath = [IO.Path]::GetFullPath((Convert-ToGeneratedPath $legacyEventRelativePath))
$safeModRoot = $ModPath.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if (-not $legacyEventPath.StartsWith($safeModRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe stale generated-file path: $legacyEventPath"
}
if (Test-Path -LiteralPath $legacyEventPath -PathType Leaf) {
    [IO.File]::Delete($legacyEventPath)
}

# Remove stale generated aggregate/family building files only after all new
# family files have been written. Hand-authored files are preserved because
# deletion requires the generator marker in their header.
$expectedBuildingPaths = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
foreach ($object in $generatedBuildingObjects) {
    [void]$expectedBuildingPaths.Add([IO.Path]::GetFullPath((Convert-ToGeneratedPath $object.TargetFile)))
}
$buildingOutputDirectory = [IO.Path]::GetFullPath((Join-Path $ModPath 'common\domiciles\buildings'))
if (-not $buildingOutputDirectory.StartsWith($safeModRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe generated-building directory: $buildingOutputDirectory"
}
foreach ($candidateFile in Get-ChildItem -LiteralPath $buildingOutputDirectory -Filter 'zzz_RB_UD_*.txt' -File) {
    $candidatePath = [IO.Path]::GetFullPath($candidateFile.FullName)
    if ($expectedBuildingPaths.Contains($candidatePath)) { continue }
    $candidateHeader = (Get-Content -LiteralPath $candidatePath -Encoding UTF8 -TotalCount 6) -join "`n"
    if ($candidateHeader -notmatch 'GENERATED FILE - DO NOT EDIT BY HAND') { continue }
    if ($candidateHeader -notmatch 'Generator: tools/Generate-RBUDOverrides.ps1') { continue }
    [IO.File]::Delete($candidatePath)
}

# Parse every emitted database/effect file again. This catches broken braces and
# duplicate objects inside a generated file before the game sees it.
foreach ($generatedFile in $generatedFiles) {
    $fullPath = Convert-ToGeneratedPath $generatedFile.Path
    if (-not (Test-Utf8Bom $fullPath)) {
        throw "Generated CK3 script file lacks UTF-8 BOM: $($generatedFile.Path)."
    }
    $parsed = Get-TopLevelBlocks (Get-Content -LiteralPath $fullPath -Encoding UTF8) $generatedFile.Path
    if ($parsed.Count -ne [int]$generatedFile.ObjectCount) {
        throw "Generated object-count mismatch in $($generatedFile.Path): expected $($generatedFile.ObjectCount), parsed $($parsed.Count)."
    }
    $rawText = Get-Content -LiteralPath $fullPath -Raw -Encoding UTF8
    $referencedTokens = @(
        [regex]::Matches($rawText, '@[A-Za-z0-9_]+') |
            ForEach-Object { $_.Value } |
            Sort-Object -Unique
    )
    $definedTokens = @(
        [regex]::Matches($rawText, '(?m)^\s*(@[A-Za-z0-9_]+)\s*=') |
            ForEach-Object { $_.Groups[1].Value } |
            Sort-Object -Unique
    )
    foreach ($token in $referencedTokens) {
        if ($definedTokens -notcontains $token) {
            throw "Generated file $($generatedFile.Path) references undefined local constant $token."
        }
    }
}

$familySummary = @(
    $generatedBuildingObjects |
        Group-Object DomicileType |
        Sort-Object Name |
        ForEach-Object {
            [ordered]@{
                DomicileType = $_.Name
                BuildingCount = $_.Count
                FamilyCount = @($_.Group.FamilyRootId | Sort-Object -Unique).Count
            }
        }
)

$generationManifest = [ordered]@{
    SchemaVersion = 2
    GeneratedAtUtc = [DateTime]::UtcNow.ToString('o')
    GameVersion = $manifest.GameVersion
    PlanSha256 = $planWrapper.PlanSha256
    SettingsSha256 = Get-FileSha256 $SettingsPath
    VanillaSignatures = $manifest.VanillaSignatures
    InputHashValidation = 'passed'
    LayoutSchemaVersion = $layoutConfig.SchemaVersion
    GeneratedFiles = @($generatedFiles | Sort-Object Path)
    GeneratedDomicileTypeCount = $generatedTypeBlocks.Count
    GeneratedBuildingObjectCount = $generatedBuildingObjects.Count
    GeneratedBuildingFamilyCount = $familyRoots.Count
    BuildingFamiliesByDomicileType = $familySummary
    GeneratedScriptedEffectObjectCount = $scriptedEffectObjects.Count
    GeneratedCostScriptValueCount = $costValueObjects.Count
    ConstructionTimeDays = $constructionTimeDays
    ConstructionTimeLocalConstant = $constructionTimeToken
    RewrittenSpecialAccessBuildingCount = @($rewrittenAccessBuildings | Sort-Object -Unique).Count
    RemovedCampPurposeCleanupCount = @(Convert-ToArray $plan.ConditionalOverrides.CampPurpose).Count
    Validation = [ordered]@{
        BracesAndObjectCounts = 'passed'
        ExactVanillaBuildingCoverage = 'passed'
        OneRootFamilyPerBuildingFile = 'passed'
        ConstructionTimeNormalization = 'passed'
        PlanSignature = 'passed'
        VanillaInputHashes = 'passed'
        Utf8Bom = 'passed'
        LocalConstantDefinitions = 'passed'
        InitialFillLoopCaps = 'passed'
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
$report.Add("- Settings: ``$(Get-FileSha256 $SettingsPath)``")
$report.Add('- Vanilla input hashes: **passed**')
$report.Add("- Generated domicile types: **$($generatedTypeBlocks.Count)**")
$report.Add("- Generated building objects: **$($generatedBuildingObjects.Count) / $expectedBuildingCount**")
$report.Add("- Generated root-family files: **$($familyRoots.Count)**")
$report.Add("- Construction time: **$constructionTimeDays days** via local ``$constructionTimeToken``")
$report.Add("- Generated numeric cost script values: **$($costValueObjects.Count)**")
$report.Add("- Generated scripted-effect overrides: **$($scriptedEffectObjects.Count)**")
$report.Add("- Rewritten specialization-access buildings: **$(@($rewrittenAccessBuildings | Sort-Object -Unique).Count)**")
$report.Add("- Disabled camp-purpose cleanup pairs: **$(@(Convert-ToArray $plan.ConditionalOverrides.CampPurpose).Count)**")
$report.Add('')
$report.Add('## Building families')
$report.Add('')
$report.Add('| Domicile type | Buildings | Root-family files |')
$report.Add('|---|---:|---:|')
foreach ($summary in $familySummary) {
    $report.Add("| ``$($summary.DomicileType)`` | $($summary.BuildingCount) | $($summary.FamilyCount) |")
}
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
Write-Output "Building objects: $($generatedBuildingObjects.Count) / $expectedBuildingCount"
Write-Output "Building root families: $($familyRoots.Count)"
Write-Output "Construction time: $constructionTimeDays days"
Write-Output "Special-access rewrites: $(@($rewrittenAccessBuildings | Sort-Object -Unique).Count)"
Write-Output "Camp cleanup removals disabled: $(@(Convert-ToArray $plan.ConditionalOverrides.CampPurpose).Count)"
Write-Output "Generation manifest: $generationManifestPath"
Write-Output "Generation report:   $reportPath"
