param(
    [string]$MainPath='E:\SteamLibrary\steamapps\workshop\content\1158310\2950245430',
    [string]$AgotPath='E:\SteamLibrary\steamapps\workshop\content\1158310\2962333032'
)
. (Join-Path $PSScriptRoot '../../../tools/RepositoryText.ps1')

$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'NativeFiles.ps1')
$modRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$utf8=[Text.UTF8Encoding]::new($false,$true)
$roots=@{AGOT_PLUS=$MainPath;AGOT=$AgotPath}
$baseline=Get-Content -LiteralPath (Join-Path $modRoot 'docs/source-baseline.json') -Raw -Encoding UTF8|ConvertFrom-Json
$fixes=Get-Content -LiteralPath (Join-Path $modRoot 'docs/fixes.json') -Raw -Encoding UTF8|ConvertFrom-Json
$additions=Get-Content -LiteralPath (Join-Path $modRoot 'docs/additions.json') -Raw -Encoding UTF8|ConvertFrom-Json
$binaryFixes=Get-Content -LiteralPath (Join-Path $modRoot 'docs/binary-fixes.json') -Raw -Encoding UTF8|ConvertFrom-Json
& python (Join-Path $PSScriptRoot 'DNA-Stage9.py') sources
if($LASTEXITCODE -ne 0){throw 'Stage-nine DNA sources or effective gene schema changed.'}
& python (Join-Path $PSScriptRoot 'DNA-Stage10.py') sources
if($LASTEXITCODE -ne 0){throw 'Stage-ten DNA selection, sources or effective gene schema changed.'}
& python (Join-Path $PSScriptRoot 'Portraits-Stage11.py') sources
if($LASTEXITCODE -ne 0){throw 'Stage-eleven portrait/model sources or approved candidates changed.'}
& python (Join-Path $PSScriptRoot 'Variables-Stage12.py') sources
if($LASTEXITCODE -ne 0){throw 'Stage-twelve variable sources or approved candidates changed.'}
foreach($source in $baseline){
    $path=Join-Path $roots[$source.Catalog] $source.File
    if((Get-NativeSHA256 $path) -cne $source.SHA256){throw "Upstream source changed; review before building: $path"}
}
$prepared=[Collections.Generic.List[object]]::new()
foreach($group in $fixes|Group-Object File){
    $relative=$group.Name
    $catalogs=@($group.Group|ForEach-Object {if($_.Catalog){$_.Catalog}else{'AGOT_PLUS'}}|Sort-Object -Unique)
    if($catalogs.Count -ne 1 -or -not $roots.ContainsKey($catalogs[0])){throw "Ambiguous source catalog: $relative"}
    $catalog=$catalogs[0]
    if(@($baseline|Where-Object { $_.Catalog -eq $catalog -and $_.File -eq $relative }).Count -ne 1){throw "Missing source baseline: $catalog/$relative"}
    $source=Join-Path $roots[$catalog] $relative
    $destination=[IO.Path]::GetFullPath((Join-Path $modRoot $relative))
    if(-not $destination.StartsWith($modRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw "Unsafe output path: $relative"}
    $original=[IO.File]::ReadAllText($source,$utf8)
    $body=$original
    $changes=[Collections.Generic.List[object]]::new()
    foreach($fix in $group.Group){
        if(-not $fix.Before -or $fix.Before -ceq $fix.After){throw "Invalid repair: $($fix.Id)"}
        # Later stages can refine an already migrated preset. Keep separate exact
        # guards for its original upstream text and the current intermediate text.
        $sourceBefore=if($fix.SourceBefore){$fix.SourceBefore}else{$fix.Before}
        $sourceMatches=[regex]::Matches($original,[regex]::Escape($sourceBefore))
        $currentMatches=[regex]::Matches($body,[regex]::Escape($fix.Before))
        if($sourceMatches.Count -ne $fix.ExpectedCount -or $currentMatches.Count -ne $fix.ExpectedCount){throw "Repair count changed: $($fix.Id)"}
        $sourceLines=@($sourceMatches|ForEach-Object {1+[regex]::Matches($original.Substring(0,$_.Index),"`n").Count})
        $body=$body.Replace($fix.Before,$fix.After)
        $record=[ordered]@{Id=$fix.Id;Group=$fix.Group;SourceLines=$sourceLines;Occurrences=$sourceMatches.Count;Before=$fix.Before;After=$fix.After}
        if($fix.SourceBefore){$record.SourceBefore=$fix.SourceBefore}
        $changes.Add([pscustomobject]$record)
    }
    $bytes=[IO.File]::ReadAllBytes($source)
    $bom=$bytes.Length -ge 3 -and $bytes[0] -eq 239 -and $bytes[1] -eq 187 -and $bytes[2] -eq 191
    $prepared.Add([pscustomobject]@{File=$relative;Kind='Shadow';Catalog=$catalog;Destination=$destination;Body=$body;BOM=$bom;SourceSHA256=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash;Changes=@($changes.ToArray())})
}
foreach($fix in $binaryFixes){
    if(-not $roots.ContainsKey($fix.Catalog)){throw 'Unknown binary source catalog.'}
    $source=Join-Path $roots[$fix.Catalog] $fix.File
    $destination=[IO.Path]::GetFullPath((Join-Path $modRoot $fix.File))
    if(-not $destination.StartsWith($modRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Unsafe binary destination.'}
    if(@($prepared|Where-Object File -eq $fix.File).Count -or @($baseline|Where-Object { $_.Catalog -eq $fix.Catalog -and $_.File -eq $fix.File }).Count -ne 1){throw 'Ambiguous binary repair or missing source baseline.'}
    [byte[]]$data=Get-RepairedBinary $source $fix
    $prepared.Add([pscustomobject]@{File=$fix.File;Kind='BinaryShadow';Catalog=$fix.Catalog;Destination=$destination;Bytes=$data;BOM=$null;SourceSHA256=$fix.SourceSHA256;Changes=@($fix)})
}
foreach($addition in $additions){
    $destination=[IO.Path]::GetFullPath((Join-Path $modRoot $addition.File))
    if(-not $destination.StartsWith($modRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw "Unsafe addition path: $($addition.File)"}
    if(@($prepared|Where-Object File -eq $addition.File).Count -or (Test-Path -LiteralPath (Join-Path $MainPath $addition.File)) -or (Test-Path -LiteralPath (Join-Path $AgotPath $addition.File))){throw "Addition shadows an existing file: $($addition.File)"}
    $prepared.Add([pscustomobject]@{File=$addition.File;Kind='Addition';Catalog=$null;Destination=$destination;Body=$addition.Text;BOM=$addition.UTF8BOM;SourceSHA256=$null;Changes=@()})
}
# All source checks finish before the first generated file is written.
$files=@(foreach($item in $prepared){
    [IO.Directory]::CreateDirectory((Get-NativePath ([IO.Path]::GetDirectoryName($item.Destination))))|Out-Null
    if($item.Kind -eq 'BinaryShadow'){
        [IO.File]::WriteAllBytes((Get-NativePath $item.Destination),$item.Bytes)
    }else{
        [RepositoryText]::WriteAllText((Get-NativePath $item.Destination),$item.Body,[Text.UTF8Encoding]::new($item.BOM,$true))
    }
    [pscustomobject]@{File=$item.File;Kind=$item.Kind;Catalog=$item.Catalog;SourceSHA256=$item.SourceSHA256;PatchedSHA256=(Get-NativeSHA256 $item.Destination);UTF8BOM=$item.BOM;Changes=$item.Changes}
})
$manifest=[ordered]@{
    PatchVersion='0.1.0';Revision=12;AGOTPlusWorkshopId='2950245430';AGOTPlusMetadataVersion='1.0.0';AGOTVersion='0.5.2.1';CK3Version='1.19.0.6'
    SourceHashesChecked=$baseline.Count;FixGroups=@(@($fixes.Group)+@($additions.Group)+@($binaryFixes.Group)|Sort-Object -Unique).Count
    ReplacementRules=$fixes.Count;ReplacementOccurrences=($fixes|Measure-Object ExpectedCount -Sum).Sum
    ShadowFiles=@($prepared|Where-Object Kind -in @('Shadow','BinaryShadow')).Count;AddedFiles=$additions.Count
    BinaryShadowFiles=$binaryFixes.Count;BinaryBytesRemoved=($binaryFixes|ForEach-Object {$_.RemoveHex.Length/2}|Measure-Object -Sum).Sum
    Files=$files
}
[RepositoryText]::WriteAllText((Join-Path $modRoot 'docs/source-manifest.json'),($manifest|ConvertTo-Json -Depth 9)+"`n",$utf8)
$descriptor=[IO.File]::ReadAllText((Join-Path $modRoot 'descriptor.mod'),$utf8).TrimEnd()
if($descriptor -match '(?m)^\s*(replace_path|path)\s*='){throw 'Internal descriptor must not replace directories or include an external path.'}
$external=$descriptor+"`n"+'path="'+$modRoot.Replace('\','/')+'"'+"`n"
[RepositoryText]::WriteAllText((Join-Path $modRoot '../AGOT_PLUS_FIX.mod'),$external,$utf8)
Write-Output "Built $($manifest.ShadowFiles) file shadows and $($manifest.AddedFiles) additions; $($manifest.FixGroups) groups; $($manifest.ReplacementOccurrences) exact replacements."
Write-Output 'External descriptor prepared in the repository. Game profile and playsets were not changed.'
