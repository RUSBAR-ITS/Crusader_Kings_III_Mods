param(
    [Parameter(Mandatory = $true)]
    [string]$GamePath,

    [string]$ModPath
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ModPath)) {
    $ModPath = Join-Path $PSScriptRoot '..\HM_RE'
}

function Get-TopLevelBlocks {
    param([string[]]$Lines)

    $result = @{}
    $depth = 0
    $name = $null
    $buffer = $null

    foreach ($rawLine in $Lines) {
        $codeLine = ($rawLine -split '#', 2)[0]

        if ($depth -eq 0 -and $codeLine -match '^([A-Za-z0-9_]+)\s*=\s*\{') {
            $name = $Matches[1]
            $buffer = [System.Collections.Generic.List[string]]::new()
        }

        if ($null -ne $name) {
            $buffer.Add($rawLine)
        }

        $depth += ([regex]::Matches($codeLine, '\{')).Count
        $depth -= ([regex]::Matches($codeLine, '\}')).Count

        if ($null -ne $name -and $depth -eq 0) {
            $result[$name] = $buffer.ToArray()
            $name = $null
            $buffer = $null
        }
    }

    return $result
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
        $codeLine = ($rawLine -split '#', 2)[0]

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

        $depth += ([regex]::Matches($codeLine, '\{')).Count
        $depth -= ([regex]::Matches($codeLine, '\}')).Count

        if ($capturing -and $depth -eq $startDepth) {
            return $buffer.ToArray()
        }
    }

    return @()
}

function Get-BlockBody {
    param([string[]]$Block)

    if ($Block.Count -eq 0) {
        return @()
    }

    $text = $Block -join "`n"
    $firstBrace = $text.IndexOf('{')
    $lastBrace = $text.LastIndexOf('}')

    if ($firstBrace -lt 0 -or $lastBrace -le $firstBrace) {
        return @()
    }

    $bodyLines = @(
        $text.Substring($firstBrace + 1, $lastBrace - $firstBrace - 1) -split "`n"
    )

    while ($bodyLines.Count -gt 0 -and $bodyLines[0].Trim().Length -eq 0) {
        $bodyLines = @($bodyLines | Select-Object -Skip 1)
    }

    while ($bodyLines.Count -gt 0 -and $bodyLines[-1].Trim().Length -eq 0) {
        $bodyLines = @($bodyLines | Select-Object -First ($bodyLines.Count - 1))
    }

    if ($bodyLines.Count -eq 0) {
        return @()
    }

    $minimumIndent = [int]::MaxValue
    foreach ($line in $bodyLines) {
        if ($line.Trim().Length -eq 0) {
            continue
        }

        $indent = ([regex]::Match($line, '^\s*')).Length
        if ($indent -lt $minimumIndent) {
            $minimumIndent = $indent
        }
    }

    return @(
        $bodyLines | ForEach-Object {
            if ($_.Length -ge $minimumIndent) {
                $_.Substring($minimumIndent)
            }
            else {
                ''
            }
        }
    )
}

function Convert-VanillaConstraintBody {
    param([string[]]$Lines)

    return @(
        $Lines | ForEach-Object {
            $converted = $_ -replace 'scope:holder', 'province_owner' `
                           -replace '\bbuilding_requirement_tribal\b', 'HM_RE_building_requirement_tribal' `
                           -replace '\bbuilding_requirement_wanua\b', 'HM_RE_building_requirement_wanua' `
                           -replace '\bbuilding_wind_furnace_requirement_terrain\b', 'HM_RE_building_wind_furnace_requirement_terrain' `
                           -replace '\bbuilding_waterworks_requirement_terrain\b', 'HM_RE_building_waterworks_requirement_terrain'
            $converted.TrimEnd()
        }
    )
}

$resolvedGamePath = [IO.Path]::GetFullPath($GamePath)
$resolvedModPath = [IO.Path]::GetFullPath($ModPath)
$vanillaBuildingPath = Join-Path $resolvedGamePath 'common\buildings'
$triggerPath = Join-Path $resolvedModPath 'common\scripted_triggers'

if (-not (Test-Path -LiteralPath $vanillaBuildingPath -PathType Container)) {
    throw "Vanilla building directory was not found: $vanillaBuildingPath"
}

if (-not (Test-Path -LiteralPath $triggerPath -PathType Container)) {
    throw "HM_RE scripted trigger directory was not found: $triggerPath"
}

$triggerFiles = @(
    'hm_triggers_ach_buildings.txt'
    'hm_triggers_admin_buildings.txt'
    'hm_triggers_castle_buildings.txt'
    'hm_triggers_city_buildings.txt'
    'hm_triggers_common_buildings.txt'
    'hm_triggers_standard_economy_buildings.txt'
    'hm_triggers_standard_fortification_buildings.txt'
    'hm_triggers_standard_military_buildings.txt'
    'hm_triggers_temple_buildings.txt'
    'hm_triggers_temple_citadel_buildings.txt'
    'hm_triggers_tribal_buildings.txt'
)

