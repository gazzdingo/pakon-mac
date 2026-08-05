
// Metadata version: v1.1.4322
.assembly extern mscorlib
{
  .publickeytoken = (B7 7A 5C 56 19 34 E0 89 )                         // .z\V.4..
  .ver 1:0:5000:0
}
.assembly Interop.LLCLib
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 34 38 37 66 32 38 37 32 2D 38 37 35 33   // ..$487f2872-8753
                                                                                                  2D 34 64 39 34 2D 38 34 39 66 2D 31 35 63 30 39   // -4d94-849f-15c09
                                                                                                  31 39 61 66 36 61 34 00 00 )                      // 19af6a4..
  .custom instance void [mscorlib]System.Runtime.InteropServices.ImportedFromTypeLibAttribute::.ctor(string) = ( 01 00 06 4C 4C 43 4C 69 62 00 00 )                // ...LLCLib..
  .hash algorithm 0x00008004
  .ver 1:0:0:0
}
.module LLCLib.dll
// MVID: {F7F0CCBD-6D61-451A-8336-B166138B5290}
.imagebase 0x00400000
.file alignment 0x00000200
.stackreserve 0x00100000
.subsystem 0x0003       // WINDOWS_CUI
.corflags 0x00000001    //  ILONLY


// =============== CLASS MEMBERS DECLARATION ===================

