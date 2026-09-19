param(
	[Parameter(Mandatory=$true)][string[]]$Titles,
	[switch]$Search
)

$ErrorActionPreference = 'Stop'
$cacheRoot = Join-Path ([IO.Path]::GetTempPath()) 'ck3-agot-rus-correct-7kingdoms'
[IO.Directory]::CreateDirectory($cacheRoot) | Out-Null
# Windows PowerShell -File passes a comma-separated list as one argument.
foreach ($title in ($Titles -split ',')) {
	# Only public pages on the requested reference site are fetched.
	$uri = if ($Search) {
		'https://7kingdoms.ru/wiki/Special:Search?fulltext=1&search=' + [Uri]::EscapeDataString($title)
	} else {
		'https://7kingdoms.ru/wiki/' + [Uri]::EscapeDataString($title.Replace(' ', '_'))
	}
	$sha = [Security.Cryptography.SHA256]::Create()
	try { $cacheName = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($uri))).Replace('-', '') + '.json' }
	finally { $sha.Dispose() }
	$cachePath = Join-Path $cacheRoot $cacheName
	if (Test-Path -LiteralPath $cachePath) {
		$record = Get-Content -LiteralPath $cachePath -Raw -Encoding UTF8 | ConvertFrom-Json
	} else {
		try {
			$response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 25
			$html = $response.Content
			$heading = [Net.WebUtility]::HtmlDecode(([regex]::Match($html, '(?s)<h1[^>]*>(.*?)</h1>').Groups[1].Value -replace '<[^>]+>', ''))
			$body = [regex]::Match($html, '(?s)<div class="mw-parser-output">(.*?)(?:<div class="printfooter|<!--\s*NewPP limit report|<!--\s*Saved in parser cache)').Groups[1].Value
			if (-not $body) { $body = $html }
			$plain = $body -replace '(?s)<(script|style)\b[^>]*>.*?</\1>', '' -replace '(?i)<(?:br\s*/?|/?p|/?li|/?h[1-6]|/?div|/?tr)\b[^>]*>', "`n" -replace '<[^>]+>', ''
			$plain = [Net.WebUtility]::HtmlDecode($plain) -replace '[ \t]+', ' ' -replace '(\r?\n\s*){3,}', "`n`n"
			$record = [pscustomobject]@{ Query=$title; URL=$response.BaseResponse.ResponseUri.AbsoluteUri; Heading=$heading; FetchedAt=(Get-Date).ToString('o'); Text=$plain.Trim() }
			[IO.File]::WriteAllText($cachePath, ($record | ConvertTo-Json -Depth 4), [Text.UTF8Encoding]::new($true))
		} catch {
			[pscustomobject]@{ Query=$title; Error=$_.Exception.Message } | ConvertTo-Json -Compress
			continue
		}
	}
	[pscustomobject]@{ Query=$title; Heading=$record.Heading; URL=$record.URL; Cache=$cachePath; Preview=$record.Text.Substring(0, [Math]::Min(650, $record.Text.Length)) } | ConvertTo-Json -Compress
}
