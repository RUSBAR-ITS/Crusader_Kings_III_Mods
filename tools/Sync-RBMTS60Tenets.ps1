param(
	[string]$GamePath = 'E:\SteamLibrary\steamapps\common\Crusader Kings III\game',
	[string]$ModPath,
	[string]$DoctrineSourcePath,
	[string]$GuiSourcePath
)

$ErrorActionPreference = 'Stop'

$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ([string]::IsNullOrWhiteSpace($ModPath)) {
	$ModPath = Join-Path $repositoryRoot 'RB_MTS60'
}
$ModPath = [IO.Path]::GetFullPath($ModPath)

if ([string]::IsNullOrWhiteSpace($DoctrineSourcePath)) {
	$DoctrineSourcePath = Join-Path $GamePath 'common\religion\doctrine_group_types\00_doctrine_group_types.txt'
}
$DoctrineSourcePath = [IO.Path]::GetFullPath($DoctrineSourcePath)

if ([string]::IsNullOrWhiteSpace($GuiSourcePath)) {
	$GuiSourcePath = Join-Path $GamePath 'gui'
}
$GuiSourcePath = [IO.Path]::GetFullPath($GuiSourcePath)

$pickCount = 60
$standardPickCount = 3
$emptyTenetCount = $pickCount - $standardPickCount
$utf8NoBom = [Text.UTF8Encoding]::new($false)
$utf8Bom = [Text.UTF8Encoding]::new($true)

function Get-CodeBraceDelta {
	param([string]$Line)

	$code = $Line -replace '#.*$', ''
	return ([regex]::Matches($code, '\{')).Count - ([regex]::Matches($code, '\}')).Count
}

function Get-BlockEnd {
	param(
		[string[]]$Lines,
		[int]$Start,
		[string]$Description
	)

	$depth = 0
	for ($index = $Start; $index -lt $Lines.Count; $index++) {
		$depth += Get-CodeBraceDelta -Line $Lines[$index]
		if (($index -gt $Start) -and ($depth -eq 0)) {
			return $index
		}
	}
	throw "Block '$Description' has no closing brace."
}

function Get-TopLevelObjectRange {
	param(
		[string[]]$Lines,
		[string]$ObjectName,
		[string]$SourcePath
	)

	$escapedName = [regex]::Escape($ObjectName)
	$objectIndexes = [Collections.Generic.List[int]]::new()
	for ($index = 0; $index -lt $Lines.Count; $index++) {
		if ($Lines[$index] -match "^$escapedName\s*=\s*\{") {
			$objectIndexes.Add($index)
		}
	}
	if ($objectIndexes.Count -ne 1) {
		throw "Expected one top-level object '$ObjectName' in '$SourcePath', found $($objectIndexes.Count)."
	}
	$end = Get-BlockEnd -Lines $Lines -Start $objectIndexes[0] -Description $ObjectName
	return @{ Start = $objectIndexes[0]; End = $end }
}

function Find-ChildBlockRange {
	param(
		[string[]]$Lines,
		[string]$PropertyName
	)

	$escapedName = [regex]::Escape($PropertyName)
	for ($index = 1; $index -lt ($Lines.Count - 1); $index++) {
		if ($Lines[$index] -match "^\s*$escapedName\s*=\s*\{") {
			$end = Get-BlockEnd -Lines $Lines -Start $index -Description $PropertyName
			return @{ Start = $index; End = $end }
		}
	}
	throw "Child block '$PropertyName' was not found."
}