.class public auto ansi import LLCLib.FWLoaderMainClass
       extends [mscorlib]System.Object
       implements LLCLib.IFWLoaderMain,
                  LLCLib.FWLoaderMain,
                  LLCLib.ILongOpsCB
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 34 34 33 41 43 32 39 37 2D 35 39 37 44   // ..$443AC297-597D
                                                                                                  2D 34 45 35 41 2D 39 35 46 44 2D 42 38 31 42 34   // -4E5A-95FD-B81B4
                                                                                                  46 30 34 33 44 31 45 00 00 )                      // F043D1E..
  .custom instance void [mscorlib]System.Runtime.InteropServices.ClassInterfaceAttribute::.ctor(int16) = ( 01 00 00 00 00 00 ) 
  .custom instance void [mscorlib]System.Runtime.InteropServices.TypeLibTypeAttribute::.ctor(int16) = ( 01 00 02 00 00 00 ) 
  .method public specialname rtspecialname 
          instance void  .ctor() runtime managed internalcall
  {
  } // end of method FWLoaderMainClass::.ctor

  .method public hidebysig newslot virtual 
          instance void  InitializeScanner() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 01 00 00 00 00 00 ) 
    .override LLCLib.IFWLoaderMain::InitializeScanner
  } // end of method FWLoaderMainClass::InitializeScanner

  .method public hidebysig newslot virtual 
          instance int32  GetAndClearLastError([in] int32 iShort_IID,
                                               [in][out] string&  marshal( bstr) pbstrError,
                                               [in][out] string&  marshal( bstr) pbstrErrorNumbers) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 02 00 00 00 00 00 ) 
    .override LLCLib.IFWLoaderMain::GetAndClearLastError
  } // end of method FWLoaderMainClass::GetAndClearLastError

  .method public hidebysig newslot virtual 
          instance void  FindPersonality([in][out] int32& piScannerModel,
                                         [in][out] int32& piPersonality,
                                         [in][out] int32& pbVerified) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 03 00 00 00 00 00 ) 
    .override LLCLib.IFWLoaderMain::FindPersonality
  } // end of method FWLoaderMainClass::FindPersonality

  .method public hidebysig newslot virtual 
          instance void  SetPersonality([in] int32 iPersonality) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 04 00 00 00 00 00 ) 
    .override LLCLib.IFWLoaderMain::SetPersonality
  } // end of method FWLoaderMainClass::SetPersonality

  .method public hidebysig newslot virtual 
          instance void  FirmwareAssess([in][out] int32& piInitializeWarnings0,
                                        [in][out] int32& piInitializeWarnings1,
                                        [in][out] int32& piScannerType,
                                        [in][out] int32& piScannerVersionHw,
                                        [in][out] int32& piScannerSerialNumber,
                                        [in][out] int32& piVersionHwUSB,
                                        [in][out] int32& piVersionHwLamp,
                                        [in][out] int32& piVersionHwCCD,
                                        [in][out] int32& piVersionHwDX,
                                        [in][out] int32& piVersionHwMotor,
                                        [in][out] int32& piVersionHwAps,
                                        [in][out] int32& piVersionSwUSB,
                                        [in][out] int32& piVersionSwLamp,
                                        [in][out] int32& piVersionSwCCD,
                                        [in][out] int32& piVersionSwDX,
                                        [in][out] int32& piVersionSwMotor,
                                        [in][out] int32& piVersionSwAps) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 05 00 00 00 00 00 ) 
    .override LLCLib.IFWLoaderMain::FirmwareAssess
  } // end of method FWLoaderMainClass::FirmwareAssess

  .method public hidebysig newslot virtual 
          instance void  LoadFirmware([in] int32 iPicIndex,
                                      [in] string  marshal( bstr) bstrFirmwareFileName,
                                      [in] int32 bVerifyOnly) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 06 00 00 00 00 00 ) 
    .override LLCLib.IFWLoaderMain::LoadFirmware
  } // end of method FWLoaderMainClass::LoadFirmware

  .method public hidebysig newslot virtual 
          instance void  CancelFirmware() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 07 00 00 00 00 00 ) 
    .override LLCLib.IFWLoaderMain::CancelFirmware
  } // end of method FWLoaderMainClass::CancelFirmware

  .method public hidebysig newslot virtual 
          instance void  DriveMotorRun([in] int32 iSpeedPercent) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 08 00 00 00 00 00 ) 
    .override LLCLib.IFWLoaderMain::DriveMotorRun
  } // end of method FWLoaderMainClass::DriveMotorRun

  .method public hidebysig newslot virtual 
          instance void  ReleasePressureRollers() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 09 00 00 00 00 00 ) 
    .override LLCLib.IFWLoaderMain::ReleasePressureRollers
  } // end of method FWLoaderMainClass::ReleasePressureRollers

  .method public hidebysig newslot virtual 
          instance void  MoveFilmGuides([in] int32 b24mm) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0A 00 00 00 00 00 ) 
    .override LLCLib.IFWLoaderMain::MoveFilmGuides
  } // end of method FWLoaderMainClass::MoveFilmGuides

  .method public hidebysig newslot virtual 
          instance void  EraseEEPROM() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0B 00 00 00 00 00 ) 
    .override LLCLib.IFWLoaderMain::EraseEEPROM
  } // end of method FWLoaderMainClass::EraseEEPROM

  .method public hidebysig newslot virtual 
          instance void  CalibrationDotNet([in] valuetype LLCLib.ERROR_CODES_000 Unused1,
                                           [in] valuetype LLCLib.WORKER_THREAD_OPERATION_000 Unused2,
                                           [in] valuetype LLCLib.WORKER_THREAD_PROGRESS_000 Unused3,
                                           [in] valuetype LLCLib.FILM_FORMAT_000 Unused4,
                                           [in] valuetype LLCLib.RESOLUTION_000 Unused5,
                                           [in] valuetype LLCLib.INITIALIZE_WARNINGS_000 Unused6,
                                           [in] valuetype LLCLib.FACTORY_RESET_CONTROL_000 Unused7,
                                           [in] valuetype LLCLib.INT_IID_000 Unused8,
                                           [in] valuetype LLCLib.SCANNER_MODEL_000 Unused9,
                                           [in] valuetype LLCLib.PERSONALITY_000 Unused10,
                                           [in] valuetype LLCLib.PIC_000 Unused11,
                                           [in] valuetype LLCLib.PIC_VERSION_000 Unused12) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0C 00 00 00 00 00 ) 
    .override LLCLib.IFWLoaderMain::CalibrationDotNet
  } // end of method FWLoaderMainClass::CalibrationDotNet

  .method public hidebysig newslot virtual 
          instance int32  CBAdvise([in] class LLCLib.ICallBackClient  marshal( interface ) pICallBackClient) runtime managed internalcall
  {
    .override LLCLib.ILongOpsCB::CBAdvise
  } // end of method FWLoaderMainClass::CBAdvise

  .method public hidebysig newslot virtual 
          instance void  CBUnadvise([in] int32 lCookie) runtime managed internalcall
  {
    .override LLCLib.ILongOpsCB::CBUnadvise
  } // end of method FWLoaderMainClass::CBUnadvise

  .method public hidebysig newslot virtual 
          instance void  CBHelperNTS([in] int32 lOperation,
                                     [in] int32 lStatus) runtime managed internalcall
  {
    .override LLCLib.ILongOpsCB::CBHelperNTS
  } // end of method FWLoaderMainClass::CBHelperNTS

} // end of class LLCLib.FWLoaderMainClass

