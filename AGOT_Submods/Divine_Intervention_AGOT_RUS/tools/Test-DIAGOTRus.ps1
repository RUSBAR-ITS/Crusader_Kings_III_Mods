param(
    [string]$MainPath='E:\SteamLibrary\steamapps\workshop\content\1158310\2996152542',
    [string]$BasePath='E:\SteamLibrary\steamapps\workshop\content\1158310\2986538297',
    [string]$BaseRussianPath='E:\SteamLibrary\steamapps\workshop\content\1158310\3041996936',
    [string]$AgotPath='E:\SteamLibrary\steamapps\workshop\content\1158310\2962333032',
    [string]$AgotRussianPath='E:\SteamLibrary\steamapps\workshop\content\1158310\2962803371',
    [string]$GamePath='E:\SteamLibrary\steamapps\common\Crusader Kings III\game'
)
. (Join-Path $PSScriptRoot '../../../tools/RepositoryText.ps1')

$ErrorActionPreference='Stop'
$modRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$utf8=[Text.UTF8Encoding]::new($false,$true)
$roots=@{Main=$MainPath;Base=$BasePath;BaseRussian=$BaseRussianPath;AGOT=$AgotPath;AGOT_RU=$AgotRussianPath;CK3=$GamePath}
$baseline=Get-Content -LiteralPath (Join-Path $modRoot 'docs/source-baseline.json') -Encoding UTF8 -Raw|ConvertFrom-Json
$runtimeRepairs=Get-Content -LiteralPath (Join-Path $modRoot 'docs/runtime-localization-repairs.json') -Encoding UTF8 -Raw|ConvertFrom-Json
$additions=Get-Content -LiteralPath (Join-Path $modRoot 'docs/runtime-additions.json') -Encoding UTF8 -Raw|ConvertFrom-Json
$shadows=Get-Content -LiteralPath (Join-Path $modRoot 'docs/shadow-manifest.json') -Encoding UTF8 -Raw|ConvertFrom-Json
foreach($item in $baseline){if((Get-FileHash -LiteralPath (Join-Path $roots[$item.Catalog] $item.File) -Algorithm SHA256).Hash -cne $item.SHA256){throw ('Changed source: '+$item.File)}}
function New-DIMap {return ,([Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal))}
function Read-DIFile([string]$Path,[switch]$Strict){
    $map=New-DIMap
    foreach($line in [IO.File]::ReadAllLines($Path,$utf8)){
        if($line -match '^\s*(#.*)?$|^\s*l_\w+:\s*$'){continue}
        # Retain upstream interior quotes; our overlay has an additional
        # unescaped-quote check below. Require valid separators and endings.
        if($Strict -and $line -notmatch '^\s*[^\s#":]+:[ \t]*(?:\d+[ \t]+)?"(?:[^\\]|\\[nrt"\\])*"[ \t]*(?:#.*)?$'){throw "Malformed localization syntax: $Path / $line"}
        if($line -match '^\s*(?<key>[^\s#":]+):\s*(?:\d+\s*)?"(?<value>.*)"\s*(?:#.*)?$'){
            if($Strict -and $map.ContainsKey($Matches.key)){throw "Duplicate key: $Path / $($Matches.key)"}
            $map[$Matches.key]=$Matches.value
        }elseif($Strict){throw "Malformed line: $Path / $line"}
    }
    return ,$map
}
function Read-DICatalog([string]$Root,[string]$Language){
    $map=New-DIMap
    foreach($file in Get-ChildItem -LiteralPath (Join-Path $Root 'localization') -Recurse -File -Filter ('*_l_'+$Language+'.yml')|Sort-Object FullName){
        if([IO.File]::ReadAllText($file.FullName) -notmatch ('(?m)^\s*l_'+$Language+':\s*$')){continue}
        $values=Read-DIFile $file.FullName
        foreach($key in $values.Keys){$map[$key]=$values[$key]}
    }
    return ,$map
}
$en=Read-DICatalog $MainPath 'english'
$builtin=Read-DICatalog $MainPath 'russian'
$baseEN=Read-DICatalog $BasePath 'english'
$baseRU=Read-DICatalog $BasePath 'russian'
$baseExternalRU=Read-DICatalog $BaseRussianPath 'russian'
$runtimePath=Join-Path $modRoot 'localization/replace/russian/zzzz_di_agot_l_russian.yml'
$bytes=[IO.File]::ReadAllBytes($runtimePath)
if($bytes.Length -lt 3 -or $bytes[0] -ne 239 -or $bytes[1] -ne 187 -or $bytes[2] -ne 191){throw 'Localization must have UTF-8 BOM.'}
if([IO.File]::ReadAllText($runtimePath,$utf8) -cnotmatch '\Al_russian:\r?\n'){throw 'Incorrect language header.'}
$ru=Read-DIFile $runtimePath -Strict
if($en.Count -ne 71 -or $builtin.Count -ne 73 -or $ru.Count -ne 102 -or $runtimeRepairs.Count -ne 3 -or $additions.Count -ne 26){throw 'Catalog size changed; review the source update.'}
foreach($key in $en.Keys){if(-not $ru.ContainsKey($key)){throw "Untranslated English key: $key"}}
foreach($key in $builtin.Keys){if(-not $ru.ContainsKey($key)){throw "Builtin Russian key omitted: $key"}}
foreach($key in $ru.Keys){if(-not $builtin.ContainsKey($key) -and $key -cnotin $runtimeRepairs.Key -and $key -cnotin $additions.Key){throw "Unreviewed additional key: $key"}}

