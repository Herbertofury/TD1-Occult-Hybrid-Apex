"""Acknowledge only EA's exact game-launch permission dialog via Windows UIA.

This is a product CLI feature, not screen/coordinate or keyboard automation.
Never approves Windows UAC/secure-desktop prompts or changes process integrity.
"""
import json
import subprocess


SCRIPT = r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$eaProcesses = @(Get-Process -Name EADesktop -ErrorAction SilentlyContinue)
$accepted = $false
$reason = 'Exact EA launch-permission dialog was not accessible.'
foreach ($eaProcess in $eaProcesses) {
    $condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $eaProcess.Id)
    $surfaces = [System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children, $condition)
    foreach ($surface in $surfaces) {
        $elements = $surface.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
        if ($elements.Count -gt 4096) { throw 'EA accessibility tree exceeds the consent-handler bound.' }
        $heading = $null
        foreach ($element in $elements) {
            if ($element.Current.Name -ceq 'This game requires permissions') { $heading = $element; break }
        }
        if ($null -eq $heading) { continue }
        # A sibling ancestor must contain both the exact explanatory message and
        # a single enabled OK button. Other EA errors/UAC cannot match this.
        $parent = $heading
        for ($depth = 0; $depth -lt 4; $depth++) {
            $parent = [System.Windows.Automation.TreeWalker]::ControlViewWalker.GetParent($parent)
            if ($null -eq $parent -or $parent.Current.ProcessId -ne $eaProcess.Id) { break }
            $children = $parent.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
            if ($children.Count -gt 4096) { break }
            $messageMatched = $false
            $buttons = @()
            foreach ($child in $children) {
                if ($child.Current.Name -ceq 'This game requires administrative privileges. Do you want to grant access and launch the game?') { $messageMatched = $true }
                if ($child.Current.Name -ceq 'OK' -and $child.Current.IsEnabled -and $child.Current.ControlType -eq [System.Windows.Automation.ControlType]::Button) { $buttons += $child }
            }
            if ($messageMatched -and $buttons.Count -eq 1) {
                $pattern = $buttons[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
                $pattern.Invoke()
                $accepted = $true
                $reason = 'Invoked the exact EA game-launch permission OK button; game start still requires observation.'
                break
            }
        }
        if ($accepted) { break }
    }
    if ($accepted) { break }
}
@{ ok=$accepted; acknowledged=$accepted; message=$reason; windows_uac_approved=$false } | ConvertTo-Json -Compress
'''


def acknowledge(work=None):
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', SCRIPT],
        capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        response = {'ok': False, 'acknowledged': False, 'message': 'EA accessibility consent could not be invoked at this process integrity; owner acknowledgement is required.',
                    'windows_uac_approved': False}
    else:
        response = json.loads(result.stdout)
    if response.get('acknowledged') or work is None:
        return response
    import ea_native_permission
    try:
        native = ea_native_permission.acknowledge(work)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        native = {'ok': False, 'acknowledged': False, 'windows_uac_approved': False, 'message': str(error)}
    if native.get('acknowledged'):
        return native
    return dict(response, native_fallback=native)