.class interface public abstract auto ansi import LLCLib.FWLoaderMain
       implements LLCLib.IFWLoaderMain
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 46 43 38 42 31 46 46 45 2D 42 37 39 30   // ..$FC8B1FFE-B790
                                                                                                  2D 34 42 32 35 2D 41 38 42 46 2D 32 30 37 33 39   // -4B25-A8BF-20739
                                                                                                  41 30 32 38 44 34 45 00 00 )                      // A028D4E..
  .custom instance void [mscorlib]System.Runtime.InteropServices.CoClassAttribute::.ctor([mscorlib]System.Type) = ( 01 00 18 4C 4C 43 4C 69 62 2E 46 57 4C 6F 61 64   // ...LLCLib.FWLoad
                                                                                                                    65 72 4D 61 69 6E 43 6C 61 73 73 00 00 )          // erMainClass..
} // end of class LLCLib.FWLoaderMain

.class interface public abstract auto ansi import LLCLib.IFWLoaderMain
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 46 43 38 42 31 46 46 45 2D 42 37 39 30   // ..$FC8B1FFE-B790
                                                                                                  2D 34 42 32 35 2D 41 38 42 46 2D 32 30 37 33 39   // -4B25-A8BF-20739
                                                                                                  41 30 32 38 44 34 45 00 00 )                      // A028D4E..
  .custom instance void [mscorlib]System.Runtime.InteropServices.TypeLibTypeAttribute::.ctor(int16) = ( 01 00 C0 10 00 00 ) 
  .method public hidebysig newslot abstract virtual 
          instance void  InitializeScanner() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 01 00 00 00 00 00 ) 
  } // end of method IFWLoaderMain::InitializeScanner

  .method public hidebysig newslot abstract virtual 
          instance int32  GetAndClearLastError([in] int32 iShort_IID,
                                               [in][out] string&  marshal( bstr) pbstrError,
                                               [in][out] string&  marshal( bstr) pbstrErrorNumbers) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 02 00 00 00 00 00 ) 
  } // end of method IFWLoaderMain::GetAndClearLastError

  .method public hidebysig newslot abstract virtual 
          instance void  FindPersonality([in][out] int32& piScannerModel,
                                         [in][out] int32& piPersonality,
                                         [in][out] int32& pbVerified) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 03 00 00 00 00 00 ) 
  } // end of method IFWLoaderMain::FindPersonality

  .method public hidebysig newslot abstract virtual 
          instance void  SetPersonality([in] int32 iPersonality) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 04 00 00 00 00 00 ) 
  } // end of method IFWLoaderMain::SetPersonality

  .method public hidebysig newslot abstract virtual 
          instance void  FirmwareAssess([in][out] int32& piInitializeWarnings0,
                                        [in][out] int32& piInitializeWarnings1,
                                        [in][out] int32& piScannerType,
                                        [in][out] int32& piScannerVersionHw,
                                        [in][out] int32& piScannerSerialNumber,
                                        [in][out] int32& piVersionHwUSB,
                                        [in][out] int32& piVersionHwLamp,
                                        [in][out] int32& piVersionHwCCD,
                                        [in][out] int32& piVersionHwDX,
                                        [in][out] int32& piVersionHwMotor,
                                        [in][out] int32& piVersionHwAps,
                                        [in][out] int32& piVersionSwUSB,
                                        [in][out] int32& piVersionSwLamp,
                                        [in][out] int32& piVersionSwCCD,
                                        [in][out] int32& piVersionSwDX,
                                        [in][out] int32& piVersionSwMotor,
                                        [in][out] int32& piVersionSwAps) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 05 00 00 00 00 00 ) 
  } // end of method IFWLoaderMain::FirmwareAssess

  .method public hidebysig newslot abstract virtual 
          instance void  LoadFirmware([in] int32 iPicIndex,
                                      [in] string  marshal( bstr) bstrFirmwareFileName,
                                      [in] int32 bVerifyOnly) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 06 00 00 00 00 00 ) 
  } // end of method IFWLoaderMain::LoadFirmware

  .method public hidebysig newslot abstract virtual 
          instance void  CancelFirmware() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 07 00 00 00 00 00 ) 
  } // end of method IFWLoaderMain::CancelFirmware

  .method public hidebysig newslot abstract virtual 
          instance void  DriveMotorRun([in] int32 iSpeedPercent) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 08 00 00 00 00 00 ) 
  } // end of method IFWLoaderMain::DriveMotorRun

  .method public hidebysig newslot abstract virtual 
          instance void  ReleasePressureRollers() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 09 00 00 00 00 00 ) 
  } // end of method IFWLoaderMain::ReleasePressureRollers

  .method public hidebysig newslot abstract virtual 
          instance void  MoveFilmGuides([in] int32 b24mm) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0A 00 00 00 00 00 ) 
  } // end of method IFWLoaderMain::MoveFilmGuides

  .method public hidebysig newslot abstract virtual 
          instance void  EraseEEPROM() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0B 00 00 00 00 00 ) 
  } // end of method IFWLoaderMain::EraseEEPROM

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationDotNet([in] valuetype LLCLib.ERROR_CODES_000 Unused1,
                                           [in] valuetype LLCLib.WORKER_THREAD_OPERATION_000 Unused2,
                                           [in] valuetype LLCLib.WORKER_THREAD_PROGRESS_000 Unused3,
                                           [in] valuetype LLCLib.FILM_FORMAT_000 Unused4,
                                           [in] valuetype LLCLib.RESOLUTION_000 Unused5,
                                           [in] valuetype LLCLib.INITIALIZE_WARNINGS_000 Unused6,
                                           [in] valuetype LLCLib.FACTORY_RESET_CONTROL_000 Unused7,
                                           [in] valuetype LLCLib.INT_IID_000 Unused8,
                                           [in] valuetype LLCLib.SCANNER_MODEL_000 Unused9,
                                           [in] valuetype LLCLib.PERSONALITY_000 Unused10,
                                           [in] valuetype LLCLib.PIC_000 Unused11,
                                           [in] valuetype LLCLib.PIC_VERSION_000 Unused12) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0C 00 00 00 00 00 ) 
  } // end of method IFWLoaderMain::CalibrationDotNet

} // end of class LLCLib.IFWLoaderMain

