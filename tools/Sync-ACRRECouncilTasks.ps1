param(
	[string]$GamePath = 'E:\SteamLibrary\steamapps\common\Crusader Kings III\game',
	[string]$OutputPath
)

$ErrorActionPreference = 'Stop'

$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
	$OutputPath = Join-Path $repositoryRoot 'ACR_RE\common\council_tasks\zzz_ACR_RE_council_tasks.txt'
}
$OutputPath = [IO.Path]::GetFullPath($OutputPath)

$taskSpecs = @(
	@{ Name = 'task_integrate_title'; File = '00_chancellor_tasks.txt'; Boost = 'ACR_RE_council_task_integration_boost'; IntegrateActualProgress = $true },
	@{ Name = 'task_bestow_royal_favor'; File = '00_chancellor_tasks.txt'; Boost = 'ACR_RE_council_task_progress_boost' },
	@{ Name = 'task_conversion'; File = '00_court_chaplain_tasks.txt'; Boost = 'ACR_RE_council_task_progress_boost' },
	@{ Name = 'task_fabricate_claim'; File = '00_court_chaplain_tasks.txt'; Boost = 'ACR_RE_council_task_progress_boost' },
	@{ Name = 'task_increase_control'; File = '00_marshal_tasks.txt'; Boost = 'ACR_RE_council_task_progress_boost'; ActualCountyModifier = 'control' },
	@{ Name = 'task_find_secrets'; File = '00_spymaster_tasks.txt'; Boost = 'ACR_RE_council_task_progress_boost' },
	@{ Name = 'task_develop_county'; File = '00_steward_tasks.txt'; Boost = 'ACR_RE_council_task_progress_boost'; ActualCountyModifier = 'development' },
	@{ Name = 'task_promote_culture'; File = '00_steward_tasks.txt'; Boost = 'ACR_RE_council_task_progress_boost' },
	@{ Name = 'task_convince_dejure'; File = '00_steward_tasks.txt'; Boost = 'ACR_RE_council_task_progress_boost' }
)

function Get-CodeBraceDelta {
	param([string]$Line)

	$code = $Line -replace '#.*$', ''
	$openCount = ([regex]::Matches($code, '\{')).Count
	$closeCount = ([regex]::Matches($code, '\}')).Count
	return $openCount - $closeCount
}

function Get-TopLevelObject {
	param(
		[string[]]$Lines,
		[string]$ObjectName,
		[string]$SourcePath
	)

	$escapedName = [regex]::Escape($ObjectName)
	$start = -1
	for ($index = 0; $index -lt $Lines.Count; $index++) {
		if ($Lines[$index] -match "^\s*$escapedName\s*=\s*\{") {
			$start = $index
			break
		}
	}
	if ($start -lt 0) {
		throw "Object '$ObjectName' was not found in '$SourcePath'."
	}

	$depth = 0
	for ($index = $start; $index -lt $Lines.Count; $index++) {
		$depth += Get-CodeBraceDelta -Line $Lines[$index]
		if (($index -gt $start) -and ($depth -eq 0)) {
			return [string[]]$Lines[$start..$index]
		}
	}

	throw "Object '$ObjectName' in '$SourcePath' has no closing brace."
}

function Find-ChildBlockRange {
	param(
		[string[]]$Lines,
		[string]$PropertyName
	)

	$escapedName = [regex]::Escape($PropertyName)
	$start = -1
	for ($index = 1; $index -lt ($Lines.Count - 1); $index++) {
		if ($Lines[$index] -match "^\s*$escapedName\s*=\s*\{") {
			$start = $index
			break
		}
	}
	if ($start -lt 0) {
		throw "Child block '$PropertyName' was not found in '$($Lines[0])'."
	}

	$depth = 0
	for ($index = $start; $index -lt $Lines.Count; $index++) {
		$depth += Get-CodeBraceDelta -Line $Lines[$index]
		if (($index -gt $start) -and ($depth -eq 0)) {
			return @{ Start = $start; End = $index }
		}
	}

	throw "Child block '$PropertyName' in '$($Lines[0])' has no closing brace."
}

function Insert-LinesBefore {
	param(
		[string[]]$Lines,
		[int]$Index,
		[string[]]$Insertion
	)

	$result = [Collections.Generic.List[string]]::new()
	for ($lineIndex = 0; $lineIndex -lt $Lines.Count; $lineIndex++) {
		if ($lineIndex -eq $Index) {
			$result.AddRange($Insertion)
		}
		$result.Add($Lines[$lineIndex])
	}
	return [string[]]$result.ToArray()
}

function Add-FinalProgressBoost {
	param(
		[string[]]$TaskLines,
		[string]$BoostValue
	)

	$range = Find-ChildBlockRange -Lines $TaskLines -PropertyName 'progress'
	$propertyIndent = ([regex]::Match($TaskLines[$range.Start], '^\s*')).Value
	$indent = "$propertyIndent`t"
	$insertion = [string[]]@(
		'',
		"$indent# ACR_RE: apply acceleration after every standard penalty and multiplier.",
		"${indent}add = {",
		"$indent`tvalue = $BoostValue",
		"$indent`tdesc = ACR_RE_COUNCIL_TASK_ACCELERATION",
		"${indent}}"
	)

	return Insert-LinesBefore -Lines $TaskLines -Index $range.End -Insertion $insertion
}

