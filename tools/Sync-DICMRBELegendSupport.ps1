param(
	[string]$GamePath = 'E:\SteamLibrary\steamapps\common\Crusader Kings III\game',
	[string]$ModPath
)
. (Join-Path $PSScriptRoot 'RepositoryText.ps1')


$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ([string]::IsNullOrWhiteSpace($ModPath)) {
	$ModPath = Join-Path $repositoryRoot 'DICM_RBE'
}
$GamePath = [IO.Path]::GetFullPath($GamePath).TrimEnd('\', '/')
$ModPath = [IO.Path]::GetFullPath($ModPath).TrimEnd('\', '/')
if ($ModPath.Equals($GamePath, [StringComparison]::OrdinalIgnoreCase) -or
	$ModPath.StartsWith($GamePath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
	throw 'The output mod directory must not be inside the vanilla game directory.'
}

$sourceRelativePath = 'common/script_values/06_ce1_legends_values.txt'
$sourcePath = Join-Path $GamePath $sourceRelativePath
$sourceLines = [IO.File]::ReadAllLines($sourcePath)
$objectNames = @(
	'famed_legend_promoter_cost',
	'illustrious_legend_promoter_cost',
	'mythical_legend_promoter_cost'
)

function Get-CodeBraceDelta {
	param([string]$Line)

	$code = [regex]::Replace($Line, '"(?:\\.|[^"\\])*"|#.*$', '')
	return [regex]::Matches($code, '\{').Count - [regex]::Matches($code, '\}').Count
}

function Get-VanillaObjectBody {
	param([string]$Name)

	$pattern = '^' + [regex]::Escape($Name) + '\s*=\s*\{\s*(?:#.*)?$'
	$starts = @(
		for ($index = 0; $index -lt $sourceLines.Count; $index++) {
			if ($sourceLines[$index] -match $pattern) { $index }
		}
	)
	if ($starts.Count -ne 1) {
		throw "Expected exactly one top-level '$Name' block in '$sourcePath'; found $($starts.Count)."
	}

	$depth = 1
	$body = [Collections.Generic.List[string]]::new()
	for ($index = $starts[0] + 1; $index -lt $sourceLines.Count; $index++) {
		$depth += Get-CodeBraceDelta -Line $sourceLines[$index]
		if ($depth -eq 0) {
			if ($sourceLines[$index] -notmatch '^\s*\}\s*(?:#.*)?$') {
				throw "Unsupported closing line in '$Name'; review the updated vanilla block."
			}
			return $body.ToArray()
		}
		if ($depth -lt 0) {
			throw "Unbalanced braces in vanilla '$Name'."
		}
		$body.Add($sourceLines[$index])
	}
	throw "Missing closing brace for vanilla '$Name'."
}

$sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
$output = [Collections.Generic.List[string]]::new()
$output.Add('# GENERATED FILE: vanilla promoter costs with a conditional Caesar-subject discount.')
$output.Add('# Regenerate with tools/Sync-DICMRBELegendSupport.ps1 after game updates.')
$output.Add("# Source: $sourceRelativePath")
$output.Add("# Source SHA256: $sourceHash")
$output.Add('# Only the three promoter-cost objects are overridden. Owner costs are unchanged.')
$output.Add('')

foreach ($name in $objectNames) {
	$body = @(Get-VanillaObjectBody -Name $name)
	$output.Add("$name = {")
	$output.Add("`tif = {")
	$output.Add("`t`tlimit = { DICM_RBE_has_ceasar_legend_support_discount_trigger = yes }")
	$output.Add("`t`tvalue = DICM_RBE_ceasar_legend_support_cost")
	$output.Add("`t}")
	$output.Add("`telse = {")
	foreach ($line in $body) {
		$output.Add(("`t" + $line).TrimEnd())
	}
	$output.Add("`t}")
	$output.Add('}')
	$output.Add('')
}

$outputPath = Join-Path $ModPath 'common/script_values/zzz_DICM_RBE_legend_support_costs.txt'
[IO.Directory]::CreateDirectory((Split-Path -Parent $outputPath)) | Out-Null
[RepositoryText]::WriteAllText($outputPath, ($output -join "`n"), [Text.UTF8Encoding]::new($true))
Write-Output "Generated $outputPath (3 promoter-cost overrides; source SHA256: $sourceHash)"
