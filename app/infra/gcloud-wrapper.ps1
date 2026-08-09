param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $GcloudArgs
)

& gcloud @GcloudArgs
exit $LASTEXITCODE
