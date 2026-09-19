$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$patch = Join-Path $repo 'AGOT_Submods/AGOT_PLUS_FIX'
$previous = Join-Path $PSScriptRoot '../ck3-agot-plus-fix-stage4-log-2026-09-18'
$runStart = [DateTimeOffset]'2026-09-19T03:45:41+07:00'
$roots = @{
    AGOT_PLUS = 'E:/SteamLibrary/steamapps/workshop/content/1158310/2950245430'
    AGOT = 'E:/SteamLibrary/steamapps/workshop/content/1158310/2962333032'
}
$baseline = Get-Content -LiteralPath (Join-Path $patch 'docs/source-baseline.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$records = @(foreach ($entry in $baseline) {
    $path = Join-Path $roots[$entry.Catalog] $entry.File
    $info = Get-Item -LiteralPath $path
    [pscustomobject]@{
        Catalog=$entry.Catalog; File=$entry.File; SHA256=(Get-FileHash -LiteralPath $path).Hash
        ExpectedSHA256=$entry.SHA256; LastWriteTime=$info.LastWriteTime.ToString('o')
    }
})
if (@($records | Where-Object {$_.SHA256 -cne $_.ExpectedSHA256}).Count) { throw 'Source changed since static verification' }
if (@($records | Where-Object {[DateTimeOffset]$_.LastWriteTime -ge $runStart}).Count) { throw 'Source changed after launch' }
$records | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'source-hash-verification.csv') -Encoding UTF8 -NoTypeInformation

$dependencies = @(foreach ($stage in @(5,6)) {
    $result = Get-Content -LiteralPath (Join-Path $PSScriptRoot "snapshot/stage$stage-static-validation.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    $items = if ($stage -eq 5) {$result.NativeDependencies} else {$result.Dependencies}
    foreach ($entry in $items) {
        $path = Join-Path $entry.Provider $entry.File
        $info = Get-Item -LiteralPath $path
        $hash = (Get-FileHash -LiteralPath $path).Hash
        if ($hash -cne $entry.SHA256 -or [DateTimeOffset]$info.LastWriteTime -ge $runStart) { throw "Dependency changed: $path" }
        [pscustomobject]@{Stage=$stage;File=$entry.File;Provider=$entry.Provider;SHA256=$hash;LastWriteTime=$info.LastWriteTime.ToString('o')}
    }
})
$dependencies | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'dependency-hash-verification.csv') -Encoding UTF8 -NoTypeInformation

$runtime = @(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'runtime-files.csv'))
if (@($runtime | Where-Object {[DateTimeOffset]$_.LastWriteTime -ge $runStart}).Count) { throw 'Runtime files changed after launch' }
$duplicateSources = Get-Content -LiteralPath (Join-Path $previous 'duplicate-event-source-evidence.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$duplicateEvidence = @(foreach ($entry in $duplicateSources) {
    $info = Get-Item -LiteralPath $entry.Path
    $hash = (Get-FileHash -LiteralPath $entry.Path).Hash
    if ($hash -cne $entry.SHA256) { throw 'Known duplicate event source changed' }
    $text = Get-Content -LiteralPath $entry.Path -Raw -Encoding UTF8
    if (-not [regex]::IsMatch($text,'(?m)^agot_activity_commission_crown\.0001\s*=\s*\{')) { throw 'Missing duplicate definition' }
    [pscustomobject]@{Mod=$entry.Mod;Path=$entry.Path;LastWriteTime=$info.LastWriteTime.ToString('o');SHA256=$hash;MatchesPreviousSnapshot=$true}
})
$duplicateEvidence | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'duplicate-event-source-evidence.json') -Encoding UTF8

$rows = @(Import-Csv -LiteralPath (Join-Path $PSScriptRoot 'agot-plus-remaining.csv') | Where-Object Evidence -notmatch 'gfx/portraits/')
$rows | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'agot-plus-without-portraits.csv') -Encoding UTF8 -NoTypeInformation
$counts = @($rows | Group-Object IssueClass | Sort-Object Name | ForEach-Object {[pscustomobject]@{IssueClass=$_.Name;Messages=$_.Count}})
$counts | Export-Csv -LiteralPath (Join-Path $PSScriptRoot 'agot-plus-without-portraits-classes.csv') -Encoding UTF8 -NoTypeInformation
$comparison = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'comparison-summary.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($comparison.Targets -ne 151 -or $comparison.TargetsRemaining -ne 0 -or $comparison.TargetsMissingFromBaseline -ne 0 -or $comparison.UnreviewedAddedOccurrences -ne 0) { throw 'Unexpected comparison outcome' }
if (-not $comparison.SameActiveModsAndOrder) { throw 'Mod set changed' }
$capture = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'snapshot-summary.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'snapshot/patch-source-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.Revision -ne 6) { throw 'Unexpected tested revision' }
$errorLog = $capture.Logs | Where-Object File -eq 'error.log'
$snapshotHash = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'snapshot/error.log')).Hash
if ($snapshotHash -cne $errorLog.SHA256) { throw 'Snapshot hash changed' }
$summary = [ordered]@{
    Revision=6; Status='PASS'; EngineStartupChecked=$true; FreshLogChecked=$true
    GameplayAutoBondingChecked=$false; GameplayArtifactCreationChecked=$false
    RunStartedAt=$runStart.ToString('o'); LastErrorEntry='2026-09-19T03:48:32+07:00'
    Scope='Startup diagnostics only; no gameplay bonding, artifact creation, ownership or notification behavior verified.'
    ManifestSHA256=$capture.PatchManifestSHA256; ErrorLogSHA256=$errorLog.SHA256
    SourceHashesMatched=$records.Count; NativeDependencyRecordsMatched=$dependencies.Count
    RuntimeFilesMatched=$runtime.Count; RuntimeFilesPredateLaunch=$true; SameActiveModsAndOrder=$true
    Stage5TargetMessagesAbsent=102; Stage6TargetMessagesAbsent=49
    EarlierStageTargetsRemaining=@($comparison.Stage1TargetsRemaining,$comparison.Stage2TargetsRemaining,$comparison.Stage3TargetsRemaining,$comparison.Stage4TargetsRemaining)
    LocalizationTargetsRemaining=$comparison.LocalizationTargetsRemaining
    RawAddedOccurrences=$comparison.AddedOccurrences; RawRemovedOccurrences=$comparison.RemovedOccurrences
    ReviewedExistingDuplicateVariations=$comparison.ReviewedExistingDuplicateVariations
    NewFunctionalDiagnosticOccurrences=$comparison.UnreviewedAddedOccurrences
    AGOTPlusMessagesWithoutPortraitFiles=$rows.Count; RemainingClasses=$counts
    Report='../../../docs/reports/ck3-agot-plus-fix-stage6-log-2026-09-19/README.md'
}
$summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'startup-validation.json') -Encoding UTF8
$summary | ConvertTo-Json -Depth 5
