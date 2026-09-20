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
    if($Recipe.RemoveSpans){
        $spans=@($Recipe.RemoveSpans|Sort-Object Offset)
        [int]$previousEnd=0
        [int]$removed=0
        $algorithm=[Security.Cryptography.SHA256]::Create()
        try{
            foreach($span in $spans){
                [int]$start=$span.Offset;[int]$length=$span.Length
                if($start -lt $previousEnd -or $length -le 0 -or $start+$length -gt $original.Length){throw 'Invalid or overlapping UV removal span.'}
                $hash=[BitConverter]::ToString($algorithm.ComputeHash($original,$start,$length)).Replace('-','')
                if($hash -cne $span.SHA256){throw 'UV property bytes differ from approved source.'}
                $previousEnd=$start+$length;$removed+=$length
            }
        }finally{$algorithm.Dispose()}
        [byte[]]$result=New-Object byte[] ($original.Length-$removed)
        [int]$sourceOffset=0;[int]$targetOffset=0
        foreach($span in $spans){
            [int]$length=$span.Offset-$sourceOffset
            [Array]::Copy($original,$sourceOffset,$result,$targetOffset,$length)
            $sourceOffset=$span.Offset+$span.Length;$targetOffset+=$length
        }
        [Array]::Copy($original,$sourceOffset,$result,$targetOffset,$original.Length-$sourceOffset)
        if((Get-BytesSHA256 $result) -cne $Recipe.PatchedSHA256){throw 'UV output differs from approved model.'}
        return ,$result
    }
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
function Get-BinaryRemovedByteCount($Recipe){
    if($Recipe.RemoveSpans){return ($Recipe.RemoveSpans|Measure-Object Length -Sum).Sum}
    return $Recipe.RemoveHex.Length/2
}