# Check the package that CK3 actually reads, including the source-path shadow.
$packaged=@(Get-ChildItem -LiteralPath (Join-Path $modRoot 'localization') -Recurse -File -Filter '*.yml')
if($packaged.Count -ne 2 -or $shadows.Count -ne 1){throw 'Unexpected localization package contents.'}
foreach($file in $packaged){
    $data=[IO.File]::ReadAllBytes($file.FullName)
    if($data[0] -ne 239 -or $data[1] -ne 187 -or $data[2] -ne 191){throw "Missing UTF-8 BOM: $($file.Name)"}
    if([IO.File]::ReadAllText($file.FullName,$utf8) -cnotmatch '\Al_russian:\r?\n'){throw "Wrong language header: $($file.Name)"}
    $null=Read-DIFile $file.FullName -Strict
}
foreach($shadow in $shadows){
    $source=Join-Path $BaseRussianPath $shadow.File
    $destination=Join-Path $modRoot $shadow.File
    if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -cne $shadow.SourceSHA256 -or (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -cne $shadow.PatchedSHA256){throw 'Source/shadow hash changed; review and rebuild.'}
    $lines=[regex]::Split([IO.File]::ReadAllText($source,$utf8),'(?<=\n)')
    if($shadow.Changes.Count -ne 3){throw 'Expected exactly three base DI fixes.'}
    foreach($fix in $shadow.Changes){
        $contract=@($runtimeRepairs|Where-Object Key -CEQ $fix.Key)
        $i=$fix.Line-1
        $body=$lines[$i].TrimEnd([char[]]"`r`n")
        if($contract.Count -ne 1 -or $body -cne $fix.Before -or $contract[0].After -cne $fix.After -or $contract[0].Before -cne $fix.Before){throw "Unexpected shadow change: $($fix.Key)"}
        if($fix.After -notmatch '^\s*[^:]+:\s*(?:\d+\s+)?"(.*)"\s*$' -or $Matches[1] -cne $ru[$fix.Key]){throw "Shadow/overlay mismatch: $($fix.Key)"}
        $lines[$i]=$fix.After+$lines[$i].Substring($body.Length)
    }
    if([RepositoryText]::Normalize([string]::Concat($lines)) -cne [IO.File]::ReadAllText($destination,$utf8)){throw 'Unrecorded change in base DI translation shadow.'}
}
foreach($item in $additions){
    if(-not $ru.ContainsKey($item.Key)){throw "Missing additional label: $($item.Key)"}
    $definition=[IO.File]::ReadAllText((Join-Path $roots[$item.Catalog] $item.DefinitionFile))
    if($definition -cnotmatch ('(?m)^\s*'+[regex]::Escape($item.Definition)+'\s*=\s*\{')){throw "Missing actual building/unit/debug action: $($item.Key)"}
}
$aliasExceptions=@('DI_holding_type_settlement_holding','DI_holding_type_unknown_holding','DI_holding_type_wilderness_holding','DI_holding_type_monastery_holding','DI_holding_type_pirate_den_holding','DI_holding_type_ruin_holding')
$review=[Collections.Generic.List[object]]::new()
foreach($key in $ru.Keys|Sort-Object -CaseSensitive){
    $value=$ru[$key]
    if($value -match '(?<!\\)"|\\(?![nrt"\\])' -or [regex]::Matches($value,'\[').Count -ne [regex]::Matches($value,'\]').Count -or [regex]::Matches($value,'\$').Count % 2){throw "Broken template: $key"}
    $depth=0
    foreach($tag in [regex]::Matches($value,'#!|#[A-Za-z][A-Za-z0-9_]*')){if($tag.Value -eq '#!'){$depth--}else{$depth++};if($depth -lt 0){throw "Formatting underflow: $key"}}
    if($depth){throw "Unclosed formatting: $key"}
    $english=if($en.ContainsKey($key)){$en[$key]}elseif($key -cin $runtimeRepairs.Key){$baseEN[$key]}else{$null}
    $englishOriginal=$english
    if($english){
        # Translate visible text embedded inside the stress expression, while
        # preserving the actual English function names and their arguments.
        if($key -ceq 'DI_STRESS_TOOLTIP'){$english=$english.Replace('#S Effects:#!','#S Эффекты:#!')}
        foreach($pattern in @('\[[^\]]*\]','#!|#[A-Za-z][A-Za-z0-9_]*','@[^!\s]+!','\\[nrt]','\$[^$]+\$')){
            if($key -cin $aliasExceptions -and $pattern -ceq '\$[^$]+\$'){continue}
            $before=([regex]::Matches($english,$pattern)|ForEach-Object Value|Sort-Object -CaseSensitive)-join '|'
            $after=([regex]::Matches($value,$pattern)|ForEach-Object Value|Sort-Object -CaseSensitive)-join '|'
            if($key -cin @('DI_select_kingdoms_tt','DI_select_counties_tt')){$before=$before.Replace('#bold','#Bold')}
            if($before -cne $after){throw "Changed protected token: $key / $pattern"}
        }
    }
    $visible=$value -replace '\[[^\]]*\]|\$[^$]+\$|#[A-Za-z0-9_!]+|\\[nrt]','' -replace 'AGOT',''
    if($visible -match '[A-Za-z]'){throw "Untranslated prose remains: $key"}
    $review.Add([pscustomobject]@{Key=$key;English=$englishOriginal;BuiltinRussian=$builtin[$key];BaseRussian=$baseExternalRU[$key];Russian=$value})
}