.class public auto ansi sealed LLCLib.ERROR_CODES_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 35 36 35 38 44 30 36 30 2D 30 37 37 41   // ..$5658D060-077A
                                                                                                  2D 34 46 44 36 2D 41 42 31 46 2D 30 32 42 43 36   // -4FD6-AB1F-02BC6
                                                                                                  36 34 45 32 45 44 38 00 00 )                      // 64E2ED8..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_InvalidPtrToClientCallback = int32(0x00000001)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WorkerThreadExists = int32(0x00000002)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_QueryInterface = int32(0x00000003)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_CoMarshalInterThreadInterfaceInStream = int32(0x00000004)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_UnableToCreateWorkerThread = int32(0x00000005)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WorkerThreadCoInitialize = int32(0x00000006)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WorkerThreadCoGetInterfaceAndReleaseStream = int32(0x00000007)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WorkerThreadClientSignal = int32(0x00000008)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WorkerThreadStartTimeout = int32(0x00000009)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_InvalidIndex = int32(0x0000000A)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_InvalidMemberVariable = int32(0x0000000B)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_InvalidParameter = int32(0x0000000C)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_CBAdviseAlreadyCalled = int32(0x0000000D)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_CBAdviseNotCalled = int32(0x0000000E)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_InitializeScannerAlreadyCalled = int32(0x0000000F)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_PreviousError = int32(0x00000010)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_CreateDirectoryInvalidForm = int32(0x00000064)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_EEPromAddress = int32(0x00000065)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_EEPromCorrupted = int32(0x00000066)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_EEPromLength = int32(0x00000067)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_EEPromMemoryAddress = int32(0x00000068)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_EEPromWarningBlank = int32(0x00000069)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_EEPromWarningCheckSumBad = int32(0x0000006A)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_FileCorrupted = int32(0x0000006B)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_FileNotFound = int32(0x0000006C)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_FirmwareFilesNotFound = int32(0x0000006D)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_FirmwareVerification = int32(0x0000006E)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_LogHardwareString = int32(0x0000006F)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_MemoryNew = int32(0x00000070)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_MotorBoardNotFound = int32(0x00000071)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_NoBootLoader = int32(0x00000072)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_ParsingError = int32(0x00000073)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_PpbFailure = int32(0x00000074)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_PpbFailureTest = int32(0x00000075)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_ReadRegistry = int32(0x00000076)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_ScannerNotFound = int32(0x00000077)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_SelfTestFailedCcdStepper = int32(0x00000078)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_SelfTestFailedFilmDrive = int32(0x00000079)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_SelfTestFailedLensStepper = int32(0x0000007A)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_StartUpError = int32(0x0000007B)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_StepperAlreadyMoving = int32(0x0000007C)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_StepperDidNotStop = int32(0x0000007D)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_StepperPosition = int32(0x0000007E)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_TimeOut = int32(0x0000007F)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_UuidCreate = int32(0x00000080)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_VerifyFailed = int32(0x00000081)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WrongByteCount = int32(0x00000082)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_CancelIo = int32(0x00000083)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_CreateDirectory = int32(0x00000084)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_CreateEvent = int32(0x00000085)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_CreateFileMapping = int32(0x00000086)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_DeviceIoControl = int32(0x00000087)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_FileClose = int32(0x00000088)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_FileOpen = int32(0x00000089)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_FileRead = int32(0x0000008A)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_FileSetPointer = int32(0x0000008B)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_FileTimeToSystemTime = int32(0x0000008C)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_FileWrite = int32(0x0000008D)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_FindFirstFile = int32(0x0000008E)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_FreeLibrary = int32(0x0000008F)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_GetDiskFreeSpace = int32(0x00000090)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_GetDiskFreeSpaceEx = int32(0x00000091)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_GetFileSize = int32(0x00000092)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_GetOverlappedResult = int32(0x00000093)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_GetProcessWorkingSetSize = int32(0x00000094)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_LoadLibrary = int32(0x00000095)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_MapViewOfFile = int32(0x00000096)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_OpenEvent = int32(0x00000097)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_OpenFileMapping = int32(0x00000098)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_ResetEvent = int32(0x00000099)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_SetEndOfFile = int32(0x0000009A)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_SetEvent = int32(0x0000009B)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_SetFilePointerEx = int32(0x0000009C)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_SetProcessWorkingSetSize = int32(0x0000009D)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_UnmapViewOfFile = int32(0x0000009E)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_VirtualAlloc = int32(0x0000009F)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_VirtualFree = int32(0x000000A0)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_VirtualLock = int32(0x000000A1)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_VirtualUnlock = int32(0x000000A2)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_WIN_WaitForSingleObject = int32(0x000000A3)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_Unknown = int32(0x000003E8)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_CannotFindStartOfScanLine = int32(0x000003E9)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_RingTailOverflow = int32(0x000003EA)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_LostSync = int32(0x000003EB)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_InvalidPacketType = int32(0x000003EC)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketBusy = int32(0x000003ED)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_FifoOverflow = int32(0x000003EE)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketChecksumErr = int32(0x000003EF)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketOverFlowErr = int32(0x000003F0)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketCommErr = int32(0x000003F1)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketCmdErr = int32(0x000003F2)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketHostErrorNoAck = int32(0x000003F3)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketHostErrorFormat = int32(0x000003F4)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketHostErrorCkSum = int32(0x000003F5)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketHostErrorEndPointFormat = int32(0x000003F6)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketHostErrorEndPointTimeOut = int32(0x000003F7)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketHostErrorEndPointLength = int32(0x000003F8)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketHostErrorAlgo = int32(0x000003F9)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketHostErrorBus = int32(0x000003FA)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketHostErrorUndefined = int32(0x000003FB)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_PacketReadWriteMismatch = int32(0x000003FC)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_InfoBufferString = int32(0x000003FD)
  .field public static literal valuetype LLCLib.ERROR_CODES_000 EC_DRV_TransferInProgress = int32(0x000003FE)
} // end of class LLCLib.ERROR_CODES_000

