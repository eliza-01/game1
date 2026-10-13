@echo off
setlocal EnableExtensions

rem ============================================================
rem game1 diagnostic project dump (model binaries excluded)
rem
rem source:
rem   e:\robloxprojects\game1
rem
rem excluded:
rem   .git, .venv, venv, .tools, .idea, __pycache__
rem   .env.local and common credential/secret files
rem   all model, texture, image, audio and video binaries (metadata only)
rem
rem model/place/texture/image/media binary payloads are NOT copied.
rem instead, _dump/model_files.json contains their metadata + SHA-256.
rem
rem remaining source and metadata are copied into the zip, including:
rem   .control-center database (check for private data before sharing)
rem   manifests
rem   source code
rem   patches
rem   generated text/code files
rem
rem output:
rem   next to this bat file
rem ============================================================

set "game1_dump_self=%~f0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p=$env:game1_dump_self; $raw=[IO.File]::ReadAllText($p); $m='# powershell_'+'payload_begin'; $i=$raw.IndexOf($m); if($i -lt 0){throw 'powershell payload marker not found.'}; Invoke-Expression $raw.Substring($i+$m.Length)"

set "rc=%ERRORLEVEL%"
set "game1_dump_self="

echo.
if not "%rc%"=="0" (
    echo dump failed with exit code %rc%.
) else (
    echo dump completed.
)
echo.
echo press any key to close.
pause >nul
exit /b %rc%

# powershell_payload_begin

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$source = 'E:\RobloxProjects\game1'

$scriptPath = $env:game1_dump_self
if ([string]::IsNullOrWhiteSpace($scriptPath)) {
    throw 'cannot determine bat path.'
}

$batDir = Split-Path -Parent $scriptPath
$stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$finalZip = Join-Path $batDir ("game1_diag_{0}.zip" -f $stamp)

$runId = [guid]::NewGuid().ToString('N')
$stageRoot = Join-Path ([IO.Path]::GetTempPath()) ("game1_diag_dump_{0}" -f $runId)
$stageProject = Join-Path $stageRoot 'game1'
$tempZip = Join-Path $stageRoot 'game1_diag.zip'

$skipDirNames = @('.git', '.venv', 'venv', '.tools', '.idea', '__pycache__', 'node_modules', '.pytest_cache')
$skipFileNames = @('.git', '.env.local', '.env', '.env.production', '.env.development', 'credentials.json', 'secrets.json', 'token.json', 'desktop.ini')

# Heavy model/texture/media payloads are intentionally omitted from the dump.
# Their metadata and SHA-256 hashes are written to _dump/model_files.json.
$modelExtensions = @(
    '.fbx', '.obj', '.dae', '.gltf', '.glb', '.blend',
    '.3ds', '.max', '.ma', '.mb', '.abc',
    '.usd', '.usda', '.usdc', '.usdz', '.stl', '.ply',
    '.rbxm', '.rbxmx', '.rbxl', '.rbxlx',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tif', '.tiff', '.tga',
    '.webp', '.svg', '.ico', '.avif', '.dds', '.ktx', '.exr', '.hdr',
    '.mp4', '.webm', '.mov', '.avi', '.mkv', '.mp3', '.wav', '.ogg', '.flac'
)

function get-model-kind([string]$extension) {
    switch ($extension.ToLowerInvariant()) {
        '.rbxl'  { return 'roblox_place' }
        '.rbxlx' { return 'roblox_place' }
        '.rbxm'  { return 'roblox_model' }
        { $_ -in @('.png','.jpg','.jpeg','.gif','.bmp','.tif','.tiff','.tga','.webp','.svg','.ico','.avif','.dds','.ktx','.exr','.hdr') } { return 'texture_or_image' }
        { $_ -in @('.mp4','.webm','.mov','.avi','.mkv','.mp3','.wav','.ogg','.flac') } { return 'media' }
        '.rbxmx' { return 'roblox_model' }
        default  { return '3d_source' }
    }
}

function write-log([string]$message) {
    Write-Host ('[{0}] {1}' -f (Get-Date -Format 'HH:mm:ss'), $message)
}

function format-bytes([long]$bytes) {
    if ($bytes -ge 1GB) { return ('{0:N2} gb' -f ($bytes / 1GB)) }
    if ($bytes -ge 1MB) { return ('{0:N2} mb' -f ($bytes / 1MB)) }
    if ($bytes -ge 1KB) { return ('{0:N2} kb' -f ($bytes / 1KB)) }
    return ('{0} b' -f $bytes)
}

