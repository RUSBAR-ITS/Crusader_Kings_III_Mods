# Windows PowerShell 5.1 needs extended paths for the deeply nested model files.
function Get-NativePath([string]$FilePath){
    if($FilePath.StartsWith('\\?\')){return $FilePath}
    $full=[IO.Path]::GetFullPath($FilePath)
    if($full.StartsWith('\\')){return '\\?\UNC\'+$full.Substring(2)}
    return '\\?\'+$full
}
function Get-BytesSHA256([byte[]]$Bytes){
    $algorithm=[Security.Cryptography.SHA256]::Create()
    try{return [BitConverter]::ToString($algorithm.ComputeHash($Bytes)).Replace('-','')}
    finally{$algorithm.Dispose()}
}
function Get-NativeSHA256([string]$FilePath){
    $stream=[IO.File]::OpenRead((Get-NativePath $FilePath))
    $algorithm=[Security.Cryptography.SHA256]::Create()
    try{return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','')}
    finally{$algorithm.Dispose();$stream.Dispose()}
}
function ConvertFrom-HexBytes([string]$Hex){
    if($Hex.Length % 2 -ne 0 -or $Hex -notmatch '^[0-9a-fA-F]+$'){throw 'Invalid binary recipe hex.'}
    [byte[]]$result=New-Object byte[] ($Hex.Length/2)
    for($i=0;$i -lt $result.Length;$i++){$result[$i]=[Convert]::ToByte($Hex.Substring(2*$i,2),16)}
    return ,$result
}
function Get-RepairedBinary([string]$Source,$Recipe){
    [byte[]]$original=[IO.File]::ReadAllBytes((Get-NativePath $Source))
    if((Get-BytesSHA256 $original) -cne $Recipe.SourceSHA256){throw "Binary source changed: $Source"}
    [byte[]]$remove=ConvertFrom-HexBytes $Recipe.RemoveHex
    [byte[]]$following=ConvertFrom-HexBytes $Recipe.FollowingHex
    [int]$offset=$Recipe.Offset
    if($offset -lt 0 -or $offset+$remove.Length+$following.Length -gt $original.Length){throw 'Invalid binary repair bounds.'}
    for($i=0;$i -lt $remove.Length;$i++){if($original[$offset+$i] -ne $remove[$i]){throw 'Binary removal bytes differ.'}}
    for($i=0;$i -lt $following.Length;$i++){if($original[$offset+$remove.Length+$i] -ne $following[$i]){throw 'Binary following node differs.'}}
    [byte[]]$result=New-Object byte[] ($original.Length-$remove.Length)
    [Array]::Copy($original,0,$result,0,$offset)
    [Array]::Copy($original,$offset+$remove.Length,$result,$offset,$original.Length-$offset-$remove.Length)
    if((Get-BytesSHA256 $result) -cne $Recipe.PatchedSHA256){throw 'Binary output differs from approved model.'}
    return ,$result
}
