# ============================================================
# pull-updated.ps1
# Launch Docling Serve CPU (official image, PyTorch CPU)
# ============================================================

Write-Host "===========================================" -ForegroundColor Cyan
Write-Host " Docling Serve CPU Launcher (PowerShell)   " -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""

# 1) Pull the latest official image
Write-Host "[1/4] Pulling latest Docling Serve CPU image..." -ForegroundColor Yellow
docker pull ghcr.io/docling-project/docling-serve-cpu:latest

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker pull failed. Check your Docker login / network." -ForegroundColor Red
    exit 1
}

Write-Host "OK: Image pull completed: ghcr.io/docling-project/docling-serve-cpu:latest" -ForegroundColor Green
Write-Host ""

# 2) Show basic image details (use single quotes to avoid interpolation issues)
Write-Host '[2/4] Inspecting image details (tag, OS/arch)...' -ForegroundColor Yellow
try {
    $imageInfo = docker inspect ghcr.io/docling-project/docling-serve-cpu:latest --format '{{.RepoTags}} {{.Os}}/{{.Architecture}} {{.Created}}'
    Write-Host ("Image info: {0}" -f $imageInfo) -ForegroundColor Green
}
catch {
    Write-Host ("Warning: Could not inspect image details: {0}" -f $_) -ForegroundColor DarkYellow
}
Write-Host ""

# 3) Function to find available port on host
function Get-AvailablePort {
    param(
        [int]$StartPort = 5001,
        [int]$MaxPort   = 5095
    )

    Write-Host ("[Info] Scanning for a free port between {0} and {1}..." -f $StartPort, $MaxPort) -ForegroundColor DarkCyan

    for ($port = $StartPort; $port -le $MaxPort; $port++) {
        try {
            $ipGlobal         = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties()
            $tcpConnInfoArray = $ipGlobal.GetActiveTcpListeners()

            if ($tcpConnInfoArray.Port -notcontains $port) {
                Write-Host ("[Info] Found free port: {0}" -f $port) -ForegroundColor DarkGreen
                return $port
            }
        }
        catch {
            Write-Host ("Error checking port {0}: {1}" -f $port, $_) -ForegroundColor Red
            return $port  # Fallback to current port
        }
    }

    Write-Host ("[Warn] No free port found in range, falling back to {0}" -f $MaxPort) -ForegroundColor DarkYellow
    return $MaxPort  # Return last port if all are taken
}

# 4) Find an available port
Write-Host "[3/4] Selecting host port for Docling Serve..." -ForegroundColor Yellow
$SelectedPort = Get-AvailablePort
Write-Host ("Using port: {0}" -f $SelectedPort) -ForegroundColor Green

# 5) Stop any existing container with the same name
Write-Host "[Info] Checking for existing 'docling-serve-cpu' container..." -ForegroundColor DarkCyan
$existing = docker ps -a --filter "name=docling-serve-cpu" --format "{{.ID}}"

if ($existing) {
    Write-Host ("[Info] Existing container found (ID: {0}). Stopping and removing..." -f $existing) -ForegroundColor DarkYellow
    docker stop docling-serve-cpu | Out-Null
    docker rm docling-serve-cpu   | Out-Null
    Write-Host "[Info] Old 'docling-serve-cpu' container removed." -ForegroundColor DarkGreen
} else {
    Write-Host "[Info] No existing 'docling-serve-cpu' container found." -ForegroundColor DarkGreen
}
Write-Host ""

# 6) Run Docling Serve CPU container with dynamic port
#    Docling Serve listens on 5001 inside the container by default
Write-Host "[4/4] Starting Docling Serve CPU container in detached mode..." -ForegroundColor Yellow
Write-Host ("Container name : {0}" -f 'docling-serve-cpu') -ForegroundColor DarkCyan
Write-Host ("Host port      : {0}" -f $SelectedPort) -ForegroundColor DarkCyan
Write-Host "Container port : 5001" -ForegroundColor DarkCyan
Write-Host ""

docker run -d `
  --platform linux/amd64 `
  -p "$SelectedPort`:5001" `
  -v "${PWD}:/app/data" `
  -e DOCLING_SERVE_MAX_SYNC_WAIT=10800 `
  --name docling-serve-cpu `
  ghcr.io/docling-project/docling-serve-cpu:latest | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to start docling-serve-cpu container." -ForegroundColor Red
    exit 1
}

Write-Host "OK: Docling Serve CPU container started successfully." -ForegroundColor Green
Write-Host ""

# 7) Show helpful URLs and summary
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host " Docling Serve is now running              " -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ("Container name : {0}" -f 'docling-serve-cpu') -ForegroundColor Green
Write-Host ("Host port      : {0}" -f $SelectedPort) -ForegroundColor Green
Write-Host ""
Write-Host ("Docling Serve API base URL : http://localhost:{0}" -f $SelectedPort) -ForegroundColor Yellow
Write-Host ("OpenAPI docs (Swagger)     : http://localhost:{0}/docs" -f $SelectedPort) -ForegroundColor Yellow
Write-Host ("Scalar docs (if enabled)   : http://localhost:{0}/scalar" -f $SelectedPort) -ForegroundColor Yellow
Write-Host ""
Write-Host "You can now run your Python GUI script to select a PDF" -ForegroundColor Cyan
Write-Host "and send it to the running Docling Serve instance." -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