function get-open-file-sha256([string]$sourcePath) {
    $sourceStream = $null
    $sha = $null

    try {
        $share = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete

        $sourceStream = [IO.File]::Open(
            $sourcePath,
            [IO.FileMode]::Open,
            [IO.FileAccess]::Read,
            $share
        )

        $sha = [System.Security.Cryptography.SHA256]::Create()
        $hashBytes = $sha.ComputeHash($sourceStream)
        return ([BitConverter]::ToString($hashBytes)).Replace('-', '').ToLowerInvariant()
    }
    finally {
        if ($null -ne $sha) {
            $sha.Dispose()
        }

        if ($null -ne $sourceStream) {
            $sourceStream.Dispose()
        }
    }
}

function copy-open-file([string]$sourcePath, [string]$destinationPath) {
    $sourceStream = $null
    $destinationStream = $null

    try {
        $share = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete

        $sourceStream = [IO.File]::Open(
            $sourcePath,
            [IO.FileMode]::Open,
            [IO.FileAccess]::Read,
            $share
        )

        $destinationStream = [IO.File]::Open(
            $destinationPath,
            [IO.FileMode]::Create,
            [IO.FileAccess]::Write,
            [IO.FileShare]::None
        )

        $sourceStream.CopyTo($destinationStream)
    }
    finally {
        if ($null -ne $destinationStream) {
            $destinationStream.Dispose()
        }

        if ($null -ne $sourceStream) {
            $sourceStream.Dispose()
        }
    }
}

