param([string]$Profile='C:/Users/RUSBAR/Documents/Paradox Interactive/Crusader Kings III')
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$snapshot=Join-Path $PSScriptRoot 'snapshot'
if(Test-Path -LiteralPath $snapshot){throw 'Snapshot exists; do not overwrite historical evidence.'}
[IO.Directory]::CreateDirectory($snapshot)|Out-Null
$utf8=[Text.UTF8Encoding]::new($false,$true)
$logRecords=@(foreach($file in @('error.log','game.log','system.log','debug.log','database_conflicts.log','code_revisions.log')){
 $source=Join-Path $Profile ('logs/'+$file)
 $info=Get-Item -LiteralPath $source
 $before=(Get-FileHash -LiteralPath $source).Hash
 $target=Join-Path $snapshot $file
 Copy-Item -LiteralPath $source -Destination $target
 $hash=(Get-FileHash -LiteralPath $target).Hash
 if($before -cne $hash -or $hash -cne (Get-FileHash -LiteralPath $source).Hash){throw 'Log changed during capture'}
 [pscustomobject]@{File=$file;Length=$info.Length;LastWriteTime=$info.LastWriteTime.ToString('o');SHA256=$hash}
})
Copy-Item -LiteralPath (Join-Path $Profile 'dlc_load.json') -Destination (Join-Path $snapshot 'dlc_load.json')
$load=Get-Content -LiteralPath (Join-Path $snapshot 'dlc_load.json') -Raw -Encoding UTF8|ConvertFrom-Json
$order=0
$mods=@(foreach($descriptor in $load.enabled_mods){
 $body=[IO.File]::ReadAllText((Join-Path $Profile $descriptor))
 $path=[regex]::Match($body,'(?m)^\s*path="([^"]+)"').Groups[1].Value
 $name=[regex]::Match($body,'(?m)^\s*name="([^"]+)"').Groups[1].Value
 $order++
 if(-not $path -or -not $name -or -not (Test-Path -LiteralPath $path -PathType Container)){throw "Unresolved mod: $descriptor"}
 [pscustomobject]@{Order=$order;Name=$name;Path=$path;Descriptor=$descriptor;Exists=$true}
})
$mods|Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'active-mods.csv') -Encoding UTF8 -NoTypeInformation
$runtime=[Collections.Generic.List[object]]::new()
$manifestHashes=@{}
foreach($spec in @(@('AGOT_PLUS_FIX','patch'),@('AGOT_PLUS_RUS_CORRECT','localization'))){
 $root=Join-Path $repo ('AGOT_Submods/'+$spec[0])
 $manifestPath=Join-Path $root 'docs/source-manifest.json'
 $manifest=Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8|ConvertFrom-Json
 $manifestHashes[$spec[1]]=(Get-FileHash -LiteralPath $manifestPath).Hash
 Copy-Item -LiteralPath $manifestPath -Destination (Join-Path $snapshot ($spec[1]+'-source-manifest.json'))
 $files=@($manifest.Files|ForEach-Object {[pscustomobject]@{File=$_.File;Hash=$_.PatchedSHA256}})
 if($spec[1] -ceq 'localization'){
  $files += [pscustomobject]@{File=$manifest.Overlay;Hash=$manifest.OverlaySHA256}
  $files += [pscustomobject]@{File=$manifest.RuntimeNames.File;Hash=$manifest.RuntimeNames.SHA256}
 }
 foreach($file in $files){
  $path=Join-Path $root $file.File
  $info=Get-Item -LiteralPath $path
  $hash=(Get-FileHash -LiteralPath $path).Hash
  if($hash -cne $file.Hash){throw "Runtime file differs from manifest: $path"}
  $providers=@($mods|Where-Object {Test-Path -LiteralPath (Join-Path $_.Path $file.File) -PathType Leaf})
  if([IO.Path]::GetFullPath($providers[-1].Path) -ine [IO.Path]::GetFullPath($root)){throw "Patch file is shadowed: $path"}
  $runtime.Add([pscustomobject]@{Mod=$spec[0];File=$file.File;LastWriteTime=$info.LastWriteTime.ToString('o');SHA256=$hash})
 }
}
$runtime|Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'runtime-files.csv') -Encoding UTF8 -NoTypeInformation
foreach($file in @('source-baseline.json','stage9-plan.json','stage9-validation.json','stage9-targeted-log-messages.csv','stage9-deferred-log-messages.csv','stage10-plan.json','stage10-validation.json','stage10-targeted-log-messages.csv')){
 Copy-Item -LiteralPath (Join-Path $repo ('AGOT_Submods/AGOT_PLUS_FIX/docs/'+$file)) -Destination (Join-Path $snapshot $file)
}
$summary=[ordered]@{CapturedAt=[DateTimeOffset]::Now.ToString('o');ActiveMods=$mods.Count;Logs=$logRecords;PatchManifestSHA256=$manifestHashes.patch;LocalizationManifestSHA256=$manifestHashes.localization;RuntimeFiles=$runtime.Count;RuntimeMatchesManifest=$true;ActiveVFSMatches=$true}
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'snapshot-summary.json'),($summary|ConvertTo-Json -Depth 5)+[Environment]::NewLine,$utf8)
$summary|ConvertTo-Json -Depth 5
