param(
    [Parameter(Mandatory = $false)]
    [string]$DistRoot = "dist/FieldTechCopilot"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$LockPath = Join-Path $PSScriptRoot "bundle-lock.json"
$Lock = Get-Content $LockPath -Raw | ConvertFrom-Json
$DistPath = Join-Path $RepoRoot $DistRoot
$DownloadPath = Join-Path $RepoRoot "build/windows-downloads"

New-Item -ItemType Directory -Force -Path $DistPath, $DownloadPath | Out-Null

function Get-VerifiedFile {
    param(
        [string]$Url,
        [string]$Destination,
        [string]$Sha256,
        [long]$Size
    )

    if (Test-Path $Destination) {
        $ExistingHash = (Get-FileHash $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
        $ExistingSize = (Get-Item $Destination).Length
        if ($ExistingHash -eq $Sha256 -and $ExistingSize -eq $Size) {
            Write-Host "Using verified cached file: $Destination"
            return
        }
        Remove-Item -Force $Destination
    }

    Write-Host "Downloading $Url"
    & curl.exe --fail --location --retry 4 --retry-delay 5 --output $Destination $Url
    if ($LASTEXITCODE -ne 0) {
        throw "Download failed: $Url"
    }
    $ActualHash = (Get-FileHash $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
    $ActualSize = (Get-Item $Destination).Length
    if ($ActualHash -ne $Sha256 -or $ActualSize -ne $Size) {
        throw "Integrity check failed for $Destination"
    }
}

$RuntimeZip = Join-Path $DownloadPath $Lock.llamaCpp.asset
Get-VerifiedFile `
    -Url $Lock.llamaCpp.url `
    -Destination $RuntimeZip `
    -Sha256 $Lock.llamaCpp.sha256 `
    -Size $Lock.llamaCpp.size

$RuntimePath = Join-Path $DistPath "runtime"
if (Test-Path $RuntimePath) {
    Remove-Item -Recurse -Force $RuntimePath
}
Expand-Archive -Path $RuntimeZip -DestinationPath $RuntimePath

$ModelPath = Join-Path $DistPath "models"
New-Item -ItemType Directory -Force -Path $ModelPath | Out-Null
$ModelFile = Join-Path $ModelPath $Lock.model.name
Get-VerifiedFile `
    -Url $Lock.model.url `
    -Destination $ModelFile `
    -Sha256 $Lock.model.sha256 `
    -Size $Lock.model.size

$VsWherePath = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $VsWherePath)) {
    throw "Visual Studio vswhere.exe is required to collect the app-local MSVC runtime"
}
$VisualStudioPath = & $VsWherePath `
    -latest `
    -products * `
    -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
    -property installationPath
if (-not $VisualStudioPath) {
    throw "Visual Studio with the x64 C++ tools is required to build Field Kit Lite"
}
$RedistRoot = Join-Path $VisualStudioPath "VC\Redist\MSVC"
$AppLocalCrtPath = Get-ChildItem $RedistRoot -Directory |
    Sort-Object Name -Descending |
    ForEach-Object {
        Get-ChildItem (Join-Path $_.FullName "x64") `
            -Directory `
            -Filter "Microsoft.VC*.CRT" `
            -ErrorAction SilentlyContinue
    } |
    Select-Object -First 1
if (-not $AppLocalCrtPath) {
    throw "The Visual Studio app-local x64 MSVC runtime directory was not found"
}
$RuntimeVersionFile = Get-Item (Join-Path $AppLocalCrtPath.FullName "msvcp140.dll")
$RuntimeVersion = [version]$RuntimeVersionFile.VersionInfo.FileVersion
$MinimumRuntimeVersion = [version]$Lock.visualCppRuntime.minimumVersion
if ($RuntimeVersion -lt $MinimumRuntimeVersion) {
    throw "MSVC runtime $RuntimeVersion is older than required $MinimumRuntimeVersion"
}
$AppLocalRuntimeFiles = @()
Get-ChildItem $AppLocalCrtPath.FullName -File -Filter "*.dll" | ForEach-Object {
    $Destination = Join-Path $RuntimePath $_.Name
    Copy-Item $_.FullName $Destination
    $AppLocalRuntimeFiles += [ordered]@{
        name = $_.Name
        version = $_.VersionInfo.FileVersion
        sha256 = (Get-FileHash $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
        size = [long]$_.Length
    }
}

$KnowledgePath = Join-Path $DistPath "knowledge"
if (Test-Path $KnowledgePath) {
    Remove-Item -Recurse -Force $KnowledgePath
}
Copy-Item -Recurse (Join-Path $RepoRoot "examples/knowledge") $KnowledgePath

$LicensesPath = Join-Path $DistPath "licenses"
New-Item -ItemType Directory -Force -Path $LicensesPath | Out-Null
Invoke-WebRequest -UseBasicParsing -Uri $Lock.llamaCpp.licenseUrl -OutFile (Join-Path $LicensesPath "llama.cpp-MIT.txt")
Invoke-WebRequest -UseBasicParsing -Uri $Lock.model.licenseUrl -OutFile (Join-Path $LicensesPath "Qwen3-Apache-2.0.txt")
Copy-Item (Join-Path $RuntimePath "LICENSE-LLVM-OpenMP") (Join-Path $LicensesPath "LLVM-OpenMP.txt")
Copy-Item (Join-Path $RepoRoot "THIRD_PARTY_NOTICES.md") (Join-Path $DistPath "THIRD_PARTY_NOTICES.md")
Copy-Item (Join-Path $RepoRoot "LICENSE") (Join-Path $DistPath "LICENSE.txt")

$Manifest = [ordered]@{
    schemaVersion = 1
    bundle = "Field Kit Lite"
    generatedAt = (Get-Date).ToUniversalTime().ToString("o")
    model = [ordered]@{
        name = $Lock.model.name
        repository = $Lock.model.repository
        commit = $Lock.model.commit
        sha256 = $Lock.model.sha256
        size = [long]$Lock.model.size
        modified = $false
    }
    runtime = [ordered]@{
        name = "llama.cpp"
        tag = $Lock.llamaCpp.tag
        asset = $Lock.llamaCpp.asset
        sha256 = $Lock.llamaCpp.sha256
    }
    appLocalVisualCppRuntime = [ordered]@{
        deployment = $Lock.visualCppRuntime.deployment
        version = $RuntimeVersion.ToString()
        files = $AppLocalRuntimeFiles
    }
    knowledgePackVersion = 1
}
$Manifest | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $DistPath "bundle-manifest.json")

Write-Host "Prepared verified offline bundle at $DistPath"