.class public auto ansi sealed LLCLib.WORKER_THREAD_OPERATION_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 42 42 46 45 46 46 35 45 2D 34 44 44 31   // ..$BBFEFF5E-4DD1
                                                                                                  2D 34 35 42 36 2D 38 36 31 45 2D 41 30 38 38 31   // -45B6-861E-A0881
                                                                                                  32 33 46 32 33 45 32 00 00 )                      // 23F23E2..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_InitializeProgress = int32(0x00000000)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_InitializeError = int32(0x00000001)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateApsProgress = int32(0x00000002)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateApsError = int32(0x00000003)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateCcdProgress = int32(0x00000004)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateCcdError = int32(0x00000005)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateDxProgress = int32(0x00000006)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateDxError = int32(0x00000007)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateLampProgress = int32(0x00000008)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateLampError = int32(0x00000009)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateMotorProgress = int32(0x0000000A)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateMotorError = int32(0x0000000B)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_HardwareProgress = int32(0x0000000C)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_HardwareError = int32(0x0000000D)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_ExerciseSteppersProgress = int32(0x0000000E)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_ExerciseSteppersError = int32(0x0000000F)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_LampWarmUpProgress = int32(0x00000010)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_LampWarmUpError = int32(0x00000011)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_AdvanceFilmProgress = int32(0x00000012)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_AdvanceFilmError = int32(0x00000013)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_PutFilmGuidePositionProgress = int32(0x00000014)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_PutFilmGuidePositionError = int32(0x00000015)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_PutFilmPressureRollersPositionProgress = int32(0x00000016)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_PutFilmPressureRollersPositionError = int32(0x00000017)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_ScanProgress = int32(0x00000018)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_ScanError = int32(0x00000019)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_LLCProgress = int32(0x0000001A)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_LLCError = int32(0x0000001B)
  .field public static literal valuetype LLCLib.WORKER_THREAD_OPERATION_000 WTO_Last = int32(0x0000001B)
} // end of class LLCLib.WORKER_THREAD_OPERATION_000

