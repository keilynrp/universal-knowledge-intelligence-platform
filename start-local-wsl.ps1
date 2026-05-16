param(
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Mode = "start",
    [switch]$NoFrontend,
    [switch]$NoBackend,
    [switch]$NoEngine,
    [switch]$RebuildEngine
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $Root "frontend"
$LogDir = Join-Path $Root ".local-logs"
$WslDistro = "Ubuntu"
$EngineBuildDir = "/tmp/ukip-engine-build"
$EngineSource = "/mnt/d/universal-knowledge-intelligence-platform/engine"
$WslUser = "keilyn"
$PgHost = "127.0.0.1"
$EngineHost = "127.0.0.1"
$PgUrlPython = "postgresql+psycopg2://ukip:ukip_secret@${PgHost}:5432/ukip"
$PgUrlRust = "postgresql://ukip:ukip_secret@127.0.0.1:5432/ukip"
$EngineToken = "dev-secret"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Write-Step($Message) {
    Write-Host " [UKIP] $Message" -ForegroundColor Cyan
}

function Get-ListenerPid([int]$Port) {
    @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
}

function Stop-Port([int]$Port, [string]$Name) {
    $pids = Get-ListenerPid $Port
    foreach ($pidToStop in $pids) {
        if ($pidToStop -and $pidToStop -ne 0 -and $pidToStop -ne $PID) {
            Write-Step "Stopping $Name on port $Port (PID $pidToStop)"
            & taskkill.exe /PID $pidToStop /T /F | Out-Null
        }
    }
}

function Invoke-WSL([string]$Command, [int]$TimeoutSeconds = 120) {
    $job = Start-Job -ScriptBlock {
        param($cmd)
        wsl bash -lc $cmd
    } -ArgumentList $Command

    if (-not (Wait-Job $job -Timeout $TimeoutSeconds)) {
        Stop-Job $job -Force | Out-Null
        Receive-Job $job -ErrorAction SilentlyContinue | Out-Host
        Remove-Job $job -Force | Out-Null
        throw "WSL command timed out after ${TimeoutSeconds}s: $Command"
    }

    Receive-Job $job
    Remove-Job $job -Force | Out-Null
}

function Ensure-Postgres {
    $script:PgHost = "127.0.0.1"
    Write-Step "Ensuring PostgreSQL is running in WSL"
    wsl -u root bash -lc "service postgresql start" | Out-Host

    $probe = & $VenvPython -c "import psycopg2; conn=psycopg2.connect('$PgUrlRust', connect_timeout=5); conn.close(); print('ok')" 2>&1
    if ($LASTEXITCODE -ne 0) {
        $wslIp = (wsl hostname -I).Trim().Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)[0]
        if (-not $wslIp) {
            throw "PostgreSQL is not reachable from Windows at 127.0.0.1:5432, and WSL IP could not be detected. Output: $probe"
        }
        Write-Step "127.0.0.1:5432 is not forwarded; falling back to WSL IP $wslIp"
        $fallbackUrl = "postgresql://ukip:ukip_secret@${wslIp}:5432/ukip"
        $probe = & $VenvPython -c "import psycopg2; conn=psycopg2.connect('$fallbackUrl', connect_timeout=5); conn.close(); print('ok')" 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "PostgreSQL is not reachable from Windows via 127.0.0.1 or $wslIp. Output: $probe"
        }
        $script:PgHost = $wslIp
    }
    $script:PgUrlPython = "postgresql+psycopg2://ukip:ukip_secret@${script:PgHost}:5432/ukip"
    $script:EngineHost = $script:PgHost
}

function Ensure-EngineBuild {
    $exists = Invoke-WSL "test -x $EngineBuildDir/target/debug/engine && echo yes || echo no" 20
    if ($exists.Trim() -eq "yes" -and -not $RebuildEngine) {
        return
    }

    Write-Step "Preparing Rust engine build in WSL native filesystem"
    Invoke-WSL "rm -rf $EngineBuildDir && mkdir -p $EngineBuildDir && cd $EngineSource && tar --exclude=target -cf - . | tar -C $EngineBuildDir -xf -" 120 | Out-Host

    Write-Step "Building Rust engine (debug profile, lower memory than release)"
    wsl -d $WslDistro -u $WslUser -- bash -lc "cd $EngineBuildDir && CARGO_BUILD_JOBS=1 `$HOME/.cargo/bin/cargo build --jobs 1" | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Rust engine build failed in WSL."
    }
}

function Test-EngineWsl {
    $result = Invoke-WSL "ss -ltnp 2>/dev/null | grep -q ':50051 ' && echo yes || echo no" 20
    return $result.Trim() -eq "yes"
}

function Test-PostgresWsl {
    $result = Invoke-WSL "ss -ltnp 2>/dev/null | grep -q ':5432 ' && echo yes || echo no" 20
    return $result.Trim() -eq "yes"
}