try {
    $sourceFull = [IO.Path]::GetFullPath($source).TrimEnd('\')

    if (-not (Test-Path -LiteralPath $sourceFull -PathType Container)) {
        throw "source folder not found: $sourceFull"
    }

    $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if ($null -eq $tar) {
        throw 'windows tar.exe was not found.'
    }

    if (Test-Path -LiteralPath $finalZip) {
        throw "output already exists: $finalZip"
    }

    write-log 'game1 diagnostic dump (model binaries excluded)'
    write-log ("source: {0}" -f $sourceFull)
    write-log ("output: {0}" -f $finalZip)
    write-log 'excluding directories: .git, .venv, venv'
    write-log 'model/place binaries are excluded; metadata + SHA-256 are written to _dump/model_files.json.'
    write-log 'secrets files and media payloads are excluded; database metadata can still contain private information.'

    New-Item -ItemType Directory -Force -Path $stageProject | Out-Null

    $pending = New-Object 'System.Collections.Generic.Stack[string]'
    $visited = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)

    $pending.Push($sourceFull)

    [long]$fileCount = 0
    [long]$byteCount = 0
    [long]$directoryCount = 0
    [long]$skippedDirectoryCount = 0
    [long]$skippedReparseCount = 0
    [long]$excludedModelCount = 0
    [long]$excludedModelBytes = 0
    $modelInventory = New-Object 'System.Collections.Generic.List[object]'

    while ($pending.Count -gt 0) {
        $current = $pending.Pop()

        if (-not $visited.Add($current)) {
            continue
        }

        $directoryCount++

        foreach ($entry in [IO.Directory]::EnumerateFileSystemEntries($current)) {
            $attributes = [IO.File]::GetAttributes($entry)
            $isDirectory = (($attributes -band [IO.FileAttributes]::Directory) -ne 0)
            $isReparse = (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)

            if ($isReparse) {
                $skippedReparseCount++
                write-log ("skip reparse point: {0}" -f $entry)
                continue
            }

            if ($isDirectory) {
                $name = [IO.Path]::GetFileName($entry)

                if ($skipDirNames -contains $name) {
                    $skippedDirectoryCount++
                    write-log ("skip directory: {0}" -f $entry)
                    continue
                }

                $pending.Push($entry)
                continue
            }

            $fileName = [IO.Path]::GetFileName($entry)
            if ($skipFileNames -contains $fileName) {
                continue
            }

            $relative = $entry.Substring($sourceFull.Length).TrimStart('\')
            $extension = [IO.Path]::GetExtension($entry).ToLowerInvariant()
            $info = Get-Item -LiteralPath $entry -Force

            if ($modelExtensions -contains $extension) {
                $hash = $null

                try {
                    $hash = get-open-file-sha256 $entry
                }
                catch {
                    $hash = '<hash-failed: {0}>' -f $_.Exception.Message
                }

                $modelInventory.Add([pscustomobject]@{
                    path = $relative.Replace('\', '/')
                    kind = get-model-kind $extension
                    extension = $extension
                    size_bytes = [long]$info.Length
                    modified_utc = $info.LastWriteTimeUtc.ToString('o')
                    sha256 = $hash
                })

                $excludedModelCount++
                $excludedModelBytes += [long]$info.Length
                continue
            }

            $destination = Join-Path $stageProject $relative
            $destinationDir = Split-Path -Parent $destination

            if (-not (Test-Path -LiteralPath $destinationDir)) {
                New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
            }

            try {
                copy-open-file $entry $destination
            }
            catch {
                throw ("cannot copy file: {0}`r`n{1}" -f $entry, $_.Exception.Message)
            }

            try {
                (Get-Item -LiteralPath $destination -Force).LastWriteTimeUtc = $info.LastWriteTimeUtc
            }
            catch {
                # timestamp preservation is best effort only
            }

            $fileCount++
            $byteCount += [long]$info.Length

            if (($fileCount -eq 1) -or (($fileCount % 250) -eq 0)) {
                write-log ("copied {0} files · {1}" -f $fileCount, (format-bytes $byteCount))
            }
        }
    }

    $dumpInfoDir = Join-Path $stageProject '_dump'
    New-Item -ItemType Directory -Force -Path $dumpInfoDir | Out-Null

    $inventoryPath = Join-Path $dumpInfoDir 'model_files.json'
    $inventoryDocument = [ordered]@{
        schema = 1
        generated_utc = (Get-Date).ToUniversalTime().ToString('o')
        source_root = $sourceFull
        note = 'Model/place binary payloads are intentionally excluded from this dump. Registry/database/manifests remain in the archive.'
        excluded_extensions = $modelExtensions
        file_count = $excludedModelCount
        total_bytes = $excludedModelBytes
        files = @($modelInventory | Sort-Object path)
    }

    [IO.File]::WriteAllText(
        $inventoryPath,
        ($inventoryDocument | ConvertTo-Json -Depth 8),
        ([System.Text.UTF8Encoding]::new($false))
    )

    $readmePath = Join-Path $dumpInfoDir 'README.txt'
    $readme = @(
        'game1 diagnostic dump',
        '',
        '3D models, textures, images, audio and video files were intentionally not copied into this archive.',
        'See model_files.json for path, type, byte size, modified time, and SHA-256 of every omitted file.',
        'Project database, manifests, source code and settings remain; model, image, texture and media payloads are excluded.',
        '',
        ('Excluded model/place files: {0}' -f $excludedModelCount),
        ('Excluded payload size: {0}' -f (format-bytes $excludedModelBytes))
    ) -join "`r`n"

    [IO.File]::WriteAllText(
        $readmePath,
        $readme,
        ([System.Text.UTF8Encoding]::new($false))
    )

    write-log ("staging complete: {0} copied files · {1}" -f $fileCount, (format-bytes $byteCount))
    write-log ("model/texture/media payloads excluded: {0} files · {1}" -f $excludedModelCount, (format-bytes $excludedModelBytes))
    write-log ("model inventory: {0}" -f $inventoryPath)
    write-log ("directories scanned: {0}" -f $directoryCount)
    write-log ("excluded directories: {0}" -f $skippedDirectoryCount)

    if ($skippedReparseCount -gt 0) {
        write-log ("reparse points skipped for recursion safety: {0}" -f $skippedReparseCount)
    }

    write-log 'creating zip...'

    & $tar.Source -a -c -f $tempZip -C $stageRoot 'game1'

    if ($LASTEXITCODE -ne 0) {
        throw "tar.exe failed with exit code $LASTEXITCODE"
    }

    if (-not (Test-Path -LiteralPath $tempZip -PathType Leaf)) {
        throw 'zip was not created.'
    }

    Move-Item -LiteralPath $tempZip -Destination $finalZip -Force

    $zipSize = (Get-Item -LiteralPath $finalZip -Force).Length

    write-log ("done: {0}" -f $finalZip)
    write-log ("zip size: {0}" -f (format-bytes $zipSize))
    write-log ("project files archived: {0}" -f $fileCount)
    write-log ("model/place files represented by metadata only: {0}" -f $excludedModelCount)
}
finally {
    if (Test-Path -LiteralPath $stageRoot) {
        Remove-Item -LiteralPath $stageRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