.class public auto ansi sealed LLCLib.WORKER_THREAD_PROGRESS_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 31 35 31 44 42 30 39 30 2D 38 37 38 45   // ..$151DB090-878E
                                                                                                  2D 34 31 33 32 2D 41 31 39 45 2D 39 31 30 31 30   // -4132-A19E-91010
                                                                                                  39 42 32 41 41 41 37 00 00 )                      // 9B2AAA7..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype LLCLib.WORKER_THREAD_PROGRESS_000 WTP_Initialize = int32(0x00000000)
  .field public static literal valuetype LLCLib.WORKER_THREAD_PROGRESS_000 WTP_ProgressStart = int32(0x000003E8)
  .field public static literal valuetype LLCLib.WORKER_THREAD_PROGRESS_000 WTP_ProgressEnd = int32(0x000007D0)
  .field public static literal valuetype LLCLib.WORKER_THREAD_PROGRESS_000 WTP_ProgressComplete = int32(0x00000BB8)
} // end of class LLCLib.WORKER_THREAD_PROGRESS_000

.class public auto ansi sealed LLCLib.FILM_FORMAT_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 42 43 33 31 31 32 46 32 2D 43 33 42 39   // ..$BC3112F2-C3B9
                                                                                                  2D 34 36 30 42 2D 42 37 33 35 2D 43 34 43 31 45   // -460B-B735-C4C1E
                                                                                                  38 42 32 39 42 43 44 00 00 )                      // 8B29BCD..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype LLCLib.FILM_FORMAT_000 FILM_FORMAT_INDETERMINATE = int32(0xFFFFFFFF)
  .field public static literal valuetype LLCLib.FILM_FORMAT_000 FILM_FORMAT_24MM = int32(0x00000000)
  .field public static literal valuetype LLCLib.FILM_FORMAT_000 FILM_FORMAT_35MM = int32(0x00000001)
} // end of class LLCLib.FILM_FORMAT_000

.class public auto ansi sealed LLCLib.RESOLUTION_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 45 37 38 30 45 39 32 37 2D 32 43 41 30   // ..$E780E927-2CA0
                                                                                                  2D 34 41 36 35 2D 42 30 34 41 2D 41 38 42 32 33   // -4A65-B04A-A8B23
                                                                                                  30 39 34 36 42 30 32 00 00 )                      // 0946B02..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype LLCLib.RESOLUTION_000 RESOLUTION_BASE_4 = int32(0x00000000)
  .field public static literal valuetype LLCLib.RESOLUTION_000 RESOLUTION_BASE_8 = int32(0x00000001)
  .field public static literal valuetype LLCLib.RESOLUTION_000 RESOLUTION_BASE_16 = int32(0x00000002)
} // end of class LLCLib.RESOLUTION_000

