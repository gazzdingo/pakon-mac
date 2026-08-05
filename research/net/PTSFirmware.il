.class public auto ansi beforefieldinit PTS.PTSFirmware
       extends [mscorlib]System.Object
       implements PTS.IFormPTS,
                  PTS.IFormPCS
{
  .field private [System.Windows.Forms]System.Windows.Forms.Form m_formOwner
  .field private class PTS.EnableActionUI m_evEnableActionUI
  .field private class PTS.ClearFirmwareUI m_evClearUI
  .field private class PTS.RefreshFirmwareUI m_evRefreshUI
  .field private class PTS.UpdateFirmwareUI m_evUpdateUI
  .field private class PTS.GetNextFirmwareStore m_evGetNextFirmwareStore
  .field private bool m_bFullFeature
  .field private valuetype PTS.FirmwareAction m_faAction
  .field private valuetype PTS.FirmwareLoad m_flCurrent
  .field private valuetype PTS.FirmwareStore m_fsCurrent
  .method public hidebysig specialname instance void 
          add_m_evEnableActionUI(class PTS.EnableActionUI 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class PTS.EnableActionUI PTS.PTSFirmware::m_evEnableActionUI
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  PTS.EnableActionUI
    IL_0012:  stfld      class PTS.EnableActionUI PTS.PTSFirmware::m_evEnableActionUI
    IL_0017:  ret
  } // end of method PTSFirmware::add_m_evEnableActionUI

  .method public hidebysig specialname instance void 
          remove_m_evEnableActionUI(class PTS.EnableActionUI 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class PTS.EnableActionUI PTS.PTSFirmware::m_evEnableActionUI
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  PTS.EnableActionUI
    IL_0012:  stfld      class PTS.EnableActionUI PTS.PTSFirmware::m_evEnableActionUI
    IL_0017:  ret
  } // end of method PTSFirmware::remove_m_evEnableActionUI

  .method public hidebysig specialname instance void 
          add_m_evClearUI(class PTS.ClearFirmwareUI 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class PTS.ClearFirmwareUI PTS.PTSFirmware::m_evClearUI
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  PTS.ClearFirmwareUI
    IL_0012:  stfld      class PTS.ClearFirmwareUI PTS.PTSFirmware::m_evClearUI
    IL_0017:  ret
  } // end of method PTSFirmware::add_m_evClearUI

  .method public hidebysig specialname instance void 
          remove_m_evClearUI(class PTS.ClearFirmwareUI 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class PTS.ClearFirmwareUI PTS.PTSFirmware::m_evClearUI
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  PTS.ClearFirmwareUI
    IL_0012:  stfld      class PTS.ClearFirmwareUI PTS.PTSFirmware::m_evClearUI
    IL_0017:  ret
  } // end of method PTSFirmware::remove_m_evClearUI

  .method public hidebysig specialname instance void 
          add_m_evRefreshUI(class PTS.RefreshFirmwareUI 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class PTS.RefreshFirmwareUI PTS.PTSFirmware::m_evRefreshUI
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  PTS.RefreshFirmwareUI
    IL_0012:  stfld      class PTS.RefreshFirmwareUI PTS.PTSFirmware::m_evRefreshUI
    IL_0017:  ret
  } // end of method PTSFirmware::add_m_evRefreshUI

  .method public hidebysig specialname instance void 
          remove_m_evRefreshUI(class PTS.RefreshFirmwareUI 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class PTS.RefreshFirmwareUI PTS.PTSFirmware::m_evRefreshUI
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  PTS.RefreshFirmwareUI
    IL_0012:  stfld      class PTS.RefreshFirmwareUI PTS.PTSFirmware::m_evRefreshUI
    IL_0017:  ret
  } // end of method PTSFirmware::remove_m_evRefreshUI

  .method public hidebysig specialname instance void 
          add_m_evUpdateUI(class PTS.UpdateFirmwareUI 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class PTS.UpdateFirmwareUI PTS.PTSFirmware::m_evUpdateUI
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  PTS.UpdateFirmwareUI
    IL_0012:  stfld      class PTS.UpdateFirmwareUI PTS.PTSFirmware::m_evUpdateUI
    IL_0017:  ret
  } // end of method PTSFirmware::add_m_evUpdateUI

  .method public hidebysig specialname instance void 
          remove_m_evUpdateUI(class PTS.UpdateFirmwareUI 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class PTS.UpdateFirmwareUI PTS.PTSFirmware::m_evUpdateUI
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  PTS.UpdateFirmwareUI
    IL_0012:  stfld      class PTS.UpdateFirmwareUI PTS.PTSFirmware::m_evUpdateUI
    IL_0017:  ret
  } // end of method PTSFirmware::remove_m_evUpdateUI

  .method public hidebysig specialname instance void 
          add_m_evGetNextFirmwareStore(class PTS.GetNextFirmwareStore 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class PTS.GetNextFirmwareStore PTS.PTSFirmware::m_evGetNextFirmwareStore
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  PTS.GetNextFirmwareStore
    IL_0012:  stfld      class PTS.GetNextFirmwareStore PTS.PTSFirmware::m_evGetNextFirmwareStore
    IL_0017:  ret
  } // end of method PTSFirmware::add_m_evGetNextFirmwareStore

  .method public hidebysig specialname instance void 
          remove_m_evGetNextFirmwareStore(class PTS.GetNextFirmwareStore 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class PTS.GetNextFirmwareStore PTS.PTSFirmware::m_evGetNextFirmwareStore
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  PTS.GetNextFirmwareStore
    IL_0012:  stfld      class PTS.GetNextFirmwareStore PTS.PTSFirmware::m_evGetNextFirmwareStore
    IL_0017:  ret
  } // end of method PTSFirmware::remove_m_evGetNextFirmwareStore

  .method public hidebysig specialname instance void 
          set_FullFeature(bool 'value') cil managed
  {
    // Code size       8 (0x8)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      bool PTS.PTSFirmware::m_bFullFeature
    IL_0007:  ret
  } // end of method PTSFirmware::set_FullFeature

  .method public hidebysig specialname instance valuetype PTS.FirmwareAction 
          get_Action() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  1
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype PTS.FirmwareAction PTS.PTSFirmware::m_faAction
    IL_0006:  ret
  } // end of method PTSFirmware::get_Action

  .method public hidebysig specialname instance valuetype PTS.FirmwareLoad 
          get_Load() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  1
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype PTS.FirmwareLoad PTS.PTSFirmware::m_flCurrent
    IL_0006:  ret
  } // end of method PTSFirmware::get_Load

  .method public hidebysig specialname instance valuetype PTS.FirmwareStore 
          get_Store() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  1
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype PTS.FirmwareStore PTS.PTSFirmware::m_fsCurrent
    IL_0006:  ret
  } // end of method PTSFirmware::get_Store

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor([System.Windows.Forms]System.Windows.Forms.Form formOwner) cil managed
  {
    // Code size       49 (0x31)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  ldnull
    IL_0002:  stfld      [System.Windows.Forms]System.Windows.Forms.Form PTS.PTSFirmware::m_formOwner
    IL_0007:  ldarg.0
    IL_0008:  ldc.i4.0
    IL_0009:  stfld      bool PTS.PTSFirmware::m_bFullFeature
    IL_000e:  ldarg.0
    IL_000f:  ldc.i4.0
    IL_0010:  stfld      valuetype PTS.FirmwareAction PTS.PTSFirmware::m_faAction
    IL_0015:  ldarg.0
    IL_0016:  ldc.i4.0
    IL_0017:  stfld      valuetype PTS.FirmwareLoad PTS.PTSFirmware::m_flCurrent
    IL_001c:  ldarg.0
    IL_001d:  ldc.i4.0
    IL_001e:  stfld      valuetype PTS.FirmwareStore PTS.PTSFirmware::m_fsCurrent
    IL_0023:  ldarg.0
    IL_0024:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0029:  ldarg.0
    IL_002a:  ldarg.1
    IL_002b:  stfld      [System.Windows.Forms]System.Windows.Forms.Form PTS.PTSFirmware::m_formOwner
    IL_0030:  ret
  } // end of method PTSFirmware::.ctor

  .method public hidebysig newslot virtual final 
          instance void  UpdateTaskButtons([Calibration]Calibration.ScannerSettings csScannerSettings,
                                           [System.Windows.Forms]System.Windows.Forms.Button btnExecute,
                                           [System.Windows.Forms]System.Windows.Forms.Button btnUpdate) cil managed
  {
    // Code size       20 (0x14)
    .maxstack  2
    IL_0000:  ldarg.2
    IL_0001:  ldarg.0
    IL_0002:  ldfld      bool PTS.PTSFirmware::m_bFullFeature
    IL_0007:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Enabled(bool)
    IL_000c:  ldarg.3
    IL_000d:  ldc.i4.1
    IL_000e:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Enabled(bool)
    IL_0013:  ret
  } // end of method PTSFirmware::UpdateTaskButtons

  .method public hidebysig newslot virtual final 
          instance void  UpdateTaskButtonToolTips([Calibration]Calibration.ScannerSettings csScannerSettings,
                                                  [System.Windows.Forms]System.Windows.Forms.ToolTip ttForm,
                                                  [System.Windows.Forms]System.Windows.Forms.Button btnExecute,
                                                  [System.Windows.Forms]System.Windows.Forms.Button btnUpdate) cil managed
  {
    // Code size       26 (0x1a)
    .maxstack  3
    IL_0000:  ldarg.2
    IL_0001:  ldarg.3
    IL_0002:  ldstr      "Make each attribute equal to the newly selected st"
    + "ate"
    IL_0007:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.ToolTip::SetToolTip([System.Windows.Forms]System.Windows.Forms.Control,
                                                                                                      string)
    IL_000c:  ldarg.2
    IL_000d:  ldarg.s    btnUpdate
    IL_000f:  ldstr      "Reload all the current attribute and new states"
    IL_0014:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.ToolTip::SetToolTip([System.Windows.Forms]System.Windows.Forms.Control,
                                                                                                      string)
    IL_0019:  ret
  } // end of method PTSFirmware::UpdateTaskButtonToolTips

  .method public hidebysig newslot virtual final 
          instance void  Execute([Calibration]Calibration.Scanner csScanner,
                                 [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       23 (0x17)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.1
    IL_0002:  stfld      valuetype PTS.FirmwareAction PTS.PTSFirmware::m_faAction
    IL_0007:  ldarg.0
    IL_0008:  ldc.i4.0
    IL_0009:  stfld      valuetype PTS.FirmwareStore PTS.PTSFirmware::m_fsCurrent
    IL_000e:  ldarg.0
    IL_000f:  ldarg.1
    IL_0010:  ldarg.2
    IL_0011:  call       instance void PTS.PTSFirmware::ExecuteAction([Calibration]Calibration.Scanner,
                                                                      [Calibration]Calibration.ScannerSettings)
    IL_0016:  ret
  } // end of method PTSFirmware::Execute

  .method public hidebysig newslot virtual final 
          instance void  Update([Calibration]Calibration.Scanner csScanner,
                                [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       23 (0x17)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.0
    IL_0002:  stfld      valuetype PTS.FirmwareAction PTS.PTSFirmware::m_faAction
    IL_0007:  ldarg.0
    IL_0008:  ldc.i4.0
    IL_0009:  stfld      valuetype PTS.FirmwareLoad PTS.PTSFirmware::m_flCurrent
    IL_000e:  ldarg.0
    IL_000f:  ldarg.1
    IL_0010:  ldarg.2
    IL_0011:  call       instance void PTS.PTSFirmware::ExecuteAction([Calibration]Calibration.Scanner,
                                                                      [Calibration]Calibration.ScannerSettings)
    IL_0016:  ret
  } // end of method PTSFirmware::Update

  .method public hidebysig newslot virtual final 
          instance void  Cancel([Calibration]Calibration.Scanner csScanner,
                                [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       1 (0x1)
    .maxstack  0
    IL_0000:  ret
  } // end of method PTSFirmware::Cancel

  .method public hidebysig newslot virtual final 
          instance bool  CanCancel() cil managed
  {
    // Code size       2 (0x2)
    .maxstack  1
    IL_0000:  ldc.i4.0
    IL_0001:  ret
  } // end of method PTSFirmware::CanCancel

  .method public hidebysig newslot virtual final 
          instance void  ErrorRecovery([Calibration]Calibration.Scanner csScanner,
                                       [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       26 (0x1a)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype PTS.FirmwareAction PTS.PTSFirmware::m_faAction
    IL_0006:  brtrue.s   IL_0011

    IL_0008:  ldarg.0
    IL_0009:  ldarg.1
    IL_000a:  ldarg.2
    IL_000b:  call       instance void PTS.PTSFirmware::LoadAttributesErrorRecovery([Calibration]Calibration.Scanner,
                                                                                    [Calibration]Calibration.ScannerSettings)
    IL_0010:  ret

    IL_0011:  ldarg.0
    IL_0012:  ldarg.1
    IL_0013:  ldarg.2
    IL_0014:  call       instance void PTS.PTSFirmware::StoreAttributesErrorRecovery([Calibration]Calibration.Scanner,
                                                                                     [Calibration]Calibration.ScannerSettings)
    IL_0019:  ret
  } // end of method PTSFirmware::ErrorRecovery

  .method public hidebysig newslot virtual final 
          instance void  FormPTSCallback([Calibration]Calibration.Scanner csScanner,
                                         [Calibration]Calibration.ScannerSettings csScannerSettings,
                                         [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                                         int32 lStatus) cil managed
  {
    // Code size       234 (0xea)
    .maxstack  3
    .locals init (bool V_0,
             valuetype PTS.FirmwareAction V_1,
             valuetype PTS.FirmwareLoad V_2,
             valuetype PTS.FirmwareStore V_3)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldarg.0
    IL_0003:  ldfld      valuetype PTS.FirmwareAction PTS.PTSFirmware::m_faAction
    IL_0008:  stloc.1
    IL_0009:  ldloc.1
    IL_000a:  switch     ( 
                          IL_001c,
                          IL_0078)
    IL_0017:  br         IL_00de

    IL_001c:  ldarg.0
    IL_001d:  ldfld      valuetype PTS.FirmwareLoad PTS.PTSFirmware::m_flCurrent
    IL_0022:  stloc.2
    IL_0023:  ldloc.2
    IL_0024:  switch     ( 
                          IL_003a,
                          IL_004e,
                          IL_005f)
    IL_0035:  br         IL_00de

    IL_003a:  ldarg.3
    IL_003b:  brtrue     IL_00de

    IL_0040:  ldarg.0
    IL_0041:  ldc.i4.1
    IL_0042:  stfld      valuetype PTS.FirmwareLoad PTS.PTSFirmware::m_flCurrent
    IL_0047:  ldc.i4.1
    IL_0048:  stloc.0
    IL_0049:  br         IL_00de

    IL_004e:  ldarg.3
    IL_004f:  brtrue     IL_00de

    IL_0054:  ldarg.0
    IL_0055:  ldc.i4.2
    IL_0056:  stfld      valuetype PTS.FirmwareLoad PTS.PTSFirmware::m_flCurrent
    IL_005b:  ldc.i4.1
    IL_005c:  stloc.0
    IL_005d:  br.s       IL_00de

    IL_005f:  ldarg.3
    IL_0060:  ldc.i4.s   20
    IL_0062:  bne.un.s   IL_00de

    IL_0064:  ldarg.s    lStatus
    IL_0066:  ldc.i4     0x3e8
    IL_006b:  bne.un.s   IL_00de

    IL_006d:  ldarg.0
    IL_006e:  ldc.i4.3
    IL_006f:  stfld      valuetype PTS.FirmwareLoad PTS.PTSFirmware::m_flCurrent
    IL_0074:  ldc.i4.1
    IL_0075:  stloc.0
    IL_0076:  br.s       IL_00de

    IL_0078:  ldarg.0
    IL_0079:  ldfld      valuetype PTS.FirmwareStore PTS.PTSFirmware::m_fsCurrent
    IL_007e:  stloc.3
    IL_007f:  ldloc.3
    IL_0080:  switch     ( 
                          IL_009f,
                          IL_00b5,
                          IL_00b5,
                          IL_00b5,
                          IL_00b5,
                          IL_00b5)
    IL_009d:  br.s       IL_00de

    IL_009f:  ldarg.3
    IL_00a0:  brtrue.s   IL_00de

    IL_00a2:  ldarg.2
    IL_00a3:  ldarg.1
    IL_00a4:  callvirt   instance bool [Calibration]Calibration.ScannerSettings::CompleteLLCInitialization([Calibration]Calibration.Scanner)
    IL_00a9:  pop
    IL_00aa:  ldarg.0
    IL_00ab:  ldc.i4.1
    IL_00ac:  stfld      valuetype PTS.FirmwareStore PTS.PTSFirmware::m_fsCurrent
    IL_00b1:  ldc.i4.1
    IL_00b2:  stloc.0
    IL_00b3:  br.s       IL_00de

    IL_00b5:  ldarg.3
    IL_00b6:  ldc.i4.2
    IL_00b7:  beq.s      IL_00ca

    IL_00b9:  ldarg.3
    IL_00ba:  ldc.i4.4
    IL_00bb:  beq.s      IL_00ca

    IL_00bd:  ldarg.3
    IL_00be:  ldc.i4.6
    IL_00bf:  beq.s      IL_00ca

    IL_00c1:  ldarg.3
    IL_00c2:  ldc.i4.8
    IL_00c3:  beq.s      IL_00ca

    IL_00c5:  ldarg.3
    IL_00c6:  ldc.i4.s   10
    IL_00c8:  bne.un.s   IL_00de

    IL_00ca:  ldarg.0
    IL_00cb:  ldfld      class PTS.UpdateFirmwareUI PTS.PTSFirmware::m_evUpdateUI
    IL_00d0:  ldarg.0
    IL_00d1:  ldarg.3
    IL_00d2:  call       instance [Calibration]Calibration.ScannerFirmware PTS.PTSFirmware::Convert([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000)
    IL_00d7:  callvirt   instance void PTS.UpdateFirmwareUI::Invoke([Calibration]Calibration.ScannerFirmware)
    IL_00dc:  ldc.i4.1
    IL_00dd:  stloc.0
    IL_00de:  ldloc.0
    IL_00df:  brfalse.s  IL_00e9

    IL_00e1:  ldarg.0
    IL_00e2:  ldarg.1
    IL_00e3:  ldarg.2
    IL_00e4:  call       instance void PTS.PTSFirmware::ExecuteAction([Calibration]Calibration.Scanner,
                                                                      [Calibration]Calibration.ScannerSettings)
    IL_00e9:  ret
  } // end of method PTSFirmware::FormPTSCallback

  .method public hidebysig newslot virtual final 
          instance void  Acquire([Calibration]Calibration.Scanner csScanner,
                                 [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       1 (0x1)
    .maxstack  0
    IL_0000:  ret
  } // end of method PTSFirmware::Acquire

  .method public hidebysig newslot virtual final 
          instance void  AfterAcquire([Calibration]Calibration.Scanner csScanner,
                                      [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       13 (0xd)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  ldfld      class PTS.EnableActionUI PTS.PTSFirmware::m_evEnableActionUI
    IL_0006:  ldc.i4.1
    IL_0007:  callvirt   instance void PTS.EnableActionUI::Invoke(bool)
    IL_000c:  ret
  } // end of method PTSFirmware::AfterAcquire

  .method public hidebysig newslot virtual final 
          instance void  UpdateWizardButtons([Calibration]Calibration.ScannerSettings csScannerSettings,
                                             [System.Windows.Forms]System.Windows.Forms.Button btnBack,
                                             [System.Windows.Forms]System.Windows.Forms.Button btnNext) cil managed
  {
    // Code size       15 (0xf)
    .maxstack  2
    IL_0000:  ldarg.2
    IL_0001:  ldc.i4.0
    IL_0002:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Enabled(bool)
    IL_0007:  ldarg.3
    IL_0008:  ldc.i4.0
    IL_0009:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Enabled(bool)
    IL_000e:  ret
  } // end of method PTSFirmware::UpdateWizardButtons

  .method public hidebysig newslot virtual final 
          instance void  Back([Calibration]Calibration.Scanner csScanner,
                              [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       1 (0x1)
    .maxstack  0
    IL_0000:  ret
  } // end of method PTSFirmware::Back

  .method public hidebysig newslot virtual final 
          instance void  Next([Calibration]Calibration.Scanner csScanner,
                              [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       1 (0x1)
    .maxstack  0
    IL_0000:  ret
  } // end of method PTSFirmware::Next

  .method public hidebysig newslot virtual final 
          instance void  Closing([Calibration]Calibration.Scanner csScanner,
                                 [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       1 (0x1)
    .maxstack  0
    IL_0000:  ret
  } // end of method PTSFirmware::Closing

  .method public hidebysig newslot virtual final 
          instance valuetype PTS.PCSTab  GetTab() cil managed
  {
    // Code size       11 (0xb)
    .maxstack  2
    IL_0000:  ldstr      "Not a PCS Tab"
    IL_0005:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_000a:  throw
  } // end of method PTSFirmware::GetTab

  .method public hidebysig instance [Calibration]Calibration.ScannerFirmware 
          Convert(valuetype PTS.FirmwareStore fsConvert) cil managed
  {
    // Code size       53 (0x35)
    .maxstack  2
    .locals init (valuetype PTS.FirmwareStore V_0)
    IL_0000:  ldarg.1
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  ldc.i4.1
    IL_0004:  sub
    IL_0005:  switch     ( 
                          IL_0028,
                          IL_0024,
                          IL_0026,
                          IL_0022,
                          IL_0020)
    IL_001e:  br.s       IL_002a

    IL_0020:  ldc.i4.5
    IL_0021:  ret

    IL_0022:  ldc.i4.4
    IL_0023:  ret

    IL_0024:  ldc.i4.2
    IL_0025:  ret

    IL_0026:  ldc.i4.3
    IL_0027:  ret

    IL_0028:  ldc.i4.1
    IL_0029:  ret

    IL_002a:  ldstr      "FirmwareStore invalid"
    IL_002f:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0034:  throw
  } // end of method PTSFirmware::Convert

  .method public hidebysig instance [Calibration]Calibration.ScannerFirmware 
          Convert([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 wtoConvert) cil managed
  {
    // Code size       69 (0x45)
    .maxstack  2
    .locals init ([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 V_0)
    IL_0000:  ldarg.1
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  ldc.i4.2
    IL_0004:  sub
    IL_0005:  switch     ( 
                          IL_0030,
                          IL_003a,
                          IL_0032,
                          IL_003a,
                          IL_0034,
                          IL_003a,
                          IL_0036,
                          IL_003a,
                          IL_0038)
    IL_002e:  br.s       IL_003a

    IL_0030:  ldc.i4.5
    IL_0031:  ret

    IL_0032:  ldc.i4.4
    IL_0033:  ret

    IL_0034:  ldc.i4.2
    IL_0035:  ret

    IL_0036:  ldc.i4.3
    IL_0037:  ret

    IL_0038:  ldc.i4.1
    IL_0039:  ret

    IL_003a:  ldstr      "Worker Thread Operation invalid"
    IL_003f:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0044:  throw
  } // end of method PTSFirmware::Convert

  .method public hidebysig instance void 
          ExecuteAction([Calibration]Calibration.Scanner csScanner,
                        [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       138 (0x8a)
    .maxstack  4
    .locals init ([mscorlib]System.Runtime.InteropServices.COMException V_0,
             [mscorlib]System.Exception V_1)
    .try
    {
      IL_0000:  ldarg.0
      IL_0001:  ldfld      valuetype PTS.FirmwareAction PTS.PTSFirmware::m_faAction
      IL_0006:  brtrue.s   IL_0012

      IL_0008:  ldarg.0
      IL_0009:  ldarg.1
      IL_000a:  ldarg.2
      IL_000b:  call       instance void PTS.PTSFirmware::LoadAttributes([Calibration]Calibration.Scanner,
                                                                         [Calibration]Calibration.ScannerSettings)
      IL_0010:  br.s       IL_001a

      IL_0012:  ldarg.0
      IL_0013:  ldarg.1
      IL_0014:  ldarg.2
      IL_0015:  call       instance void PTS.PTSFirmware::StoreAttributes([Calibration]Calibration.Scanner,
                                                                          [Calibration]Calibration.ScannerSettings)
      IL_001a:  leave.s    IL_0089

    }  // end .try
    catch [mscorlib]System.Runtime.InteropServices.COMException 
    {
      IL_001c:  stloc.0
      IL_001d:  ldarg.0
      IL_001e:  ldfld      valuetype PTS.FirmwareAction PTS.PTSFirmware::m_faAction
      IL_0023:  brtrue.s   IL_0039

      IL_0025:  ldarg.0
      IL_0026:  ldfld      [System.Windows.Forms]System.Windows.Forms.Form PTS.PTSFirmware::m_formOwner
      IL_002b:  ldarg.1
      IL_002c:  ldloc.0
      IL_002d:  ldstr      "Pakon Troubleshooter"
      IL_0032:  call       void [Calibration]Calibration.Global::ErrorCOM([System.Windows.Forms]System.Windows.Forms.Form,
                                                                          [Calibration]Calibration.Scanner,
                                                                          [mscorlib]System.Runtime.InteropServices.COMException,
                                                                          string)
      IL_0037:  br.s       IL_004b

      IL_0039:  ldarg.0
      IL_003a:  ldfld      [System.Windows.Forms]System.Windows.Forms.Form PTS.PTSFirmware::m_formOwner
      IL_003f:  ldarg.1
      IL_0040:  ldloc.0
      IL_0041:  ldstr      "Pakon Troubleshooter"
      IL_0046:  call       void [Calibration]Calibration.Global::ErrorCOM([System.Windows.Forms]System.Windows.Forms.Form,
                                                                          [Calibration]Calibration.Scanner,
                                                                          [mscorlib]System.Runtime.InteropServices.COMException,
                                                                          string)
      IL_004b:  ldarg.0
      IL_004c:  ldarg.1
      IL_004d:  ldarg.2
      IL_004e:  call       instance void PTS.PTSFirmware::ErrorRecovery([Calibration]Calibration.Scanner,
                                                                        [Calibration]Calibration.ScannerSettings)
      IL_0053:  ldarg.0
      IL_0054:  ldfld      class PTS.EnableActionUI PTS.PTSFirmware::m_evEnableActionUI
      IL_0059:  ldc.i4.1
      IL_005a:  callvirt   instance void PTS.EnableActionUI::Invoke(bool)
      IL_005f:  leave.s    IL_0089

    }  // end handler
    catch [mscorlib]System.Exception 
    {
      IL_0061:  stloc.1
      IL_0062:  ldarg.0
      IL_0063:  ldfld      [System.Windows.Forms]System.Windows.Forms.Form PTS.PTSFirmware::m_formOwner
      IL_0068:  ldloc.1
      IL_0069:  ldstr      "Pakon Troubleshooter"
      IL_006e:  call       void [Pakon]Pakon.Global::ErrorGeneral([System.Windows.Forms]System.Windows.Forms.Form,
                                                                  [mscorlib]System.Exception,
                                                                  string)
      IL_0073:  ldarg.0
      IL_0074:  ldarg.1
      IL_0075:  ldarg.2
      IL_0076:  call       instance void PTS.PTSFirmware::ErrorRecovery([Calibration]Calibration.Scanner,
                                                                        [Calibration]Calibration.ScannerSettings)
      IL_007b:  ldarg.0
      IL_007c:  ldfld      class PTS.EnableActionUI PTS.PTSFirmware::m_evEnableActionUI
      IL_0081:  ldc.i4.1
      IL_0082:  callvirt   instance void PTS.EnableActionUI::Invoke(bool)
      IL_0087:  leave.s    IL_0089

    }  // end handler
    IL_0089:  ret
  } // end of method PTSFirmware::ExecuteAction

  .method public hidebysig instance void 
          StoreAttributes([Calibration]Calibration.Scanner csScanner,
                          [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       244 (0xf4)
    .maxstack  5
    .locals init (bool V_0,
             string V_1,
             string V_2,
             [Interop.LLCLib]LLCLib.PIC_000 V_3,
             string V_4)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype PTS.FirmwareStore PTS.PTSFirmware::m_fsCurrent
    IL_0006:  brtrue.s   IL_0010

    IL_0008:  ldarg.2
    IL_0009:  ldarg.1
    IL_000a:  callvirt   instance void [Calibration]Calibration.ScannerSettings::OpenLLC([Calibration]Calibration.Scanner)
    IL_000f:  ret

    IL_0010:  ldarg.0
    IL_0011:  ldfld      valuetype PTS.FirmwareStore PTS.PTSFirmware::m_fsCurrent
    IL_0016:  ldc.i4.6
    IL_0017:  bne.un.s   IL_0056

    IL_0019:  ldarg.0
    IL_001a:  ldarg.1
    IL_001b:  ldarg.2
    IL_001c:  call       instance void PTS.PTSFirmware::CheckUSBBoardSettings([Calibration]Calibration.Scanner,
                                                                              [Calibration]Calibration.ScannerSettings)
    IL_0021:  ldarg.2
    IL_0022:  ldarg.1
    IL_0023:  callvirt   instance bool [Calibration]Calibration.ScannerSettings::CompleteLLCInitialization([Calibration]Calibration.Scanner)
    IL_0028:  pop
    IL_0029:  ldarg.0
    IL_002a:  ldfld      class PTS.RefreshFirmwareUI PTS.PTSFirmware::m_evRefreshUI
    IL_002f:  callvirt   instance void PTS.RefreshFirmwareUI::Invoke()
    IL_0034:  ldarg.1
    IL_0035:  ldc.i4.s   40
    IL_0037:  ldc.i4     0x3e8
    IL_003c:  callvirt   instance void [Pakon]Pakon.Scanner::TLXAwake(int32,
                                                                      int32)
    IL_0041:  ldarg.2
    IL_0042:  ldarg.1
    IL_0043:  callvirt   instance void [Calibration]Calibration.ScannerSettings::CloseLLC([Calibration]Calibration.Scanner)
    IL_0048:  ldarg.1
    IL_0049:  ldc.i4.s   40
    IL_004b:  ldc.i4     0xbb8
    IL_0050:  callvirt   instance void [Pakon]Pakon.Scanner::TLXAwake(int32,
                                                                      int32)
    IL_0055:  ret

    IL_0056:  ldc.i4.0
    IL_0057:  stloc.0
    IL_0058:  ldstr      ""
    IL_005d:  stloc.1
    IL_005e:  ldstr      ""
    IL_0063:  stloc.2
    IL_0064:  br.s       IL_00b0

    IL_0066:  ldarg.0
    IL_0067:  ldfld      class PTS.GetNextFirmwareStore PTS.PTSFirmware::m_evGetNextFirmwareStore
    IL_006c:  ldarg.0
    IL_006d:  ldarg.0
    IL_006e:  ldfld      valuetype PTS.FirmwareStore PTS.PTSFirmware::m_fsCurrent
    IL_0073:  call       instance [Calibration]Calibration.ScannerFirmware PTS.PTSFirmware::Convert(valuetype PTS.FirmwareStore)
    IL_0078:  ldloca.s   V_1
    IL_007a:  ldloca.s   V_2
    IL_007c:  callvirt   instance void PTS.GetNextFirmwareStore::Invoke([Calibration]Calibration.ScannerFirmware,
                                                                        string&,
                                                                        string&)
    IL_0081:  ldloc.1
    IL_0082:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_0087:  brfalse.s  IL_009f

    IL_0089:  ldloc.2
    IL_008a:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_008f:  brfalse.s  IL_009f

    IL_0091:  ldloc.1
    IL_0092:  ldloc.2
    IL_0093:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_0098:  ldc.i4.0
    IL_0099:  ceq
    IL_009b:  ldc.i4.0
    IL_009c:  ceq
    IL_009e:  stloc.0
    IL_009f:  ldloc.0
    IL_00a0:  brtrue.s   IL_00b0

    IL_00a2:  ldarg.0
    IL_00a3:  dup
    IL_00a4:  ldfld      valuetype PTS.FirmwareStore PTS.PTSFirmware::m_fsCurrent
    IL_00a9:  ldc.i4.1
    IL_00aa:  add
    IL_00ab:  stfld      valuetype PTS.FirmwareStore PTS.PTSFirmware::m_fsCurrent
    IL_00b0:  ldloc.0
    IL_00b1:  brtrue.s   IL_00bc

    IL_00b3:  ldarg.0
    IL_00b4:  ldfld      valuetype PTS.FirmwareStore PTS.PTSFirmware::m_fsCurrent
    IL_00b9:  ldc.i4.5
    IL_00ba:  ble.s      IL_0066

    IL_00bc:  ldarg.0
    IL_00bd:  ldfld      valuetype PTS.FirmwareStore PTS.PTSFirmware::m_fsCurrent
    IL_00c2:  ldc.i4.6
    IL_00c3:  bne.un.s   IL_00ce

    IL_00c5:  ldarg.0
    IL_00c6:  ldarg.1
    IL_00c7:  ldarg.2
    IL_00c8:  call       instance void PTS.PTSFirmware::StoreAttributes([Calibration]Calibration.Scanner,
                                                                        [Calibration]Calibration.ScannerSettings)
    IL_00cd:  ret

    IL_00ce:  ldarg.2
    IL_00cf:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_00d4:  ldarg.0
    IL_00d5:  ldarg.0
    IL_00d6:  ldfld      valuetype PTS.FirmwareStore PTS.PTSFirmware::m_fsCurrent
    IL_00db:  call       instance [Calibration]Calibration.ScannerFirmware PTS.PTSFirmware::Convert(valuetype PTS.FirmwareStore)
    IL_00e0:  ldloc.2
    IL_00e1:  ldloca.s   V_3
    IL_00e3:  ldloca.s   V_4
    IL_00e5:  callvirt   instance void [Calibration]Calibration.ScannerSettingsFirmware::GetFirmwareFile([Calibration]Calibration.ScannerFirmware,
                                                                                                         string,
                                                                                                         [Interop.LLCLib]LLCLib.PIC_000&,
                                                                                                         string&)
    IL_00ea:  ldarg.1
    IL_00eb:  ldloc.3
    IL_00ec:  ldloc.s    V_4
    IL_00ee:  callvirt   instance void [Calibration]Calibration.Scanner::LoadFirmware([Interop.LLCLib]LLCLib.PIC_000,
                                                                                      string)
    IL_00f3:  ret
  } // end of method PTSFirmware::StoreAttributes

  .method public hidebysig instance void 
          StoreAttributesErrorRecovery([Calibration]Calibration.Scanner csScanner,
                                       [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       34 (0x22)
    .maxstack  3
    IL_0000:  ldarg.1
    IL_0001:  ldc.i4.s   40
    IL_0003:  ldc.i4     0x3e8
    IL_0008:  callvirt   instance void [Pakon]Pakon.Scanner::TLXAwake(int32,
                                                                      int32)
    IL_000d:  ldarg.2
    IL_000e:  ldarg.1
    IL_000f:  callvirt   instance void [Calibration]Calibration.ScannerSettings::CloseLLC([Calibration]Calibration.Scanner)
    IL_0014:  ldarg.1
    IL_0015:  ldc.i4.s   40
    IL_0017:  ldc.i4     0xbb8
    IL_001c:  callvirt   instance void [Pakon]Pakon.Scanner::TLXAwake(int32,
                                                                      int32)
    IL_0021:  ret
  } // end of method PTSFirmware::StoreAttributesErrorRecovery

  .method public hidebysig instance void 
          LoadAttributes([Calibration]Calibration.Scanner csScanner,
                         [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       215 (0xd7)
    .maxstack  4
    .locals init (bool V_0,
             valuetype PTS.FirmwareLoad V_1)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype PTS.FirmwareLoad PTS.PTSFirmware::m_flCurrent
    IL_0006:  stloc.1
    IL_0007:  ldloc.1
    IL_0008:  switch     ( 
                          IL_001e,
                          IL_0037,
                          IL_007d,
                          IL_009c)
    IL_001d:  ret

    IL_001e:  ldarg.2
    IL_001f:  callvirt   instance void [Pakon]Pakon.ScannerSettings::Reset()
    IL_0024:  ldarg.0
    IL_0025:  ldfld      class PTS.ClearFirmwareUI PTS.PTSFirmware::m_evClearUI
    IL_002a:  callvirt   instance void PTS.ClearFirmwareUI::Invoke()
    IL_002f:  ldarg.2
    IL_0030:  ldarg.1
    IL_0031:  callvirt   instance void [Calibration]Calibration.ScannerSettings::OpenLLC([Calibration]Calibration.Scanner)
    IL_0036:  ret

    IL_0037:  ldarg.2
    IL_0038:  ldarg.1
    IL_0039:  callvirt   instance bool [Calibration]Calibration.ScannerSettings::CompleteLLCInitialization([Calibration]Calibration.Scanner)
    IL_003e:  stloc.0
    IL_003f:  ldarg.1
    IL_0040:  ldc.i4.0
    IL_0041:  ldc.i4     0x3e8
    IL_0046:  callvirt   instance void [Pakon]Pakon.Scanner::TLXAwake(int32,
                                                                      int32)
    IL_004b:  ldarg.2
    IL_004c:  ldarg.1
    IL_004d:  callvirt   instance void [Calibration]Calibration.ScannerSettings::CloseLLC([Calibration]Calibration.Scanner)
    IL_0052:  ldloc.0
    IL_0053:  brfalse.s  IL_005d

    IL_0055:  ldarg.2
    IL_0056:  ldarg.1
    IL_0057:  callvirt   instance void [Pakon]Pakon.ScannerSettings::OpenTLX([Pakon]Pakon.Scanner)
    IL_005c:  ret

    IL_005d:  ldarg.0
    IL_005e:  ldc.i4.3
    IL_005f:  stfld      valuetype PTS.FirmwareLoad PTS.PTSFirmware::m_flCurrent
    IL_0064:  ldarg.1
    IL_0065:  ldc.i4.s   40
    IL_0067:  ldc.i4     0xbb8
    IL_006c:  callvirt   instance void [Pakon]Pakon.Scanner::TLXAwake(int32,
                                                                      int32)
    IL_0071:  ldarg.0
    IL_0072:  ldfld      class PTS.RefreshFirmwareUI PTS.PTSFirmware::m_evRefreshUI
    IL_0077:  callvirt   instance void PTS.RefreshFirmwareUI::Invoke()
    IL_007c:  ret

    IL_007d:  ldarg.1
    IL_007e:  ldc.i4.s   20
    IL_0080:  ldc.i4.0
    IL_0081:  callvirt   instance void [Pakon]Pakon.Scanner::TLXAwake(int32,
                                                                      int32)
    IL_0086:  ldarg.2
    IL_0087:  ldarg.1
    IL_0088:  callvirt   instance void [Calibration]Calibration.ScannerSettings::CompleteTLXInitialization([Calibration]Calibration.Scanner)
    IL_008d:  ldarg.1
    IL_008e:  callvirt   instance [Calibration]Calibration.ICalibrate [Calibration]Calibration.Scanner::get_ICalibration()
    IL_0093:  ldc.i4.2
    IL_0094:  ldc.i4.1
    IL_0095:  ldc.i4.0
    IL_0096:  callvirt   instance void [Calibration]Calibration.ICalibrate::Begin([Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                  [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                  bool)
    IL_009b:  ret

    IL_009c:  ldarg.2
    IL_009d:  ldarg.1
    IL_009e:  callvirt   instance void [Calibration]Calibration.ScannerSettings::LoadDpiSettings([Calibration]Calibration.Scanner)
    IL_00a3:  ldarg.2
    IL_00a4:  ldarg.1
    IL_00a5:  callvirt   instance void [Calibration]Calibration.ScannerSettings::LoadColorMatrices([Calibration]Calibration.Scanner)
    IL_00aa:  ldarg.0
    IL_00ab:  ldfld      class PTS.RefreshFirmwareUI PTS.PTSFirmware::m_evRefreshUI
    IL_00b0:  callvirt   instance void PTS.RefreshFirmwareUI::Invoke()
    IL_00b5:  ldarg.1
    IL_00b6:  ldc.i4.s   40
    IL_00b8:  ldc.i4     0x3e8
    IL_00bd:  callvirt   instance void [Pakon]Pakon.Scanner::TLXAwake(int32,
                                                                      int32)
    IL_00c2:  ldarg.2
    IL_00c3:  ldarg.1
    IL_00c4:  callvirt   instance void [Pakon]Pakon.ScannerSettings::CloseTLX([Pakon]Pakon.Scanner)
    IL_00c9:  ldarg.1
    IL_00ca:  ldc.i4.s   40
    IL_00cc:  ldc.i4     0xbb8
    IL_00d1:  callvirt   instance void [Pakon]Pakon.Scanner::TLXAwake(int32,
                                                                      int32)
    IL_00d6:  ret
  } // end of method PTSFirmware::LoadAttributes

  .method public hidebysig instance void 
          LoadAttributesErrorRecovery([Calibration]Calibration.Scanner csScanner,
                                      [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       98 (0x62)
    .maxstack  3
    .locals init (valuetype PTS.FirmwareLoad V_0)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype PTS.FirmwareLoad PTS.PTSFirmware::m_flCurrent
    IL_0006:  stloc.0
    IL_0007:  ldloc.0
    IL_0008:  switch     ( 
                          IL_001e,
                          IL_0040,
                          IL_0040,
                          IL_0040)
    IL_001d:  ret

    IL_001e:  ldarg.1
    IL_001f:  ldc.i4.s   40
    IL_0021:  ldc.i4     0x3e8
    IL_0026:  callvirt   instance void [Pakon]Pakon.Scanner::TLXAwake(int32,
                                                                      int32)
    IL_002b:  ldarg.2
    IL_002c:  ldarg.1
    IL_002d:  callvirt   instance void [Calibration]Calibration.ScannerSettings::CloseLLC([Calibration]Calibration.Scanner)
    IL_0032:  ldarg.1
    IL_0033:  ldc.i4.s   40
    IL_0035:  ldc.i4     0xbb8
    IL_003a:  callvirt   instance void [Pakon]Pakon.Scanner::TLXAwake(int32,
                                                                      int32)
    IL_003f:  ret

    IL_0040:  ldarg.1
    IL_0041:  ldc.i4.s   40
    IL_0043:  ldc.i4     0x3e8
    IL_0048:  callvirt   instance void [Pakon]Pakon.Scanner::TLXAwake(int32,
                                                                      int32)
    IL_004d:  ldarg.2
    IL_004e:  ldarg.1
    IL_004f:  callvirt   instance void [Pakon]Pakon.ScannerSettings::CloseTLX([Pakon]Pakon.Scanner)
    IL_0054:  ldarg.1
    IL_0055:  ldc.i4.s   40
    IL_0057:  ldc.i4     0xbb8
    IL_005c:  callvirt   instance void [Pakon]Pakon.Scanner::TLXAwake(int32,
                                                                      int32)
    IL_0061:  ret
  } // end of method PTSFirmware::LoadAttributesErrorRecovery

  .method public hidebysig instance void 
          CheckUSBBoardSettings([Calibration]Calibration.Scanner csScanner,
                                [Calibration]Calibration.ScannerSettings csScannerSettings) cil managed
  {
    // Code size       77 (0x4d)
    .maxstack  4
    .locals init (string V_0,
             string V_1,
             bool V_2)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      class PTS.GetNextFirmwareStore PTS.PTSFirmware::m_evGetNextFirmwareStore
    IL_0006:  ldc.i4.0
    IL_0007:  ldloca.s   V_0
    IL_0009:  ldloca.s   V_1
    IL_000b:  callvirt   instance void PTS.GetNextFirmwareStore::Invoke([Calibration]Calibration.ScannerFirmware,
                                                                        string&,
                                                                        string&)
    IL_0010:  ldc.i4.0
    IL_0011:  stloc.2
    IL_0012:  ldloc.0
    IL_0013:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_0018:  brfalse.s  IL_0030

    IL_001a:  ldloc.1
    IL_001b:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_0020:  brfalse.s  IL_0030

    IL_0022:  ldloc.0
    IL_0023:  ldloc.1
    IL_0024:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_0029:  ldc.i4.0
    IL_002a:  ceq
    IL_002c:  ldc.i4.0
    IL_002d:  ceq
    IL_002f:  stloc.2
    IL_0030:  ldloc.2
    IL_0031:  brfalse.s  IL_004c

    IL_0033:  ldarg.2
    IL_0034:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_0039:  ldarg.1
    IL_003a:  ldloc.1
    IL_003b:  callvirt   instance void [Calibration]Calibration.ScannerSettingsFirmware::SetPersonality([Calibration]Calibration.Scanner,
                                                                                                        string)
    IL_0040:  ldarg.0
    IL_0041:  ldfld      class PTS.UpdateFirmwareUI PTS.PTSFirmware::m_evUpdateUI
    IL_0046:  ldc.i4.0
    IL_0047:  callvirt   instance void PTS.UpdateFirmwareUI::Invoke([Calibration]Calibration.ScannerFirmware)
    IL_004c:  ret
  } // end of method PTSFirmware::CheckUSBBoardSettings

  .method public hidebysig instance void 
          LoadScannerTypeInformation([Calibration]Calibration.ScannerSettings csScannerSettings,
                                     [System.Windows.Forms]System.Windows.Forms.TextBox tbScannerType) cil managed
  {
    // Code size       61 (0x3d)
    .maxstack  3
    IL_0000:  ldarg.2
    IL_0001:  ldarg.1
    IL_0002:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0007:  box        [Interop.TLXLib]TLXLib.SCANNER_TYPE_000
    IL_000c:  call       instance string [mscorlib]System.Enum::ToString()
    IL_0011:  ldc.i4.s   13
    IL_0013:  callvirt   instance string [mscorlib]System.String::Substring(int32)
    IL_0018:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_001d:  ldarg.1
    IL_001e:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0023:  brtrue.s   IL_0031

    IL_0025:  ldarg.2
    IL_0026:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_002b:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0030:  ret

    IL_0031:  ldarg.2
    IL_0032:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0037:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_003c:  ret
  } // end of method PTSFirmware::LoadScannerTypeInformation

  .method public hidebysig instance void 
          LoadSerialNumberInformation([Calibration]Calibration.ScannerSettings csScannerSettings,
                                      [System.Windows.Forms]System.Windows.Forms.TextBox tbSerialNumber) cil managed
  {
    // Code size       21 (0x15)
    .maxstack  3
    .locals init (int32 V_0)
    IL_0000:  ldarg.2
    IL_0001:  ldarg.1
    IL_0002:  callvirt   instance int32 [Pakon]Pakon.ScannerSettings::get_SerialNumber()
    IL_0007:  stloc.0
    IL_0008:  ldloca.s   V_0
    IL_000a:  call       instance string [mscorlib]System.Int32::ToString()
    IL_000f:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_0014:  ret
  } // end of method PTSFirmware::LoadSerialNumberInformation

  .method public hidebysig instance void 
          LoadHardwareVersionInformation([Calibration]Calibration.ScannerSettings csScannerSettings,
                                         [System.Windows.Forms]System.Windows.Forms.TextBox tbHardwareVersion) cil managed
  {
    // Code size       259 (0x103)
    .maxstack  3
    .locals init ([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_0)
    IL_0000:  ldarg.1
    IL_0001:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0006:  stloc.0
    IL_0007:  ldloc.0
    IL_0008:  ldc.i4.7
    IL_0009:  sub
    IL_000a:  switch     ( 
                          IL_007a,
                          IL_007a)
    IL_0017:  ldloc.0
    IL_0018:  ldc.i4     0x546
    IL_001d:  sub
    IL_001e:  switch     ( 
                          IL_0044,
                          IL_0044)
    IL_002b:  ldloc.0
    IL_002c:  ldc.i4     0xd16
    IL_0031:  sub
    IL_0032:  switch     ( 
                          IL_00b0,
                          IL_00b0)
    IL_003f:  br         IL_00e6

    IL_0044:  ldarg.2
    IL_0045:  ldarg.1
    IL_0046:  callvirt   instance [Pakon]Pakon.ScannerHW135 [Pakon]Pakon.ScannerSettings::get_Hardware135()
    IL_004b:  box        [Pakon]Pakon.ScannerHW135
    IL_0050:  call       instance string [mscorlib]System.Enum::ToString()
    IL_0055:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_005a:  ldarg.1
    IL_005b:  callvirt   instance [Pakon]Pakon.ScannerHW135 [Pakon]Pakon.ScannerSettings::get_Hardware135()
    IL_0060:  brtrue.s   IL_006e

    IL_0062:  ldarg.2
    IL_0063:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_0068:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_006d:  ret

    IL_006e:  ldarg.2
    IL_006f:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0074:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0079:  ret

    IL_007a:  ldarg.2
    IL_007b:  ldarg.1
    IL_007c:  callvirt   instance [Pakon]Pakon.ScannerHW235 [Pakon]Pakon.ScannerSettings::get_Hardware235()
    IL_0081:  box        [Pakon]Pakon.ScannerHW235
    IL_0086:  call       instance string [mscorlib]System.Enum::ToString()
    IL_008b:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_0090:  ldarg.1
    IL_0091:  callvirt   instance [Pakon]Pakon.ScannerHW235 [Pakon]Pakon.ScannerSettings::get_Hardware235()
    IL_0096:  brtrue.s   IL_00a4

    IL_0098:  ldarg.2
    IL_0099:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_009e:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00a3:  ret

    IL_00a4:  ldarg.2
    IL_00a5:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_00aa:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00af:  ret

    IL_00b0:  ldarg.2
    IL_00b1:  ldarg.1
    IL_00b2:  callvirt   instance [Pakon]Pakon.ScannerHW335 [Pakon]Pakon.ScannerSettings::get_Hardware335()
    IL_00b7:  box        [Pakon]Pakon.ScannerHW335
    IL_00bc:  call       instance string [mscorlib]System.Enum::ToString()
    IL_00c1:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_00c6:  ldarg.1
    IL_00c7:  callvirt   instance [Pakon]Pakon.ScannerHW335 [Pakon]Pakon.ScannerSettings::get_Hardware335()
    IL_00cc:  brtrue.s   IL_00da

    IL_00ce:  ldarg.2
    IL_00cf:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_00d4:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00d9:  ret

    IL_00da:  ldarg.2
    IL_00db:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_00e0:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00e5:  ret

    IL_00e6:  ldarg.2
    IL_00e7:  ldc.i4.0
    IL_00e8:  box        [Pakon]Pakon.ScannerHW235
    IL_00ed:  call       instance string [mscorlib]System.Enum::ToString()
    IL_00f2:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_00f7:  ldarg.2
    IL_00f8:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_00fd:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0102:  ret
  } // end of method PTSFirmware::LoadHardwareVersionInformation

  .method public hidebysig instance void 
          LoadEEPromInformation([Calibration]Calibration.ScannerSettings csScannerSettings,
                                [System.Windows.Forms]System.Windows.Forms.TextBox tbEEProm) cil managed
  {
    // Code size       73 (0x49)
    .maxstack  3
    .locals init ([Calibration]Calibration.EEPromState V_0)
    IL_0000:  ldarg.1
    IL_0001:  ldarg.1
    IL_0002:  callvirt   instance [Pakon]Pakon.ScannerInitializeWarnings [Pakon]Pakon.ScannerSettings::get_InitializeWarnings()
    IL_0007:  callvirt   instance [Calibration]Calibration.EEPromState [Calibration]Calibration.ScannerSettings::ValidateEEProm([Pakon]Pakon.ScannerInitializeWarnings)
    IL_000c:  stloc.0
    IL_000d:  ldarg.2
    IL_000e:  ldloc.0
    IL_000f:  box        [Calibration]Calibration.EEPromState
    IL_0014:  call       instance string [mscorlib]System.Enum::ToString()
    IL_0019:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_001e:  ldloc.0
    IL_001f:  ldc.i4.1
    IL_0020:  bne.un.s   IL_002e

    IL_0022:  ldarg.2
    IL_0023:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0028:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_002d:  ret

    IL_002e:  ldloc.0
    IL_002f:  brtrue.s   IL_003d

    IL_0031:  ldarg.2
    IL_0032:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_0037:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_003c:  ret

    IL_003d:  ldarg.2
    IL_003e:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_0043:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0048:  ret
  } // end of method PTSFirmware::LoadEEPromInformation

  .method public hidebysig instance void 
          LoadUSBBoardInformation([Calibration]Calibration.ScannerSettings csScannerSettings,
                                  [System.Windows.Forms]System.Windows.Forms.TextBox tbUSBBoard,
                                  [System.Windows.Forms]System.Windows.Forms.ComboBox cbUSBBoardChange) cil managed
  {
    // Code size       507 (0x1fb)
    .maxstack  4
    .locals init (string[] V_0,
             string V_1,
             string V_2,
             int32 V_3,
             [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_4,
             string[] V_5,
             int32 V_6)
    IL_0000:  ldnull
    IL_0001:  stloc.0
    IL_0002:  ldnull
    IL_0003:  stloc.1
    IL_0004:  ldarg.1
    IL_0005:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_000a:  stloc.s    V_4
    IL_000c:  ldloc.s    V_4
    IL_000e:  ldc.i4.7
    IL_000f:  sub
    IL_0010:  switch     ( 
                          IL_00bb,
                          IL_00bb)
    IL_001d:  ldloc.s    V_4
    IL_001f:  ldc.i4     0x546
    IL_0024:  sub
    IL_0025:  switch     ( 
                          IL_004c,
                          IL_004c)
    IL_0032:  ldloc.s    V_4
    IL_0034:  ldc.i4     0xd16
    IL_0039:  sub
    IL_003a:  switch     ( 
                          IL_0124,
                          IL_0124)
    IL_0047:  br         IL_018b

    IL_004c:  ldarg.2
    IL_004d:  ldarg.1
    IL_004e:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_0053:  callvirt   instance [Calibration]Calibration.USB135 [Calibration]Calibration.ScannerSettingsFirmware::get_USB135()
    IL_0058:  box        [Calibration]Calibration.USB135
    IL_005d:  call       instance string [mscorlib]System.Enum::ToString()
    IL_0062:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_0067:  ldarg.1
    IL_0068:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_006d:  callvirt   instance [Calibration]Calibration.USB135 [Calibration]Calibration.ScannerSettingsFirmware::get_USB135()
    IL_0072:  box        [Calibration]Calibration.USB135
    IL_0077:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_007c:  call       string[] [mscorlib]System.Enum::GetNames([mscorlib]System.Type)
    IL_0081:  stloc.0
    IL_0082:  ldc.i4.0
    IL_0083:  box        [Pakon]Pakon.ScannerHW135
    IL_0088:  call       instance string [mscorlib]System.Enum::ToString()
    IL_008d:  stloc.1
    IL_008e:  ldarg.1
    IL_008f:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_0094:  callvirt   instance [Calibration]Calibration.USB135 [Calibration]Calibration.ScannerSettingsFirmware::get_USB135()
    IL_0099:  brtrue.s   IL_00ab

    IL_009b:  ldarg.2
    IL_009c:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_00a1:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00a6:  br         IL_018b

    IL_00ab:  ldarg.2
    IL_00ac:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_00b1:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00b6:  br         IL_018b

    IL_00bb:  ldarg.2
    IL_00bc:  ldarg.1
    IL_00bd:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_00c2:  callvirt   instance [Calibration]Calibration.USB235 [Calibration]Calibration.ScannerSettingsFirmware::get_USB235()
    IL_00c7:  box        [Calibration]Calibration.USB235
    IL_00cc:  call       instance string [mscorlib]System.Enum::ToString()
    IL_00d1:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_00d6:  ldarg.1
    IL_00d7:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_00dc:  callvirt   instance [Calibration]Calibration.USB235 [Calibration]Calibration.ScannerSettingsFirmware::get_USB235()
    IL_00e1:  box        [Calibration]Calibration.USB235
    IL_00e6:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_00eb:  call       string[] [mscorlib]System.Enum::GetNames([mscorlib]System.Type)
    IL_00f0:  stloc.0
    IL_00f1:  ldc.i4.0
    IL_00f2:  box        [Pakon]Pakon.ScannerHW235
    IL_00f7:  call       instance string [mscorlib]System.Enum::ToString()
    IL_00fc:  stloc.1
    IL_00fd:  ldarg.1
    IL_00fe:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_0103:  callvirt   instance [Calibration]Calibration.USB235 [Calibration]Calibration.ScannerSettingsFirmware::get_USB235()
    IL_0108:  brtrue.s   IL_0117

    IL_010a:  ldarg.2
    IL_010b:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_0110:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0115:  br.s       IL_018b

    IL_0117:  ldarg.2
    IL_0118:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_011d:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0122:  br.s       IL_018b

    IL_0124:  ldarg.2
    IL_0125:  ldarg.1
    IL_0126:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_012b:  callvirt   instance [Calibration]Calibration.USB335 [Calibration]Calibration.ScannerSettingsFirmware::get_USB335()
    IL_0130:  box        [Calibration]Calibration.USB335
    IL_0135:  call       instance string [mscorlib]System.Enum::ToString()
    IL_013a:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_013f:  ldarg.1
    IL_0140:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_0145:  callvirt   instance [Calibration]Calibration.USB335 [Calibration]Calibration.ScannerSettingsFirmware::get_USB335()
    IL_014a:  box        [Calibration]Calibration.USB335
    IL_014f:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_0154:  call       string[] [mscorlib]System.Enum::GetNames([mscorlib]System.Type)
    IL_0159:  stloc.0
    IL_015a:  ldc.i4.0
    IL_015b:  box        [Pakon]Pakon.ScannerHW335
    IL_0160:  call       instance string [mscorlib]System.Enum::ToString()
    IL_0165:  stloc.1
    IL_0166:  ldarg.1
    IL_0167:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_016c:  callvirt   instance [Calibration]Calibration.USB335 [Calibration]Calibration.ScannerSettingsFirmware::get_USB335()
    IL_0171:  brtrue.s   IL_0180

    IL_0173:  ldarg.2
    IL_0174:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_0179:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_017e:  br.s       IL_018b

    IL_0180:  ldarg.2
    IL_0181:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0186:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_018b:  ldarg.3
    IL_018c:  callvirt   instance [System.Windows.Forms]System.Windows.Forms.ComboBox/ObjectCollection [System.Windows.Forms]System.Windows.Forms.ComboBox::get_Items()
    IL_0191:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.ComboBox/ObjectCollection::Clear()
    IL_0196:  ldloc.0
    IL_0197:  brfalse.s  IL_01fa

    IL_0199:  ldloc.0
    IL_019a:  stloc.s    V_5
    IL_019c:  ldc.i4.0
    IL_019d:  stloc.s    V_6
    IL_019f:  br.s       IL_01c3

    IL_01a1:  ldloc.s    V_5
    IL_01a3:  ldloc.s    V_6
    IL_01a5:  ldelem.ref
    IL_01a6:  stloc.2
    IL_01a7:  ldloc.2
    IL_01a8:  ldloc.1
    IL_01a9:  call       bool [mscorlib]System.String::op_Inequality(string,
                                                                     string)
    IL_01ae:  brfalse.s  IL_01bd

    IL_01b0:  ldarg.3
    IL_01b1:  callvirt   instance [System.Windows.Forms]System.Windows.Forms.ComboBox/ObjectCollection [System.Windows.Forms]System.Windows.Forms.ComboBox::get_Items()
    IL_01b6:  ldloc.2
    IL_01b7:  callvirt   instance int32 [System.Windows.Forms]System.Windows.Forms.ComboBox/ObjectCollection::Add(object)
    IL_01bc:  pop
    IL_01bd:  ldloc.s    V_6
    IL_01bf:  ldc.i4.1
    IL_01c0:  add
    IL_01c1:  stloc.s    V_6
    IL_01c3:  ldloc.s    V_6
    IL_01c5:  ldloc.s    V_5
    IL_01c7:  ldlen
    IL_01c8:  conv.i4
    IL_01c9:  blt.s      IL_01a1

    IL_01cb:  ldarg.3
    IL_01cc:  callvirt   instance [System.Windows.Forms]System.Windows.Forms.ComboBox/ObjectCollection [System.Windows.Forms]System.Windows.Forms.ComboBox::get_Items()
    IL_01d1:  callvirt   instance int32 [System.Windows.Forms]System.Windows.Forms.ComboBox/ObjectCollection::get_Count()
    IL_01d6:  ldc.i4.0
    IL_01d7:  ble.s      IL_01e0

    IL_01d9:  ldarg.3
    IL_01da:  ldc.i4.1
    IL_01db:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Enabled(bool)
    IL_01e0:  ldc.i4.0
    IL_01e1:  ldarg.3
    IL_01e2:  ldarg.2
    IL_01e3:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_01e8:  callvirt   instance int32 [System.Windows.Forms]System.Windows.Forms.ComboBox::FindString(string)
    IL_01ed:  call       int32 [mscorlib]System.Math::Max(int32,
                                                          int32)
    IL_01f2:  stloc.3
    IL_01f3:  ldarg.3
    IL_01f4:  ldloc.3
    IL_01f5:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.ListControl::set_SelectedIndex(int32)
    IL_01fa:  ret
  } // end of method PTSFirmware::LoadUSBBoardInformation

  .method public hidebysig instance void 
          LoadMotorBoardInformation([Calibration]Calibration.Scanner csScanner,
                                    [Calibration]Calibration.ScannerSettings csScannerSettings,
                                    [System.Windows.Forms]System.Windows.Forms.TextBox tbMotorBoard,
                                    [System.Windows.Forms]System.Windows.Forms.ComboBox cbMotorBoardChange) cil managed
  {
    // Code size       162 (0xa2)
    .maxstack  5
    IL_0000:  ldarg.2
    IL_0001:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_0006:  ldarg.1
    IL_0007:  ldc.i4.1
    IL_0008:  ldarg.3
    IL_0009:  ldarg.s    cbMotorBoardChange
    IL_000b:  callvirt   instance void [Calibration]Calibration.ScannerSettingsFirmware::GetFileInformation([Calibration]Calibration.Scanner,
                                                                                                            [Calibration]Calibration.ScannerFirmware,
                                                                                                            [System.Windows.Forms]System.Windows.Forms.TextBox,
                                                                                                            [System.Windows.Forms]System.Windows.Forms.ComboBox)
    IL_0010:  ldarg.3
    IL_0011:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0016:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_001b:  brtrue.s   IL_0035

    IL_001d:  ldarg.3
    IL_001e:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_0023:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0028:  ldarg.s    cbMotorBoardChange
    IL_002a:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_002f:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0034:  ret

    IL_0035:  ldarg.2
    IL_0036:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_003b:  callvirt   instance string [Calibration]Calibration.ScannerSettingsFirmware::get_Motor()
    IL_0040:  ldstr      "Boot"
    IL_0045:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_004a:  brtrue.s   IL_0064

    IL_004c:  ldarg.3
    IL_004d:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_0052:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0057:  ldarg.s    cbMotorBoardChange
    IL_0059:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_005e:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0063:  ret

    IL_0064:  ldarg.3
    IL_0065:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_006a:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_006f:  ldarg.s    cbMotorBoardChange
    IL_0071:  callvirt   instance object [System.Windows.Forms]System.Windows.Forms.ComboBox::get_SelectedItem()
    IL_0076:  callvirt   instance string [mscorlib]System.Object::ToString()
    IL_007b:  ldarg.3
    IL_007c:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0081:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_0086:  brfalse.s  IL_0095

    IL_0088:  ldarg.s    cbMotorBoardChange
    IL_008a:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_008f:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0094:  ret

    IL_0095:  ldarg.s    cbMotorBoardChange
    IL_0097:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_009c:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00a1:  ret
  } // end of method PTSFirmware::LoadMotorBoardInformation

  .method public hidebysig instance void 
          LoadDXBoardInformation([Calibration]Calibration.Scanner csScanner,
                                 [Calibration]Calibration.ScannerSettings csScannerSettings,
                                 [System.Windows.Forms]System.Windows.Forms.TextBox tbDXBoard,
                                 [System.Windows.Forms]System.Windows.Forms.ComboBox cbDXBoardChange) cil managed
  {
    // Code size       200 (0xc8)
    .maxstack  5
    IL_0000:  ldarg.2
    IL_0001:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_0006:  ldarg.1
    IL_0007:  ldc.i4.2
    IL_0008:  ldarg.3
    IL_0009:  ldarg.s    cbDXBoardChange
    IL_000b:  callvirt   instance void [Calibration]Calibration.ScannerSettingsFirmware::GetFileInformation([Calibration]Calibration.Scanner,
                                                                                                            [Calibration]Calibration.ScannerFirmware,
                                                                                                            [System.Windows.Forms]System.Windows.Forms.TextBox,
                                                                                                            [System.Windows.Forms]System.Windows.Forms.ComboBox)
    IL_0010:  ldarg.3
    IL_0011:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0016:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_001b:  brtrue.s   IL_005b

    IL_001d:  ldarg.s    cbDXBoardChange
    IL_001f:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0024:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0029:  ldarg.2
    IL_002a:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_002f:  ldc.i4     0x546
    IL_0034:  beq.s      IL_0043

    IL_0036:  ldarg.2
    IL_0037:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_003c:  ldc.i4     0x547
    IL_0041:  bne.un.s   IL_004f

    IL_0043:  ldarg.3
    IL_0044:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0049:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_004e:  ret

    IL_004f:  ldarg.3
    IL_0050:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_0055:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_005a:  ret

    IL_005b:  ldarg.2
    IL_005c:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_0061:  callvirt   instance string [Calibration]Calibration.ScannerSettingsFirmware::get_DX()
    IL_0066:  ldstr      "Boot"
    IL_006b:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_0070:  brtrue.s   IL_008a

    IL_0072:  ldarg.3
    IL_0073:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_0078:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_007d:  ldarg.s    cbDXBoardChange
    IL_007f:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_0084:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0089:  ret

    IL_008a:  ldarg.3
    IL_008b:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0090:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0095:  ldarg.s    cbDXBoardChange
    IL_0097:  callvirt   instance object [System.Windows.Forms]System.Windows.Forms.ComboBox::get_SelectedItem()
    IL_009c:  callvirt   instance string [mscorlib]System.Object::ToString()
    IL_00a1:  ldarg.3
    IL_00a2:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_00a7:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_00ac:  brfalse.s  IL_00bb

    IL_00ae:  ldarg.s    cbDXBoardChange
    IL_00b0:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_00b5:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00ba:  ret

    IL_00bb:  ldarg.s    cbDXBoardChange
    IL_00bd:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_00c2:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00c7:  ret
  } // end of method PTSFirmware::LoadDXBoardInformation

  .method public hidebysig instance void 
          LoadLampBoardInformation([Calibration]Calibration.Scanner csScanner,
                                   [Calibration]Calibration.ScannerSettings csScannerSettings,
                                   [System.Windows.Forms]System.Windows.Forms.TextBox tbLampBoard,
                                   [System.Windows.Forms]System.Windows.Forms.ComboBox cbLampBoardChange) cil managed
  {
    // Code size       162 (0xa2)
    .maxstack  5
    IL_0000:  ldarg.2
    IL_0001:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_0006:  ldarg.1
    IL_0007:  ldc.i4.3
    IL_0008:  ldarg.3
    IL_0009:  ldarg.s    cbLampBoardChange
    IL_000b:  callvirt   instance void [Calibration]Calibration.ScannerSettingsFirmware::GetFileInformation([Calibration]Calibration.Scanner,
                                                                                                            [Calibration]Calibration.ScannerFirmware,
                                                                                                            [System.Windows.Forms]System.Windows.Forms.TextBox,
                                                                                                            [System.Windows.Forms]System.Windows.Forms.ComboBox)
    IL_0010:  ldarg.3
    IL_0011:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0016:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_001b:  brtrue.s   IL_0035

    IL_001d:  ldarg.3
    IL_001e:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_0023:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0028:  ldarg.s    cbLampBoardChange
    IL_002a:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_002f:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0034:  ret

    IL_0035:  ldarg.2
    IL_0036:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_003b:  callvirt   instance string [Calibration]Calibration.ScannerSettingsFirmware::get_Lamp()
    IL_0040:  ldstr      "Boot"
    IL_0045:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_004a:  brtrue.s   IL_0064

    IL_004c:  ldarg.3
    IL_004d:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_0052:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0057:  ldarg.s    cbLampBoardChange
    IL_0059:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_005e:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0063:  ret

    IL_0064:  ldarg.3
    IL_0065:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_006a:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_006f:  ldarg.s    cbLampBoardChange
    IL_0071:  callvirt   instance object [System.Windows.Forms]System.Windows.Forms.ComboBox::get_SelectedItem()
    IL_0076:  callvirt   instance string [mscorlib]System.Object::ToString()
    IL_007b:  ldarg.3
    IL_007c:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0081:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_0086:  brfalse.s  IL_0095

    IL_0088:  ldarg.s    cbLampBoardChange
    IL_008a:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_008f:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0094:  ret

    IL_0095:  ldarg.s    cbLampBoardChange
    IL_0097:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_009c:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00a1:  ret
  } // end of method PTSFirmware::LoadLampBoardInformation

  .method public hidebysig instance void 
          LoadCCDBoardInformation([Calibration]Calibration.Scanner csScanner,
                                  [Calibration]Calibration.ScannerSettings csScannerSettings,
                                  [System.Windows.Forms]System.Windows.Forms.TextBox tbCCDBoard,
                                  [System.Windows.Forms]System.Windows.Forms.ComboBox cbCCDBoardChange) cil managed
  {
    // Code size       200 (0xc8)
    .maxstack  5
    IL_0000:  ldarg.2
    IL_0001:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_0006:  ldarg.1
    IL_0007:  ldc.i4.4
    IL_0008:  ldarg.3
    IL_0009:  ldarg.s    cbCCDBoardChange
    IL_000b:  callvirt   instance void [Calibration]Calibration.ScannerSettingsFirmware::GetFileInformation([Calibration]Calibration.Scanner,
                                                                                                            [Calibration]Calibration.ScannerFirmware,
                                                                                                            [System.Windows.Forms]System.Windows.Forms.TextBox,
                                                                                                            [System.Windows.Forms]System.Windows.Forms.ComboBox)
    IL_0010:  ldarg.3
    IL_0011:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0016:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_001b:  brtrue.s   IL_005b

    IL_001d:  ldarg.s    cbCCDBoardChange
    IL_001f:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0024:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0029:  ldarg.2
    IL_002a:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_002f:  ldc.i4     0x546
    IL_0034:  beq.s      IL_0043

    IL_0036:  ldarg.2
    IL_0037:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_003c:  ldc.i4     0x547
    IL_0041:  bne.un.s   IL_004f

    IL_0043:  ldarg.3
    IL_0044:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0049:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_004e:  ret

    IL_004f:  ldarg.3
    IL_0050:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_0055:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_005a:  ret

    IL_005b:  ldarg.2
    IL_005c:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_0061:  callvirt   instance string [Calibration]Calibration.ScannerSettingsFirmware::get_CCD()
    IL_0066:  ldstr      "Boot"
    IL_006b:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_0070:  brtrue.s   IL_008a

    IL_0072:  ldarg.3
    IL_0073:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_0078:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_007d:  ldarg.s    cbCCDBoardChange
    IL_007f:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_0084:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0089:  ret

    IL_008a:  ldarg.3
    IL_008b:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0090:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0095:  ldarg.s    cbCCDBoardChange
    IL_0097:  callvirt   instance object [System.Windows.Forms]System.Windows.Forms.ComboBox::get_SelectedItem()
    IL_009c:  callvirt   instance string [mscorlib]System.Object::ToString()
    IL_00a1:  ldarg.3
    IL_00a2:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_00a7:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_00ac:  brfalse.s  IL_00bb

    IL_00ae:  ldarg.s    cbCCDBoardChange
    IL_00b0:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_00b5:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00ba:  ret

    IL_00bb:  ldarg.s    cbCCDBoardChange
    IL_00bd:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_00c2:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00c7:  ret
  } // end of method PTSFirmware::LoadCCDBoardInformation

  .method public hidebysig instance void 
          LoadAPSBoardInformation([Calibration]Calibration.Scanner csScanner,
                                  [Calibration]Calibration.ScannerSettings csScannerSettings,
                                  [System.Windows.Forms]System.Windows.Forms.TextBox tbAPSBoard,
                                  [System.Windows.Forms]System.Windows.Forms.ComboBox cbAPSBoardChange) cil managed
  {
    // Code size       162 (0xa2)
    .maxstack  5
    IL_0000:  ldarg.2
    IL_0001:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_0006:  ldarg.1
    IL_0007:  ldc.i4.5
    IL_0008:  ldarg.3
    IL_0009:  ldarg.s    cbAPSBoardChange
    IL_000b:  callvirt   instance void [Calibration]Calibration.ScannerSettingsFirmware::GetFileInformation([Calibration]Calibration.Scanner,
                                                                                                            [Calibration]Calibration.ScannerFirmware,
                                                                                                            [System.Windows.Forms]System.Windows.Forms.TextBox,
                                                                                                            [System.Windows.Forms]System.Windows.Forms.ComboBox)
    IL_0010:  ldarg.3
    IL_0011:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0016:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_001b:  brtrue.s   IL_0035

    IL_001d:  ldarg.3
    IL_001e:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0023:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0028:  ldarg.s    cbAPSBoardChange
    IL_002a:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_002f:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0034:  ret

    IL_0035:  ldarg.2
    IL_0036:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_003b:  callvirt   instance string [Calibration]Calibration.ScannerSettingsFirmware::get_APS()
    IL_0040:  ldstr      "Boot"
    IL_0045:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_004a:  brtrue.s   IL_0064

    IL_004c:  ldarg.3
    IL_004d:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_0052:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0057:  ldarg.s    cbAPSBoardChange
    IL_0059:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_005e:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0063:  ret

    IL_0064:  ldarg.3
    IL_0065:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_006a:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_006f:  ldarg.s    cbAPSBoardChange
    IL_0071:  callvirt   instance object [System.Windows.Forms]System.Windows.Forms.ComboBox::get_SelectedItem()
    IL_0076:  callvirt   instance string [mscorlib]System.Object::ToString()
    IL_007b:  ldarg.3
    IL_007c:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0081:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_0086:  brfalse.s  IL_0095

    IL_0088:  ldarg.s    cbAPSBoardChange
    IL_008a:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_008f:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0094:  ret

    IL_0095:  ldarg.s    cbAPSBoardChange
    IL_0097:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_009c:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00a1:  ret
  } // end of method PTSFirmware::LoadAPSBoardInformation

  .method public hidebysig instance void 
          ValidateUSBBoardChange([Calibration]Calibration.Scanner csScanner,
                                 [Calibration]Calibration.ScannerSettings csScannerSettings,
                                 [System.Windows.Forms]System.Windows.Forms.TextBox tbUSBBoard,
                                 [System.Windows.Forms]System.Windows.Forms.ComboBox cbUSBBoardChange) cil managed
  {
    // Code size       51 (0x33)
    .maxstack  3
    IL_0000:  ldarg.s    cbUSBBoardChange
    IL_0002:  callvirt   instance object [System.Windows.Forms]System.Windows.Forms.ComboBox::get_SelectedItem()
    IL_0007:  callvirt   instance string [mscorlib]System.Object::ToString()
    IL_000c:  ldarg.3
    IL_000d:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0012:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_0017:  brfalse.s  IL_0026

    IL_0019:  ldarg.s    cbUSBBoardChange
    IL_001b:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_0020:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0025:  ret

    IL_0026:  ldarg.s    cbUSBBoardChange
    IL_0028:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_002d:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0032:  ret
  } // end of method PTSFirmware::ValidateUSBBoardChange

  .method public hidebysig instance void 
          ValidateHardwareVersion([Calibration]Calibration.Scanner csScanner,
                                  [Calibration]Calibration.ScannerSettings csScannerSettings,
                                  [System.Windows.Forms]System.Windows.Forms.TextBox tbHardwareVersion,
                                  [System.Windows.Forms]System.Windows.Forms.TextBox tbMotorBoard,
                                  [System.Windows.Forms]System.Windows.Forms.ComboBox cbMotorBoardChange) cil managed
  {
    // Code size       253 (0xfd)
    .maxstack  3
    .locals init (string V_0,
             string V_1,
             uint8 V_2)
    IL_0000:  ldarg.2
    IL_0001:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0006:  ldc.i4.7
    IL_0007:  beq.s      IL_0015

    IL_0009:  ldarg.2
    IL_000a:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_000f:  ldc.i4.8
    IL_0010:  bne.un     IL_00c9

    IL_0015:  ldarg.s    cbMotorBoardChange
    IL_0017:  callvirt   instance object [System.Windows.Forms]System.Windows.Forms.ComboBox::get_SelectedItem()
    IL_001c:  castclass  [mscorlib]System.String
    IL_0021:  stloc.0
    IL_0022:  ldloc.0
    IL_0023:  ldc.i4.2
    IL_0024:  ldc.i4.2
    IL_0025:  callvirt   instance string [mscorlib]System.String::Substring(int32,
                                                                            int32)
    IL_002a:  stloc.1
    IL_002b:  ldloc.1
    IL_002c:  ldc.i4.s   16
    IL_002e:  call       uint8 [mscorlib]System.Convert::ToByte(string,
                                                                int32)
    IL_0033:  stloc.2
    IL_0034:  ldarg.2
    IL_0035:  callvirt   instance [Pakon]Pakon.ScannerHW235 [Pakon]Pakon.ScannerSettings::get_Hardware235()
    IL_003a:  ldc.i4     0x3e8
    IL_003f:  beq.s      IL_004e

    IL_0041:  ldarg.2
    IL_0042:  callvirt   instance [Pakon]Pakon.ScannerHW235 [Pakon]Pakon.ScannerSettings::get_Hardware235()
    IL_0047:  ldc.i4     0x44c
    IL_004c:  bne.un.s   IL_0082

    IL_004e:  ldloc.2
    IL_004f:  ldc.i4.7
    IL_0050:  bgt.s      IL_006a

    IL_0052:  ldarg.s    cbMotorBoardChange
    IL_0054:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_0059:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_005e:  ldarg.3
    IL_005f:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_0064:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0069:  ret

    IL_006a:  ldarg.s    cbMotorBoardChange
    IL_006c:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_0071:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0076:  ldarg.3
    IL_0077:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_007c:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0081:  ret

    IL_0082:  ldarg.2
    IL_0083:  callvirt   instance [Pakon]Pakon.ScannerHW235 [Pakon]Pakon.ScannerSettings::get_Hardware235()
    IL_0088:  ldc.i4.3
    IL_0089:  beq.s      IL_0095

    IL_008b:  ldarg.2
    IL_008c:  callvirt   instance [Pakon]Pakon.ScannerHW235 [Pakon]Pakon.ScannerSettings::get_Hardware235()
    IL_0091:  ldc.i4.s   50
    IL_0093:  bne.un.s   IL_00fc

    IL_0095:  ldloc.2
    IL_0096:  ldc.i4.8
    IL_0097:  blt.s      IL_00b1

    IL_0099:  ldarg.s    cbMotorBoardChange
    IL_009b:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_00a0:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00a5:  ldarg.3
    IL_00a6:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_00ab:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00b0:  ret

    IL_00b1:  ldarg.s    cbMotorBoardChange
    IL_00b3:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_00b8:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00bd:  ldarg.3
    IL_00be:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_00c3:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00c8:  ret

    IL_00c9:  ldarg.s    cbMotorBoardChange
    IL_00cb:  callvirt   instance object [System.Windows.Forms]System.Windows.Forms.ComboBox::get_SelectedItem()
    IL_00d0:  callvirt   instance string [mscorlib]System.Object::ToString()
    IL_00d5:  ldarg.s    tbMotorBoard
    IL_00d7:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_00dc:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_00e1:  brfalse.s  IL_00f0

    IL_00e3:  ldarg.s    cbMotorBoardChange
    IL_00e5:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_00ea:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00ef:  ret

    IL_00f0:  ldarg.s    cbMotorBoardChange
    IL_00f2:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_00f7:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00fc:  ret
  } // end of method PTSFirmware::ValidateHardwareVersion

  .method public hidebysig instance void 
          ValidateDXBoardChange([Calibration]Calibration.Scanner csScanner,
                                [Calibration]Calibration.ScannerSettings csScannerSettings,
                                [System.Windows.Forms]System.Windows.Forms.TextBox tbDXBoard,
                                [System.Windows.Forms]System.Windows.Forms.ComboBox cbDXBoardChange) cil managed
  {
    // Code size       51 (0x33)
    .maxstack  3
    IL_0000:  ldarg.s    cbDXBoardChange
    IL_0002:  callvirt   instance object [System.Windows.Forms]System.Windows.Forms.ComboBox::get_SelectedItem()
    IL_0007:  callvirt   instance string [mscorlib]System.Object::ToString()
    IL_000c:  ldarg.3
    IL_000d:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0012:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_0017:  brfalse.s  IL_0026

    IL_0019:  ldarg.s    cbDXBoardChange
    IL_001b:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_0020:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0025:  ret

    IL_0026:  ldarg.s    cbDXBoardChange
    IL_0028:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_002d:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0032:  ret
  } // end of method PTSFirmware::ValidateDXBoardChange

  .method public hidebysig instance void 
          ValidateLampBoardChange([Calibration]Calibration.Scanner csScanner,
                                  [Calibration]Calibration.ScannerSettings csScannerSettings,
                                  [System.Windows.Forms]System.Windows.Forms.TextBox tbLampBoard,
                                  [System.Windows.Forms]System.Windows.Forms.ComboBox cbLampBoardChange) cil managed
  {
    // Code size       51 (0x33)
    .maxstack  3
    IL_0000:  ldarg.s    cbLampBoardChange
    IL_0002:  callvirt   instance object [System.Windows.Forms]System.Windows.Forms.ComboBox::get_SelectedItem()
    IL_0007:  callvirt   instance string [mscorlib]System.Object::ToString()
    IL_000c:  ldarg.3
    IL_000d:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0012:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_0017:  brfalse.s  IL_0026

    IL_0019:  ldarg.s    cbLampBoardChange
    IL_001b:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_0020:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0025:  ret

    IL_0026:  ldarg.s    cbLampBoardChange
    IL_0028:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_002d:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0032:  ret
  } // end of method PTSFirmware::ValidateLampBoardChange

  .method public hidebysig instance void 
          ValidateCCDBoardChange([Calibration]Calibration.Scanner csScanner,
                                 [Calibration]Calibration.ScannerSettings csScannerSettings,
                                 [System.Windows.Forms]System.Windows.Forms.TextBox tbCCDBoard,
                                 [System.Windows.Forms]System.Windows.Forms.ComboBox cbCCDBoardChange) cil managed
  {
    // Code size       51 (0x33)
    .maxstack  3
    IL_0000:  ldarg.s    cbCCDBoardChange
    IL_0002:  callvirt   instance object [System.Windows.Forms]System.Windows.Forms.ComboBox::get_SelectedItem()
    IL_0007:  callvirt   instance string [mscorlib]System.Object::ToString()
    IL_000c:  ldarg.3
    IL_000d:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0012:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_0017:  brfalse.s  IL_0026

    IL_0019:  ldarg.s    cbCCDBoardChange
    IL_001b:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_0020:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0025:  ret

    IL_0026:  ldarg.s    cbCCDBoardChange
    IL_0028:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_002d:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0032:  ret
  } // end of method PTSFirmware::ValidateCCDBoardChange

  .method public hidebysig instance void 
          ValidateScannerType([Calibration]Calibration.Scanner csScanner,
                              [Calibration]Calibration.ScannerSettings csScannerSettings,
                              [System.Windows.Forms]System.Windows.Forms.TextBox tbScannerType,
                              [System.Windows.Forms]System.Windows.Forms.TextBox tbAPSBoard,
                              [System.Windows.Forms]System.Windows.Forms.ComboBox cbAPSBoardChange) cil managed
  {
    // Code size       303 (0x12f)
    .maxstack  3
    IL_0000:  ldarg.2
    IL_0001:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0006:  ldc.i4.7
    IL_0007:  beq.s      IL_0016

    IL_0009:  ldarg.2
    IL_000a:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_000f:  ldc.i4     0xd16
    IL_0014:  bne.un.s   IL_0065

    IL_0016:  ldarg.2
    IL_0017:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_001c:  callvirt   instance string [Calibration]Calibration.ScannerSettingsFirmware::get_APS()
    IL_0021:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_0026:  brfalse.s  IL_004c

    IL_0028:  ldarg.3
    IL_0029:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_002e:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0033:  ldarg.s    cbAPSBoardChange
    IL_0035:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_003a:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_003f:  ldarg.s    tbAPSBoard
    IL_0041:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_0046:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_004b:  ret

    IL_004c:  ldarg.s    cbAPSBoardChange
    IL_004e:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0053:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0058:  ldarg.s    tbAPSBoard
    IL_005a:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_005f:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0064:  ret

    IL_0065:  ldarg.2
    IL_0066:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_006b:  ldc.i4.8
    IL_006c:  beq.s      IL_007e

    IL_006e:  ldarg.2
    IL_006f:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0074:  ldc.i4     0xd17
    IL_0079:  bne.un     IL_012e

    IL_007e:  ldarg.2
    IL_007f:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_0084:  callvirt   instance string [Calibration]Calibration.ScannerSettingsFirmware::get_APS()
    IL_0089:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_008e:  brtrue.s   IL_00a8

    IL_0090:  ldarg.s    cbAPSBoardChange
    IL_0092:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_0097:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_009c:  ldarg.3
    IL_009d:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_00a2:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00a7:  ret

    IL_00a8:  ldarg.2
    IL_00a9:  callvirt   instance [Calibration]Calibration.ScannerSettingsFirmware [Calibration]Calibration.ScannerSettings::get_Firmware()
    IL_00ae:  callvirt   instance string [Calibration]Calibration.ScannerSettingsFirmware::get_APS()
    IL_00b3:  ldstr      "Boot"
    IL_00b8:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_00bd:  brtrue.s   IL_00d8

    IL_00bf:  ldarg.s    tbAPSBoard
    IL_00c1:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_00c6:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00cb:  ldarg.s    cbAPSBoardChange
    IL_00cd:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_00d2:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00d7:  ret

    IL_00d8:  ldarg.s    cbAPSBoardChange
    IL_00da:  callvirt   instance object [System.Windows.Forms]System.Windows.Forms.ComboBox::get_SelectedItem()
    IL_00df:  callvirt   instance string [mscorlib]System.Object::ToString()
    IL_00e4:  ldarg.s    tbAPSBoard
    IL_00e6:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_00eb:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_00f0:  brfalse.s  IL_010b

    IL_00f2:  ldarg.s    cbAPSBoardChange
    IL_00f4:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_00f9:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00fe:  ldarg.s    tbAPSBoard
    IL_0100:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0105:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_010a:  ret

    IL_010b:  ldarg.3
    IL_010c:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0111:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0116:  ldarg.s    cbAPSBoardChange
    IL_0118:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Window()
    IL_011d:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_0122:  ldarg.s    tbAPSBoard
    IL_0124:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0129:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_012e:  ret
  } // end of method PTSFirmware::ValidateScannerType

  .event PTS.EnableActionUI m_evEnableActionUI
  {
    .addon instance void PTS.PTSFirmware::add_m_evEnableActionUI(class PTS.EnableActionUI)
    .removeon instance void PTS.PTSFirmware::remove_m_evEnableActionUI(class PTS.EnableActionUI)
  } // end of event PTSFirmware::m_evEnableActionUI
  .event PTS.ClearFirmwareUI m_evClearUI
  {
    .addon instance void PTS.PTSFirmware::add_m_evClearUI(class PTS.ClearFirmwareUI)
    .removeon instance void PTS.PTSFirmware::remove_m_evClearUI(class PTS.ClearFirmwareUI)
  } // end of event PTSFirmware::m_evClearUI
  .event PTS.RefreshFirmwareUI m_evRefreshUI
  {
    .addon instance void PTS.PTSFirmware::add_m_evRefreshUI(class PTS.RefreshFirmwareUI)
    .removeon instance void PTS.PTSFirmware::remove_m_evRefreshUI(class PTS.RefreshFirmwareUI)
  } // end of event PTSFirmware::m_evRefreshUI
  .event PTS.UpdateFirmwareUI m_evUpdateUI
  {
    .removeon instance void PTS.PTSFirmware::remove_m_evUpdateUI(class PTS.UpdateFirmwareUI)
    .addon instance void PTS.PTSFirmware::add_m_evUpdateUI(class PTS.UpdateFirmwareUI)
  } // end of event PTSFirmware::m_evUpdateUI
  .event PTS.GetNextFirmwareStore m_evGetNextFirmwareStore
  {
    .addon instance void PTS.PTSFirmware::add_m_evGetNextFirmwareStore(class PTS.GetNextFirmwareStore)
    .removeon instance void PTS.PTSFirmware::remove_m_evGetNextFirmwareStore(class PTS.GetNextFirmwareStore)
  } // end of event PTSFirmware::m_evGetNextFirmwareStore
  .property instance bool FullFeature()
  {
    .set instance void PTS.PTSFirmware::set_FullFeature(bool)
  } // end of property PTSFirmware::FullFeature
  .property instance valuetype PTS.FirmwareAction
          Action()
  {
    .get instance valuetype PTS.FirmwareAction PTS.PTSFirmware::get_Action()
  } // end of property PTSFirmware::Action
  .property instance valuetype PTS.FirmwareLoad
          Load()
  {
    .get instance valuetype PTS.FirmwareLoad PTS.PTSFirmware::get_Load()
  } // end of property PTSFirmware::Load
  .property instance valuetype PTS.FirmwareStore
          Store()
  {
    .get instance valuetype PTS.FirmwareStore PTS.PTSFirmware::get_Store()
  } // end of property PTSFirmware::Store
} // end of class PTS.PTSFirmware