# Resolve nested holding-type aliases against real CK3 / AGOT Russian text.
$aliases=New-DIMap
foreach($item in $baseline|Where-Object {$_.Catalog -in @('AGOT_RU','CK3') -and $_.File -like '*_l_russian.yml'}){
    $values=Read-DIFile (Join-Path $roots[$item.Catalog] $item.File)
    foreach($key in $values.Keys){$aliases[$key]=$values[$key]}
}
foreach($key in $ru.Keys){$aliases[$key]=$ru[$key]}
function Expand-DIValue([string]$Key,[string[]]$Stack){
    if($Key -cin $Stack){throw "Localization alias cycle: $Key"}
    if(-not $aliases.ContainsKey($Key)){throw "Missing alias definition: $Key"}
    $value=$aliases[$Key]
    foreach($match in [regex]::Matches($value,'\$([^$]+)\$')){
        $expanded=Expand-DIValue $match.Groups[1].Value ($Stack+@($Key))
        $value=$value.Replace($match.Value,$expanded)
    }
    return $value
}
$expanded=@(foreach($key in $ru.Keys|Where-Object {$_ -like 'DI_holding_*'}|Sort-Object -CaseSensitive){
    [pscustomobject]@{Key=$key;Russian=(Expand-DIValue $key @())}
})

