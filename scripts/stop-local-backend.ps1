param(
    [int]$Port = 8000
)

$ErrorActionPreference = "SilentlyContinue"

$ids = @()

$ids += Get-NetTCPConnection -LocalPort $Port -State Listen |
    Select-Object -ExpandProperty OwningProcess

$ids += Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -like "python*" -and
        $_.CommandLine -match "uvicorn" -and
        $_.CommandLine -match "backend\.main:app"
    } |
    Select-Object -ExpandProperty ProcessId

$ids = $ids |
    Where-Object { $_ -and $_ -ne 0 -and $_ -ne $PID } |
    Sort-Object -Unique

foreach ($id in $ids) {
    Write-Host " [INFO] Stopping backend process tree on port $Port (PID $id)..."
    & taskkill.exe /PID $id /T /F | Out-Null
}

Start-Sleep -Seconds 2

$remaining = Get-NetTCPConnection -LocalPort $Port -State Listen |
    Select-Object -ExpandProperty OwningProcess -Unique

if ($remaining) {
    Write-Host " [WARN] Port $Port still has listener PID(s): $($remaining -join ', ')"
    exit 1
}

Write-Host " [OK] No backend listener remains on port $Port."