.class public auto ansi sealed LLCLib.INITIALIZE_WARNINGS_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 35 42 41 31 31 43 45 31 2D 35 38 46 46   // ..$5BA11CE1-58FF
                                                                                                  2D 34 34 31 38 2D 42 33 36 44 2D 31 32 43 41 30   // -4418-B36D-12CA0
                                                                                                  36 36 34 35 45 39 34 00 00 )                      // 6645E94..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype LLCLib.INITIALIZE_WARNINGS_000 INITIALIZEW_NONE = int32(0x00000000)
  .field public static literal valuetype LLCLib.INITIALIZE_WARNINGS_000 INITIALIZEW_EEPROM_BLANK = int32(0x00000001)
  .field public static literal valuetype LLCLib.INITIALIZE_WARNINGS_000 INITIALIZEW_EEPROM_CHECKSUM_BAD = int32(0x00000002)
} // end of class LLCLib.INITIALIZE_WARNINGS_000

.class public auto ansi sealed LLCLib.FACTORY_RESET_CONTROL_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 44 39 45 41 33 30 33 30 2D 34 44 38 32   // ..$D9EA3030-4D82
                                                                                                  2D 34 42 30 39 2D 38 39 44 33 2D 35 32 45 35 37   // -4B09-89D3-52E57
                                                                                                  33 31 34 31 32 33 39 00 00 )                      // 3141239..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype LLCLib.FACTORY_RESET_CONTROL_000 FACTORY_RESET_Focus = int32(0x00000001)
  .field public static literal valuetype LLCLib.FACTORY_RESET_CONTROL_000 FACTORY_RESET_MotorSpeed = int32(0x00000002)
} // end of class LLCLib.FACTORY_RESET_CONTROL_000

.class public auto ansi sealed LLCLib.INT_IID_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 38 34 30 43 34 42 42 34 2D 31 30 34 39   // ..$840C4BB4-1049
                                                                                                  2D 34 43 37 34 2D 39 37 34 39 2D 32 46 33 30 45   // -4C74-9749-2F30E
                                                                                                  31 36 39 44 43 46 38 00 00 )                      // 169DCF8..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype LLCLib.INT_IID_000 INT_IID_IFWLoaderMain = int32(0x00000000)
} // end of class LLCLib.INT_IID_000

.class public auto ansi sealed LLCLib.SCANNER_MODEL_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 31 31 39 34 42 32 34 30 2D 30 39 44 32   // ..$1194B240-09D2
                                                                                                  2D 34 31 45 32 2D 38 31 36 44 2D 45 35 31 43 34   // -41E2-816D-E51C4
                                                                                                  36 30 36 41 41 38 36 00 00 )                      // 606AA86..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype LLCLib.SCANNER_MODEL_000 iSCANNER_MODEL_F235 = int32(0x00000000)
  .field public static literal valuetype LLCLib.SCANNER_MODEL_000 iSCANNER_MODEL_F135_PLUS = int32(0x00000001)
  .field public static literal valuetype LLCLib.SCANNER_MODEL_000 iSCANNER_MODEL_F335 = int32(0x00000002)
  .field public static literal valuetype LLCLib.SCANNER_MODEL_000 iSCANNER_MODEL_F135 = int32(0x00000003)
  .field public static literal valuetype LLCLib.SCANNER_MODEL_000 iSCANNER_MODEL_COUNT = int32(0x00000004)
} // end of class LLCLib.SCANNER_MODEL_000

.class public auto ansi sealed LLCLib.PERSONALITY_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 43 33 35 44 44 35 30 36 2D 36 41 41 39   // ..$C35DD506-6AA9
                                                                                                  2D 34 42 43 32 2D 42 35 37 34 2D 36 45 41 33 38   // -4BC2-B574-6EA38
                                                                                                  45 31 38 39 39 34 39 00 00 )                      // E189949..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype LLCLib.PERSONALITY_000 iPERSONALITY_INVALID = int32(0xFFFFFFFF)
  .field public static literal valuetype LLCLib.PERSONALITY_000 iPERSONALITY_F235_FIFO = int32(0x00000000)
  .field public static literal valuetype LLCLib.PERSONALITY_000 iPERSONALITY_F235_DDR = int32(0x00000001)
  .field public static literal valuetype LLCLib.PERSONALITY_000 iPERSONALITY_F135 = int32(0x00000002)
  .field public static literal valuetype LLCLib.PERSONALITY_000 iPERSONALITY_F335 = int32(0x00000003)
  .field public static literal valuetype LLCLib.PERSONALITY_000 iPERSONALITY_COUNT = int32(0x00000004)
} // end of class LLCLib.PERSONALITY_000