function Get-NamedGuiBlockRange {
	param(
		[string[]]$Lines,
		[string]$Name,
		[string]$BlockType,
		[string]$SourcePath
	)

	$escapedName = [regex]::Escape($Name)
	$nameMatches = [Collections.Generic.List[int]]::new()
	for ($index = 0; $index -lt $Lines.Count; $index++) {
		if ($Lines[$index] -match "^\s*name\s*=\s*`"$escapedName`"\s*$") {
			$nameMatches.Add($index)
		}
	}
	if ($nameMatches.Count -ne 1) {
		throw "Expected one GUI object named '$Name' in '$SourcePath', found $($nameMatches.Count)."
	}

	$nameIndex = $nameMatches[0]
	$nameIndent = ([regex]::Match($Lines[$nameIndex], '^\s*')).Value.Length
	$escapedType = [regex]::Escape($BlockType)
	for ($index = $nameIndex - 1; $index -ge 0; $index--) {
		if ($Lines[$index] -match "^(\s*)$escapedType\s*=\s*\{") {
			if ($Matches[1].Length -lt $nameIndent) {
				$end = Get-BlockEnd -Lines $Lines -Start $index -Description "$BlockType '$Name'"
				if ($end -ge $nameIndex) {
					return @{ Start = $index; End = $end }
				}
			}
		}
	}
	throw "Parent $BlockType for GUI object '$Name' was not found in '$SourcePath'."
}

function Get-GuiBlockRangeByDataModel {
	param(
		[string[]]$Lines,
		[string]$DataModel,
		[string]$BlockType,
		[string]$SourcePath
	)

	$lineMatches = [Collections.Generic.List[int]]::new()
	for ($index = 0; $index -lt $Lines.Count; $index++) {
		if ($Lines[$index].Contains($DataModel)) {
			$lineMatches.Add($index)
		}
	}
	if ($lineMatches.Count -ne 1) {
		throw "Expected one GUI data model '$DataModel' in '$SourcePath', found $($lineMatches.Count)."
	}

	$dataIndex = $lineMatches[0]
	$dataIndent = ([regex]::Match($Lines[$dataIndex], '^\s*')).Value.Length
	$escapedType = [regex]::Escape($BlockType)
	for ($index = $dataIndex - 1; $index -ge 0; $index--) {
		if ($Lines[$index] -match "^(\s*)$escapedType\s*=\s*\{") {
			if ($Matches[1].Length -lt $dataIndent) {
				$end = Get-BlockEnd -Lines $Lines -Start $index -Description "$BlockType containing $DataModel"
				if ($end -ge $dataIndex) {
					return @{ Start = $index; End = $end }
				}
			}
		}
	}
	throw "Parent $BlockType for '$DataModel' was not found in '$SourcePath'."
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
		$result.AddRange([string[]]$Lines[0..($Start - 1)])
	}
	$result.AddRange([string[]]$Replacement)
	if ($End -lt ($Lines.Count - 1)) {
		$result.AddRange([string[]]$Lines[($End + 1)..($Lines.Count - 1)])
	}
	return [string[]]$result.ToArray()
}

function Insert-LinesAt {
	param(
		[string[]]$Lines,
		[int]$Index,
		[string[]]$Insertion
	)

	return Replace-LineRange -Lines $Lines -Start $Index -End ($Index - 1) -Replacement $Insertion
}

function Convert-Indent {
	param(
		[string[]]$Lines,
		[string]$OldIndent,
		[string]$NewIndent
	)

	$result = [Collections.Generic.List[string]]::new()
	foreach ($line in $Lines) {
		if ([string]::IsNullOrWhiteSpace($line)) {
			$result.Add('')
		}
		elseif ($line.StartsWith($OldIndent, [StringComparison]::Ordinal)) {
			$result.Add($NewIndent + $line.Substring($OldIndent.Length))
		}
		else {
			throw "Cannot re-indent unexpected GUI line: '$line'."
		}
	}
	return [string[]]$result.ToArray()
}

function Replace-UniqueText {
	param(
		[string]$Text,
		[string]$Needle,
		[string]$Replacement,
		[string]$Description
	)

	$first = $Text.IndexOf($Needle, [StringComparison]::Ordinal)
	if ($first -lt 0) {
		throw "GUI synchronization marker '$Description' was not found."
	}
	$second = $Text.IndexOf($Needle, $first + $Needle.Length, [StringComparison]::Ordinal)
	if ($second -ge 0) {
		throw "GUI synchronization marker '$Description' is not unique."
	}
	return $Text.Substring(0, $first) + $Replacement + $Text.Substring($first + $Needle.Length)
}

function Write-TextFile {
	param(
		[string]$Path,
		[string[]]$Lines,
		[Text.Encoding]$Encoding = $utf8NoBom
	)

	$directory = Split-Path -Parent $Path
	[IO.Directory]::CreateDirectory($directory) | Out-Null
	$content = [string]::Join("`r`n", $Lines) + "`r`n"
	[IO.File]::WriteAllText($Path, $content, $Encoding)
}

function New-ScrollableGridReplacement {
	param(
		[string[]]$Block,
		[string]$Name,
		[int]$Columns,
		[int]$MaxRows,
		[int]$ColumnWidth,
		[int]$RowHeight,
		[switch]$AddSize
	)

	$baseIndent = ([regex]::Match($Block[0], '^\s*')).Value
	$oldInnerIndent = "$baseIndent`t"
	$newInnerIndent = "$baseIndent`t`t`t"
	$preserved = [Collections.Generic.List[string]]::new()
	foreach ($line in $Block[1..($Block.Count - 2)]) {
		if ($line.StartsWith($oldInnerIndent, [StringComparison]::Ordinal)) {
			$directContent = $line.Substring($oldInnerIndent.Length)
			if (($directContent -match '^name\s*=') -or ($directContent -match '^spacing\s*=')) {
				continue
			}
		}
		$preserved.Add($line)
	}
	$preservedLines = Convert-Indent -Lines ([string[]]$preserved.ToArray()) -OldIndent $oldInnerIndent -NewIndent $newInnerIndent

	$result = [Collections.Generic.List[string]]::new()
	$result.Add("${baseIndent}# RB_MTS60: scrollable grid for up to $pickCount tenets.")
	$result.Add("${baseIndent}scrollbox = {")
	$result.Add("$baseIndent`tlayoutpolicy_vertical = expanding")
	$result.Add("$baseIndent`tlayoutpolicy_horizontal = expanding")
	if ($AddSize) {
		$result.Add("$baseIndent`tsize = { 200 250 }")
	}
	$result.Add('')
	$result.Add("$baseIndent`tblockoverride `"scrollbox_content`"")
	$result.Add("$baseIndent`t{")
	$result.Add("$baseIndent`t`tfixedgridbox = {")
	$result.Add("$baseIndent`t`t`tname = `"$Name`"")
	$result.Add("$baseIndent`t`t`tflipdirection = yes")
	$result.Add("$baseIndent`t`t`taddcolumn = $ColumnWidth")
	$result.Add("$baseIndent`t`t`taddrow = $RowHeight")
	$result.Add("$baseIndent`t`t`tsetitemsizefromcell = yes")
	$result.Add("$baseIndent`t`t`tdatamodel_wrap = $Columns")
	$result.Add("$baseIndent`t`t`tmaxhorizontalslots = -1")
	$result.Add("$baseIndent`t`t`tmaxverticalslots = $MaxRows")
	$result.Add("$baseIndent`t`t`tlayoutpolicy_vertical = expanding")
	$result.Add("$baseIndent`t`t`tlayoutpolicy_horizontal = expanding")
	$result.AddRange([string[]]$preservedLines)
	$result.Add("$baseIndent`t`t}")
	$result.Add("$baseIndent`t}")
	$result.Add("${baseIndent}}")
	return [string[]]$result.ToArray()
}

function Convert-SinsOrVirtuesGrid {
	param(
		[string[]]$Lines,
		[string]$DataModel,
		[string]$GridName,
		[string]$SourcePath
	)

	$range = Get-GuiBlockRangeByDataModel -Lines $Lines -DataModel $DataModel -BlockType 'hbox' -SourcePath $SourcePath
	$block = [string[]]$Lines[$range.Start..$range.End]
	$indent = ([regex]::Match($block[0], '^\s*')).Value
	$block[0] = "${indent}dynamicgridbox = {"
	$nameIndex = -1
	for ($index = 1; $index -lt ($block.Count - 1); $index++) {
		if ($block[$index] -match '^\s*name\s*=') {
			$nameIndex = $index
			break
		}
	}
	if ($nameIndex -lt 0) {
		throw "Named row for '$DataModel' was not found."
	}
	$propertyIndent = ([regex]::Match($block[$nameIndex], '^\s*')).Value
	$block[$nameIndex] = "${propertyIndent}name = `"$GridName`""
	$block = Insert-LinesAt -Lines $block -Index ($nameIndex + 1) -Insertion @(
		"${propertyIndent}flipdirection = yes",
		"${propertyIndent}datamodel_wrap = 8"
	)
	$Lines = Replace-LineRange -Lines $Lines -Start $range.Start -End $range.End -Replacement $block

	$range = Get-GuiBlockRangeByDataModel -Lines $Lines -DataModel $DataModel -BlockType 'dynamicgridbox' -SourcePath $SourcePath
	$Lines = Insert-LinesAt -Lines $Lines -Index ($range.End + 1) -Insertion @('', "${indent}expand = {}")
	return [string[]]$Lines
}

if (-not (Test-Path -LiteralPath $DoctrineSourcePath -PathType Leaf)) {
	throw "Doctrine source file was not found: '$DoctrineSourcePath'."
}
$faithGuiSource = Join-Path $GuiSourcePath 'window_faith.gui'
$faithCreationGuiSource = Join-Path $GuiSourcePath 'window_faith_creation.gui'
foreach ($path in @($faithGuiSource, $faithCreationGuiSource)) {
	if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
		throw "GUI source file was not found: '$path'."
	}
}

# Synchronize the standard doctrine list and prepend the temporary empty slots.
$sourceDoctrineLines = [IO.File]::ReadAllLines($DoctrineSourcePath)
$groupRange = Get-TopLevelObjectRange -Lines $sourceDoctrineLines -ObjectName 'doctrine_core_tenets' -SourcePath $DoctrineSourcePath
$groupLines = [string[]]$sourceDoctrineLines[$groupRange.Start..$groupRange.End]
# Allow the synchronizer to consume the original More Tenets Slots group as well as vanilla.
# Its legacy temporary tenets must not become real selectable doctrines in RB_MTS60.
$groupLines = [string[]]($groupLines | Where-Object {
	$_ -notmatch '^\s*(?:tenet_zz_empty_\d+|RB_MTS60_tenet_empty_\d{2})\s*(?:#.*)?$'
})
$pickMatches = 0
for ($index = 0; $index -lt $groupLines.Count; $index++) {
	if ($groupLines[$index] -match '^(\s*)number_of_picks\s*=\s*\d+') {
		$groupLines[$index] = "$($Matches[1])number_of_picks = $pickCount"
		$pickMatches++
	}
}
if ($pickMatches -ne 1) {
	throw "Expected one number_of_picks property in doctrine_core_tenets, found $pickMatches."
}

$doctrineTypesRange = Find-ChildBlockRange -Lines $groupLines -PropertyName 'doctrine_types'
$doctrineIndent = ([regex]::Match($groupLines[$doctrineTypesRange.Start], '^\s*')).Value + "`t"
$emptyDoctrineLines = [Collections.Generic.List[string]]::new()
$emptyDoctrineLines.Add("${doctrineIndent}# RB_MTS60: temporary empty positions removed immediately after faith creation.")
for ($number = 1; $number -le $emptyTenetCount; $number++) {
	$emptyDoctrineLines.Add("${doctrineIndent}RB_MTS60_tenet_empty_{0:D2}" -f $number)
}
$emptyDoctrineLines.Add('')
$groupLines = Insert-LinesAt -Lines $groupLines -Index ($doctrineTypesRange.Start + 1) -Insertion ([string[]]$emptyDoctrineLines.ToArray())

$realTenets = [Collections.Generic.List[string]]::new()
foreach ($line in $groupLines) {
	if ($line -match '^\s*(tenet_[A-Za-z0-9_]+)\s*(?:#.*)?$') {
		$realTenets.Add($Matches[1])
	}
}
if ($realTenets.Count -eq 0) {
	throw 'No standard tenets were found in doctrine_core_tenets.'
}

$groupOutput = [Collections.Generic.List[string]]::new()
$groupOutput.Add('# AUTO-GENERATED by tools/Sync-RBMTS60Tenets.ps1')
$groupOutput.Add("# Source: $DoctrineSourcePath")
$groupOutput.Add('# Do not hand-edit; regenerate after updating CK3 or a doctrine compatibility source.')
$groupOutput.Add('')
$groupOutput.AddRange([string[]]$groupLines)
Write-TextFile -Path (Join-Path $ModPath 'common\religion\doctrine_group_types\zzz_RB_MTS60_doctrine_group_types.txt') -Lines ([string[]]$groupOutput.ToArray())

# Generate the empty doctrines from one canonical template.
$emptyDefinitions = [Collections.Generic.List[string]]::new()
$emptyDefinitions.Add('# AUTO-GENERATED by tools/Sync-RBMTS60Tenets.ps1')
$emptyDefinitions.Add('# Temporary doctrines let the faith-creation interface expose up to 60 positions.')
$emptyDefinitions.Add('')
for ($number = 1; $number -le $emptyTenetCount; $number++) {
	$id = 'RB_MTS60_tenet_empty_{0:D2}' -f $number
	$emptyDefinitions.Add("$id = {")
	$emptyDefinitions.Add("`ticon = RB_MTS60_core_tenet_empty")
	$emptyDefinitions.Add('')
	$emptyDefinitions.Add("`tpiety_cost = {")
	$emptyDefinitions.Add("`t`tvalue = 0")
	$emptyDefinitions.Add("`t}")
	$emptyDefinitions.Add('')
	$emptyDefinitions.Add("`tis_shown = {")
	$emptyDefinitions.Add("`t`talways = yes")
	$emptyDefinitions.Add("`t}")
	$emptyDefinitions.Add('')
	$emptyDefinitions.Add("`tcan_pick = {")
	$emptyDefinitions.Add("`t`talways = yes")
	$emptyDefinitions.Add("`t}")
	$emptyDefinitions.Add('}')
	$emptyDefinitions.Add('')
}
Write-TextFile -Path (Join-Path $ModPath 'common\religion\doctrine_types\RB_MTS60_empty_tenets.txt') -Lines ([string[]]$emptyDefinitions.ToArray())

# Generate the cleanup hook and event so their ranges can never drift apart.
$onActionLines = @(
	'# AUTO-GENERATED by tools/Sync-RBMTS60Tenets.ps1',
	'on_faith_created = {',
	"`ton_actions = {",
	"`t`tRB_MTS60_on_faith_created",
	"`t}",
	'}',
	'',
	'RB_MTS60_on_faith_created = {',
	"`tevents = {",
	"`t`tRB_MTS60_faith_creation.0001",
	"`t}",
	'}'
)
Write-TextFile -Path (Join-Path $ModPath 'common\on_action\RB_MTS60_religion_on_actions.txt') -Lines $onActionLines

$eventLines = [Collections.Generic.List[string]]::new()
$eventLines.Add('# AUTO-GENERATED by tools/Sync-RBMTS60Tenets.ps1')
$eventLines.Add('namespace = RB_MTS60_faith_creation')
$eventLines.Add('')
$eventLines.Add('RB_MTS60_faith_creation.0001 = {')
$eventLines.Add("`thidden = yes")
$eventLines.Add('')
$eventLines.Add("`timmediate = {")
$eventLines.Add("`t`tfaith = {")
for ($number = 1; $number -le $emptyTenetCount; $number++) {
	$eventLines.Add("`t`t`tremove_doctrine = RB_MTS60_tenet_empty_{0:D2}" -f $number)
}
$eventLines.Add("`t`t}")
$eventLines.Add("`t}")
$eventLines.Add('}')
Write-TextFile -Path (Join-Path $ModPath 'events\religion_events\RB_MTS60_faith_creation_events.txt') -Lines ([string[]]$eventLines.ToArray())

# Generate English and Russian localization with the exact same key set.
foreach ($language in @('english', 'russian')) {
	$locLines = [Collections.Generic.List[string]]::new()
	$locLines.Add("l_${language}:")
	if ($language -eq 'russian') {
		$description = 'Нажмите, чтобы выбрать другой догмат, или оставьте эту позицию пустой.'
	}
	else {
		$description = 'Click to select another tenet or leave this position empty.'
	}
	for ($number = 1; $number -le $emptyTenetCount; $number++) {
		$id = 'RB_MTS60_tenet_empty_{0:D2}' -f $number
		$locLines.Add(" ${id}_name:0 `"_`"")
		$locLines.Add(" ${id}_desc:0 `"$description`"")
	}
	$locPath = Join-Path $ModPath "localization\$language\RB_MTS60_religion_l_${language}.yml"
	Write-TextFile -Path $locPath -Lines ([string[]]$locLines.ToArray()) -Encoding $utf8Bom
}

# Rebuild the faith view from the current standard GUI and patch only the tenet area.
$faithLines = [IO.File]::ReadAllLines($faithGuiSource)
$faithText = [string]::Join("`n", $faithLines)
$faithText = Replace-UniqueText -Text $faithText -Needle "`tvbox = {`n`t`tusing = Window_Margins_Sidebar" -Replacement "`tvbox = {`n`t`tlayoutpolicy_horizontal = expanding`n`t`tlayoutpolicy_vertical = expanding`n`n`t`tusing = Window_Margins_Sidebar" -Description 'faith root layout'
$faithText = Replace-UniqueText -Text $faithText -Needle "`t`t`thbox = {`n`t`t`t`tdatacontext = `"[FaithWindow.GetFaith]`"" -Replacement "`t`t`thbox = {`n`t`t`t`tlayoutpolicy_horizontal = expanding`n`t`t`t`tlayoutpolicy_vertical = expanding`n`n`t`t`t`tdatacontext = `"[FaithWindow.GetFaith]`"" -Description 'faith header layout'
$faithText = Replace-UniqueText -Text $faithText -Needle "`t`t`t`tvbox = {`n`t`t`t`t`tmargin_top = 30`n`t`t`t`t`tmargin_left = 10" -Replacement "`t`t`t`tvbox = {`n`t`t`t`t`tlayoutpolicy_vertical = expanding`n`t`t`t`t`tmargin_top = 30`n`t`t`t`t`tmargin_left = 10" -Description 'faith icon column layout'
$faithLines = $faithText -split "`n"
$faithGridRange = Get-NamedGuiBlockRange -Lines $faithLines -Name 'doctrines_grid_core_tenets' -BlockType 'hbox' -SourcePath $faithGuiSource
$faithGridBlock = [string[]]$faithLines[$faithGridRange.Start..$faithGridRange.End]
$faithGridReplacement = New-ScrollableGridReplacement -Block $faithGridBlock -Name 'doctrines_grid_core_tenets' -Columns 4 -MaxRows -1 -ColumnWidth 143 -RowHeight 210 -AddSize
$faithLines = Replace-LineRange -Lines $faithLines -Start $faithGridRange.Start -End $faithGridRange.End -Replacement $faithGridReplacement
$faithHeader = @(
	'# AUTO-GENERATED by tools/Sync-RBMTS60Tenets.ps1',
	"# Source: $faithGuiSource",
	'# Do not hand-edit; regenerate after updating CK3.',
	''
)
$faithLines = Insert-LinesAt -Lines $faithLines -Index 0 -Insertion $faithHeader
Write-TextFile -Path (Join-Path $ModPath 'gui\window_faith.gui') -Lines $faithLines

# Rebuild the creation window and patch selected-tenet, sin, and virtue grids.
$creationLines = [IO.File]::ReadAllLines($faithCreationGuiSource)
$creationText = [string]::Join("`n", $creationLines)
$creationText = Replace-UniqueText -Text $creationText -Needle "`t`t`t`t`tvbox = {`n`t`t`t`t`t`tname = `"tenets`"`n`t`t`t`t`t`tlayoutpolicy_horizontal = expanding`n`t`t`t`t`t`tspacing = 15" -Replacement "`t`t`t`t`tvbox = {`n`t`t`t`t`t`tname = `"tenets`"`n`t`t`t`t`t`tlayoutpolicy_horizontal = expanding`n`t`t`t`t`t`tlayoutpolicy_vertical = expanding`n`t`t`t`t`t`tspacing = 5" -Description 'creation tenet container layout'
$creationText = Replace-UniqueText -Text $creationText -Needle "`t`t`t`t`t`t`tvbox = {`n`t`t`t`t`t`t`t`tname = `"sins`"`n`t`t`t`t`t`t`t`tspacing = 3" -Replacement "`t`t`t`t`t`t`tvbox = {`n`t`t`t`t`t`t`t`tname = `"sins`"`n`t`t`t`t`t`t`t`tspacing = 3`n`t`t`t`t`t`t`t`tlayoutpolicy_vertical = expanding" -Description 'creation sins layout'
$creationText = Replace-UniqueText -Text $creationText -Needle "`t`t`t`t`t`t`tvbox = {`n`t`t`t`t`t`t`t`tname = `"virtues`"`n`t`t`t`t`t`t`t`tspacing = 3" -Replacement "`t`t`t`t`t`t`tvbox = {`n`t`t`t`t`t`t`t`tname = `"virtues`"`n`t`t`t`t`t`t`t`tspacing = 3`n`t`t`t`t`t`t`t`tlayoutpolicy_vertical = expanding" -Description 'creation virtues layout'
$creationLines = $creationText -split "`n"
$creationGridRange = Get-NamedGuiBlockRange -Lines $creationLines -Name 'tenets_grid' -BlockType 'hbox' -SourcePath $faithCreationGuiSource
$creationGridBlock = [string[]]$creationLines[$creationGridRange.Start..$creationGridRange.End]
$creationGridReplacement = New-ScrollableGridReplacement -Block $creationGridBlock -Name 'tenets_grid' -Columns 5 -MaxRows 12 -ColumnWidth 140 -RowHeight 210
$creationLines = Replace-LineRange -Lines $creationLines -Start $creationGridRange.Start -End $creationGridRange.End -Replacement $creationGridReplacement
$creationLines = Convert-SinsOrVirtuesGrid -Lines $creationLines -DataModel '[FaithCreationWindow.GetSins]' -GridName 'sins_grid' -SourcePath $faithCreationGuiSource
$creationLines = Convert-SinsOrVirtuesGrid -Lines $creationLines -DataModel '[FaithCreationWindow.GetVirtues]' -GridName 'virtues_grid' -SourcePath $faithCreationGuiSource
$creationHeader = @(
	'# AUTO-GENERATED by tools/Sync-RBMTS60Tenets.ps1',
	"# Source: $faithCreationGuiSource",
	'# Do not hand-edit; regenerate after updating CK3.',
	''
)
$creationLines = Insert-LinesAt -Lines $creationLines -Index 0 -Insertion $creationHeader
Write-TextFile -Path (Join-Path $ModPath 'gui\window_faith_creation.gui') -Lines $creationLines

$reportLines = @(
	'# RB_MTS60 synchronization report',
	'',
	"- Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')",
	"- Doctrine source: ``$DoctrineSourcePath``",
	"- Faith GUI source: ``$faithGuiSource``",
	"- Faith creation GUI source: ``$faithCreationGuiSource``",
	"- Maximum tenet positions: **$pickCount**",
	"- Temporary empty tenets: **$emptyTenetCount**",
	"- Standard real tenets copied into the group: **$($realTenets.Count)**",
	'',
	'## Standard tenets',
	''
) + ($realTenets | ForEach-Object { "- ``$_``" })
Write-TextFile -Path (Join-Path $ModPath 'docs\generated\RB_MTS60_SYNC_REPORT.md') -Lines $reportLines

Write-Output "RB_MTS60 synchronized successfully."
Write-Output "Standard tenets: $($realTenets.Count)"
Write-Output "Temporary empty tenets: $emptyTenetCount"
Write-Output "Output: $ModPath"
