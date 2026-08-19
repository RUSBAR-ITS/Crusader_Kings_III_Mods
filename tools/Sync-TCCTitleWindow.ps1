param(
	[string]$VanillaTitleWindow = 'E:\SteamLibrary\steamapps\common\Crusader Kings III\game\gui\window_title.gui'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$tccOutput = Join-Path $repoRoot 'TCC\gui\window_title.gui'
$hmSource = Join-Path $repoRoot 'HM_RE\gui\window_title.gui'
$hmOutput = Join-Path $repoRoot 'TCC_HM_RE\gui\window_title.gui'

$buttonBlock = @'
						button_round = {
							name = "TCC_change_de_jure_capital"
							visible = "[GetScriptedGui('TCC_open_title_capital_window').IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).AddScope('target_title', TitleViewWindow.GetTitle.MakeScope).End)]"
							enabled = "[GetScriptedGui('TCC_open_title_capital_window').IsValid(GuiScope.SetRoot(GetPlayer.MakeScope).AddScope('target_title', TitleViewWindow.GetTitle.MakeScope).End)]"
							onclick = "[GetScriptedGui('TCC_open_title_capital_window').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).AddScope('target_title', TitleViewWindow.GetTitle.MakeScope).End)]"
							tooltip = "[GetScriptedGui('TCC_open_title_capital_window').BuildTooltip(GuiScope.SetRoot(GetPlayer.MakeScope).AddScope('target_title', TitleViewWindow.GetTitle.MakeScope).End)]"

							button_move_capital = {
								parentanchor = center
								alwaystransparent = yes
							}
						}
'@

function Write-TCCTitleWindow {
	param(
		[Parameter(Mandatory = $true)][string]$Source,
		[Parameter(Mandatory = $true)][string]$Output
	)

	if (-not (Test-Path -LiteralPath $Source)) {
		throw "Title-window source not found: $Source"
	}

	$sourceBytes = [IO.File]::ReadAllBytes($Source)
	$hasUtf8Bom = $sourceBytes.Length -ge 3 -and $sourceBytes[0] -eq 0xEF -and $sourceBytes[1] -eq 0xBB -and $sourceBytes[2] -eq 0xBF
	$content = [IO.File]::ReadAllText($Source)
	if ($content.Contains('TCC_change_de_jure_capital')) {
		throw "Source already contains the TCC insertion: $Source"
	}

	$anchor = '(?m)^(\s*)button_round = \{\r?\n\1\tname = "toggle_find_vassal"'
	$matches = [regex]::Matches($content, $anchor)
	if ($matches.Count -ne 1) {
		throw "Expected exactly one title-capital button anchor in $Source; found $($matches.Count)."
	}

	$insertAt = $matches[0].Index
	$generated = $content.Insert($insertAt, $buttonBlock + [Environment]::NewLine)
	$outputDirectory = Split-Path -Parent $Output
	[IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
	[IO.File]::WriteAllText($Output, $generated, [Text.UTF8Encoding]::new($hasUtf8Bom))
	Write-Output "Generated $Output from $Source"
}

Write-TCCTitleWindow -Source $VanillaTitleWindow -Output $tccOutput

if (Test-Path -LiteralPath $hmSource) {
	Write-TCCTitleWindow -Source $hmSource -Output $hmOutput
}
