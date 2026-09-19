# Static checks against the installed script conditions. Does not execute CK3.
function Get-COWBlock([string]$Text,[string]$Key) {
    $clean = [regex]::Replace($Text,'"[^"\r\n]*"|#[^\r\n]*',{param($m) if($m.Value.StartsWith('#')){''}else{'""'}})
    $match = [regex]::Match($clean,'(?m)(?<!\S)'+[regex]::Escape($Key)+'\s*=\s*\{')
    if (-not $match.Success) { throw "Missing script block: $Key" }
    $open = $match.Index+$match.Length-1
    $depth = 1
    for ($i=$open+1;$i -lt $clean.Length;$i++) {
        if($clean[$i] -eq '{'){$depth++}
        if($clean[$i] -eq '}'){$depth--}
        if(-not $depth){return $clean.Substring($open+1,$i-$open-1)}
    }
    throw "Unclosed script block: $Key"
}
function Test-COWContracts([Collections.IDictionary]$Catalogs,[string]$MainModPath,[string]$AgotPath) {
    $buildings = [IO.File]::ReadAllText((Join-Path $MainModPath 'common/buildings/yy_agotcities_special_buildings_westeros.txt'))
    foreach ($case in @(
        @{Building='agot_castamere_ruins_02';Key='REBUILD_CASTAMERE_SECOND';Required='medium_ruin_03';Forbidden='medium_ruin_04'},
        @{Building='agot_oldstones_02';Key='REBUILD_OLDSTONES_SECOND';Required='large_ruin_03';Forbidden='large_ruin_04'}
    )) {
        $block = Get-COWBlock $buildings $case.Building
        $condition = Get-COWBlock $block 'can_construct_showing_failures_only'
        $stages = [regex]::Matches($condition,'\bhas_building_or_higher\s*=\s*([A-Za-z_0-9]+)')
        if ($stages.Count -ne 1 -or $stages[0].Groups[1].Value -cne $case.Required) { throw 'Ruin restoration stage changed; review tooltip.' }
        foreach ($lang in @('EN','RU')) {
            $text = $Catalogs[$lang][$case.Key]
            $ref = "[GetBuilding('$($stages[0].Groups[1].Value)').GetName]"
            if (-not $text.Contains($ref) -or $text.Contains($case.Forbidden)) { throw "Ruin tooltip does not match condition: $($case.Key)" }
            $higher = if ($lang -eq 'RU') {'или выше'} else {'or higher'}
            if (-not $text.Contains($higher)) { throw 'Tooltip lost higher-stage support.' }
        }
    }
    $hoare = Get-COWBlock (Get-COWBlock $buildings 'agot_hoare_castle_02') 'can_construct_potential'
    if ($hoare -notmatch 'building_requirement_tribal\s*=\s*no') { throw 'Hoare government restriction changed.' }
    foreach ($title in @('k_two_wyks','e_the_iron_islands','b_hoare_castle')) {
        if ($hoare -notmatch ('has_title\s*=\s*title:'+ $title+'\b')) { throw "Hoare title condition changed: $title" }
    }
    $triggers = [IO.File]::ReadAllText((Join-Path $AgotPath 'common/scripted_triggers/00_building_requirement_triggers.txt'))
    $tribal = Get-COWBlock $triggers 'building_requirement_tribal'
    $flags = @([regex]::Matches($tribal,'government_has_flag\s*=\s*(\w+)') | ForEach-Object {$_.Groups[1].Value} | Sort-Object)
    if (($flags -join '|') -cne 'government_is_nomadic|government_is_tribal|government_is_wanua') { throw 'Government flags changed; review Hoare tooltip.' }
    foreach ($word in @('племенной','кочевой','вануа')) {
        if (-not $Catalogs.RU['CASTLE_HOARE_REQUIREMENT'].Contains($word)) { throw 'Missing Russian government restriction.' }
    }
    foreach ($word in @('tribal','nomadic','wanua')) {
        if (-not $Catalogs.EN['CASTLE_HOARE_REQUIREMENT'].Contains($word)) { throw 'Missing English government restriction.' }
    }
    $null = Get-COWBlock $buildings 'agot_karhold_01'
    foreach ($lang in @('EN','RU')) {
        foreach ($key in @('building_agot_karhold_01','building_agot_karhold_01_desc','building_type_agot_karhold_01','building_type_agot_karhold_01_desc')) {
            if (-not $Catalogs[$lang].ContainsKey($key)) { throw "Real Karhold key missing: $key" }
        }
    }
    $map = [IO.File]::ReadAllText((Join-Path $MainModPath 'gfx/map/map_modes/cow_custom_map_modes.txt'))
    $key = [regex]::Match($map,'desc\s*=\s*(cow_custom_mapmode\.t)\b').Groups[1].Value
    foreach ($lang in @('EN','RU')) {
        if (-not $key -or -not $Catalogs[$lang].ContainsKey($key)) { throw 'Map-mode description unresolved.' }
    }
    $mapLevels = @([regex]::Matches($map,'has_building_or_higher\s*=\s*(\w+)') | ForEach-Object {$_.Groups[1].Value} | Sort-Object)
    if (($mapLevels -join '|') -cne 'castle_05|city_05') { throw 'Map level conditions changed; review new description.' }
    foreach ($key in @('building_palestone_sword_01','building_type_palestone_sword_01')) {
        if ($Catalogs.RU[$key] -cne 'Белокаменный Меч') { throw 'Inconsistent tower name.' }
    }
    # The generic building description delegates to the edited type description.
    if ($Catalogs.RU['building_agot_lonely_light_01_desc'] -cne '$building_type_agot_lonely_light_01_desc$') { throw 'Lost Lonely Light alias.' }
    if ($Catalogs.EN['building_oldstones_old_final_desc'] -notmatch 'Tristifer IV' -or
        $Catalogs.RU['building_oldstones_old_final_desc'] -notmatch 'Тристифер IV') { throw 'Wrong owner of the Oldstones tomb.' }
}