$vanillaBuildings = @{}
Get-ChildItem -LiteralPath $vanillaBuildingPath -Filter '*.txt' | Sort-Object Name | ForEach-Object {
    $blocks = Get-TopLevelBlocks (Get-Content -LiteralPath $_.FullName)
    foreach ($key in $blocks.Keys) {
        $vanillaBuildings[$key] = $blocks[$key]
    }
}

$constraintFields = @(
    'is_enabled'
    'can_construct_potential'
    'can_construct_showing_failures_only'
    'can_construct'
)

$utf8WithoutBom = [Text.UTF8Encoding]::new($false)

foreach ($triggerFile in $triggerFiles) {
    $targetPath = Join-Path $triggerPath $triggerFile
    if (-not (Test-Path -LiteralPath $targetPath -PathType Leaf)) {
        throw "Expected HM_RE trigger file was not found: $targetPath"
    }

    $buildingIds = [System.Collections.Generic.List[string]]::new()
    Get-Content -LiteralPath $targetPath | ForEach-Object {
        if ($_ -match '^\s*HM_RE_can_construct_([A-Za-z0-9_]+)\s*=\s*\{') {
            $buildingId = $Matches[1]
            if ($buildingId -match '_\d\d$') {
                $buildingIds.Add($buildingId)
            }
        }
    }

    $output = [System.Collections.Generic.List[string]]::new()
    $output.Add('# Generated from the current vanilla building eligibility blocks.')
    $output.Add('# Re-run tools/Sync-HMREBuildingTriggers.ps1 after CK3 updates.')
    $output.Add('')

    foreach ($group in ($buildingIds | Group-Object { $_ -replace '_\d\d$', '' })) {
        $stem = $group.Name
        $output.Add("### $stem")
        $output.Add('')

        foreach ($buildingId in $group.Group) {
            if (-not $vanillaBuildings.ContainsKey($buildingId)) {
                throw "HM_RE building is missing from vanilla definitions: $buildingId"
            }

            $null = $buildingId -match '_(\d\d)$'
            $level = [int]$Matches[1]

            $output.Add("HM_RE_can_construct_$buildingId = {")
            if ($level -eq 1) {
                $output.Add("`tNOT = { has_building_or_higher = $buildingId }")
            }
            else {
                $previousBuilding = '{0}_{1:D2}' -f $stem, ($level - 1)
                $output.Add("`thas_building = $previousBuilding")
            }

            foreach ($field in $constraintFields) {
                $block = Get-ChildBlock $vanillaBuildings[$buildingId] $field
                $body = Convert-VanillaConstraintBody (Get-BlockBody $block)

                $hasConstraint = @(
                    $body | Where-Object {
                        $null -ne $_ -and
                        $_.Trim().Length -gt 0 -and
                        -not $_.TrimStart().StartsWith('#')
                    }
                ).Count -gt 0

                if (-not $hasConstraint) {
                    continue
                }

                $output.Add('')
                $output.Add("`t# Vanilla $field")
                foreach ($line in $body) {
                    if ($line.Length -eq 0) {
                        $output.Add('')
                    }
                    else {
                        $output.Add("`t$line")
                    }
                }
            }

            $output.Add('}')
            $output.Add('')
        }

        $levels = @(
            $group.Group | ForEach-Object {
                if ($_ -match '_(\d\d)$') {
                    [int]$Matches[1]
                }
            } | Sort-Object
        )

        if ($levels -contains 1) {
            $output.Add("HM_RE_can_construct_$stem = {")
            $output.Add("`tHM_RE_can_construct_${stem}_01 = yes")
            $output.Add('}')
            $output.Add('')
        }

        $upgradeLevels = @($levels | Where-Object { $_ -gt 1 })
        if ($upgradeLevels.Count -gt 0) {
            $output.Add("HM_RE_can_upgrade_$stem = {")
            $output.Add("`tOR = {")
            foreach ($upgradeLevel in $upgradeLevels) {
                $output.Add(("`t`tHM_RE_can_construct_{0}_{1:D2} = yes" -f $stem, $upgradeLevel))
            }
            $output.Add("`t}")
            $output.Add('}')
            $output.Add('')
        }
    }

    $content = ($output -join "`r`n").TrimEnd() + "`r`n"
    [IO.File]::WriteAllText($targetPath, $content, $utf8WithoutBom)
    Write-Output "Updated $triggerFile ($($buildingIds.Count) building tiers)."
}