function Add-IntegrationActualProgressBoost {
	param([string[]]$TaskLines)

	$range = Find-ChildBlockRange -Lines $TaskLines -PropertyName 'on_monthly_county'
	$propertyIndent = ([regex]::Match($TaskLines[$range.Start], '^\s*')).Value
	$indent = "$propertyIndent`t"
	$insertion = [string[]]@(
		'',
		"$indent# ACR_RE: task progress above is informational; de-jure drift must receive the same final boost.",
		"${indent}if = {",
		"$indent`tlimit = {",
		"$indent`t`tscope:county = {",
		"$indent`t`t`tde_jure_drifting_towards = scope:councillor_liege.primary_title",
		"$indent`t`t}",
		"$indent`t}",
		"$indent`tscope:county = {",
		"$indent`t`tchange_de_jure_drift_progress = {",
		"$indent`t`t`ttarget = scope:councillor_liege.primary_title",
		"$indent`t`t`tvalue = ACR_RE_council_task_integration_boost",
		"$indent`t`t}",
		"$indent`t}",
		"${indent}}"
	)

	return Insert-LinesBefore -Lines $TaskLines -Index $range.End -Insertion $insertion
}

function Add-ActualCountyModifier {
	param(
		[string[]]$TaskLines,
		[ValidateSet('control', 'development')]
		[string]$ModifierType
	)

	if ($ModifierType -eq 'control') {
		$insertion = [string[]]@(
			'',
			"`t# ACR_RE: the task's progress field is informational; apply the same boost to county control.",
			"`tcounty_modifier = {",
			"`t`tname = ACR_RE_marshal_increase_control_acceleration_modifier",
			"`t`tmonthly_county_control_growth_add = 1",
			"`t`tscale = ACR_RE_council_task_progress_boost",
			"`t}"
		)
	}
	else {
		$insertion = [string[]]@(
			'',
			"`t# ACR_RE: apply acceleration independently from standard development and tribal penalties.",
			"`tcounty_modifier = {",
			"`t`tname = ACR_RE_steward_develop_county_acceleration_modifier",
			"`t`tdevelopment_growth = 100",
			"`t`tscale = {",
			"`t`t`tvalue = ACR_RE_council_task_progress_boost",
			"`t`t`tdivide = 100",
			"`t`t}",
			"`t}"
		)
	}

	return Insert-LinesBefore -Lines $TaskLines -Index ($TaskLines.Count - 1) -Insertion $insertion
}

$councilTaskRoot = Join-Path $GamePath 'common\council_tasks'
if (-not (Test-Path -LiteralPath $councilTaskRoot -PathType Container)) {
	throw "Vanilla council-task directory was not found: '$councilTaskRoot'."
}

$sourceCache = @{}
$output = [Collections.Generic.List[string]]::new()
$output.Add('# AUTO-GENERATED by tools/Sync-ACRRECouncilTasks.ps1')
$output.Add('# Source: the currently installed Crusader Kings III council tasks.')
$output.Add('# Regenerate after a game update; do not hand-edit this file.')
$output.Add('# ACR_RE changes only the final progress layer and preserves the remaining standard task logic.')
$output.Add('')

foreach ($spec in $taskSpecs) {
	$sourcePath = Join-Path $councilTaskRoot $spec.File
	if (-not $sourceCache.ContainsKey($sourcePath)) {
		if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
			throw "Vanilla source file was not found: '$sourcePath'."
		}
		$sourceCache[$sourcePath] = [IO.File]::ReadAllLines($sourcePath)
	}

	$taskLines = Get-TopLevelObject -Lines $sourceCache[$sourcePath] -ObjectName $spec.Name -SourcePath $sourcePath
	$taskLines = Add-FinalProgressBoost -TaskLines $taskLines -BoostValue $spec.Boost
	if ($spec.IntegrateActualProgress) {
		$taskLines = Add-IntegrationActualProgressBoost -TaskLines $taskLines
	}
	if ($spec.ActualCountyModifier) {
		$taskLines = Add-ActualCountyModifier -TaskLines $taskLines -ModifierType $spec.ActualCountyModifier
	}

	$output.Add("# Vanilla source: common/council_tasks/$($spec.File) :: $($spec.Name)")
	$output.AddRange([string[]]$taskLines)
	$output.Add('')
}

$outputDirectory = Split-Path -Parent $OutputPath
[IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
$encoding = [Text.UTF8Encoding]::new($true)
[IO.File]::WriteAllText($OutputPath, (($output -join "`r`n") + "`r`n"), $encoding)

Write-Output "Generated $OutputPath"
Write-Output "Overridden council tasks: $($taskSpecs.Count)"