.class public auto ansi sealed LLCLib.PIC_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 37 33 36 30 37 41 46 30 2D 35 35 46 35   // ..$73607AF0-55F5
                                                                                                  2D 34 30 41 36 2D 39 38 32 39 2D 46 44 46 39 46   // -40A6-9829-FDF9F
                                                                                                  42 37 41 36 30 46 45 00 00 )                      // B7A60FE..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype LLCLib.PIC_000 iPIC_MOTOR = int32(0x00000000)
  .field public static literal valuetype LLCLib.PIC_000 iPIC_LAMP = int32(0x00000001)
  .field public static literal valuetype LLCLib.PIC_000 iPIC_CCD = int32(0x00000002)
  .field public static literal valuetype LLCLib.PIC_000 iPIC_DX = int32(0x00000003)
  .field public static literal valuetype LLCLib.PIC_000 iPIC_APS = int32(0x00000004)
  .field public static literal valuetype LLCLib.PIC_000 iPIC_COUNT = int32(0x00000005)
  .field public static literal valuetype LLCLib.PIC_000 iPIC_COUNT_F135 = int32(0x00000002)
} // end of class LLCLib.PIC_000

.class public auto ansi sealed LLCLib.PIC_VERSION_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 38 43 38 36 30 42 32 46 2D 38 43 31 34   // ..$8C860B2F-8C14
                                                                                                  2D 34 36 37 32 2D 38 36 36 46 2D 45 37 36 36 32   // -4672-866F-E7662
                                                                                                  36 34 31 30 31 45 45 00 00 )                      // 64101EE..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype LLCLib.PIC_VERSION_000 iPIC_VERSION_INIT = int32(0x00001000)
  .field public static literal valuetype LLCLib.PIC_VERSION_000 iPIC_VERSION_BOOT_FOUND = int32(0x00001001)
  .field public static literal valuetype LLCLib.PIC_VERSION_000 iPIC_VERSION_BOOT_16_FOUND = int32(0x00001002)
  .field public static literal valuetype LLCLib.PIC_VERSION_000 iPIC_VERSION_PROGRAM_FOUND = int32(0x00001003)
} // end of class LLCLib.PIC_VERSION_000

.class interface public abstract auto ansi import LLCLib.ILongOpsCB
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 44 41 42 46 41 41 38 46 2D 45 42 39 43   // ..$DABFAA8F-EB9C
                                                                                                  2D 34 37 32 32 2D 39 32 46 32 2D 32 37 36 34 34   // -4722-92F2-27644
                                                                                                  41 44 38 45 43 44 34 00 00 )                      // AD8ECD4..
  .custom instance void [mscorlib]System.Runtime.InteropServices.InterfaceTypeAttribute::.ctor(int16) = ( 01 00 01 00 00 00 ) 
  .method public hidebysig newslot abstract virtual 
          instance int32  CBAdvise([in] class LLCLib.ICallBackClient  marshal( interface ) pICallBackClient) runtime managed internalcall
  {
  } // end of method ILongOpsCB::CBAdvise

  .method public hidebysig newslot abstract virtual 
          instance void  CBUnadvise([in] int32 lCookie) runtime managed internalcall
  {
  } // end of method ILongOpsCB::CBUnadvise

  .method public hidebysig newslot abstract virtual 
          instance void  CBHelperNTS([in] int32 lOperation,
                                     [in] int32 lStatus) runtime managed internalcall
  {
  } // end of method ILongOpsCB::CBHelperNTS

} // end of class LLCLib.ILongOpsCB

.class interface public abstract auto ansi import LLCLib.ICallBackClient
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 34 33 43 32 31 35 38 37 2D 43 42 31 45   // ..$43C21587-CB1E
                                                                                                  2D 34 41 44 38 2D 42 36 41 35 2D 38 36 31 32 39   // -4AD8-B6A5-86129
                                                                                                  41 31 43 35 39 32 32 00 00 )                      // A1C5922..
  .custom instance void [mscorlib]System.Runtime.InteropServices.InterfaceTypeAttribute::.ctor(int16) = ( 01 00 01 00 00 00 ) 
  .method public hidebysig newslot abstract virtual 
          instance void  Awake([in] int32 lOperation,
                               [in] int32 lStatus) runtime managed internalcall
  {
  } // end of method ICallBackClient::Awake

} // end of class LLCLib.ICallBackClient


// =============================================================

// *********** DISASSEMBLY COMPLETE ***********************
