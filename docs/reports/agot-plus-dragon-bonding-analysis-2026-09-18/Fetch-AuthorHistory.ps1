param([int]$MaxPage=27,[switch]$OfflineOnly)
$ErrorActionPreference='Stop'
$utf8=[Text.UTF8Encoding]::new($false,$true)
$destination=Join-Path $PSScriptRoot 'author-sources'
[IO.Directory]::CreateDirectory($destination)|Out-Null
$entries=[Collections.Generic.List[object]]::new()
$sources=[Collections.Generic.List[object]]::new()
for($page=1;$page -le $MaxPage;$page++){
 $url='https://steamcommunity.com/sharedfiles/filedetails/changelog/2950245430?p='+$page
 $file=Join-Path $destination ('changelog-page-{0:00}.html' -f $page)
 if(Test-Path -LiteralPath $file){$html=[IO.File]::ReadAllText($file)}else{
  if($OfflineOnly){Write-Warning "Missing cached page $page; stopping at available coverage.";break}
  try {$response=Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 30}
  catch {Write-Warning "Request failed on page $page; keeping available coverage. $($_.Exception.Message)";break}
  $html=$response.Content
  [IO.File]::WriteAllText($file,$html,$utf8)
 }
 $matches=[regex]::Matches($html,'(?s)<div class="changelog headline">\s*Update:\s*(?<date>.*?)</div>.*?<p id="(?<timestamp>\d+)">(?<body>.*?)</p>')
 if($matches.Count -eq 0){throw "No changelog entries on page $page"}
 foreach($m in $matches){
  $body=$m.Groups['body'].Value -replace '(?i)<br\s*/?>',[Environment]::NewLine
  $body=[Net.WebUtility]::HtmlDecode(($body -replace '<[^>]+>','')).Trim()
  $timestamp=[long]$m.Groups['timestamp'].Value
  $entries.Add([pscustomobject]@{Page=$page;DateLabel=[Net.WebUtility]::HtmlDecode($m.Groups['date'].Value.Trim());UTC=[DateTimeOffset]::FromUnixTimeSeconds($timestamp).ToString('o');Timestamp=$timestamp;URL=$url+'#'+$timestamp;Body=$body})
 }
 $sources.Add([pscustomobject]@{URL=$url;File=[IO.Path]::GetFileName($file);Entries=$matches.Count;SHA256=(Get-FileHash -LiteralPath $file).Hash})
 Write-Output "Page $page : $($matches.Count) entries"
}
[IO.File]::WriteAllText((Join-Path $destination 'changelog-entries.json'),(ConvertTo-Json -InputObject $entries.ToArray() -Depth 5)+[Environment]::NewLine,$utf8)
[IO.File]::WriteAllText((Join-Path $destination 'source-manifest.json'),(ConvertTo-Json -InputObject $sources.ToArray() -Depth 5)+[Environment]::NewLine,$utf8)
$relevant=@(foreach($entry in $entries){
 $lines=@($entry.Body -split '\r?\n'|Where-Object {$_ -match '(?i)dragon|bond|scheme|canon children|obsolete'})
 if($lines.Count){[pscustomobject]@{Date=$entry.UTC;Page=$entry.Page;URL=$entry.URL;Text=$lines -join [Environment]::NewLine}}
})
$relevant|Export-Csv -LiteralPath (Join-Path $destination 'relevant-history.csv') -NoTypeInformation -Encoding UTF8
Write-Output "Total: $($entries.Count); relevant updates: $($relevant.Count)"
