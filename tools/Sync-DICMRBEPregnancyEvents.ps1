param(
	[string]$GamePath = 'E:\SteamLibrary\steamapps\common\Crusader Kings III\game',
	[string]$ModPath
)

$ErrorActionPreference = 'Stop'

$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ([string]::IsNullOrWhiteSpace($ModPath)) {
	$ModPath = Join-Path $repositoryRoot 'DICM_RBE'
}
$ModPath = [IO.Path]::GetFullPath($ModPath)

$guardLine = 'NOT = { has_character_flag = DICM_RBE_obstetrics_suppress_deferred_critical_birth }'
$specifications = @(
	@{ File = 'pregnancy_events.txt'; Events = @('pregnancy.2101') },
	@{ File = 'birth_events.txt'; Events = @('birth.3001', 'birth.3021') }
)

function Get-CodeBraceDelta {
	param([string]$Line)

	$code = $Line -replace '#.*$', ''
	return ([regex]::Matches($code, '\{')).Count - ([regex]::Matches($code, '\}')).Count
}

function Get-TopLevelObjectRange {
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
		throw "Event '$ObjectName' was not found in '$SourcePath'."
	}

	$depth = 0
	for ($index = $start; $index -lt $Lines.Count; $index++) {
		$depth += Get-CodeBraceDelta -Line $Lines[$index]
		if (($index -gt $start) -and ($depth -eq 0)) {
			return @{ Start = $start; End = $index }
		}
	}

	throw "Event '$ObjectName' in '$SourcePath' has no closing brace."
}

function Add-EventTriggerGuard {
	param(
		[Collections.Generic.List[string]]$Lines,
		[string]$EventName,
		[string]$SourcePath
	)

	$range = Get-TopLevelObjectRange -Lines $Lines.ToArray() -ObjectName $EventName -SourcePath $SourcePath
	$depth = 0
	$triggerStart = -1
	for ($index = $range.Start; $index -le $range.End; $index++) {
		if (($depth -eq 1) -and ($Lines[$index] -match '^\s*trigger\s*=\s*\{')) {
			$triggerStart = $index
			break
		}
		$depth += Get-CodeBraceDelta -Line $Lines[$index]
	}
	if ($triggerStart -lt 0) {
		throw "Top-level trigger for '$EventName' was not found in '$SourcePath'."
	}

	$triggerIndent = ([regex]::Match($Lines[$triggerStart], '^\s*')).Value + "`t"
	$nearbyEnd = [Math]::Min($triggerStart + 12, $Lines.Count - 1)
	if (($Lines[$triggerStart..$nearbyEnd] -join "`n").Contains($guardLine)) {
		throw "Event '$EventName' in '$SourcePath' already contains the clinic guard."
	}

	$Lines.Insert($triggerStart + 1, $triggerIndent + $guardLine)
}

foreach ($specification in $specifications) {
	$sourcePath = Join-Path $GamePath (Join-Path 'events' $specification.File)
	if (-not (Test-Path -LiteralPath $sourcePath)) {
		throw "Vanilla event file was not found: $sourcePath"
	}

	$sourceBytes = [IO.File]::ReadAllBytes($sourcePath)
	$hasUtf8Bom = $sourceBytes.Length -ge 3 -and $sourceBytes[0] -eq 0xEF -and $sourceBytes[1] -eq 0xBB -and $sourceBytes[2] -eq 0xBF
	$content = [IO.File]::ReadAllText($sourcePath)
	$newLine = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }
	$hadTrailingNewLine = $content.EndsWith("`n")
	$lines = [Collections.Generic.List[string]]::new()
	$lines.AddRange([string[]]($content -split "`r?`n"))
	if ($hadTrailingNewLine -and $lines.Count -gt 0 -and $lines[$lines.Count - 1] -eq '') {
		$lines.RemoveAt($lines.Count - 1)
	}

	foreach ($eventName in $specification.Events) {
		Add-EventTriggerGuard -Lines $lines -EventName $eventName -SourcePath $sourcePath
	}

	$header = [string[]]@(
		'# GENERATED FILE: current vanilla event file with narrowly scoped DICM RBE clinic guards.',
		'# Regenerate with tools/Sync-DICMRBEPregnancyEvents.ps1 after every game update.',
		''
	)
	$lines.InsertRange(0, $header)
	$generated = $lines.ToArray() -join $newLine
	if ($hadTrailingNewLine) {
		$generated += $newLine
	}

	$outputPath = Join-Path $ModPath (Join-Path 'events' $specification.File)
	[IO.Directory]::CreateDirectory((Split-Path -Parent $outputPath)) | Out-Null
	[IO.File]::WriteAllText($outputPath, $generated, [Text.UTF8Encoding]::new($hasUtf8Bom))

	$sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
	Write-Output "Generated $outputPath from $sourcePath (source SHA256: $sourceHash)"
}
