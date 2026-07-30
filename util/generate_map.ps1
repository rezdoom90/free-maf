$scriptPath = $PSScriptRoot
$agentDir = Split-Path $scriptPath -Parent
$projectRoot = Split-Path $agentDir -Parent
$projectDir = Join-Path $agentDir "project"
$outputFile = Join-Path $projectDir "MAP.md"

if (-not (Test-Path -Path $projectDir)) {
    New-Item -ItemType Directory -Path $projectDir | Out-Null
}

$excludeList = @(
    ".git", ".idea", ".vscode", "target", "build", "out",
    "logs", "node_modules", "venv", "__pycache__"
)

"# PROJECT STRUCTURE MAP`n" | Out-File -FilePath $outputFile -Encoding utf8
"Source of Truth for LLM-agents. Reflects the actual codebase structure.`n" | Out-File -FilePath $outputFile -Encoding utf8 -Append
'```text' | Out-File -FilePath $outputFile -Encoding utf8 -Append

function Get-Tree {
    param (
        [string]$targetFolder,
        [string]$prefix = ""
    )

    $items = Get-ChildItem -Path $targetFolder -Force |
        Where-Object { $excludeList -notcontains $_.Name } |
        Sort-Object @{ Expression = { $_.PSIsContainer }; Descending = $true }, Name

    $count = $items.Count
    $i = 0

    foreach ($item in $items) {
        $i++
        $isLast = ($i -eq $count)

        # Используем безопасные ASCII-символы
        $connector = if ($isLast) { "\-- " } else { "+-- " }
        $childPrefix = if ($isLast) { "    " } else { "|   " }

        $line = $prefix + $connector + $item.Name
        $line | Out-File -FilePath $outputFile -Encoding utf8 -Append

        if ($item.PSIsContainer) {
            Get-Tree -targetFolder $item.FullName -prefix ($prefix + $childPrefix)
        }
    }
}

Get-Tree -targetFolder $projectRoot

'```' | Out-File -FilePath $outputFile -Encoding utf8 -Append