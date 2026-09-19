# Static contract checks, invoked by the build command. This is not a CK3 runtime.
function Get-LegacyBlock([string]$Text, [string]$Key) {
    $clean = [regex]::Replace($Text, '"[^"\r\n]*"|#[^\r\n]*', {param($m) if ($m.Value.StartsWith('#')) { '' } else { '""' }})
    $match = [regex]::Match($clean, '(?m)(?<!\S)' + [regex]::Escape($Key) + '\s*=\s*\{')
    if (-not $match.Success) { throw "Missing script block: $Key" }
    $open = $match.Index + $match.Length - 1
    $depth = 1
    for ($i=$open+1; $i -lt $clean.Length; $i++) {
        if ($clean[$i] -eq '{') { $depth++ }
        if ($clean[$i] -eq '}') { $depth-- }
        if ($depth -eq 0) {
            return [pscustomobject]@{Body=$clean.Substring($open+1,$i-$open-1);Full=$clean.Substring($match.Index,$i-$match.Index+1)}
        }
    }
    throw "Unclosed script block: $Key"
}

function Get-LegacyLiteral([string]$Text, [string]$Key) {
    $matches = [regex]::Matches($Text, '(?m)(?<!\S)' + [regex]::Escape($Key) + '\s*=\s*([A-Za-z_][A-Za-z_0-9.:]*)')
    if ($matches.Count -ne 1) { throw "Expected one scalar $Key, found $($matches.Count)." }
    return $matches[0].Groups[1].Value
}

