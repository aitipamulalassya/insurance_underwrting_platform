
$ApiUrl = "http://127.0.0.1:8000/api/renewals/expire"

try {
    $Response = Invoke-RestMethod `
        -Uri $ApiUrl `
        -Method Post `
        -TimeoutSec 30

    Write-Output "Renewal expiry process completed."
    Write-Output ($Response | ConvertTo-Json -Depth 5)
}
catch {
    Write-Output "Renewal expiry process failed."
    Write-Output $_.Exception.Message
    exit 1
}