# Include building labels and generated-army names, which are outside DI_*.
$agotRU=Read-DICatalog $AgotRussianPath 'russian'
$gameRU=Read-DICatalog $GamePath 'russian'
function Get-DILabelSource([string]$Key){
    if($ru.ContainsKey($Key)){return 'This translation'}
    if($baseExternalRU.ContainsKey($Key)){return 'Base DI external Russian'}
    if($baseRU.ContainsKey($Key)){return 'Base DI builtin Russian'}
    if($agotRU.ContainsKey($Key)){return 'AGOT Russian'}
    if($gameRU.ContainsKey($Key)){return 'CK3 Russian'}
    if($baseEN.ContainsKey($Key)){return 'Base DI English only'}
    return 'Unresolved'
}
$references=[Collections.Generic.List[object]]::new()
$rawLiterals=[Collections.Generic.List[object]]::new()
$scripts=@(foreach($folder in @('common','gui','events')){Get-ChildItem -LiteralPath (Join-Path $MainPath $folder) -Recurse -File|Where-Object {$_.Extension -in @('.txt','.gui')}})
$actualScripts=@($scripts|ForEach-Object {$_.FullName.Substring($MainPath.TrimEnd('\','/').Length+1).Replace('\','/')})
$expectedScripts=@($baseline|Where-Object {$_.Catalog -eq 'Main' -and $_.File -match '^(common|gui|events)/'}|ForEach-Object File)
if((($actualScripts|Sort-Object -CaseSensitive)-join '|') -cne (($expectedScripts|Sort-Object -CaseSensitive)-join '|')){throw 'Addon script inventory changed.'}
foreach($file in $scripts){
    $relative=$file.FullName.Substring($MainPath.TrimEnd('\','/').Length+1).Replace('\','/')
    $number=0
    foreach($line in [IO.File]::ReadAllLines($file.FullName)){
        $number++
        if($line -match '^\s*#'){continue}
        foreach($match in [regex]::Matches($line,'\b(?:text|tooltip|custom_tooltip|desc|title|localization_key)\s*=\s*"?((?:DI_|building_type_)[A-Za-z_0-9.]+)(?=[\s"}]|$)')){
            $key=$match.Groups[1].Value
            $source=Get-DILabelSource $key
            $references.Add([pscustomobject]@{File=$relative;Line=$number;Key=$key;Source=$source})
        }
        if($relative -ceq 'common/scripted_guis/DI_army_spawner_maa_sgui.txt' -and $line -cmatch '^\s*name\s*=\s*"?([A-Za-z_][A-Za-z_0-9.]*)"?\s*$'){
            $key=$Matches[1]
            $references.Add([pscustomobject]@{File=$relative;Line=$number;Key=$key;Source=(Get-DILabelSource $key)})
        }
        foreach($match in [regex]::Matches($line,'\braw_text\s*=\s*"([^"\r\n]*)"')){
            $value=$match.Groups[1].Value
            if(($value -replace '\[[^\]]*\]','') -match '[A-Za-z]'){$rawLiterals.Add([pscustomobject]@{File=$relative;Line=$number;Text=$value})}
        }
    }
}
$debugGui=[IO.File]::ReadAllText((Join-Path $BasePath 'gui/DI_artifact_creator.gui'))
if($debugGui -notmatch 'text\s*=\s*"testbutton"' -or -not $ru.ContainsKey('testbutton')){throw 'Debug button localization contract changed.'}
$references.Add([pscustomobject]@{File='[Base DI] gui/DI_artifact_creator.gui';Line=267;Key='testbutton';Source=(Get-DILabelSource 'testbutton')})
foreach($item in $additions){if(-not @($references|Where-Object Key -CEQ $item.Key).Count){throw "Additional label has no checked call site: $($item.Key)"}}
$unknown=@($references|Where-Object Source -eq 'Unresolved')
if($unknown.Count){$unknown|Format-Table -AutoSize|Out-Host;throw 'Unresolved DI GUI/script localization references.'}
if($rawLiterals.Count){$rawLiterals|Format-Table -AutoSize|Out-Host;throw 'Hardcoded English GUI prose requires review.'}
$referenceGroups=@($references|Group-Object Source|ForEach-Object {[ordered]@{Source=$_.Name;Occurrences=$_.Count;UniqueKeys=@($_.Group.Key|Sort-Object -Unique -CaseSensitive).Count}})
$manifest=[ordered]@{
    MainWorkshopId='2996152542';MainVersion='0.2.1';BaseWorkshopId='2986538297';BaseVersion='0.4.0';BaseRussianWorkshopId='3041996936'
    SourceHashesChecked=$baseline.Count;EnglishKeys=$en.Count;BuiltinRussianKeys=$builtin.Count;OutputRussianKeys=$ru.Count
    IdenticalBuiltinEnglish=@($en.Keys|Where-Object {$builtin[$_] -ceq $en[$_]}).Count
    MissingRussianKeys=0;ExpandedHoldingLabels=$expanded.Count;ScannedScriptFiles=$scripts.Count;References=$referenceGroups;UnresolvedReferences=0;HardcodedEnglishProse=0
    AdditionalRuntimeLabels=$additions.Count;BaseTranslationRepairs=$runtimeRepairs.Count;LocalizationShadows=$shadows.Count
    ScriptOverrides=0;GameLaunched=$false
    LocalizationSHA256=(Get-FileHash -LiteralPath $runtimePath -Algorithm SHA256).Hash
}
foreach($folder in @('common','events','gui','gfx','history')){if(Test-Path -LiteralPath (Join-Path $modRoot $folder)){throw 'Translation-only package contains script/assets folder.'}}
[RepositoryText]::WriteAllLines((Join-Path $modRoot 'docs/translations.csv'), [string[]]@($review | ConvertTo-Csv -NoTypeInformation), [Text.UTF8Encoding]::new($true))
[RepositoryText]::WriteAllLines((Join-Path $modRoot 'docs/holding-labels-expanded.csv'), [string[]]@($expanded | ConvertTo-Csv -NoTypeInformation), [Text.UTF8Encoding]::new($true))
[RepositoryText]::WriteAllLines((Join-Path $modRoot 'docs/script-references.csv'), [string[]]@($references | ConvertTo-Csv -NoTypeInformation), [Text.UTF8Encoding]::new($true))
[RepositoryText]::WriteAllText((Join-Path $modRoot 'docs/source-manifest.json'), ($manifest|ConvertTo-Json -Depth 6)+"`n", [Text.UTF8Encoding]::new($true))
$manifest|ConvertTo-Json -Depth 6
