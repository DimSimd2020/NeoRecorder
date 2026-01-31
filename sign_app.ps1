# Self-sign certificate creation and signing script
# Note: Self-signed certificates will still show warnings in Windows

$signToolPath = "C:\Program Files (x86)\Windows Kits\10\App Certification Kit\signtool.exe"

# Check if certificate already exists
$existingCert = Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object { $_.Subject -like "*DimSimd*" } | Select-Object -First 1

if ($existingCert) {
    Write-Host "Using existing certificate: $($existingCert.Thumbprint)" -ForegroundColor Green
    $cert = $existingCert
} else {
    # Create self-signed certificate
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject "CN=DimSimd, O=DimSimd, C=RU" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -NotAfter (Get-Date).AddYears(5)
    
    Write-Host "Certificate created: $($cert.Thumbprint)" -ForegroundColor Green
}

# Export certificate to PFX
$pfxPassword = ConvertTo-SecureString -String "NeoRecorder2026" -Force -AsPlainText
$pfxPath = ".\DimSimd_CodeSign.pfx"

if (-not (Test-Path $pfxPath)) {
    Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $pfxPassword
    Write-Host "Certificate exported to: $pfxPath" -ForegroundColor Green
}

# Sign the EXE
Write-Host "`nSigning NeoRecorder.exe..." -ForegroundColor Cyan
& $signToolPath sign `
    /f $pfxPath `
    /p "NeoRecorder2026" `
    /t http://timestamp.digicert.com `
    /fd SHA256 `
    /v `
    "dist\NeoRecorder.exe"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ NeoRecorder.exe signed successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to sign NeoRecorder.exe" -ForegroundColor Red
}

# Sign the Setup
Write-Host "`nSigning Setup..." -ForegroundColor Cyan
& $signToolPath sign `
    /f $pfxPath `
    /p "NeoRecorder2026" `
    /t http://timestamp.digicert.com `
    /fd SHA256 `
    /v `
    "setup\NeoRecorder_Setup_v1.4.3.exe"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Setup signed successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to sign Setup" -ForegroundColor Red
}

Write-Host "`n✅ Done!" -ForegroundColor Green
Write-Host "⚠️  Note: Self-signed certificates will still show warnings in Windows." -ForegroundColor Yellow
Write-Host "For production without warnings, purchase a certificate from:" -ForegroundColor Yellow
Write-Host "  - DigiCert (~$400-600/year)" -ForegroundColor Cyan
Write-Host "  - Sectigo (~$200-300/year)" -ForegroundColor Cyan
Write-Host "  - GlobalSign (~$250-400/year)" -ForegroundColor Cyan
