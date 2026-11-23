<#
.SYNOPSIS
  Measures RAM use and generation speed of the local Qwen3 models (Phase 1, task 1.1.6).

.DESCRIPTION
  For each model it records: RAM in use before loading, after loading (while generating),
  and after unloading, plus the Ollama-reported model size and tokens/second.
  Procedure and interpretation: docs/setup_guide.md section 3.4 and docs/architecture.md section 10.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File backend\scripts\measure_llm_memory.ps1
#>
param(
    [string[]]$Models = @('qwen3:0.6b', 'qwen3:1.7b'),
    [string]$OllamaUrl = 'http://localhost:11434',
    [int]$NumCtx = 2048
)

$ErrorActionPreference = 'Stop'

function Get-InUseGB {
    $os = Get-CimInstance Win32_OperatingSystem
    [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB, 2)
}

function Get-TotalGB {
    [math]::Round((Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize / 1MB, 2)
}

function Get-OllamaRamMB {
    $sum = (Get-Process ollama* -ErrorAction SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum
    [math]::Round($sum / 1MB)
}

# A realistic prompt: similar in size to a news-summary request.
$prompt = @'
Summarize the following headline for an investor in one neutral sentence.
Headline: "Company reports higher quarterly revenue but lower profit margins due to rising input costs."
'@

$results = @()
Write-Host ("Total RAM: {0} GB" -f (Get-TotalGB))

foreach ($model in $Models) {
    Write-Host "`n=== $model ==="
    & ollama stop $model 2>$null | Out-Null
    Start-Sleep -Seconds 5
    $before = Get-InUseGB

    $body = @{
        model    = $model
        messages = @(@{ role = 'user'; content = $prompt })
        stream   = $false
        think    = $false
        options  = @{ num_ctx = $NumCtx; temperature = 0; num_predict = 120 }
    } | ConvertTo-Json -Depth 5

    $r = Invoke-RestMethod -Uri "$OllamaUrl/api/chat" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 600
    $loaded = Get-InUseGB
    $ollamaMB = Get-OllamaRamMB
    $ps = (Invoke-RestMethod "$OllamaUrl/api/ps").models | Where-Object { $_.name -eq $model }

    & ollama stop $model | Out-Null
    Start-Sleep -Seconds 10
    $after = Get-InUseGB

    $tps = if ($r.eval_duration -gt 0) { [math]::Round($r.eval_count / ($r.eval_duration / 1e9), 1) } else { $null }
    $results += [pscustomobject]@{
        Model              = $model
        InUseBefore_GB     = $before
        InUseLoaded_GB     = $loaded
        InUseAfterUnload_GB = $after
        Delta_GB           = [math]::Round($loaded - $before, 2)
        Released_GB        = [math]::Round($loaded - $after, 2)
        OllamaProcess_MB   = $ollamaMB
        ModelSize_MB       = if ($ps) { [math]::Round($ps.size / 1MB) } else { $null }
        LoadTime_s         = [math]::Round($r.load_duration / 1e9, 1)
        TokensPerSec       = $tps
        Reply              = $r.message.content.Trim()
    }
}

Write-Host "`n=== Results ==="
$results | Format-List
