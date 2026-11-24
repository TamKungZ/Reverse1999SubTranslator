param(
    [Parameter(Mandatory)][string]$Version,
    [string]$Path = "CHANGELOG.md"
)

$ErrorActionPreference = "Stop"
$text = Get-Content -Raw -Encoding UTF8 -LiteralPath $Path
$pattern = "(?ms)^## \[" + [regex]::Escape($Version) + "\][^\r\n]*\r?\n(?<body>.*?)(?=^## \[|\z)"
$match = [regex]::Match($text, $pattern)
$body = if ($match.Success) { $match.Groups["body"].Value.Trim() } else { "" }
if (-not $body) { throw "$Path has no notes for version $Version" }
$body
