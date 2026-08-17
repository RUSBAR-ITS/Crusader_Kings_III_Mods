# RB_UD generation report

- CK3: **1.19.0.6**
- Plan: `B67EDA92FCFC46CBFF4BA32267A7822B1094E6D04A8E197839239AA11A6CCB3C`
- Settings: `A088D44D5A62DFCEC190E5FAFB5BEF51342CDCAFD6168DE35CDF80B6A1CA8264`
- Vanilla input hashes: **passed**
- Generated domicile types: **5**
- Generated building objects: **1620 / 1620**
- Generated root-family files: **62**
- Construction time: **vanilla values preserved** via generated local ``@RB_UD_*`` constants
- Distinct vanilla construction-time sources: **57**
- Generated construction-time constants: **22**
- Generated numeric cost script values: **1**
- Generated scripted-effect overrides: **5**
- Preserved vanilla special-access buildings: **137**
- Rewritten specialization-access buildings: **0**
- Disabled camp-purpose cleanup pairs: **23**
- Protected hard owner switches in completion callbacks: **147**
- Protected hard domicile-location switches in completion callbacks: **22**
- Replaced indirect unsafe owner callbacks: **6**

## Building families

| Domicile type | Buildings | Root-family files |
|---|---:|---:|
| `camp` | 104 | 8 |
| `east_asian_estate` | 545 | 16 |
| `estate` | 186 | 17 |
| `japanese_manor` | 347 | 13 |
| `yurt` | 438 | 8 |

## Files

