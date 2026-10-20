# Reviewable Windows current-user sign-in task. Default is preview, not install.
param([switch]$Install)
$ErrorActionPreference = 'Stop'
$name = 'SmartSignalHub-WSL'
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute "$env:WINDIR\System32\wsl.exe" -Argument '-d Ubuntu -u sandro --exec /home/sandro/SmartSignalHub/platform_v2/deployment/deploy/wsl-session.sh'
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Start Ubuntu and the supervised SmartSignalHub service after Windows sign-in; retain one WSL session.'
if (-not $Install) {
    [pscustomobject]@{Name=$name;User=$user;Action=$action.Execute;Arguments=$action.Arguments;Mode='PREVIEW_ONLY'} | ConvertTo-Json
    exit 0
}
if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
    throw 'Task already exists. Review it explicitly instead of overwriting.'
}
Register-ScheduledTask -TaskName $name -InputObject $task | Select-Object TaskName,State
