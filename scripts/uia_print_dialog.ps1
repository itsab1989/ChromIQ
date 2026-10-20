# The Windows 11 print dialog (the WinUI "modern" one Windows shows for a
# Win32 app's PrintDlgEx since 24H2), read and answered by UI Automation (#205).
# It is a window of its own (ApplicationFrameWindow, hosted outside the
# app's process), so neither the app's window list nor its messages reach it.
#
#   uia_print_dialog.ps1 -Action read            -> JSON: open, title, printer, hwnd, settings
#   uia_print_dialog.ps1 -Action select -Printer "Name"
#   uia_print_dialog.ps1 -Action print | cancel
#   uia_print_dialog.ps1 -Action more            (opens "More settings")
param(
    [Parameter(Mandatory)][ValidateSet("read", "select", "print", "cancel", "more", "dump", "items")]
    [string]$Action,
    [string]$Printer = "",
    [string]$TitleLike = "*",
    [int]$WaitSeconds = 20
)
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$A = [System.Windows.Automation.AutomationElement]
$TS = [System.Windows.Automation.TreeScope]

function Find-Dialog {
    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    do {
        foreach ($w in $A::RootElement.FindAll($TS::Children, [System.Windows.Automation.Condition]::TrueCondition)) {
            if ($w.Current.ClassName -eq "ApplicationFrameWindow" -and $w.Current.Name -like $TitleLike) {
                $ps = $w.FindFirst($TS::Descendants, (New-Object System.Windows.Automation.PropertyCondition($A::AutomationIdProperty, "printerSelector")))
                if ($ps) { return $w }
            }
        }
        Start-Sleep -Milliseconds 300
    } while ((Get-Date) -lt $deadline)
    return $null
}

function By-Id($root, $id) {
    $root.FindFirst($TS::Descendants, (New-Object System.Windows.Automation.PropertyCondition($A::AutomationIdProperty, $id)))
}

function Selected($combo) {
    try { $sel = $combo.GetCurrentPattern([System.Windows.Automation.SelectionPattern]::Pattern).Current.GetSelection()
          if ($sel.Count -gt 0) { return $sel[0].Current.Name } } catch {}
    $item = $combo.FindFirst($TS::Children, (New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, [System.Windows.Automation.ControlType]::ListItem)))
    if ($item) { return $item.Current.Name }
    return ""
}

$w = Find-Dialog
if (-not $w) { '{"open": false}'; exit 0 }
switch ($Action) {
    "read" {
        $out = [ordered]@{ open = $true; title = $w.Current.Name; hwnd = $w.Current.NativeWindowHandle;
                           printer = (Selected (By-Id $w "printerSelector")); settings = [ordered]@{} }
        foreach ($c in $w.FindAll($TS::Descendants, (New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, [System.Windows.Automation.ControlType]::ComboBox)))) {
            $out.settings[$c.Current.Name] = (Selected $c)
        }
        $cb = By-Id $w "UseAppFeaturesCheckBox"
        if ($cb) { $out.app_may_change_settings = $cb.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern).Current.ToggleState.ToString() }
        $out | ConvertTo-Json -Depth 4 -Compress
    }
    "dump" {
        $w.FindAll($TS::Descendants, [System.Windows.Automation.Condition]::TrueCondition) | % {
            "$($_.Current.ControlType.ProgrammaticName) | $($_.Current.Name) | $($_.Current.AutomationId)" }
    }
    "select" {
        $combo = By-Id $w "printerSelector"
        $combo.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
        Start-Sleep -Milliseconds 800
        $item = $null
        # the list is VIRTUALIZED (only the items in view exist): ask the
        # combo's item container for it, and realize it
        try {
            $ic = $combo.GetCurrentPattern([System.Windows.Automation.ItemContainerPattern]::Pattern)
            $item = $ic.FindItemByProperty($null, $A::NameProperty, $Printer)
            if ($item) {
                try { $item.GetCurrentPattern([System.Windows.Automation.VirtualizedItemPattern]::Pattern).Realize() } catch {}
                Start-Sleep -Milliseconds 500
            }
        } catch {}
        if (-not $item) {
            $item = $combo.FindFirst($TS::Descendants, (New-Object System.Windows.Automation.PropertyCondition($A::NameProperty, $Printer)))
        }
        if (-not $item) {
            $item = $A::RootElement.FindFirst($TS::Descendants, (New-Object System.Windows.Automation.AndCondition(
                (New-Object System.Windows.Automation.PropertyCondition($A::NameProperty, $Printer)),
                (New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, [System.Windows.Automation.ControlType]::ListItem)))))
        }
        if ($item) {
            # as a user does: scroll it into view and CLICK it (selecting it by
            # pattern reports success and does not change the dialog's printer)
            try { $item.GetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern).ScrollIntoView() } catch {}
            Start-Sleep -Milliseconds 600
            $r = $item.Current.BoundingRectangle
            if ($r.Width -gt 0) {
                Add-Type -Namespace W -Name U -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
[DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, System.UIntPtr e);
[DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(System.IntPtr v);
'@
                [void][W.U]::SetProcessDpiAwarenessContext([System.IntPtr](-4))
                $x = [int]($r.X + $r.Width / 2); $y = [int]($r.Y + $r.Height / 2)
                [void][W.U]::SetCursorPos($x, $y)
                Start-Sleep -Milliseconds 200
                [W.U]::mouse_event(0x2, 0, 0, 0, [System.UIntPtr]::Zero)
                [W.U]::mouse_event(0x4, 0, 0, 0, [System.UIntPtr]::Zero)
                "clicked at $x,$y"
            } else {
                $item.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select(); "selected (no rectangle)"
            }
        }
        else { "not found" }
        Start-Sleep -Milliseconds 800
        try { $combo.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Collapse() } catch {}
    }
    "items" {
        $combo = By-Id $w "printerSelector"
        $combo.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Expand()
        Start-Sleep -Milliseconds 1200
        $li = New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, [System.Windows.Automation.ControlType]::ListItem)
        "-- under the combo:"
        $combo.FindAll($TS::Descendants, $li) | % { "  [$($_.Current.Name)] id=$($_.Current.AutomationId) class=$($_.Current.ClassName)" }
        "-- under the dialog:"
        $w.FindAll($TS::Descendants, $li) | % { "  [$($_.Current.Name)] id=$($_.Current.AutomationId)" }
        "-- popups at the root:"
        foreach ($t in $A::RootElement.FindAll($TS::Children, [System.Windows.Automation.Condition]::TrueCondition)) {
            if ($t.Current.ClassName -match "Popup|Xaml|DropDown" -or $t.Current.Name -eq "") {
                $t.FindAll($TS::Descendants, $li) | Select -First 60 | % { "  [$($_.Current.Name)] in $($t.Current.ClassName)" } }
        }
        try { $combo.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern).Collapse() } catch {}
    }
    "more" { (By-Id $w "moreOptionsButton").GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke(); "more" }
    "print" { (By-Id $w "PrintButton").GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke(); "printed" }
    "cancel" { (By-Id $w "CloseButton").GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke(); "cancelled" }
}
