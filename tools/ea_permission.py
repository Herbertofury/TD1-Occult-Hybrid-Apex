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
[Console]::Out.WriteLine('{"phase":"observation-started"}')
[Console]::Out.Flush()
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
                [Console]::Out.WriteLine('{"phase":"invoke-intent"}')
                [Console]::Out.Flush()
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


def _messages(output):
    if isinstance(output, bytes):
        output = output.decode('utf-8', 'replace')
    if not isinstance(output, str) or len(output) > 16384:
        return [], None
    messages, reply = [], None
    for line in output.splitlines():
        try:
            row = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(row, dict):
            messages.append(row)
            if type(row.get('ok')) is bool and type(row.get('acknowledged')) is bool:
                reply = row
    return messages, reply


def _uncertain():
    return {'ok': False, 'acknowledged': False, 'acknowledgement_unresolved': True,
            'retry_safe': False, 'windows_uac_approved': False,
            'message': 'EA consent outcome is unknown. Observe the existing launch without replay.'}


def acknowledge(work=None):
    try:
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', SCRIPT],
            capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired as error:
        # Invoke may have run before the accessibility provider stopped
        # responding. Observe game start; never replay consent through another
        # mechanism merely because the UIA observer timed out.
        messages, _reply = _messages(error.stdout)
        phases = [row.get('phase') for row in messages]
        if 'observation-started' not in phases or 'invoke-intent' in phases:
            return _uncertain()
        # subprocess.run has killed/reaped the helper. Its flushed observation
        # marker, without its mandatory pre-Invoke marker, proves no UIA input
        # was attempted. Only this certificate permits the existing fallback.
        response = {'ok': False, 'acknowledged': False, 'readonly_probe_timed_out': True,
                    'uia_invocation_attempted': False, 'windows_uac_approved': False,
                    'message': 'EA read-only UIA observation timed out before any Invoke intent.'}
    else:
        messages, response = _messages(result.stdout)
        if response is None:
            if any(row.get('phase') == 'invoke-intent' for row in messages):
                return _uncertain()
            response = {'ok': False, 'acknowledged': False, 'windows_uac_approved': False,
                        'message': 'Exact EA dialog was not acknowledged by UIA.'}
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