function Start-Engine {
    if ($NoEngine) { return }
    if (Test-EngineWsl) {
        Write-Step "Rust engine already listening on 50051"
        return
    }

    Ensure-EngineBuild
    Write-Step "Starting Rust engine on 127.0.0.1:50051"
    Invoke-WSL "pkill -x engine || true; rm -f /tmp/ukip-engine.log; cd $EngineBuildDir; setsid -f env ENGINE_DATABASE_URL='$PgUrlRust' ENGINE_GRPC_PORT=50051 ENGINE_LOG_LEVEL=warn ENGINE_AUTH_TOKEN='$EngineToken' ENGINE_MAX_CONCURRENT_JOBS=1 RUST_LOG=warn ./target/debug/engine > /tmp/ukip-engine.log 2>&1 < /dev/null" 30 | Out-Host
    Start-Sleep -Seconds 5

    if (-not (Test-EngineWsl)) {
        $engineLog = Invoke-WSL "tail -n 80 /tmp/ukip-engine.log 2>/dev/null || true" 20
        throw "Rust engine did not open port 50051. Log:`n$engineLog"
    }
}

function Start-Backend {
    if ($NoBackend) { return }
    if (Get-ListenerPid 8000) {
        Write-Step "Backend already listening on 8000"
        return
    }

    Write-Step "Starting FastAPI backend on 127.0.0.1:8000"
    $log = Join-Path $LogDir "backend.log"
    $cmd = @"
Set-Location '$Root'
`$env:DATABASE_URL='$PgUrlPython'
`$env:ADMIN_USERNAME='superadmin'
`$env:ADMIN_PASSWORD='Eltigre811005*.*'
`$env:JWT_SECRET_KEY='CHANGE_ME_IN_PRODUCTION'
`$env:JWT_EXPIRE_MINUTES='480'
`$env:ENGINE_GRPC_URL='$($script:EngineHost):50051'
`$env:ENGINE_AUTH_TOKEN='$EngineToken'
`$env:ENGINE_GRPC_TLS='0'
`$env:ENGINE_MAX_CONCURRENT_JOBS='1'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 2>&1 | Tee-Object -FilePath '$log'
"@
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile", "-Command", $cmd -WindowStyle Hidden
    Start-Sleep -Seconds 25

    if (-not (Get-ListenerPid 8000)) {
        throw "Backend did not open port 8000. Check $log"
    }
}

function Start-Frontend {
    if ($NoFrontend) { return }
    if (Get-ListenerPid 3004) {
        Write-Step "Frontend already listening on 3004"
        return
    }

    Write-Step "Starting Next frontend on 127.0.0.1:3004 with webpack"
    $log = Join-Path $LogDir "frontend.log"
    $cmd = @"
Set-Location '$FrontendDir'
`$env:NEXT_TELEMETRY_DISABLED='1'
`$env:NODE_OPTIONS='--max-old-space-size=2048'
node node_modules/next/dist/bin/next dev -p 3004 --webpack 2>&1 | Tee-Object -FilePath '$log'
"@
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile", "-Command", $cmd -WindowStyle Hidden
    Start-Sleep -Seconds 10

    if (-not (Get-ListenerPid 3004)) {
        throw "Frontend did not open port 3004. Check $log"
    }
}

function Show-Status {
    $rows = @(
        [pscustomobject]@{ Service = "PostgreSQL WSL"; Port = 5432; Status = if (Test-PostgresWsl) { "listening" } else { "down" } }
        [pscustomobject]@{ Service = "Rust engine"; Port = 50051; Status = if (Test-EngineWsl) { "listening" } else { "down" } }
        [pscustomobject]@{ Service = "Backend"; Port = 8000; Status = if (Get-ListenerPid 8000) { "listening" } else { "down" } }
        [pscustomobject]@{ Service = "Frontend"; Port = 3004; Status = if (Get-ListenerPid 3004) { "listening" } else { "down" } }
    )
    $rows | Format-Table -AutoSize
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Missing Python virtualenv at $VenvPython"
}
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    throw "Missing frontend node_modules. Run npm install in $FrontendDir"
}

if ($Mode -in @("stop", "restart")) {
    Stop-Port 3004 "frontend"
    Stop-Port 8000 "backend"
    Write-Step "Stopping Rust engine in WSL"
    Invoke-WSL "pkill -x engine || true" 20 | Out-Null
}

if ($Mode -eq "status" -or $Mode -eq "stop") {
    Show-Status
    exit 0
}

Ensure-Postgres
Start-Engine
Start-Backend
Start-Frontend
Show-Status

Write-Host ""
Write-Host " UKIP local stack is ready:" -ForegroundColor Green
Write-Host "  Frontend: http://127.0.0.1:3004"
Write-Host "  Backend:  http://127.0.0.1:8000/docs"
Write-Host "  Engine:   $($script:EngineHost):50051"
Write-Host "  Logs:     $LogDir"