| File | Objects | SHA-256 |
|---|---:|---|
| `common/script_values/zzz_RB_UD_domicile_cost_values.txt` | 1 | `085789F27617E089DD659B18FA96ECEFF340FB68ED01B5CD0F6BD82F339D0961` |
| `common\domiciles\buildings\zzz_RB_UD_camp_baggage_train.txt` | 19 | `31926BC56B81422AAE79285ECF4180D314F11A6193D6AE01A2BFEEA325635E8C` |
| `common\domiciles\buildings\zzz_RB_UD_camp_barber_tent.txt` | 11 | `AB31060460B32F5B220EDB5CD7FA699A729A13F0FA37D2B2A35DE3694D81CAC1` |
| `common\domiciles\buildings\zzz_RB_UD_camp_fire.txt` | 14 | `96FF30F64790F9D908C9D444934B994CB5AC1D4DD036CA287B491403C7E92A00` |
| `common\domiciles\buildings\zzz_RB_UD_camp_main.txt` | 4 | `0326E911736D46BC7E4A229B5050D72B928D8FE23B3B2D38AB63A4C21541DDB1` |
| `common\domiciles\buildings\zzz_RB_UD_camp_mess_tent.txt` | 11 | `A417F6801EDB64050EE47801A659D442C12256B842D5271A7328F8574CCB047A` |
| `common\domiciles\buildings\zzz_RB_UD_camp_perimeter.txt` | 12 | `C2777FBFF050B15530882CB1804EFF5EA7B81CD58DC4A7AB29E0E0122451031E` |
| `common\domiciles\buildings\zzz_RB_UD_camp_proving_grounds.txt` | 19 | `4C03861B068D60DEA213F9384AD76698B5C4AA5EF50AB53042C2E4B9D021851A` |
| `common\domiciles\buildings\zzz_RB_UD_camp_supply_tent.txt` | 14 | `EDC31F7BE167535BF4938B8BE5D9635E88BE789131E3D3BEA2DF8831F6705072` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_ancestral_shrine.txt` | 26 | `7F58323775AFCC83F0B4316C4E8CC0755813D9AC8C8DE0C0405A564488F0B12E` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_barracks.txt` | 30 | `A844D8A94A4A2D4FADD862E33190CCB83B5BC107DC873DBFB993EC15A8307B5F` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_garden.txt` | 33 | `B4FDC645826AED5AF2C04267710D368DE499C86640ED906227E9C2E4F792C32F` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_gate.txt` | 26 | `166E733AB54463B67D718EE9F6516C6BAB6C8DEAAEA6140C7ECC3832EEE29108` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_grazing_land.txt` | 35 | `3201EC9E54CB120F47DDD7DAD23DBE1824CECAE582516FCBB21EA0B7EA33C8CC` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_health.txt` | 26 | `AFD4CEBBD14EFD6A336C077997C162D03B3B6AD065AB82BCAC7A4E84477C175E` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_main.txt` | 108 | `05B4B852144463318A242FCC6CE7ADA7F7271184D5A02AA9A51B8DBD81589ED2` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_market.txt` | 30 | `0B78DAAE466A0B36FC58F6027F29A2C4EF4AED7AEC17BDA96364C537FD7580DA` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_rice_field.txt` | 30 | `14AE051FFAC7DD9CE7C2C034C336137D962A78F0FFD800000AC920041C2FF8F3` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_silk.txt` | 26 | `92FC4DC9692FE0029C6D4A01619A8D52EA89921C3270C98501B23C748595781A` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_stable.txt` | 29 | `CD4BA98759833C4A1EF4915DF1E835BB56707A3C55C47C45DC4822325CE46572` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_storage.txt` | 34 | `F2FD151C632E5283EDAFA1F8B017E46C3623719628CF3BD1C424E9C23F3C14C8` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_tea.txt` | 26 | `A2FE9B02308C123FAAD9372E69E9157BFCD2C8AC88F1C9A3013ADB192C8C48CF` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_temple.txt` | 26 | `D007D7B21AC6EFFD0516E8778CFFF3E686B3E96B17747E557E341EB97872FD90` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_watchtower.txt` | 26 | `32D57AE300D324EF47BC9E5BC68B3F9D5828517A3E79241CDE22EE258CB2ED50` |
| `common\domiciles\buildings\zzz_RB_UD_east_asian_estate_workshop.txt` | 34 | `3954434FEE285A2841ED4D0DFC4CA03B0911CA008D7F3D99EECEF769EC94EE6D` |
| `common\domiciles\buildings\zzz_RB_UD_estate_barracks.txt` | 6 | `09654656CFE69DFC01A3B7D558E6F98A77CCF3E983DF7AE71B33C223464CB443` |
| `common\domiciles\buildings\zzz_RB_UD_estate_garden.txt` | 9 | `3A2DF28E3C27349E323ED4696016A5E955E0FA1CBD5685C830B92D773F742DBC` |
| `common\domiciles\buildings\zzz_RB_UD_estate_grain_field.txt` | 6 | `71361207C5F51855EAE31C1CF6EA6E4A8796C3A0B627B5C57788BE19F06B75C0` |
| `common\domiciles\buildings\zzz_RB_UD_estate_grazing_land.txt` | 15 | `90E00D0E634F2A6377FE5C1AAA0ABD3892BA0B9BBCCD6F6285D23AE5FC4C1675` |
| `common\domiciles\buildings\zzz_RB_UD_estate_guardhouse.txt` | 4 | `5EB2A1BFEC3842A71EC5671EFBD3BC629ECC263F4C49EA1131AC6B050A741F87` |
| `common\domiciles\buildings\zzz_RB_UD_estate_main.txt` | 60 | `FED87A12468BB8588197CEEB4468143A7AD7292AEA3DAFCA7D876D53DE1FB494` |
| `common\domiciles\buildings\zzz_RB_UD_estate_market.txt` | 6 | `3EC9FF7B460BD5355034B1CD810BFA0A08E6237E46598211AC4DE86FCD8CD7A6` |
| `common\domiciles\buildings\zzz_RB_UD_estate_olive.txt` | 6 | `401F283B930B6052F3C425BD3D6168A093F885074C1BD68387233B32A132CFE3` |
| `common\domiciles\buildings\zzz_RB_UD_estate_rice_field.txt` | 6 | `90238AE30F9B699158B61FEBDD2A68F1049BAC968887B9B100DE83E30CD5D9BC` |
| `common\domiciles\buildings\zzz_RB_UD_estate_silk.txt` | 6 | `A216BEE0384966647E6A3036BA2E19163A82C061CB687889EFD0A12C7553999D` |
| `common\domiciles\buildings\zzz_RB_UD_estate_stable.txt` | 12 | `7634A5DD9426346BD6320EB5C469D4B4591BA16432A9C81CEFB393A7F94F667D` |
| `common\domiciles\buildings\zzz_RB_UD_estate_storage.txt` | 6 | `8AE2245A04A11968E8BBA634945F3530799966A95612836818409B489E8C066D` |
| `common\domiciles\buildings\zzz_RB_UD_estate_tea.txt` | 6 | `6658261FAC6A80C6EC528A1B89660E81E42F20B765D3F90D4F0AE21B81FCA1BF` |
| `common\domiciles\buildings\zzz_RB_UD_estate_temple_small.txt` | 12 | `F630DDBD9BC6356B06FD5C6FABED783932040E49DAE6AA6DB94BC8CF3BC36763` |
| `common\domiciles\buildings\zzz_RB_UD_estate_vineyard.txt` | 6 | `609A42E0D500EFD20B7D3F4E8D32121A2084570CC59798CB710E2CCC43B9A642` |
| `common\domiciles\buildings\zzz_RB_UD_estate_watchtower.txt` | 6 | `5D58468A4B2E09A0108045D3EAAE4D5B8DFB16468C96C548B661691C2B4B1C92` |
| `common\domiciles\buildings\zzz_RB_UD_estate_workshop.txt` | 14 | `288223BC28DE7AD57113A61F1862239CDD527097495567675C5AC1F7A28E7165` |
| `common\domiciles\buildings\zzz_RB_UD_japanese_manor_archive.txt` | 24 | `52D6B05F3E74C56ED5ECEA2DB8A0207CBB965F98AED2F9D3870F4A743A5A42A4` |
| `common\domiciles\buildings\zzz_RB_UD_japanese_manor_armory.txt` | 24 | `23BB0064245815F889FF8240BDDC8ECF44A6F5A30FBD814F64D3EF2567CEF920` |
| `common\domiciles\buildings\zzz_RB_UD_japanese_manor_brewery.txt` | 24 | `319A5B3FF77E9346BEDF4B7BA868D80080E2E3ECDC6FBC0FEEF137156F2CAD14` |
| `common\domiciles\buildings\zzz_RB_UD_japanese_manor_fields.txt` | 24 | `DD47033C03BBFC8EA8E98EF2B1166A5F723135F152B2622093AD97824715C41E` |
| `common\domiciles\buildings\zzz_RB_UD_japanese_manor_garden.txt` | 24 | `427ED1387FE7C97960A6607AC37FCB048A69FBD1D6215408BD6CEAC39735EAB7` |
| `common\domiciles\buildings\zzz_RB_UD_japanese_manor_horse_pastures.txt` | 24 | `3489673898E16272E05515FBA8E44B528CB24FE1537BDC5214F57AE75A6F2053` |
| `common\domiciles\buildings\zzz_RB_UD_japanese_manor_main.txt` | 59 | `5AA5D23A09752BE53BCD338ED6391C4F64A7E5F35D1C6BC4486E8E96AF95932F` |
| `common\domiciles\buildings\zzz_RB_UD_japanese_manor_shrine.txt` | 24 | `B563CA0F103EF9FED8C5210ECA069E628DBB97CD16154166002A9F0255074355` |
| `common\domiciles\buildings\zzz_RB_UD_japanese_manor_stables.txt` | 24 | `F6E8CA4B53F33118A0C416C1FBE77D6628567C9B9F92EAC181B05BDBDDDC12CF` |
| `common\domiciles\buildings\zzz_RB_UD_japanese_manor_tea_house.txt` | 24 | `2B5BB1A625AA37A4D04F600D287277C8D382EC0AFAFF40A22F02723CDA045B4B` |
| `common\domiciles\buildings\zzz_RB_UD_japanese_manor_tea_plantation.txt` | 24 | `63755143C68C552471726DAB6291C433E54E23C9B87EFC40DF80901BF1B26761` |
| `common\domiciles\buildings\zzz_RB_UD_japanese_manor_watch_house.txt` | 24 | `E18C3A4B7EA0D8601F458C5A58B7BA2F0B46D1E0FA7F7CFC3633B3BBBCE20607` |
| `common\domiciles\buildings\zzz_RB_UD_japanese_manor_workshop.txt` | 24 | `0DD780176D7B8D0437BB5759CA0FE13C08188B97C95FFF329B4A039F291EF869` |
| `common\domiciles\buildings\zzz_RB_UD_yurt_character_warfare.txt` | 36 | `AF58198BE43502312E2A8888DC267685955662CA9656FE41AEC4BF6E52EDAECC` |
| `common\domiciles\buildings\zzz_RB_UD_yurt_court.txt` | 54 | `A6C8E8625DB7E4FCF910F4B622CA4F0891B1DE67B96ED8957CF163504A1ECFFD` |
| `common\domiciles\buildings\zzz_RB_UD_yurt_family.txt` | 54 | `6AE9D4A924D997C8D713F97E0ED665F1C6AD323A268CFE3F50F47913D823C032` |
| `common\domiciles\buildings\zzz_RB_UD_yurt_herd_welfare.txt` | 60 | `4AC5793690699CBB1428D02B7DD63AFABF1820B2BFA0F60C0C7A1F9FF06ECAB6` |
| `common\domiciles\buildings\zzz_RB_UD_yurt_main.txt` | 96 | `F691ED831BC1D7A27EC6EEA68068A85277484FC37096977B8A4AF189D8407663` |
| `common\domiciles\buildings\zzz_RB_UD_yurt_mass_warfare.txt` | 42 | `608CC51E092A2B5AD53D7226F6C7728C47E4CA3FC3C252014244B5FB9F41CCF1` |
| `common\domiciles\buildings\zzz_RB_UD_yurt_mystical.txt` | 48 | `C13E180356A0741C40CFB8C1701B14B46B283E6D353AC40D4A9FA2F0855402B2` |
| `common\domiciles\buildings\zzz_RB_UD_yurt_trade.txt` | 48 | `7B00FC57DC6B3C852EAD4B78E85F2E135F6CDDE71D528FE38E039B0DEAD434B1` |
| `common\domiciles\types\zzz_RB_UD_domicile_types.txt` | 5 | `B9A2ACF8C7C600EC77CE46AABB8EB79C9F37006FCBB449E2048B0C5B26AD83A6` |
| `common\scripted_effects\zzz_RB_UD_domicile_effects.txt` | 5 | `C19D178F7B4E89C0B1A95C3A16A1D4A59E3952414D86AC27F2913F384CC7BBCC` |

## Required manual check

The five domicile windows must be opened in game. Slot positions are deliberately stored in `tools/RB_UD_layouts.json`, so visual adjustments do not require changing the generator.
