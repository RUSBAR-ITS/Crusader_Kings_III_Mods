param([string]$BaseRussianPath='E:\SteamLibrary\steamapps\workshop\content\1158310\3041996936')
. (Join-Path $PSScriptRoot '../../../tools/RepositoryText.ps1')

$ErrorActionPreference='Stop'
$modRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$utf8=[Text.UTF8Encoding]::new($true,$true)
$repairs=Get-Content -LiteralPath (Join-Path $modRoot 'docs/runtime-localization-repairs.json') -Raw -Encoding UTF8|ConvertFrom-Json
$baseline=Get-Content -LiteralPath (Join-Path $modRoot 'docs/source-baseline.json') -Raw -Encoding UTF8|ConvertFrom-Json
$overlay=[IO.File]::ReadAllText((Join-Path $modRoot 'localization/replace/russian/zzzz_di_agot_l_russian.yml'),$utf8)
$prepared=[Collections.Generic.List[object]]::new()
foreach($group in $repairs|Group-Object File){
    $source=Join-Path $BaseRussianPath $group.Name
    $expected=@($baseline|Where-Object {$_.Catalog -eq 'BaseRussian' -and $_.File -ceq $group.Name})
    $hash=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    if($expected.Count -ne 1 -or $hash -cne $expected[0].SHA256){throw "Upstream translation changed: $source"}
    $lines=[regex]::Split([IO.File]::ReadAllText($source,$utf8),'(?<=\n)')
    foreach($fix in $group.Group){
        $i=$fix.Line-1
        $before=$lines[$i].TrimEnd([char[]]"`r`n")
        if($before -cne $fix.Before){throw "Repair changed upstream: $($fix.Key)"}
        if(-not [regex]::IsMatch($overlay,'(?m)^'+[regex]::Escape($fix.After)+'\r?$')){throw "Repair/overlay mismatch: $($fix.Key)"}
        $lines[$i]=$fix.After+$lines[$i].Substring($before.Length)
    }
    $prepared.Add([pscustomobject]@{File=$group.Name;SourceSHA256=$hash;Content=[string]::Concat($lines);Changes=@($group.Group)})
}
$manifest=@(foreach($item in $prepared){
    $path=Join-Path $modRoot $item.File
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path))|Out-Null
    [RepositoryText]::WriteAllText($path,$item.Content,$utf8)
    [pscustomobject]@{Catalog='BaseRussian';File=$item.File;SourceSHA256=$item.SourceSHA256;PatchedSHA256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash;Changes=$item.Changes}
})
[RepositoryText]::WriteAllText((Join-Path $modRoot 'docs/shadow-manifest.json'),(ConvertTo-Json -InputObject $manifest -Depth 7)+"`n",$utf8)
Write-Output "Built $($manifest.Count) localization shadow with $($repairs.Count) audited base DI repairs."