function Test-LegacyContracts([Collections.IDictionary]$Outputs, [Collections.IDictionary]$Catalogs, [string]$MainModPath) {
    $memories = $Outputs['common/character_memory_types/lotd_memories.txt']
    $types = @([regex]::Matches($memories, '(?m)^([A-Za-z_0-9]+)\s*=\s*\{') | ForEach-Object {$_.Groups[1].Value})
    if ($types.Count -ne 6) { throw 'Expected six memory types.' }
    $expectedRead = @('read_prophecy_desc','read_prophecy_desc_second_perspective','read_prophecy_desc_third_perspective')
    $expectedPass = @('read_prophecy_to_heir_desc','read_prophecy_to_heir_desc_second_perspective','read_prophecy_desc_to_heir_third_perspective')
    $perspectives = @('description','second_perspective_description','third_perspective_description')
    foreach ($type in $types) {
        $block = Get-LegacyBlock $memories $type
        $participants = Get-LegacyBlock $block.Body 'participants'
        $allowed = @('owner') + @([regex]::Matches($participants.Body, '[A-Za-z_0-9]+') | ForEach-Object {$_.Value})
        for ($i=0; $i -lt $perspectives.Count; $i++) {
            $description = Get-LegacyBlock $block.Body $perspectives[$i]
            $key = Get-LegacyLiteral $description.Body 'desc'
            if ($type -eq 'read_prophecy' -and $key -cne $expectedRead[$i]) { throw 'Reading memory was changed.' }
            if ($type -eq 'read_prophecy_to_heir' -and $key -cne $expectedPass[$i]) { throw 'Passing memory still points at a reading description.' }
            foreach ($language in @('RU','EN')) {
                if (-not $Catalogs[$language].ContainsKey($key)) { throw "Untranslated memory key: $key" }
                foreach ($scope in [regex]::Matches($Catalogs[$language][$key], '\b([A-Za-z_0-9]+)\.(?:Get|Is)[A-Za-z]+')) {
                    if ($scope.Groups[1].Value -cnotin $allowed) { throw "Unavailable memory scope: $key / $($scope.Value)" }
                }
            }
        }
    }

    $event = Get-LegacyBlock $Outputs['events/decisions_events/rehilt_blackfyre_events.txt'] 'rehilt_blackfyre.0001'
    $immediate = Get-LegacyBlock $event.Body 'immediate'
    $firstIf = Get-LegacyBlock $immediate.Body 'if'
    $rest = $immediate.Body.Replace($firstIf.Full,'')
    $restore = Get-LegacyBlock $rest 'if'
    $gild = Get-LegacyBlock $rest 'else'
    if ($restore.Body -notmatch 'has_variable\s*=\s*rehilted') { throw 'Restoration branch condition changed.' }
    $description = Get-LegacyBlock $event.Body 'desc'
    $conditionalDesc = Get-LegacyBlock $description.Body 'triggered_desc'
    $fallbackDesc = Get-LegacyLiteral ($description.Body.Replace($conditionalDesc.Full,'')) 'desc'
    $conditionalDescKey = Get-LegacyLiteral $conditionalDesc.Body 'desc'
    $portrait = Get-LegacyBlock $event.Body 'left_portrait'
    $firstPose = Get-LegacyBlock $portrait.Body 'triggered_animation'
    $secondPose = Get-LegacyBlock ($portrait.Body.Replace($firstPose.Full,'')) 'triggered_animation'
    foreach ($conditional in @($conditionalDesc,$firstPose)) {
        $trigger = Get-LegacyBlock $conditional.Body 'trigger'
        if ((Get-LegacyLiteral $trigger.Body 'exists') -cne 'scope:blackfyre_artifact_rehilt') { throw 'Unsupported result selector in the rehilt event.' }
    }
    $fallbackTrigger = Get-LegacyBlock $secondPose.Body 'trigger'
    if ((Get-LegacyLiteral $fallbackTrigger.Body 'exists') -cne 'scope:blackfyre_artifact') { throw 'Missing fallback artifact pose.' }
    $scenarios = @(
        @{Before='gold';Branch=$restore;Visual='blackfyre';Description='rehilt_blackfyre.0002_desc';Pose='valyrian_invasion_blackfyre_2'},
        @{Before='black';Branch=$gild;Visual='blackfyre_rehilt';Description='rehilt_blackfyre.0001_desc';Pose='valyrian_invasion_blackfyre_rehilt_2'}
    )
    foreach ($scenario in $scenarios) {
        $aliasExists = $scenario.Branch.Body -match 'save_scope_as\s*=\s*blackfyre_artifact_rehilt\b'
        $visual = Get-LegacyLiteral $scenario.Branch.Body 'visuals'
        $desc = if ($aliasExists) { $conditionalDescKey } else { $fallbackDesc }
        $pose = Get-LegacyLiteral $(if ($aliasExists) {$firstPose.Body} else {$secondPose.Body}) 'animation'
        if ($visual -cne $scenario.Visual -or $desc -cne $scenario.Description -or $pose -cne $scenario.Pose) { throw "Rehilt outcome/description/pose mismatch starting from $($scenario.Before)." }
        foreach ($language in @('EN','RU')) { if (-not $Catalogs[$language].ContainsKey($desc)) { throw 'Rehilt description missing.' } }
    }

    foreach ($id in @('0001','0003')) {
        $event = Get-LegacyBlock $Outputs['events/decisions_events/read_prophecy.txt'] ('read_prophecy.' + $id)
        $descBlock = Get-LegacyBlock $event.Body 'desc'
        $conditional = Get-LegacyBlock $descBlock.Body 'triggered_desc'
        $trigger = Get-LegacyBlock $conditional.Body 'trigger'
        if ((Get-LegacyLiteral $trigger.Body 'root') -cne 'character:Targaryen_27') { throw 'Aegon text is not restricted to the Conqueror.' }
        foreach ($isAegon in @($false,$true)) {
            $key = if ($isAegon) { Get-LegacyLiteral $conditional.Body 'desc' } else { Get-LegacyLiteral ($descBlock.Body.Replace($conditional.Full,'')) 'desc' }
            $expected = 'read_prophecy_' + $id + $(if ($isAegon) {'_aegon_desc'} else {'_desc'})
            if ($key -cne $expected) { throw "Incorrect prophecy text: $id / Aegon=$isAegon" }
            foreach ($language in @('RU','EN')) { if (-not $Catalogs[$language].ContainsKey($key)) { throw "Prophecy description missing: $key" } }
        }
    }

    $ancestor = $Catalogs.RU['read_prophecy_0021_b_desc']
    $selector = [regex]"\[Select_CString\(ancestor_1\.IsFemale, '([^']+)', '([^']+)'\)\]"
    if ($selector.Matches($ancestor).Count -ne 1 -or -not $selector.Replace($ancestor,'$1').Contains('Первой в тумане появляется') -or
        -not $selector.Replace($ancestor,'$2').Contains('Первым в тумане появляется')) { throw 'Wrong ancestor gender selection.' }

    $decision = [IO.File]::ReadAllText((Join-Path $MainModPath 'common/decisions/10_rediscover_decision.txt'))
    $dates = @([regex]::Matches($decision,'\bgame_start_date\s*=\s*(\d+\.\d+\.\d+)') | ForEach-Object {$_.Groups[1].Value} | Sort-Object)
    if (($dates -join ',') -cne '8233.2.8,8239.1.11,8258.12.21,8277.1.1,8282.9.15,8284.6.2') { throw 'Recovery dates changed.' }
    $russianDates = @('8 февраля 233','11 января 239','21 декабря 258','1 января 277','15 сентября 282','2 июня 284')
    $englishDates = @('8 February 233','11 January 239','21 December 258','1 January 277','15 September 282','2 June 284')
    for ($i=0; $i -lt $dates.Count; $i++) {
        if (-not $Catalogs.RU['setting_rediscover_mechanic_enabled_desc'].Contains($russianDates[$i]) -or
            -not $Catalogs.EN['setting_rediscover_mechanic_enabled_desc'].Contains($englishDates[$i])) { throw 'Recovery tooltip omits a supported date.' }
    }
    foreach ($language in @('RU','EN')) {
        foreach ($value in $Catalogs[$language].Values) {
            foreach ($color in [regex]::Matches($value,'#(?:BOLD;)?COLOR:\{([^}]+)\}')) {
                $components = $color.Groups[1].Value -split ','
                if ($components.Count -ne 3) { throw 'Invalid RGB component count.' }
                foreach ($component in $components) {
                    $number = 0.0
                    if (-not [double]::TryParse($component,[Globalization.NumberStyles]::Float,[Globalization.CultureInfo]::InvariantCulture,[ref]$number) -or $number -lt 0 -or $number -gt 1) { throw 'Invalid color component.' }
                }
            }
        }
    }
    Write-Output 'Contracts passed: six memories / 18 descriptions; two rehilt outcomes and poses; Aegon/non-Aegon descriptions; both ancestor genders; six supported dates; RGB formatting.'
}
