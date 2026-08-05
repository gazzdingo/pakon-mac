
// Metadata version: v1.1.4322
.assembly extern mscorlib
{
  .publickeytoken = (B7 7A 5C 56 19 34 E0 89 )                         // .z\V.4..
  .ver 1:0:5000:0
}
.assembly Interop.TLXLib
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 64 65 61 65 32 31 63 37 2D 66 31 66 66   // ..$deae21c7-f1ff
                                                                                                  2D 34 30 37 65 2D 62 63 32 38 2D 66 39 30 37 61   // -407e-bc28-f907a
                                                                                                  32 65 32 38 32 31 61 00 00 )                      // 2e2821a..
  .custom instance void [mscorlib]System.Runtime.InteropServices.ImportedFromTypeLibAttribute::.ctor(string) = ( 01 00 06 54 4C 58 4C 69 62 00 00 )                // ...TLXLib..
  .hash algorithm 0x00008004
  .ver 1:1:0:0
}
.module TLXLib.dll
// MVID: {54882177-6590-4F00-9337-FAF8D3CDFDA0}
.imagebase 0x00400000
.file alignment 0x00001000
.stackreserve 0x00100000
.subsystem 0x0003       // WINDOWS_CUI
.corflags 0x00000001    //  ILONLY


// =============== CLASS MEMBERS DECLARATION ===================

.class interface public abstract auto ansi import TLXLib._ITLXMainEvents
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.InterfaceTypeAttribute::.ctor(int16) = ( 01 00 02 00 00 00 ) 
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 30 42 33 30 44 45 38 46 2D 46 44 46 41   // ..$0B30DE8F-FDFA
                                                                                                  2D 34 30 41 45 2D 38 35 44 46 2D 46 46 31 38 41   // -40AE-85DF-FF18A
                                                                                                  30 37 41 42 30 31 32 00 00 )                      // 07AB012..
  .custom instance void [mscorlib]System.Runtime.InteropServices.TypeLibTypeAttribute::.ctor(int16) = ( 01 00 00 10 00 00 ) 
} // end of class TLXLib._ITLXMainEvents

.class public auto ansi import TLXLib.TLXMainClass
       extends [mscorlib]System.Object
       implements TLXLib.ITLXMain,
                  TLXLib.TLXMain,
                  TLXLib._ITLXMainEvents_Event,
                  TLXLib.ILongOpsCB,
                  TLXLib.IScanPictures,
                  TLXLib.ISavePictures,
                  TLXLib.ISavePictures1,
                  TLXLib.IScanPictures2,
                  TLXLib.ISavePictures2,
                  TLXLib.ISavePictures3,
                  TLXLib.ICalibrationWizard
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 45 41 38 32 39 38 36 42 2D 45 34 37 43   // ..$EA82986B-E47C
                                                                                                  2D 34 43 30 46 2D 39 37 45 41 2D 46 42 35 30 45   // -4C0F-97EA-FB50E
                                                                                                  44 32 31 36 44 32 45 00 00 )                      // D216D2E..
  .custom instance void [mscorlib]System.Runtime.InteropServices.TypeLibTypeAttribute::.ctor(int16) = ( 01 00 02 00 00 00 ) 
  .custom instance void [mscorlib]System.Runtime.InteropServices.ComSourceInterfacesAttribute::.ctor(string) = ( 01 00 18 54 4C 58 4C 69 62 2E 5F 49 54 4C 58 4D   // ...TLXLib._ITLXM
                                                                                                                 61 69 6E 45 76 65 6E 74 73 00 00 00 00 )          // ainEvents....
  .custom instance void [mscorlib]System.Runtime.InteropServices.ClassInterfaceAttribute::.ctor(int16) = ( 01 00 00 00 00 00 ) 
  .method public specialname rtspecialname 
          instance void  .ctor() runtime managed internalcall
  {
  } // end of method TLXMainClass::.ctor

  .method public hidebysig newslot virtual 
          instance void  InitializeScanner([in] int32 iInitializeControl,
                                           [in] int32 iSaveToMemoryTimeout) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 01 00 00 00 00 00 ) 
    .override TLXLib.ITLXMain::InitializeScanner
  } // end of method TLXMainClass::InitializeScanner

  .method public hidebysig newslot virtual 
          instance int32  GetAndClearLastError([in] int32 iShort_IID,
                                               [in][out] string&  marshal( bstr) pbstrError,
                                               [in][out] string&  marshal( bstr) pbstrErrorNumbers) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 02 00 00 00 00 00 ) 
    .override TLXLib.ITLXMain::GetAndClearLastError
  } // end of method TLXMainClass::GetAndClearLastError

  .method public hidebysig newslot virtual 
          instance void  GetInitializeWarnings([in][out] int32& piInitializeWarnings) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 03 00 00 00 00 00 ) 
    .override TLXLib.ITLXMain::GetInitializeWarnings
  } // end of method TLXMainClass::GetInitializeWarnings

  .method public hidebysig newslot virtual 
          instance int32  CBAdvise([in] class TLXLib.ICallBackClient  marshal( interface ) pICallBackClient) runtime managed internalcall
  {
    .override TLXLib.ILongOpsCB::CBAdvise
  } // end of method TLXMainClass::CBAdvise

  .method public hidebysig newslot virtual 
          instance void  CBUnadvise([in] int32 lCookie) runtime managed internalcall
  {
    .override TLXLib.ILongOpsCB::CBUnadvise
  } // end of method TLXMainClass::CBUnadvise

  .method public hidebysig newslot virtual 
          instance void  CBHelperNTS([in] int32 lOperation,
                                     [in] int32 lStatus) runtime managed internalcall
  {
    .override TLXLib.ILongOpsCB::CBHelperNTS
  } // end of method TLXMainClass::CBHelperNTS

  .method public hidebysig newslot virtual 
          instance void  ForceCorrections([in] int32 iResolution,
                                          [in] int32 iFilmColor,
                                          [in] int32 iFilmFormat,
                                          [in] int32 iCalibrateControl) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::ForceCorrections
  } // end of method TLXMainClass::ForceCorrections

  .method public hidebysig newslot virtual 
          instance void  ForceDiagnostics() runtime managed internalcall
  {
    .override TLXLib.IScanPictures::ForceDiagnostics
  } // end of method TLXMainClass::ForceDiagnostics

  .method public hidebysig newslot virtual 
          instance void  FilmTrackTest([in] int32 bDxPotsAdjust,
                                       [in] int32 iFilmFormat) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::FilmTrackTest
  } // end of method TLXMainClass::FilmTrackTest

  .method public hidebysig newslot virtual 
          instance int32  FilmTrackTestResults() runtime managed internalcall
  {
    .override TLXLib.IScanPictures::FilmTrackTestResults
  } // end of method TLXMainClass::FilmTrackTestResults

  .method public hidebysig newslot virtual 
          instance void  ScanPictures([in] int32 iResolution,
                                      [in] int32 iFilmColor,
                                      [in] int32 iFilmFormat,
                                      [in] int32 iStripMode,
                                      [in] int32 iScanControl,
                                      [in] string  marshal( bstr) bstrRollId) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::ScanPictures
  } // end of method TLXMainClass::ScanPictures

  .method public hidebysig newslot virtual 
          instance void  ScanCancel() runtime managed internalcall
  {
    .override TLXLib.IScanPictures::ScanCancel
  } // end of method TLXMainClass::ScanCancel

  .method public hidebysig newslot virtual 
          instance void  ResetStatusLeds() runtime managed internalcall
  {
    .override TLXLib.IScanPictures::ResetStatusLeds
  } // end of method TLXMainClass::ResetStatusLeds

  .method public hidebysig newslot virtual 
          instance void  AdjustMotorSpeed() runtime managed internalcall
  {
    .override TLXLib.IScanPictures::AdjustMotorSpeed
  } // end of method TLXMainClass::AdjustMotorSpeed

  .method public hidebysig newslot virtual 
          instance void  AdvanceFilm([in] int32 iAdvanceMilliseconds,
                                     [in] int32 iAdvanceSpeed) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::AdvanceFilm
  } // end of method TLXMainClass::AdvanceFilm

  .method public hidebysig newslot virtual 
          instance void  StopFilmDrive() runtime managed internalcall
  {
    .override TLXLib.IScanPictures::StopFilmDrive
  } // end of method TLXMainClass::StopFilmDrive

  .method public hidebysig newslot virtual 
          instance void  ApsManualRetract() runtime managed internalcall
  {
    .override TLXLib.IScanPictures::ApsManualRetract
  } // end of method TLXMainClass::ApsManualRetract

  .method public hidebysig newslot virtual 
          instance void  LampManualControl([in] int32 iLevel) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::LampManualControl
  } // end of method TLXMainClass::LampManualControl

  .method public hidebysig newslot virtual 
          instance int32  GetFilmGuidePosition() runtime managed internalcall
  {
    .override TLXLib.IScanPictures::GetFilmGuidePosition
  } // end of method TLXMainClass::GetFilmGuidePosition

  .method public hidebysig newslot virtual 
          instance void  PutFilmGuidePosition([in] int32 iFilmFormat) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::PutFilmGuidePosition
  } // end of method TLXMainClass::PutFilmGuidePosition

  .method public hidebysig newslot virtual 
          instance void  PutFilmPressureRollerPosition([in] int32 bEngage) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::PutFilmPressureRollerPosition
  } // end of method TLXMainClass::PutFilmPressureRollerPosition

  .method public hidebysig newslot virtual 
          instance void  GetScannerInfo000([in][out] int32& piScannerType,
                                           [in][out] string&  marshal( bstr) pbstrRomVersion,
                                           [in][out] string&  marshal( bstr) pbstrScannerModel,
                                           [in][out] int32& piScannerSerialNumber,
                                           [in][out] int32& piScannerVersionHw,
                                           [in][out] string&  marshal( bstr) pbstrTLAVersion,
                                           [in][out] int32& piDarkPointCorrectIntervalMinutes,
                                           [in][out] int32& piColorPortraitMode,
                                           [in][out] int32& pi_uiScanPacketReadyTimeOut,
                                           [in][out] int32& pi_uiNoFilmTimeOut,
                                           [in][out] int32& piLampSaverSec,
                                           [in][out] string&  marshal( bstr) pbstrTLXVersion) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::GetScannerInfo000
  } // end of method TLXMainClass::GetScannerInfo000

  .method public hidebysig newslot virtual 
          instance void  PutScannerInfo000([in] int32 iDarkPointCorrectIntervalMinutes,
                                           [in] int32 iColorPortraitMode,
                                           [in] int32 i_uiScanPacketReadyTimeOut,
                                           [in] int32 i_uiNoFilmTimeOut,
                                           [in] int32 iLampSaverSec) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::PutScannerInfo000
  } // end of method TLXMainClass::PutScannerInfo000

  .method public hidebysig newslot virtual 
          instance void  GetScannerInfo001([in][out] int32& pi_uiRingTailDriverBytes,
                                           [in][out] int32& pi_uiDriverTriggerBytes,
                                           [in][out] int32& pi_uiRingTailProcessedBytes,
                                           [in][out] int32& pi_uiProcessedTriggerBytes,
                                           [in][out] int32& piMaxFilmLength_mm) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::GetScannerInfo001
  } // end of method TLXMainClass::GetScannerInfo001

  .method public hidebysig newslot virtual 
          instance void  PutScannerInfo001([in] int32 i_uiRingTailDriverBytes,
                                           [in] int32 i_uiDriverTriggerBytes,
                                           [in] int32 i_uiRingTailProcessedBytes,
                                           [in] int32 i_uiProcessedTriggerBytes,
                                           [in] int32 iMaxFilmLength_mm) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::PutScannerInfo001
  } // end of method TLXMainClass::PutScannerInfo001

  .method public hidebysig newslot virtual 
          instance void  GetScannerInfo002([in][out] int32& piRollIndex,
                                           [in][out] int32& piStripIndex,
                                           [in][out] int32& piNumberOfPictures,
                                           [in][out] int32& piFromFileFrameNumber) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::GetScannerInfo002
  } // end of method TLXMainClass::GetScannerInfo002

  .method public hidebysig newslot virtual 
          instance void  GetScannerInfoPreFrame([in] int32 iResolution,
                                                [in] int32 iFilmFormat,
                                                [in][out] int32& piHeightLR,
                                                [in][out] int32& piHeightHR_mm,
                                                [in][out] int32& piHeightHR,
                                                [in][out] int32& piWidthHR,
                                                [in][out] int32& piWidthUnitHR,
                                                [in][out] int32& plCropHRLeft,
                                                [in][out] int32& plCropHRTop,
                                                [in][out] int32& plCropHRRight,
                                                [in][out] int32& plCropHRBottom) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::GetScannerInfoPreFrame
  } // end of method TLXMainClass::GetScannerInfoPreFrame

  .method public hidebysig newslot virtual 
          instance void  GetScannerInfoPreFrameUser([in] int32 iResolution,
                                                    [in] int32 iFilmFormat,
                                                    [in][out] int32& piWidthHR,
                                                    [in][out] int32& piWidthUnitHR,
                                                    [in][out] int32& plCropHRLeft,
                                                    [in][out] int32& plCropHRTop,
                                                    [in][out] int32& plCropHRRight,
                                                    [in][out] int32& plCropHRBottom) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::GetScannerInfoPreFrameUser
  } // end of method TLXMainClass::GetScannerInfoPreFrameUser

  .method public hidebysig newslot virtual 
          instance void  PutScannerInfoPreFrameUser([in] int32 iResolution,
                                                    [in] int32 iFilmFormat,
                                                    [in] int32 iWidthHR,
                                                    [in] int32 iWidthUnitHR,
                                                    [in] int32 lCropHRLeft,
                                                    [in] int32 lCropHRTop,
                                                    [in] int32 lCropHRRight,
                                                    [in] int32 lCropHRBottom) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::PutScannerInfoPreFrameUser
  } // end of method TLXMainClass::PutScannerInfoPreFrameUser

  .method public hidebysig newslot virtual 
          instance void  ResetFactoryDefaults([in] int32 iFactoryResetControl,
                                              [in] int32 iResolution,
                                              [in] int32 iFilmFormat) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::ResetFactoryDefaults
  } // end of method TLXMainClass::ResetFactoryDefaults

  .method public hidebysig newslot virtual 
          instance void  ImportFromFile([in] string  marshal( bstr) bstrImportFileNames,
                                        [in] int32 bDeleteImportOnRelease,
                                        [in] string  marshal( bstr) bstrRollId) runtime managed internalcall
  {
    .override TLXLib.IScanPictures::ImportFromFile
  } // end of method TLXMainClass::ImportFromFile

  .method public hidebysig newslot virtual 
          instance void  GetRollCountScanGroup([in][out] int32& piRollCount) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetRollCountScanGroup
  } // end of method TLXMainClass::GetRollCountScanGroup

  .method public hidebysig newslot virtual 
          instance void  GetPictureCountScanGroup([in] int32 iRollIndex,
                                                  [in][out] int32& piStripCount,
                                                  [in][out] int32& piPictureCount,
                                                  [in][out] int32& piScanWarnings) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetPictureCountScanGroup
  } // end of method TLXMainClass::GetPictureCountScanGroup

  .method public hidebysig newslot virtual 
          instance void  MoveOldestRollToSaveGroup() runtime managed internalcall
  {
    .override TLXLib.ISavePictures::MoveOldestRollToSaveGroup
  } // end of method TLXMainClass::MoveOldestRollToSaveGroup

  .method public hidebysig newslot virtual 
          instance void  DeleteRollInScanGroup([in] int32 iRollIndex) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::DeleteRollInScanGroup
  } // end of method TLXMainClass::DeleteRollInScanGroup

  .method public hidebysig newslot virtual 
          instance void  GetPictureCountSaveGroup([in][out] int32& piRollCount,
                                                  [in][out] int32& piStripCount,
                                                  [in][out] int32& piPictureCount,
                                                  [in][out] int32& piPictureSelectedCount,
                                                  [in][out] int32& piPictureHiddenCount) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetPictureCountSaveGroup
  } // end of method TLXMainClass::GetPictureCountSaveGroup

  .method public hidebysig newslot virtual 
          instance void  ReleaseSaveGroup() runtime managed internalcall
  {
    .override TLXLib.ISavePictures::ReleaseSaveGroup
  } // end of method TLXMainClass::ReleaseSaveGroup

  .method public hidebysig newslot virtual 
          instance void  SaveToDisk([in] int32 iIndex,
                                    [in] string  marshal( bstr) bstrFileName,
                                    [in] int32 iSaveControl,
                                    [in] int32 iBoundingWidth,
                                    [in] int32 iBoundingHeight,
                                    [in] int32 iRotation,
                                    [in] int32 iScalingMethod,
                                    [in] int32 iFileFormat,
                                    [in] int32 iCompression,
                                    [in] int32 iDpi,
                                    [in] int32 iColorBits) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::SaveToDisk
  } // end of method TLXMainClass::SaveToDisk

  .method public hidebysig newslot virtual 
          instance void  ClientMemoryBufferAdd([in] int32 i_pByteStartPointer,
                                               [in] int32 iByteCount) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::ClientMemoryBufferAdd
  } // end of method TLXMainClass::ClientMemoryBufferAdd

  .method public hidebysig newslot virtual 
          instance void  ClientMemoryBufferDismissAll() runtime managed internalcall
  {
    .override TLXLib.ISavePictures::ClientMemoryBufferDismissAll
  } // end of method TLXMainClass::ClientMemoryBufferDismissAll

  .method public hidebysig newslot virtual 
          instance void  SaveToClientMemory([in] int32 iIndex,
                                            [in] int32 iSaveControl,
                                            [in] int32 iBoundingWidth,
                                            [in] int32 iBoundingHeight,
                                            [in] int32 iRotation,
                                            [in] int32 iScalingMethod,
                                            [in] int32 iFileFormatSaveToMemory,
                                            [in] int32 bUseWorkerThread) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::SaveToClientMemory
  } // end of method TLXMainClass::SaveToClientMemory

  .method public hidebysig newslot virtual 
          instance void  SaveCancel() runtime managed internalcall
  {
    .override TLXLib.ISavePictures::SaveCancel
  } // end of method TLXMainClass::SaveCancel

  .method public hidebysig newslot virtual 
          instance void  InsertPicture([in] int32 iIndex,
                                       [in] int32 iStripIndex,
                                       [in] int32 lLeftHR,
                                       [in] int32 lTopHR,
                                       [in] int32 lRightHR,
                                       [in] int32 lBottomHR) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::InsertPicture
  } // end of method TLXMainClass::InsertPicture

  .method public hidebysig newslot virtual 
          instance void  DeletePicture([in] int32 iIndex) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::DeletePicture
  } // end of method TLXMainClass::DeletePicture

  .method public hidebysig newslot virtual 
          instance void  GetSaveInfo([in][out] int32& piDefaultFilmProduct,
                                     [in][out] int32& piDefaultFilmSpecifier,
                                     [in][out] string&  marshal( bstr) pbstrDefaultDirectory) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetSaveInfo
  } // end of method TLXMainClass::GetSaveInfo

  .method public hidebysig newslot virtual 
          instance void  PutSaveInfo([in] int32 iDefaultFilmProduct,
                                     [in] int32 iDefaultFilmSpecifier,
                                     [in] string  marshal( bstr) bstrDefaultDirectory) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::PutSaveInfo
  } // end of method TLXMainClass::PutSaveInfo

  .method public hidebysig newslot virtual 
          instance void  GetStripInfo([in] int32 iStripIndex,
                                      [in][out] int32& piRollIndex,
                                      [in][out] int32& pbIsStrip,
                                      [in][out] int32& piFilmColor,
                                      [in][out] int32& piFilmFormat,
                                      [in][out] int32& plHeightHR,
                                      [in][out] int32& plLengthHR,
                                      [in][out] int32& plHeightLR,
                                      [in][out] int32& plLengthLR,
                                      [in][out] int32& piScanWarnings,
                                      [in][out] int32& piFilmProduct,
                                      [in][out] int32& piFilmSpecifier,
                                      [in][out] int32& pi24mmFilmId,
                                      [in][out] int32& piDmin_R,
                                      [in][out] int32& piDmin_G,
                                      [in][out] int32& piDmin_B,
                                      [in][out] string&  marshal( bstr) pbstrRollId) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetStripInfo
  } // end of method TLXMainClass::GetStripInfo

  .method public hidebysig newslot virtual 
          instance void  GetStripInfoAid([in] int32 iStripIndex,
                                         [in] int32 i_pByteStartPointerHeader,
                                         [in] int32 iByteCountHeader,
                                         [in] int32 i_pByteStartPointerMag,
                                         [in] int32 iByteCountMag,
                                         [in] int32 i_pByteStartPointerOptical,
                                         [in] int32 iByteCountOptical) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetStripInfoAid
  } // end of method TLXMainClass::GetStripInfoAid

  .method public hidebysig newslot virtual 
          instance void  GetPictureInfo([in] int32 iIndex,
                                        [in][out] int32& piRollIndexFromStrip,
                                        [in][out] int32& piStripIndexFromStrip,
                                        [in][out] int32& piFilmProductFromStrip,
                                        [in][out] int32& piFilmSpecifierFromStrip,
                                        [in][out] string&  marshal( bstr) pbstrFrameName,
                                        [in][out] int32& piFrameNumber,
                                        [in][out] int32& piPrintAspectRatio,
                                        [in][out] string&  marshal( bstr) pbstrFileName,
                                        [in][out] string&  marshal( bstr) pbstrDirectory,
                                        [in][out] int32& piRotation,
                                        [in][out] int32& piSelectedHidden) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetPictureInfo
  } // end of method TLXMainClass::GetPictureInfo

  .method public hidebysig newslot virtual 
          instance void  PutPictureInfo([in] int32 iIndex,
                                        [in] int32 iFrameNumber,
                                        [in] string  marshal( bstr) bstrFileName,
                                        [in] string  marshal( bstr) bstrDirectory,
                                        [in] int32 iRotation,
                                        [in] int32 iSelectedHidden) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::PutPictureInfo
  } // end of method TLXMainClass::PutPictureInfo

  .method public hidebysig newslot virtual 
          instance void  GetPictureInfo1([in] int32 iIndex,
                                         [in][out] string&  marshal( bstr) pbstrFrameName,
                                         [in][out] int32& piFrameNumber,
                                         [in][out] string&  marshal( bstr) pbstrFileName,
                                         [in][out] string&  marshal( bstr) pbstrDirectory) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetPictureInfo1
  } // end of method TLXMainClass::GetPictureInfo1

  .method public hidebysig newslot virtual 
          instance void  PutPictureInfo1([in] int32 iIndex,
                                         [in] int32 iFrameNumber,
                                         [in] string  marshal( bstr) bstrFileName,
                                         [in] string  marshal( bstr) bstrDirectory) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::PutPictureInfo1
  } // end of method TLXMainClass::PutPictureInfo1

  .method public hidebysig newslot virtual 
          instance void  GetPictureInfo2([in] int32 iIndex,
                                         [in][out] int32& piMagneticDataStatus,
                                         [in][out] int32& piPrintAspectRatio,
                                         [in][out] string&  marshal( bstr) pbstrTitleOrImportFileName,
                                         [in][out] int32& piYear,
                                         [in][out] int32& piMonth,
                                         [in][out] int32& piDayOfMonth,
                                         [in][out] int32& piSecondsAfterMidnight) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetPictureInfo2
  } // end of method TLXMainClass::GetPictureInfo2

  .method public hidebysig newslot virtual 
          instance void  GetPictureInfoAid([in] int32 iIndex,
                                           [in][out] int32& piFrameNumberAid,
                                           [in][out] int32& piMagneticDataStatus,
                                           [in] int32 i_pByteStartPointerMag,
                                           [in] int32 iByteCountMag,
                                           [in] int32 i_pByteStartPointerOptical,
                                           [in] int32 iByteCountOptical) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetPictureInfoAid
  } // end of method TLXMainClass::GetPictureInfoAid

  .method public hidebysig newslot virtual 
          instance void  GetPictureRotation([in] int32 iIndex,
                                            [in][out] int32& piRotation) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetPictureRotation
  } // end of method TLXMainClass::GetPictureRotation

  .method public hidebysig newslot virtual 
          instance void  PutPictureRotation([in] int32 iIndex,
                                            [in] int32 iRotation) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::PutPictureRotation
  } // end of method TLXMainClass::PutPictureRotation

  .method public hidebysig newslot virtual 
          instance void  GetPictureSelection([in] int32 iIndex,
                                             [in][out] int32& piSelectedHidden) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetPictureSelection
  } // end of method TLXMainClass::GetPictureSelection

  .method public hidebysig newslot virtual 
          instance void  PutPictureSelection([in] int32 iIndex,
                                             [in] int32 iSelectedHidden,
                                             [in] int32 bSkipHidden) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::PutPictureSelection
  } // end of method TLXMainClass::PutPictureSelection

  .method public hidebysig newslot virtual 
          instance void  GetPictureFramingInfo([in] int32 iIndex,
                                               [in][out] int32& piFramingRisk,
                                               [in][out] int32& plLeftHR,
                                               [in][out] int32& plTopHR,
                                               [in][out] int32& plRightHR,
                                               [in][out] int32& plBottomHR) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetPictureFramingInfo
  } // end of method TLXMainClass::GetPictureFramingInfo

  .method public hidebysig newslot virtual 
          instance void  GetPictureFramingUserInfo([in] int32 iIndex,
                                                   [in][out] int32& plLeftHR,
                                                   [in][out] int32& plTopHR,
                                                   [in][out] int32& plRightHR,
                                                   [in][out] int32& plBottomHR) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetPictureFramingUserInfo
  } // end of method TLXMainClass::GetPictureFramingUserInfo

  .method public hidebysig newslot virtual 
          instance void  GetPictureFramingUserInfoLowRes([in] int32 iIndex,
                                                         [in][out] int32& plLeftLR,
                                                         [in][out] int32& plTopLR,
                                                         [in][out] int32& plRightLR,
                                                         [in][out] int32& plBottomLR) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetPictureFramingUserInfoLowRes
  } // end of method TLXMainClass::GetPictureFramingUserInfoLowRes

  .method public hidebysig newslot virtual 
          instance void  PutPictureFramingUserInfo([in] int32 iIndex,
                                                   [in] int32 lLeftHR,
                                                   [in] int32 lTopHR,
                                                   [in] int32 lRightHR,
                                                   [in] int32 lBottomHR) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::PutPictureFramingUserInfo
  } // end of method TLXMainClass::PutPictureFramingUserInfo

  .method public hidebysig newslot virtual 
          instance void  GetPictureColorSettings([in] int32 iIndex,
                                                 [in][out] int32& piRed,
                                                 [in][out] int32& piGreen,
                                                 [in][out] int32& piBlue,
                                                 [in][out] int32& piBrightness,
                                                 [in][out] int32& piContrast,
                                                 [in][out] int32& piSharpness) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetPictureColorSettings
  } // end of method TLXMainClass::GetPictureColorSettings

  .method public hidebysig newslot virtual 
          instance void  PutPictureColorSettings([in] int32 iIndex,
                                                 [in] int32 iRed,
                                                 [in] int32 iGreen,
                                                 [in] int32 iBlue,
                                                 [in] int32 iBrightness,
                                                 [in] int32 iContrast,
                                                 [in] int32 iSharpness) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::PutPictureColorSettings
  } // end of method TLXMainClass::PutPictureColorSettings

  .method public hidebysig newslot virtual 
          instance void  PutPictureColorSettingsDifferential([in] int32 iIndex,
                                                             [in] int32 iRed,
                                                             [in] int32 iGreen,
                                                             [in] int32 iBlue,
                                                             [in] int32 iBrightness,
                                                             [in] int32 iContrast,
                                                             [in] int32 iSharpness) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::PutPictureColorSettingsDifferential
  } // end of method TLXMainClass::PutPictureColorSettingsDifferential

  .method public hidebysig newslot virtual 
          instance void  GetPictureLightingDirection([in] int32 iIndex,
                                                     [in][out] int32& piPictureLightingDirection) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetPictureLightingDirection
  } // end of method TLXMainClass::GetPictureLightingDirection

  .method public hidebysig newslot virtual 
          instance void  PutPictureLightingDirection([in] int32 iIndex,
                                                     [in] int32 iPictureLightingDirection) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::PutPictureLightingDirection
  } // end of method TLXMainClass::PutPictureLightingDirection

  .method public hidebysig newslot virtual 
          instance void  GetPictureRedEyeSettings([in] int32 iIndex,
                                                  [in][out] int32& piRedEye,
                                                  [in][out] int32& plLeftHR,
                                                  [in][out] int32& plTopHR,
                                                  [in][out] int32& plRightHR,
                                                  [in][out] int32& plBottomHR) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::GetPictureRedEyeSettings
  } // end of method TLXMainClass::GetPictureRedEyeSettings

  .method public hidebysig newslot virtual 
          instance void  PutPictureRedEyeSettings([in] int32 iIndex,
                                                  [in] int32 iRedEye,
                                                  [in] int32 lLeftHR,
                                                  [in] int32 lTopHR,
                                                  [in] int32 lRightHR,
                                                  [in] int32 lBottomHR) runtime managed internalcall
  {
    .override TLXLib.ISavePictures::PutPictureRedEyeSettings
  } // end of method TLXMainClass::PutPictureRedEyeSettings

  .method public hidebysig newslot virtual 
          instance void  GetStripInfo1([in] int32 iStripIndex,
                                       [in][out] int32& piRollIndex,
                                       [in][out] int32& pbIsStrip,
                                       [in][out] int32& piFilmColor,
                                       [in][out] int32& piFilmFormat,
                                       [in][out] int32& plHeightHR,
                                       [in][out] int32& plLengthHR,
                                       [in][out] int32& plHeightLR,
                                       [in][out] int32& plLengthLR,
                                       [in][out] int32& piScanWarnings,
                                       [in][out] int32& piFilmProduct,
                                       [in][out] int32& piFilmSpecifier,
                                       [in][out] int32& pi24mmFilmId,
                                       [in][out] int32& piDmin_R,
                                       [in][out] int32& piDmin_G,
                                       [in][out] int32& piDmin_B,
                                       [in][out] string&  marshal( bstr) pbstrRollId,
                                       [in][out] int32& piCartridgeHandOfLoad) runtime managed internalcall
  {
    .override TLXLib.ISavePictures1::GetStripInfo1
  } // end of method TLXMainClass::GetStripInfo1

  .method public hidebysig newslot virtual 
          instance void  Put24mmFilmId([in] int32 iStripIndex,
                                       [in] int32 i24mmFilmId) runtime managed internalcall
  {
    .override TLXLib.ISavePictures1::Put24mmFilmId
  } // end of method TLXMainClass::Put24mmFilmId

  .method public hidebysig newslot virtual 
          instance void  ImportFromFile2([in] string  marshal( bstr) bstrImportFileNames,
                                         [in] int32 bDeleteImportOnRelease,
                                         [in] int32 bUsePremiumColorPath,
                                         [in] string  marshal( bstr) bstrRollId) runtime managed internalcall
  {
    .override TLXLib.IScanPictures2::ImportFromFile2
  } // end of method TLXMainClass::ImportFromFile2

  .method public hidebysig newslot virtual 
          instance void  PutPictureBnWEffect([in] int32 iIndex,
                                             [in] int32 iBnWEffect) runtime managed internalcall
  {
    .override TLXLib.ISavePictures2::PutPictureBnWEffect
  } // end of method TLXMainClass::PutPictureBnWEffect

  .method public hidebysig newslot virtual 
          instance void  GetPictureBnWEffect([in] int32 iIndex,
                                             [in][out] int32& piBnWEffect) runtime managed internalcall
  {
    .override TLXLib.ISavePictures2::GetPictureBnWEffect
  } // end of method TLXMainClass::GetPictureBnWEffect

  .method public hidebysig newslot virtual 
          instance void  PutPictureSaturation([in] int32 iIndex,
                                              [in] int32 iSaturation) runtime managed internalcall
  {
    .override TLXLib.ISavePictures2::PutPictureSaturation
  } // end of method TLXMainClass::PutPictureSaturation

  .method public hidebysig newslot virtual 
          instance void  GetPictureSaturation([in] int32 iIndex,
                                              [in][out] int32& piSaturation) runtime managed internalcall
  {
    .override TLXLib.ISavePictures2::GetPictureSaturation
  } // end of method TLXMainClass::GetPictureSaturation

  .method public hidebysig newslot virtual 
          instance void  GetSaveInfo1([out] int32& piDefaultFilmProduct,
                                      [out] int32& piDefaultFilmSpecifier,
                                      [out] string&  marshal( bstr) pbstrDefaultDirectory) runtime managed internalcall
  {
    .override TLXLib.ISavePictures3::GetSaveInfo1
  } // end of method TLXMainClass::GetSaveInfo1

  .method public hidebysig newslot virtual 
          instance void  GetStripInfo2([in] int32 iStripIndex,
                                       [out] int32& piRollIndex,
                                       [out] int32& pbIsStrip,
                                       [out] int32& piFilmColor,
                                       [out] int32& piFilmFormat,
                                       [out] int32& plHeightHR,
                                       [out] int32& plLengthHR,
                                       [out] int32& plHeightLR,
                                       [out] int32& plLengthLR,
                                       [out] int32& piScanWarnings,
                                       [out] int32& piFilmProduct,
                                       [out] int32& piFilmSpecifier,
                                       [out] int32& pi24mmFilmId,
                                       [out] int32& piDmin_R,
                                       [out] int32& piDmin_G,
                                       [out] int32& piDmin_B,
                                       [out] string&  marshal( bstr) pbstrRollId,
                                       [out] int32& piCartridgeHandOfLoad) runtime managed internalcall
  {
    .override TLXLib.ISavePictures3::GetStripInfo2
  } // end of method TLXMainClass::GetStripInfo2

  .method public hidebysig newslot virtual 
          instance void  GetPictureInfo3([in] int32 iIndex,
                                         [out] int32& piRollIndexFromStrip,
                                         [out] int32& piStripIndexFromStrip,
                                         [out] int32& piFilmProductFromStrip,
                                         [out] int32& piFilmSpecifierFromStrip,
                                         [out] string&  marshal( bstr) pbstrFrameName,
                                         [out] int32& piFrameNumber,
                                         [out] int32& piPrintAspectRatio,
                                         [out] string&  marshal( bstr) pbstrFileName,
                                         [out] string&  marshal( bstr) pbstrDirectory,
                                         [out] int32& piRotation,
                                         [out] int32& piSelectedHidden) runtime managed internalcall
  {
    .override TLXLib.ISavePictures3::GetPictureInfo3
  } // end of method TLXMainClass::GetPictureInfo3

  .method public hidebysig newslot virtual 
          instance void  GetPictureInfo4([in] int32 iIndex,
                                         [out] string&  marshal( bstr) pbstrFrameName,
                                         [out] int32& piFrameNumber,
                                         [out] string&  marshal( bstr) pbstrFileName,
                                         [out] string&  marshal( bstr) pbstrDirectory) runtime managed internalcall
  {
    .override TLXLib.ISavePictures3::GetPictureInfo4
  } // end of method TLXMainClass::GetPictureInfo4

  .method public hidebysig newslot virtual 
          instance void  GetPictureInfo5([in] int32 iIndex,
                                         [out] int32& piMagneticDataStatus,
                                         [out] int32& piPrintAspectRatio,
                                         [out] string&  marshal( bstr) pbstrTitleOrImportFileName,
                                         [out] int32& piYear,
                                         [out] int32& piMonth,
                                         [out] int32& piDayOfMonth,
                                         [out] int32& piSecondsAfterMidnight) runtime managed internalcall
  {
    .override TLXLib.ISavePictures3::GetPictureInfo5
  } // end of method TLXMainClass::GetPictureInfo5

  .method public hidebysig newslot virtual 
          instance void  CalibrationEnable([in] string  marshal( bstr) bstrLicense) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationEnable
  } // end of method TLXMainClass::CalibrationEnable

  .method public hidebysig newslot virtual 
          instance void  CalibrationBegin([in] int32 iResolution,
                                          [in] int32 iFilmColor,
                                          [in] int32 iFilmFormat,
                                          [in] int32 bUseScratchRemoval,
                                          [in] int32 i_pByteStartPointer) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationBegin
  } // end of method TLXMainClass::CalibrationBegin

  .method public hidebysig newslot virtual 
          instance void  CalibrationGetDpi([in] int32 iResolution,
                                           [in] int32 iFilmFormat,
                                           [in][out] int32& piHeightToCcd,
                                           [in][out] int32& piHeight,
                                           [in][out] int32& piOffset,
                                           [in][out] int32& piMotorAdjust,
                                           [in][out] int32& piMotorAdjust_Ir,
                                           [in][out] int32& piMotorAdjustDrag,
                                           [in][out] int32& piMotorAdjustDrag_Ir,
                                           [in][out] int32& piMotorSpeed,
                                           [in][out] int32& piMotorSpeed_Ir,
                                           [in][out] int32& piStepperLens,
                                           [in][out] int32& piStepperCCD,
                                           [in][out] int32& piStepperCCDAdjust) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationGetDpi
  } // end of method TLXMainClass::CalibrationGetDpi

  .method public hidebysig newslot virtual 
          instance void  CalibrationPutDpi([in] int32 iResolution,
                                           [in] int32 iFilmFormat,
                                           [in] int32 bCalibrateGroup,
                                           [in] int32 iHeightToCcd,
                                           [in] int32 iHeight,
                                           [in] int32 iOffset,
                                           [in] int32 iMotorSpeed,
                                           [in] int32 iMotorSpeed_Ir,
                                           [in] int32 iStepperLens,
                                           [in] int32 iStepperCCD) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationPutDpi
  } // end of method TLXMainClass::CalibrationPutDpi

  .method public hidebysig newslot virtual 
          instance void  CalibrationGetLightIncandescent([in] int32 iResolution,
                                                         [in] int32 iFilmFormat,
                                                         [in] int32 iFilmColor,
                                                         [in][out] int32& piGain_R,
                                                         [in][out] int32& piGain_G,
                                                         [in][out] int32& piGain_B,
                                                         [in][out] int32& piOffset_R,
                                                         [in][out] int32& piOffset_G,
                                                         [in][out] int32& piOffset_B,
                                                         [in][out] int32& piCcdExposure_R,
                                                         [in][out] int32& piCcdExposure_G,
                                                         [in][out] int32& piCcdExposure_B,
                                                         [in][out] int32& piIrLEDStartTime,
                                                         [in][out] int32& piCurrent_Ir,
                                                         [in][out] int32& piCcdExposureOpenGate_R,
                                                         [in][out] int32& piCcdExposureOpenGate_G,
                                                         [in][out] int32& piCcdExposureOpenGate_B,
                                                         [in][out] int32& piIrLEDStartTimeOpenGate,
                                                         [in][out] int32& piCurrentOpenGate_Ir,
                                                         [in][out] int32& piDetectWhite_G,
                                                         [in][out] int32& piDetectFilm_G) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationGetLightIncandescent
  } // end of method TLXMainClass::CalibrationGetLightIncandescent

  .method public hidebysig newslot virtual 
          instance void  CalibrationPutLightIncandescent([in] int32 iResolution,
                                                         [in] int32 iFilmFormat,
                                                         [in] int32 iFilmColor,
                                                         [in] int32 bCalibrateGroup,
                                                         [in] int32 iGain_R,
                                                         [in] int32 iGain_G,
                                                         [in] int32 iGain_B,
                                                         [in] int32 iOffset_R,
                                                         [in] int32 iOffset_G,
                                                         [in] int32 iOffset_B,
                                                         [in] int32 iCcdExposure_R,
                                                         [in] int32 iCcdExposure_G,
                                                         [in] int32 iCcdExposure_B,
                                                         [in] int32 iIrLEDStartTime,
                                                         [in] int32 iCurrent_Ir,
                                                         [in] int32 iCcdExposureOpenGate_R,
                                                         [in] int32 iCcdExposureOpenGate_G,
                                                         [in] int32 iCcdExposureOpenGate_B,
                                                         [in] int32 iIrLEDStartTimeOpenGate,
                                                         [in] int32 iCurrentOpenGate_Ir,
                                                         [in] int32 iDetectWhite_G,
                                                         [in] int32 iDetectFilm_G) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationPutLightIncandescent
  } // end of method TLXMainClass::CalibrationPutLightIncandescent

  .method public hidebysig newslot virtual 
          instance void  CalibrationGetLightLED([in] int32 iResolution,
                                                [in] int32 iFilmFormat,
                                                [in] int32 iFilmColor,
                                                [in] int32 bUseScratchRemoval,
                                                [in][out] int32& piGain_R,
                                                [in][out] int32& piGain_G,
                                                [in][out] int32& piGain_B,
                                                [in][out] int32& piOffset_R,
                                                [in][out] int32& piOffset_G,
                                                [in][out] int32& piOffset_B,
                                                [in][out] int32& piCurrent_R,
                                                [in][out] int32& piCurrent_G,
                                                [in][out] int32& piCurrent_B,
                                                [in][out] int32& piCurrent_Ir,
                                                [in][out] float64& pdfDutyCycle_R,
                                                [in][out] float64& pdfDutyCycle_G,
                                                [in][out] float64& pdfDutyCycle_B,
                                                [in][out] float64& pdfDutyCycle_Ir,
                                                [in][out] int32& piDetectWhite_G,
                                                [in][out] int32& piDetectFilm_G,
                                                [in][out] float64& pdfAmbientTemperature,
                                                [in][out] float64& pdfLockedTemperature,
                                                [in][out] float64& pdfVisibleTemperature,
                                                [in][out] float64& pdfIrTemperature) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationGetLightLED
  } // end of method TLXMainClass::CalibrationGetLightLED

  .method public hidebysig newslot virtual 
          instance void  CalibrationPutLightLED([in] int32 iResolution,
                                                [in] int32 iFilmFormat,
                                                [in] int32 iFilmColor,
                                                [in] int32 bUseScratchRemoval,
                                                [in] int32 bCalibrateGroup,
                                                [in] int32 iGain_R,
                                                [in] int32 iGain_G,
                                                [in] int32 iGain_B,
                                                [in] int32 iOffset_R,
                                                [in] int32 iOffset_G,
                                                [in] int32 iOffset_B,
                                                [in] int32 iCurrent_R,
                                                [in] int32 iCurrent_G,
                                                [in] int32 iCurrent_B,
                                                [in] int32 iCurrent_Ir,
                                                [in] float64 dfDutyCycle_R,
                                                [in] float64 dfDutyCycle_G,
                                                [in] float64 dfDutyCycle_B,
                                                [in] float64 dfDutyCycle_Ir,
                                                [in] int32 iDetectWhite_G,
                                                [in] int32 iDetectFilm_G) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationPutLightLED
  } // end of method TLXMainClass::CalibrationPutLightLED

  .method public hidebysig newslot virtual 
          instance void  CalibrationGetColorMatrix3By4([in] int32 iColorMatrix,
                                                       [in][out] float64& pdfMatrixValue0_0,
                                                       [in][out] float64& pdfMatrixValue0_1,
                                                       [in][out] float64& pdfMatrixValue0_2,
                                                       [in][out] float64& pdfMatrixValue0_3,
                                                       [in][out] float64& pdfMatrixValue1_0,
                                                       [in][out] float64& pdfMatrixValue1_1,
                                                       [in][out] float64& pdfMatrixValue1_2,
                                                       [in][out] float64& pdfMatrixValue1_3,
                                                       [in][out] float64& pdfMatrixValue2_0,
                                                       [in][out] float64& pdfMatrixValue2_1,
                                                       [in][out] float64& pdfMatrixValue2_2,
                                                       [in][out] float64& pdfMatrixValue2_3) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationGetColorMatrix3By4
  } // end of method TLXMainClass::CalibrationGetColorMatrix3By4

  .method public hidebysig newslot virtual 
          instance void  CalibrationPutColorMatrix3By4([in] int32 iColorMatrix,
                                                       [in] int32 bCalibrateGroup,
                                                       [in] float64 dfMatrixValue0_0,
                                                       [in] float64 dfMatrixValue0_1,
                                                       [in] float64 dfMatrixValue0_2,
                                                       [in] float64 dfMatrixValue0_3,
                                                       [in] float64 dfMatrixValue1_0,
                                                       [in] float64 dfMatrixValue1_1,
                                                       [in] float64 dfMatrixValue1_2,
                                                       [in] float64 dfMatrixValue1_3,
                                                       [in] float64 dfMatrixValue2_0,
                                                       [in] float64 dfMatrixValue2_1,
                                                       [in] float64 dfMatrixValue2_2,
                                                       [in] float64 dfMatrixValue2_3) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationPutColorMatrix3By4
  } // end of method TLXMainClass::CalibrationPutColorMatrix3By4

  .method public hidebysig newslot virtual 
          instance void  CalibrationGetColorMatrix3By10([in] int32 iFilmColor,
                                                        [in][out] float32& pfMatrixValue0_0,
                                                        [in][out] float32& pfMatrixValue0_1,
                                                        [in][out] float32& pfMatrixValue0_2,
                                                        [in][out] float32& pfMatrixValue0_3,
                                                        [in][out] float32& pfMatrixValue0_4,
                                                        [in][out] float32& pfMatrixValue0_5,
                                                        [in][out] float32& pfMatrixValue0_6,
                                                        [in][out] float32& pfMatrixValue0_7,
                                                        [in][out] float32& pfMatrixValue0_8,
                                                        [in][out] float32& pfMatrixValue0_9,
                                                        [in][out] float32& pfMatrixValue1_0,
                                                        [in][out] float32& pfMatrixValue1_1,
                                                        [in][out] float32& pfMatrixValue1_2,
                                                        [in][out] float32& pfMatrixValue1_3,
                                                        [in][out] float32& pfMatrixValue1_4,
                                                        [in][out] float32& pfMatrixValue1_5,
                                                        [in][out] float32& pfMatrixValue1_6,
                                                        [in][out] float32& pfMatrixValue1_7,
                                                        [in][out] float32& pfMatrixValue1_8,
                                                        [in][out] float32& pfMatrixValue1_9,
                                                        [in][out] float32& pfMatrixValue2_0,
                                                        [in][out] float32& pfMatrixValue2_1,
                                                        [in][out] float32& pfMatrixValue2_2,
                                                        [in][out] float32& pfMatrixValue2_3,
                                                        [in][out] float32& pfMatrixValue2_4,
                                                        [in][out] float32& pfMatrixValue2_5,
                                                        [in][out] float32& pfMatrixValue2_6,
                                                        [in][out] float32& pfMatrixValue2_7,
                                                        [in][out] float32& pfMatrixValue2_8,
                                                        [in][out] float32& pfMatrixValue2_9) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationGetColorMatrix3By10
  } // end of method TLXMainClass::CalibrationGetColorMatrix3By10

  .method public hidebysig newslot virtual 
          instance void  CalibrationPutColorMatrix3By10([in] int32 iFilmColor,
                                                        [in] int32 bCalibrateGroup,
                                                        [in] float32 fMatrixValue0_0,
                                                        [in] float32 fMatrixValue0_1,
                                                        [in] float32 fMatrixValue0_2,
                                                        [in] float32 fMatrixValue0_3,
                                                        [in] float32 fMatrixValue0_4,
                                                        [in] float32 fMatrixValue0_5,
                                                        [in] float32 fMatrixValue0_6,
                                                        [in] float32 fMatrixValue0_7,
                                                        [in] float32 fMatrixValue0_8,
                                                        [in] float32 fMatrixValue0_9,
                                                        [in] float32 fMatrixValue1_0,
                                                        [in] float32 fMatrixValue1_1,
                                                        [in] float32 fMatrixValue1_2,
                                                        [in] float32 fMatrixValue1_3,
                                                        [in] float32 fMatrixValue1_4,
                                                        [in] float32 fMatrixValue1_5,
                                                        [in] float32 fMatrixValue1_6,
                                                        [in] float32 fMatrixValue1_7,
                                                        [in] float32 fMatrixValue1_8,
                                                        [in] float32 fMatrixValue1_9,
                                                        [in] float32 fMatrixValue2_0,
                                                        [in] float32 fMatrixValue2_1,
                                                        [in] float32 fMatrixValue2_2,
                                                        [in] float32 fMatrixValue2_3,
                                                        [in] float32 fMatrixValue2_4,
                                                        [in] float32 fMatrixValue2_5,
                                                        [in] float32 fMatrixValue2_6,
                                                        [in] float32 fMatrixValue2_7,
                                                        [in] float32 fMatrixValue2_8,
                                                        [in] float32 fMatrixValue2_9) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationPutColorMatrix3By10
  } // end of method TLXMainClass::CalibrationPutColorMatrix3By10

  .method public hidebysig newslot virtual 
          instance void  CalibrationPutIdentification([in] int32 bCalibrateGroup,
                                                      [in] int32 iScannerVersionHw,
                                                      [in] int32 iScannerType,
                                                      [in] int32 iScannerSerialNumber) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationPutIdentification
  } // end of method TLXMainClass::CalibrationPutIdentification

  .method public hidebysig newslot virtual 
          instance void  CalibrationChange([in] int32 iResolution,
                                           [in] int32 iFilmColor,
                                           [in] int32 iFilmFormat,
                                           [in] int32 bUseScratchRemoval) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationChange
  } // end of method TLXMainClass::CalibrationChange

  .method public hidebysig newslot virtual 
          instance void  CalibrationAcquire([in] int32 iScanLines) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationAcquire
  } // end of method TLXMainClass::CalibrationAcquire

  .method public hidebysig newslot virtual 
          instance void  CalibrationPutFilterWheelPosition([in] int32 iFilmColor) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationPutFilterWheelPosition
  } // end of method TLXMainClass::CalibrationPutFilterWheelPosition

  .method public hidebysig newslot virtual 
          instance void  CalibrationPutFilmPressureRollerPosition([in] int32 bEngage) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationPutFilmPressureRollerPosition
  } // end of method TLXMainClass::CalibrationPutFilmPressureRollerPosition

  .method public hidebysig newslot virtual 
          instance void  CalibrationAdvanceFilm([in] int32 iAdvanceMilliseconds,
                                                [in] int32 iAdvanceSpeed) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationAdvanceFilm
  } // end of method TLXMainClass::CalibrationAdvanceFilm

  .method public hidebysig newslot virtual 
          instance void  CalibrationFocus([in] int32 bFindTiltTurns) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationFocus
  } // end of method TLXMainClass::CalibrationFocus

  .method public hidebysig newslot virtual 
          instance void  CalibrationFocusResults([in][out] int32& piCalibrateFocusErrorCenter,
                                                 [in][out] int32& piCalibrateFocusErrorLeft,
                                                 [in][out] int32& piCalibrateFocusErrorRight,
                                                 [in][out] int32& piCalibrateFocusOffsetCenter,
                                                 [in][out] int32& piCalibrateFocusOffsetLeft,
                                                 [in][out] int32& piCalibrateFocusOffsetRight,
                                                 [in][out] int32& piCalibrateTiltEighthTurns) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationFocusResults
  } // end of method TLXMainClass::CalibrationFocusResults

  .method public hidebysig newslot virtual 
          instance void  CalibrationPutEEProm() runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationPutEEProm
  } // end of method TLXMainClass::CalibrationPutEEProm

  .method public hidebysig newslot virtual 
          instance void  CalibrationEnd() runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationEnd
  } // end of method TLXMainClass::CalibrationEnd

  .method public hidebysig newslot virtual 
          instance void  CalibrationMofReader([in] int32 iCalibrateMofControl,
                                              [in][out] int32& piValue) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationMofReader
  } // end of method TLXMainClass::CalibrationMofReader

  .method public hidebysig newslot virtual 
          instance void  CalibrationStepperTest() runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationStepperTest
  } // end of method TLXMainClass::CalibrationStepperTest

  .method public hidebysig newslot virtual 
          instance void  CalibrationStepperTestResults([in][out] int32& piCCDExpected,
                                                       [in][out] int32& piCCDActual,
                                                       [in][out] int32& piLensExpected,
                                                       [in][out] int32& piLensActual) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationStepperTestResults
  } // end of method TLXMainClass::CalibrationStepperTestResults

  .method public hidebysig newslot virtual 
          instance void  CalibrationDotNet([in] valuetype TLXLib.CALIBRATE_CONTROL_000 Unused1,
                                           [in] valuetype TLXLib.COLOR_PORTRAIT_MODE_000 Unused2,
                                           [in] valuetype TLXLib.ERROR_CODES_000 Unused3,
                                           [in] valuetype TLXLib.FACTORY_RESET_CONTROL_000 Unused4,
                                           [in] valuetype TLXLib.FILE_FORMAT_000 Unused5,
                                           [in] valuetype TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 Unused6,
                                           [in] valuetype TLXLib.FILM_COLOR_000 Unused7,
                                           [in] valuetype TLXLib.FILM_FORMAT_000 Unused8,
                                           [in] valuetype TLXLib.FILM_TRACK_TEST_ERRORS_000 Unused9,
                                           [in] valuetype TLXLib.FRAME_SIZES_000 Unused10,
                                           [in] valuetype TLXLib.FRAME_TYPE_000 Unused11,
                                           [in] valuetype TLXLib.FRAMING_RISK_000 Unused12,
                                           [in] valuetype TLXLib.HARDWARE_CB_000 Unused13,
                                           [in] valuetype TLXLib.HARDWARE_CB_APS_000 Unused14,
                                           [in] valuetype TLXLib.INDEX_000 Unused15,
                                           [in] valuetype TLXLib.INITIALIZE_CONTROL_000 Unused16,
                                           [in] valuetype TLXLib.INITIALIZE_WARNINGS_000 Unused17,
                                           [in] valuetype TLXLib.INT_IID_000 Unused18,
                                           [in] valuetype TLXLib.RESOLUTION_000 Unused19,
                                           [in] valuetype TLXLib.ROTATE_000 Unused20,
                                           [in] valuetype TLXLib.S_OR_H_000 Unused21,
                                           [in] valuetype TLXLib.SAVE_CONTROL_000 Unused22,
                                           [in] valuetype TLXLib.SCALING_METHOD_000 Unused23,
                                           [in] valuetype TLXLib.SCAN_CONTROL_000 Unused24,
                                           [in] valuetype TLXLib.SCAN_WARNINGS_000 Unused25,
                                           [in] valuetype TLXLib.SCANNER_TYPE_000 Unused26,
                                           [in] valuetype TLXLib.SCANNER_VERSION_HW_000 Unused27,
                                           [in] valuetype TLXLib.STRIP_MODE_000 Unused28,
                                           [in] valuetype TLXLib.WORKER_THREAD_OPERATION_000 Unused29,
                                           [in] valuetype TLXLib.WORKER_THREAD_PROGRESS_000 Unused30) runtime managed internalcall
  {
    .override TLXLib.ICalibrationWizard::CalibrationDotNet
  } // end of method TLXMainClass::CalibrationDotNet

} // end of class TLXLib.TLXMainClass

.class interface public abstract auto ansi TLXLib._ITLXMainEvents_Event
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.TypeLibTypeAttribute::.ctor(int16) = ( 01 00 10 00 00 00 ) 
  .custom instance void [mscorlib]System.Runtime.InteropServices.ComVisibleAttribute::.ctor(bool) = ( 01 00 00 00 00 ) 
  .custom instance void [mscorlib]System.Runtime.InteropServices.ComEventInterfaceAttribute::.ctor([mscorlib]System.Type,
                                                                                                   [mscorlib]System.Type) = ( 01 00 17 54 4C 58 4C 69 62 2E 5F 49 54 4C 58 4D   // ...TLXLib._ITLXM
                                                                                                                              61 69 6E 45 76 65 6E 74 73 00 25 54 4C 58 4C 69   // ainEvents.%TLXLi
                                                                                                                              62 2E 5F 49 54 4C 58 4D 61 69 6E 45 76 65 6E 74   // b._ITLXMainEvent
                                                                                                                              73 5F 45 76 65 6E 74 50 72 6F 76 69 64 65 72 00   // s_EventProvider.
                                                                                                                              00 00 ) 
} // end of class TLXLib._ITLXMainEvents_Event

.class interface public abstract auto ansi import TLXLib.TLXMain
       implements TLXLib.ITLXMain,
                  TLXLib._ITLXMainEvents_Event
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.CoClassAttribute::.ctor([mscorlib]System.Type) = ( 01 00 13 54 4C 58 4C 69 62 2E 54 4C 58 4D 61 69   // ...TLXLib.TLXMai
                                                                                                                    6E 43 6C 61 73 73 00 00 )                         // nClass..
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 33 43 41 45 42 34 46 32 2D 31 46 32 37   // ..$3CAEB4F2-1F27
                                                                                                  2D 34 46 41 46 2D 39 39 34 38 2D 35 36 32 44 33   // -4FAF-9948-562D3
                                                                                                  35 30 32 42 38 35 36 00 00 )                      // 502B856..
} // end of class TLXLib.TLXMain

.class interface public abstract auto ansi import TLXLib.ITLXMain
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 33 43 41 45 42 34 46 32 2D 31 46 32 37   // ..$3CAEB4F2-1F27
                                                                                                  2D 34 46 41 46 2D 39 39 34 38 2D 35 36 32 44 33   // -4FAF-9948-562D3
                                                                                                  35 30 32 42 38 35 36 00 00 )                      // 502B856..
  .custom instance void [mscorlib]System.Runtime.InteropServices.TypeLibTypeAttribute::.ctor(int16) = ( 01 00 40 10 00 00 )                               // ..@...
  .method public hidebysig newslot abstract virtual 
          instance void  InitializeScanner([in] int32 iInitializeControl,
                                           [in] int32 iSaveToMemoryTimeout) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 01 00 00 00 00 00 ) 
  } // end of method ITLXMain::InitializeScanner

  .method public hidebysig newslot abstract virtual 
          instance int32  GetAndClearLastError([in] int32 iShort_IID,
                                               [in][out] string&  marshal( bstr) pbstrError,
                                               [in][out] string&  marshal( bstr) pbstrErrorNumbers) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 02 00 00 00 00 00 ) 
  } // end of method ITLXMain::GetAndClearLastError

  .method public hidebysig newslot abstract virtual 
          instance void  GetInitializeWarnings([in][out] int32& piInitializeWarnings) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 03 00 00 00 00 00 ) 
  } // end of method ITLXMain::GetInitializeWarnings

} // end of class TLXLib.ITLXMain

.class interface public abstract auto ansi import TLXLib.ILongOpsCB
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 44 44 44 43 46 33 39 39 2D 37 46 38 30   // ..$DDDCF399-7F80
                                                                                                  2D 34 41 35 36 2D 38 36 32 37 2D 37 34 34 43 36   // -4A56-8627-744C6
                                                                                                  38 36 32 35 46 30 46 00 00 )                      // 8625F0F..
  .custom instance void [mscorlib]System.Runtime.InteropServices.InterfaceTypeAttribute::.ctor(int16) = ( 01 00 01 00 00 00 ) 
  .method public hidebysig newslot abstract virtual 
          instance int32  CBAdvise([in] class TLXLib.ICallBackClient  marshal( interface ) pICallBackClient) runtime managed internalcall
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

} // end of class TLXLib.ILongOpsCB

.class interface public abstract auto ansi import TLXLib.ICallBackClient
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.InterfaceTypeAttribute::.ctor(int16) = ( 01 00 01 00 00 00 ) 
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 31 41 32 46 36 44 44 46 2D 41 41 44 38   // ..$1A2F6DDF-AAD8
                                                                                                  2D 34 30 46 42 2D 42 41 41 42 2D 34 46 45 45 30   // -40FB-BAAB-4FEE0
                                                                                                  31 35 41 44 43 44 35 00 00 )                      // 15ADCD5..
  .method public hidebysig newslot abstract virtual 
          instance void  Awake([in] int32 lOperation,
                               [in] int32 lStatus) runtime managed internalcall
  {
  } // end of method ICallBackClient::Awake

} // end of class TLXLib.ICallBackClient

.class interface public abstract auto ansi import TLXLib.IScanPictures
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 41 43 33 30 31 37 43 35 2D 46 30 34 37   // ..$AC3017C5-F047
                                                                                                  2D 34 46 34 35 2D 42 45 36 36 2D 33 46 37 46 35   // -4F45-BE66-3F7F5
                                                                                                  45 34 44 33 31 31 34 00 00 )                      // E4D3114..
  .custom instance void [mscorlib]System.Runtime.InteropServices.TypeLibTypeAttribute::.ctor(int16) = ( 01 00 40 10 00 00 )                               // ..@...
  .method public hidebysig newslot abstract virtual 
          instance void  ForceCorrections([in] int32 iResolution,
                                          [in] int32 iFilmColor,
                                          [in] int32 iFilmFormat,
                                          [in] int32 iCalibrateControl) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 01 00 00 00 00 00 ) 
  } // end of method IScanPictures::ForceCorrections

  .method public hidebysig newslot abstract virtual 
          instance void  ForceDiagnostics() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 02 00 00 00 00 00 ) 
  } // end of method IScanPictures::ForceDiagnostics

  .method public hidebysig newslot abstract virtual 
          instance void  FilmTrackTest([in] int32 bDxPotsAdjust,
                                       [in] int32 iFilmFormat) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 03 00 00 00 00 00 ) 
  } // end of method IScanPictures::FilmTrackTest

  .method public hidebysig newslot abstract virtual 
          instance int32  FilmTrackTestResults() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 04 00 00 00 00 00 ) 
  } // end of method IScanPictures::FilmTrackTestResults

  .method public hidebysig newslot abstract virtual 
          instance void  ScanPictures([in] int32 iResolution,
                                      [in] int32 iFilmColor,
                                      [in] int32 iFilmFormat,
                                      [in] int32 iStripMode,
                                      [in] int32 iScanControl,
                                      [in] string  marshal( bstr) bstrRollId) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 05 00 00 00 00 00 ) 
  } // end of method IScanPictures::ScanPictures

  .method public hidebysig newslot abstract virtual 
          instance void  ScanCancel() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 06 00 00 00 00 00 ) 
  } // end of method IScanPictures::ScanCancel

  .method public hidebysig newslot abstract virtual 
          instance void  ResetStatusLeds() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 07 00 00 00 00 00 ) 
  } // end of method IScanPictures::ResetStatusLeds

  .method public hidebysig newslot abstract virtual 
          instance void  AdjustMotorSpeed() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 08 00 00 00 00 00 ) 
  } // end of method IScanPictures::AdjustMotorSpeed

  .method public hidebysig newslot abstract virtual 
          instance void  AdvanceFilm([in] int32 iAdvanceMilliseconds,
                                     [in] int32 iAdvanceSpeed) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 09 00 00 00 00 00 ) 
  } // end of method IScanPictures::AdvanceFilm

  .method public hidebysig newslot abstract virtual 
          instance void  StopFilmDrive() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0A 00 00 00 00 00 ) 
  } // end of method IScanPictures::StopFilmDrive

  .method public hidebysig newslot abstract virtual 
          instance void  ApsManualRetract() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0B 00 00 00 00 00 ) 
  } // end of method IScanPictures::ApsManualRetract

  .method public hidebysig newslot abstract virtual 
          instance void  LampManualControl([in] int32 iLevel) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0C 00 00 00 00 00 ) 
  } // end of method IScanPictures::LampManualControl

  .method public hidebysig newslot abstract virtual 
          instance int32  GetFilmGuidePosition() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0D 00 00 00 00 00 ) 
  } // end of method IScanPictures::GetFilmGuidePosition

  .method public hidebysig newslot abstract virtual 
          instance void  PutFilmGuidePosition([in] int32 iFilmFormat) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0E 00 00 00 00 00 ) 
  } // end of method IScanPictures::PutFilmGuidePosition

  .method public hidebysig newslot abstract virtual 
          instance void  PutFilmPressureRollerPosition([in] int32 bEngage) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0F 00 00 00 00 00 ) 
  } // end of method IScanPictures::PutFilmPressureRollerPosition

  .method public hidebysig newslot abstract virtual 
          instance void  GetScannerInfo000([in][out] int32& piScannerType,
                                           [in][out] string&  marshal( bstr) pbstrRomVersion,
                                           [in][out] string&  marshal( bstr) pbstrScannerModel,
                                           [in][out] int32& piScannerSerialNumber,
                                           [in][out] int32& piScannerVersionHw,
                                           [in][out] string&  marshal( bstr) pbstrTLAVersion,
                                           [in][out] int32& piDarkPointCorrectIntervalMinutes,
                                           [in][out] int32& piColorPortraitMode,
                                           [in][out] int32& pi_uiScanPacketReadyTimeOut,
                                           [in][out] int32& pi_uiNoFilmTimeOut,
                                           [in][out] int32& piLampSaverSec,
                                           [in][out] string&  marshal( bstr) pbstrTLXVersion) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 10 00 00 00 00 00 ) 
  } // end of method IScanPictures::GetScannerInfo000

  .method public hidebysig newslot abstract virtual 
          instance void  PutScannerInfo000([in] int32 iDarkPointCorrectIntervalMinutes,
                                           [in] int32 iColorPortraitMode,
                                           [in] int32 i_uiScanPacketReadyTimeOut,
                                           [in] int32 i_uiNoFilmTimeOut,
                                           [in] int32 iLampSaverSec) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 11 00 00 00 00 00 ) 
  } // end of method IScanPictures::PutScannerInfo000

  .method public hidebysig newslot abstract virtual 
          instance void  GetScannerInfo001([in][out] int32& pi_uiRingTailDriverBytes,
                                           [in][out] int32& pi_uiDriverTriggerBytes,
                                           [in][out] int32& pi_uiRingTailProcessedBytes,
                                           [in][out] int32& pi_uiProcessedTriggerBytes,
                                           [in][out] int32& piMaxFilmLength_mm) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 12 00 00 00 00 00 ) 
  } // end of method IScanPictures::GetScannerInfo001

  .method public hidebysig newslot abstract virtual 
          instance void  PutScannerInfo001([in] int32 i_uiRingTailDriverBytes,
                                           [in] int32 i_uiDriverTriggerBytes,
                                           [in] int32 i_uiRingTailProcessedBytes,
                                           [in] int32 i_uiProcessedTriggerBytes,
                                           [in] int32 iMaxFilmLength_mm) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 13 00 00 00 00 00 ) 
  } // end of method IScanPictures::PutScannerInfo001

  .method public hidebysig newslot abstract virtual 
          instance void  GetScannerInfo002([in][out] int32& piRollIndex,
                                           [in][out] int32& piStripIndex,
                                           [in][out] int32& piNumberOfPictures,
                                           [in][out] int32& piFromFileFrameNumber) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 14 00 00 00 00 00 ) 
  } // end of method IScanPictures::GetScannerInfo002

  .method public hidebysig newslot abstract virtual 
          instance void  GetScannerInfoPreFrame([in] int32 iResolution,
                                                [in] int32 iFilmFormat,
                                                [in][out] int32& piHeightLR,
                                                [in][out] int32& piHeightHR_mm,
                                                [in][out] int32& piHeightHR,
                                                [in][out] int32& piWidthHR,
                                                [in][out] int32& piWidthUnitHR,
                                                [in][out] int32& plCropHRLeft,
                                                [in][out] int32& plCropHRTop,
                                                [in][out] int32& plCropHRRight,
                                                [in][out] int32& plCropHRBottom) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 15 00 00 00 00 00 ) 
  } // end of method IScanPictures::GetScannerInfoPreFrame

  .method public hidebysig newslot abstract virtual 
          instance void  GetScannerInfoPreFrameUser([in] int32 iResolution,
                                                    [in] int32 iFilmFormat,
                                                    [in][out] int32& piWidthHR,
                                                    [in][out] int32& piWidthUnitHR,
                                                    [in][out] int32& plCropHRLeft,
                                                    [in][out] int32& plCropHRTop,
                                                    [in][out] int32& plCropHRRight,
                                                    [in][out] int32& plCropHRBottom) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 16 00 00 00 00 00 ) 
  } // end of method IScanPictures::GetScannerInfoPreFrameUser

  .method public hidebysig newslot abstract virtual 
          instance void  PutScannerInfoPreFrameUser([in] int32 iResolution,
                                                    [in] int32 iFilmFormat,
                                                    [in] int32 iWidthHR,
                                                    [in] int32 iWidthUnitHR,
                                                    [in] int32 lCropHRLeft,
                                                    [in] int32 lCropHRTop,
                                                    [in] int32 lCropHRRight,
                                                    [in] int32 lCropHRBottom) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 17 00 00 00 00 00 ) 
  } // end of method IScanPictures::PutScannerInfoPreFrameUser

  .method public hidebysig newslot abstract virtual 
          instance void  ResetFactoryDefaults([in] int32 iFactoryResetControl,
                                              [in] int32 iResolution,
                                              [in] int32 iFilmFormat) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 18 00 00 00 00 00 ) 
  } // end of method IScanPictures::ResetFactoryDefaults

  .method public hidebysig newslot abstract virtual 
          instance void  ImportFromFile([in] string  marshal( bstr) bstrImportFileNames,
                                        [in] int32 bDeleteImportOnRelease,
                                        [in] string  marshal( bstr) bstrRollId) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 19 00 00 00 00 00 ) 
  } // end of method IScanPictures::ImportFromFile

} // end of class TLXLib.IScanPictures

.class interface public abstract auto ansi import TLXLib.ISavePictures
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.TypeLibTypeAttribute::.ctor(int16) = ( 01 00 40 10 00 00 )                               // ..@...
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 31 37 32 31 39 42 31 33 2D 46 31 44 39   // ..$17219B13-F1D9
                                                                                                  2D 34 37 46 37 2D 39 39 45 42 2D 35 38 34 35 37   // -47F7-99EB-58457
                                                                                                  42 30 42 38 30 39 37 00 00 )                      // B0B8097..
  .method public hidebysig newslot abstract virtual 
          instance void  GetRollCountScanGroup([in][out] int32& piRollCount) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 01 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetRollCountScanGroup

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureCountScanGroup([in] int32 iRollIndex,
                                                  [in][out] int32& piStripCount,
                                                  [in][out] int32& piPictureCount,
                                                  [in][out] int32& piScanWarnings) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 02 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetPictureCountScanGroup

  .method public hidebysig newslot abstract virtual 
          instance void  MoveOldestRollToSaveGroup() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 03 00 00 00 00 00 ) 
  } // end of method ISavePictures::MoveOldestRollToSaveGroup

  .method public hidebysig newslot abstract virtual 
          instance void  DeleteRollInScanGroup([in] int32 iRollIndex) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 04 00 00 00 00 00 ) 
  } // end of method ISavePictures::DeleteRollInScanGroup

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureCountSaveGroup([in][out] int32& piRollCount,
                                                  [in][out] int32& piStripCount,
                                                  [in][out] int32& piPictureCount,
                                                  [in][out] int32& piPictureSelectedCount,
                                                  [in][out] int32& piPictureHiddenCount) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 05 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetPictureCountSaveGroup

  .method public hidebysig newslot abstract virtual 
          instance void  ReleaseSaveGroup() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 06 00 00 00 00 00 ) 
  } // end of method ISavePictures::ReleaseSaveGroup

  .method public hidebysig newslot abstract virtual 
          instance void  SaveToDisk([in] int32 iIndex,
                                    [in] string  marshal( bstr) bstrFileName,
                                    [in] int32 iSaveControl,
                                    [in] int32 iBoundingWidth,
                                    [in] int32 iBoundingHeight,
                                    [in] int32 iRotation,
                                    [in] int32 iScalingMethod,
                                    [in] int32 iFileFormat,
                                    [in] int32 iCompression,
                                    [in] int32 iDpi,
                                    [in] int32 iColorBits) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 07 00 00 00 00 00 ) 
  } // end of method ISavePictures::SaveToDisk

  .method public hidebysig newslot abstract virtual 
          instance void  ClientMemoryBufferAdd([in] int32 i_pByteStartPointer,
                                               [in] int32 iByteCount) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 08 00 00 00 00 00 ) 
  } // end of method ISavePictures::ClientMemoryBufferAdd

  .method public hidebysig newslot abstract virtual 
          instance void  ClientMemoryBufferDismissAll() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 09 00 00 00 00 00 ) 
  } // end of method ISavePictures::ClientMemoryBufferDismissAll

  .method public hidebysig newslot abstract virtual 
          instance void  SaveToClientMemory([in] int32 iIndex,
                                            [in] int32 iSaveControl,
                                            [in] int32 iBoundingWidth,
                                            [in] int32 iBoundingHeight,
                                            [in] int32 iRotation,
                                            [in] int32 iScalingMethod,
                                            [in] int32 iFileFormatSaveToMemory,
                                            [in] int32 bUseWorkerThread) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0A 00 00 00 00 00 ) 
  } // end of method ISavePictures::SaveToClientMemory

  .method public hidebysig newslot abstract virtual 
          instance void  SaveCancel() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0B 00 00 00 00 00 ) 
  } // end of method ISavePictures::SaveCancel

  .method public hidebysig newslot abstract virtual 
          instance void  InsertPicture([in] int32 iIndex,
                                       [in] int32 iStripIndex,
                                       [in] int32 lLeftHR,
                                       [in] int32 lTopHR,
                                       [in] int32 lRightHR,
                                       [in] int32 lBottomHR) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0C 00 00 00 00 00 ) 
  } // end of method ISavePictures::InsertPicture

  .method public hidebysig newslot abstract virtual 
          instance void  DeletePicture([in] int32 iIndex) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0D 00 00 00 00 00 ) 
  } // end of method ISavePictures::DeletePicture

  .method public hidebysig newslot abstract virtual 
          instance void  GetSaveInfo([in][out] int32& piDefaultFilmProduct,
                                     [in][out] int32& piDefaultFilmSpecifier,
                                     [in][out] string&  marshal( bstr) pbstrDefaultDirectory) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0E 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetSaveInfo

  .method public hidebysig newslot abstract virtual 
          instance void  PutSaveInfo([in] int32 iDefaultFilmProduct,
                                     [in] int32 iDefaultFilmSpecifier,
                                     [in] string  marshal( bstr) bstrDefaultDirectory) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0F 00 00 00 00 00 ) 
  } // end of method ISavePictures::PutSaveInfo

  .method public hidebysig newslot abstract virtual 
          instance void  GetStripInfo([in] int32 iStripIndex,
                                      [in][out] int32& piRollIndex,
                                      [in][out] int32& pbIsStrip,
                                      [in][out] int32& piFilmColor,
                                      [in][out] int32& piFilmFormat,
                                      [in][out] int32& plHeightHR,
                                      [in][out] int32& plLengthHR,
                                      [in][out] int32& plHeightLR,
                                      [in][out] int32& plLengthLR,
                                      [in][out] int32& piScanWarnings,
                                      [in][out] int32& piFilmProduct,
                                      [in][out] int32& piFilmSpecifier,
                                      [in][out] int32& pi24mmFilmId,
                                      [in][out] int32& piDmin_R,
                                      [in][out] int32& piDmin_G,
                                      [in][out] int32& piDmin_B,
                                      [in][out] string&  marshal( bstr) pbstrRollId) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 10 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetStripInfo

  .method public hidebysig newslot abstract virtual 
          instance void  GetStripInfoAid([in] int32 iStripIndex,
                                         [in] int32 i_pByteStartPointerHeader,
                                         [in] int32 iByteCountHeader,
                                         [in] int32 i_pByteStartPointerMag,
                                         [in] int32 iByteCountMag,
                                         [in] int32 i_pByteStartPointerOptical,
                                         [in] int32 iByteCountOptical) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 11 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetStripInfoAid

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureInfo([in] int32 iIndex,
                                        [in][out] int32& piRollIndexFromStrip,
                                        [in][out] int32& piStripIndexFromStrip,
                                        [in][out] int32& piFilmProductFromStrip,
                                        [in][out] int32& piFilmSpecifierFromStrip,
                                        [in][out] string&  marshal( bstr) pbstrFrameName,
                                        [in][out] int32& piFrameNumber,
                                        [in][out] int32& piPrintAspectRatio,
                                        [in][out] string&  marshal( bstr) pbstrFileName,
                                        [in][out] string&  marshal( bstr) pbstrDirectory,
                                        [in][out] int32& piRotation,
                                        [in][out] int32& piSelectedHidden) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 12 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetPictureInfo

  .method public hidebysig newslot abstract virtual 
          instance void  PutPictureInfo([in] int32 iIndex,
                                        [in] int32 iFrameNumber,
                                        [in] string  marshal( bstr) bstrFileName,
                                        [in] string  marshal( bstr) bstrDirectory,
                                        [in] int32 iRotation,
                                        [in] int32 iSelectedHidden) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 13 00 00 00 00 00 ) 
  } // end of method ISavePictures::PutPictureInfo

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureInfo1([in] int32 iIndex,
                                         [in][out] string&  marshal( bstr) pbstrFrameName,
                                         [in][out] int32& piFrameNumber,
                                         [in][out] string&  marshal( bstr) pbstrFileName,
                                         [in][out] string&  marshal( bstr) pbstrDirectory) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 14 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetPictureInfo1

  .method public hidebysig newslot abstract virtual 
          instance void  PutPictureInfo1([in] int32 iIndex,
                                         [in] int32 iFrameNumber,
                                         [in] string  marshal( bstr) bstrFileName,
                                         [in] string  marshal( bstr) bstrDirectory) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 15 00 00 00 00 00 ) 
  } // end of method ISavePictures::PutPictureInfo1

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureInfo2([in] int32 iIndex,
                                         [in][out] int32& piMagneticDataStatus,
                                         [in][out] int32& piPrintAspectRatio,
                                         [in][out] string&  marshal( bstr) pbstrTitleOrImportFileName,
                                         [in][out] int32& piYear,
                                         [in][out] int32& piMonth,
                                         [in][out] int32& piDayOfMonth,
                                         [in][out] int32& piSecondsAfterMidnight) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 16 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetPictureInfo2

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureInfoAid([in] int32 iIndex,
                                           [in][out] int32& piFrameNumberAid,
                                           [in][out] int32& piMagneticDataStatus,
                                           [in] int32 i_pByteStartPointerMag,
                                           [in] int32 iByteCountMag,
                                           [in] int32 i_pByteStartPointerOptical,
                                           [in] int32 iByteCountOptical) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 17 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetPictureInfoAid

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureRotation([in] int32 iIndex,
                                            [in][out] int32& piRotation) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 18 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetPictureRotation

  .method public hidebysig newslot abstract virtual 
          instance void  PutPictureRotation([in] int32 iIndex,
                                            [in] int32 iRotation) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 19 00 00 00 00 00 ) 
  } // end of method ISavePictures::PutPictureRotation

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureSelection([in] int32 iIndex,
                                             [in][out] int32& piSelectedHidden) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 1A 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetPictureSelection

  .method public hidebysig newslot abstract virtual 
          instance void  PutPictureSelection([in] int32 iIndex,
                                             [in] int32 iSelectedHidden,
                                             [in] int32 bSkipHidden) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 1B 00 00 00 00 00 ) 
  } // end of method ISavePictures::PutPictureSelection

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureFramingInfo([in] int32 iIndex,
                                               [in][out] int32& piFramingRisk,
                                               [in][out] int32& plLeftHR,
                                               [in][out] int32& plTopHR,
                                               [in][out] int32& plRightHR,
                                               [in][out] int32& plBottomHR) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 1C 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetPictureFramingInfo

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureFramingUserInfo([in] int32 iIndex,
                                                   [in][out] int32& plLeftHR,
                                                   [in][out] int32& plTopHR,
                                                   [in][out] int32& plRightHR,
                                                   [in][out] int32& plBottomHR) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 1D 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetPictureFramingUserInfo

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureFramingUserInfoLowRes([in] int32 iIndex,
                                                         [in][out] int32& plLeftLR,
                                                         [in][out] int32& plTopLR,
                                                         [in][out] int32& plRightLR,
                                                         [in][out] int32& plBottomLR) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 1E 00 00 00 00 00 ) 
  } // end of method ISavePictures::GetPictureFramingUserInfoLowRes

  .method public hidebysig newslot abstract virtual 
          instance void  PutPictureFramingUserInfo([in] int32 iIndex,
                                                   [in] int32 lLeftHR,
                                                   [in] int32 lTopHR,
                                                   [in] int32 lRightHR,
                                                   [in] int32 lBottomHR) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 1F 00 00 00 00 00 ) 
  } // end of method ISavePictures::PutPictureFramingUserInfo

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureColorSettings([in] int32 iIndex,
                                                 [in][out] int32& piRed,
                                                 [in][out] int32& piGreen,
                                                 [in][out] int32& piBlue,
                                                 [in][out] int32& piBrightness,
                                                 [in][out] int32& piContrast,
                                                 [in][out] int32& piSharpness) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 20 00 00 00 00 00 )                         // .. .....
  } // end of method ISavePictures::GetPictureColorSettings

  .method public hidebysig newslot abstract virtual 
          instance void  PutPictureColorSettings([in] int32 iIndex,
                                                 [in] int32 iRed,
                                                 [in] int32 iGreen,
                                                 [in] int32 iBlue,
                                                 [in] int32 iBrightness,
                                                 [in] int32 iContrast,
                                                 [in] int32 iSharpness) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 21 00 00 00 00 00 )                         // ..!.....
  } // end of method ISavePictures::PutPictureColorSettings

  .method public hidebysig newslot abstract virtual 
          instance void  PutPictureColorSettingsDifferential([in] int32 iIndex,
                                                             [in] int32 iRed,
                                                             [in] int32 iGreen,
                                                             [in] int32 iBlue,
                                                             [in] int32 iBrightness,
                                                             [in] int32 iContrast,
                                                             [in] int32 iSharpness) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 22 00 00 00 00 00 )                         // ..".....
  } // end of method ISavePictures::PutPictureColorSettingsDifferential

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureLightingDirection([in] int32 iIndex,
                                                     [in][out] int32& piPictureLightingDirection) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 23 00 00 00 00 00 )                         // ..#.....
  } // end of method ISavePictures::GetPictureLightingDirection

  .method public hidebysig newslot abstract virtual 
          instance void  PutPictureLightingDirection([in] int32 iIndex,
                                                     [in] int32 iPictureLightingDirection) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 24 00 00 00 00 00 )                         // ..$.....
  } // end of method ISavePictures::PutPictureLightingDirection

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureRedEyeSettings([in] int32 iIndex,
                                                  [in][out] int32& piRedEye,
                                                  [in][out] int32& plLeftHR,
                                                  [in][out] int32& plTopHR,
                                                  [in][out] int32& plRightHR,
                                                  [in][out] int32& plBottomHR) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 25 00 00 00 00 00 )                         // ..%.....
  } // end of method ISavePictures::GetPictureRedEyeSettings

  .method public hidebysig newslot abstract virtual 
          instance void  PutPictureRedEyeSettings([in] int32 iIndex,
                                                  [in] int32 iRedEye,
                                                  [in] int32 lLeftHR,
                                                  [in] int32 lTopHR,
                                                  [in] int32 lRightHR,
                                                  [in] int32 lBottomHR) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 26 00 00 00 00 00 )                         // ..&.....
  } // end of method ISavePictures::PutPictureRedEyeSettings

} // end of class TLXLib.ISavePictures

.class interface public abstract auto ansi import TLXLib.ISavePictures1
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 45 45 35 36 33 45 34 37 2D 37 41 34 38   // ..$EE563E47-7A48
                                                                                                  2D 34 39 46 34 2D 41 35 43 36 2D 33 33 37 33 34   // -49F4-A5C6-33734
                                                                                                  43 36 44 30 31 46 35 00 00 )                      // C6D01F5..
  .custom instance void [mscorlib]System.Runtime.InteropServices.TypeLibTypeAttribute::.ctor(int16) = ( 01 00 40 10 00 00 )                               // ..@...
  .method public hidebysig newslot abstract virtual 
          instance void  GetStripInfo1([in] int32 iStripIndex,
                                       [in][out] int32& piRollIndex,
                                       [in][out] int32& pbIsStrip,
                                       [in][out] int32& piFilmColor,
                                       [in][out] int32& piFilmFormat,
                                       [in][out] int32& plHeightHR,
                                       [in][out] int32& plLengthHR,
                                       [in][out] int32& plHeightLR,
                                       [in][out] int32& plLengthLR,
                                       [in][out] int32& piScanWarnings,
                                       [in][out] int32& piFilmProduct,
                                       [in][out] int32& piFilmSpecifier,
                                       [in][out] int32& pi24mmFilmId,
                                       [in][out] int32& piDmin_R,
                                       [in][out] int32& piDmin_G,
                                       [in][out] int32& piDmin_B,
                                       [in][out] string&  marshal( bstr) pbstrRollId,
                                       [in][out] int32& piCartridgeHandOfLoad) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 01 00 00 00 00 00 ) 
  } // end of method ISavePictures1::GetStripInfo1

  .method public hidebysig newslot abstract virtual 
          instance void  Put24mmFilmId([in] int32 iStripIndex,
                                       [in] int32 i24mmFilmId) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 02 00 00 00 00 00 ) 
  } // end of method ISavePictures1::Put24mmFilmId

} // end of class TLXLib.ISavePictures1

.class interface public abstract auto ansi import TLXLib.IScanPictures2
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 46 42 41 31 41 38 38 31 2D 37 36 43 43   // ..$FBA1A881-76CC
                                                                                                  2D 34 31 45 33 2D 41 45 45 44 2D 30 34 42 30 32   // -41E3-AEED-04B02
                                                                                                  43 45 32 31 43 35 42 00 00 )                      // CE21C5B..
  .custom instance void [mscorlib]System.Runtime.InteropServices.TypeLibTypeAttribute::.ctor(int16) = ( 01 00 40 10 00 00 )                               // ..@...
  .method public hidebysig newslot abstract virtual 
          instance void  ImportFromFile2([in] string  marshal( bstr) bstrImportFileNames,
                                         [in] int32 bDeleteImportOnRelease,
                                         [in] int32 bUsePremiumColorPath,
                                         [in] string  marshal( bstr) bstrRollId) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 01 00 00 00 00 00 ) 
  } // end of method IScanPictures2::ImportFromFile2

} // end of class TLXLib.IScanPictures2

.class interface public abstract auto ansi import TLXLib.ISavePictures2
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 45 31 32 46 43 37 34 43 2D 32 38 44 46   // ..$E12FC74C-28DF
                                                                                                  2D 34 38 35 35 2D 42 45 35 45 2D 44 45 37 45 37   // -4855-BE5E-DE7E7
                                                                                                  46 33 46 45 38 32 36 00 00 )                      // F3FE826..
  .custom instance void [mscorlib]System.Runtime.InteropServices.TypeLibTypeAttribute::.ctor(int16) = ( 01 00 40 10 00 00 )                               // ..@...
  .method public hidebysig newslot abstract virtual 
          instance void  PutPictureBnWEffect([in] int32 iIndex,
                                             [in] int32 iBnWEffect) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 01 00 00 00 00 00 ) 
  } // end of method ISavePictures2::PutPictureBnWEffect

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureBnWEffect([in] int32 iIndex,
                                             [in][out] int32& piBnWEffect) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 02 00 00 00 00 00 ) 
  } // end of method ISavePictures2::GetPictureBnWEffect

  .method public hidebysig newslot abstract virtual 
          instance void  PutPictureSaturation([in] int32 iIndex,
                                              [in] int32 iSaturation) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 03 00 00 00 00 00 ) 
  } // end of method ISavePictures2::PutPictureSaturation

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureSaturation([in] int32 iIndex,
                                              [in][out] int32& piSaturation) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 04 00 00 00 00 00 ) 
  } // end of method ISavePictures2::GetPictureSaturation

} // end of class TLXLib.ISavePictures2

.class interface public abstract auto ansi import TLXLib.ISavePictures3
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.TypeLibTypeAttribute::.ctor(int16) = ( 01 00 40 10 00 00 )                               // ..@...
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 32 46 33 35 43 41 36 41 2D 30 35 44 37   // ..$2F35CA6A-05D7
                                                                                                  2D 34 35 31 33 2D 41 32 33 36 2D 32 44 35 38 33   // -4513-A236-2D583
                                                                                                  30 35 41 36 32 32 43 00 00 )                      // 05A622C..
  .method public hidebysig newslot abstract virtual 
          instance void  GetSaveInfo1([out] int32& piDefaultFilmProduct,
                                      [out] int32& piDefaultFilmSpecifier,
                                      [out] string&  marshal( bstr) pbstrDefaultDirectory) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 01 00 00 00 00 00 ) 
  } // end of method ISavePictures3::GetSaveInfo1

  .method public hidebysig newslot abstract virtual 
          instance void  GetStripInfo2([in] int32 iStripIndex,
                                       [out] int32& piRollIndex,
                                       [out] int32& pbIsStrip,
                                       [out] int32& piFilmColor,
                                       [out] int32& piFilmFormat,
                                       [out] int32& plHeightHR,
                                       [out] int32& plLengthHR,
                                       [out] int32& plHeightLR,
                                       [out] int32& plLengthLR,
                                       [out] int32& piScanWarnings,
                                       [out] int32& piFilmProduct,
                                       [out] int32& piFilmSpecifier,
                                       [out] int32& pi24mmFilmId,
                                       [out] int32& piDmin_R,
                                       [out] int32& piDmin_G,
                                       [out] int32& piDmin_B,
                                       [out] string&  marshal( bstr) pbstrRollId,
                                       [out] int32& piCartridgeHandOfLoad) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 02 00 00 00 00 00 ) 
  } // end of method ISavePictures3::GetStripInfo2

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureInfo3([in] int32 iIndex,
                                         [out] int32& piRollIndexFromStrip,
                                         [out] int32& piStripIndexFromStrip,
                                         [out] int32& piFilmProductFromStrip,
                                         [out] int32& piFilmSpecifierFromStrip,
                                         [out] string&  marshal( bstr) pbstrFrameName,
                                         [out] int32& piFrameNumber,
                                         [out] int32& piPrintAspectRatio,
                                         [out] string&  marshal( bstr) pbstrFileName,
                                         [out] string&  marshal( bstr) pbstrDirectory,
                                         [out] int32& piRotation,
                                         [out] int32& piSelectedHidden) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 03 00 00 00 00 00 ) 
  } // end of method ISavePictures3::GetPictureInfo3

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureInfo4([in] int32 iIndex,
                                         [out] string&  marshal( bstr) pbstrFrameName,
                                         [out] int32& piFrameNumber,
                                         [out] string&  marshal( bstr) pbstrFileName,
                                         [out] string&  marshal( bstr) pbstrDirectory) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 04 00 00 00 00 00 ) 
  } // end of method ISavePictures3::GetPictureInfo4

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureInfo5([in] int32 iIndex,
                                         [out] int32& piMagneticDataStatus,
                                         [out] int32& piPrintAspectRatio,
                                         [out] string&  marshal( bstr) pbstrTitleOrImportFileName,
                                         [out] int32& piYear,
                                         [out] int32& piMonth,
                                         [out] int32& piDayOfMonth,
                                         [out] int32& piSecondsAfterMidnight) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 05 00 00 00 00 00 ) 
  } // end of method ISavePictures3::GetPictureInfo5

} // end of class TLXLib.ISavePictures3

.class interface public abstract auto ansi import TLXLib.ICalibrationWizard
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 45 44 42 39 41 32 41 34 2D 44 44 41 32   // ..$EDB9A2A4-DDA2
                                                                                                  2D 34 33 38 35 2D 38 36 39 45 2D 41 33 45 34 30   // -4385-869E-A3E40
                                                                                                  34 45 38 38 32 42 31 00 00 )                      // 4E882B1..
  .custom instance void [mscorlib]System.Runtime.InteropServices.TypeLibTypeAttribute::.ctor(int16) = ( 01 00 40 10 00 00 )                               // ..@...
  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationEnable([in] string  marshal( bstr) bstrLicense) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 01 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationEnable

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationBegin([in] int32 iResolution,
                                          [in] int32 iFilmColor,
                                          [in] int32 iFilmFormat,
                                          [in] int32 bUseScratchRemoval,
                                          [in] int32 i_pByteStartPointer) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 02 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationBegin

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationGetDpi([in] int32 iResolution,
                                           [in] int32 iFilmFormat,
                                           [in][out] int32& piHeightToCcd,
                                           [in][out] int32& piHeight,
                                           [in][out] int32& piOffset,
                                           [in][out] int32& piMotorAdjust,
                                           [in][out] int32& piMotorAdjust_Ir,
                                           [in][out] int32& piMotorAdjustDrag,
                                           [in][out] int32& piMotorAdjustDrag_Ir,
                                           [in][out] int32& piMotorSpeed,
                                           [in][out] int32& piMotorSpeed_Ir,
                                           [in][out] int32& piStepperLens,
                                           [in][out] int32& piStepperCCD,
                                           [in][out] int32& piStepperCCDAdjust) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 03 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationGetDpi

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationPutDpi([in] int32 iResolution,
                                           [in] int32 iFilmFormat,
                                           [in] int32 bCalibrateGroup,
                                           [in] int32 iHeightToCcd,
                                           [in] int32 iHeight,
                                           [in] int32 iOffset,
                                           [in] int32 iMotorSpeed,
                                           [in] int32 iMotorSpeed_Ir,
                                           [in] int32 iStepperLens,
                                           [in] int32 iStepperCCD) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 04 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationPutDpi

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationGetLightIncandescent([in] int32 iResolution,
                                                         [in] int32 iFilmFormat,
                                                         [in] int32 iFilmColor,
                                                         [in][out] int32& piGain_R,
                                                         [in][out] int32& piGain_G,
                                                         [in][out] int32& piGain_B,
                                                         [in][out] int32& piOffset_R,
                                                         [in][out] int32& piOffset_G,
                                                         [in][out] int32& piOffset_B,
                                                         [in][out] int32& piCcdExposure_R,
                                                         [in][out] int32& piCcdExposure_G,
                                                         [in][out] int32& piCcdExposure_B,
                                                         [in][out] int32& piIrLEDStartTime,
                                                         [in][out] int32& piCurrent_Ir,
                                                         [in][out] int32& piCcdExposureOpenGate_R,
                                                         [in][out] int32& piCcdExposureOpenGate_G,
                                                         [in][out] int32& piCcdExposureOpenGate_B,
                                                         [in][out] int32& piIrLEDStartTimeOpenGate,
                                                         [in][out] int32& piCurrentOpenGate_Ir,
                                                         [in][out] int32& piDetectWhite_G,
                                                         [in][out] int32& piDetectFilm_G) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 05 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationGetLightIncandescent

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationPutLightIncandescent([in] int32 iResolution,
                                                         [in] int32 iFilmFormat,
                                                         [in] int32 iFilmColor,
                                                         [in] int32 bCalibrateGroup,
                                                         [in] int32 iGain_R,
                                                         [in] int32 iGain_G,
                                                         [in] int32 iGain_B,
                                                         [in] int32 iOffset_R,
                                                         [in] int32 iOffset_G,
                                                         [in] int32 iOffset_B,
                                                         [in] int32 iCcdExposure_R,
                                                         [in] int32 iCcdExposure_G,
                                                         [in] int32 iCcdExposure_B,
                                                         [in] int32 iIrLEDStartTime,
                                                         [in] int32 iCurrent_Ir,
                                                         [in] int32 iCcdExposureOpenGate_R,
                                                         [in] int32 iCcdExposureOpenGate_G,
                                                         [in] int32 iCcdExposureOpenGate_B,
                                                         [in] int32 iIrLEDStartTimeOpenGate,
                                                         [in] int32 iCurrentOpenGate_Ir,
                                                         [in] int32 iDetectWhite_G,
                                                         [in] int32 iDetectFilm_G) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 06 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationPutLightIncandescent

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationGetLightLED([in] int32 iResolution,
                                                [in] int32 iFilmFormat,
                                                [in] int32 iFilmColor,
                                                [in] int32 bUseScratchRemoval,
                                                [in][out] int32& piGain_R,
                                                [in][out] int32& piGain_G,
                                                [in][out] int32& piGain_B,
                                                [in][out] int32& piOffset_R,
                                                [in][out] int32& piOffset_G,
                                                [in][out] int32& piOffset_B,
                                                [in][out] int32& piCurrent_R,
                                                [in][out] int32& piCurrent_G,
                                                [in][out] int32& piCurrent_B,
                                                [in][out] int32& piCurrent_Ir,
                                                [in][out] float64& pdfDutyCycle_R,
                                                [in][out] float64& pdfDutyCycle_G,
                                                [in][out] float64& pdfDutyCycle_B,
                                                [in][out] float64& pdfDutyCycle_Ir,
                                                [in][out] int32& piDetectWhite_G,
                                                [in][out] int32& piDetectFilm_G,
                                                [in][out] float64& pdfAmbientTemperature,
                                                [in][out] float64& pdfLockedTemperature,
                                                [in][out] float64& pdfVisibleTemperature,
                                                [in][out] float64& pdfIrTemperature) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 07 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationGetLightLED

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationPutLightLED([in] int32 iResolution,
                                                [in] int32 iFilmFormat,
                                                [in] int32 iFilmColor,
                                                [in] int32 bUseScratchRemoval,
                                                [in] int32 bCalibrateGroup,
                                                [in] int32 iGain_R,
                                                [in] int32 iGain_G,
                                                [in] int32 iGain_B,
                                                [in] int32 iOffset_R,
                                                [in] int32 iOffset_G,
                                                [in] int32 iOffset_B,
                                                [in] int32 iCurrent_R,
                                                [in] int32 iCurrent_G,
                                                [in] int32 iCurrent_B,
                                                [in] int32 iCurrent_Ir,
                                                [in] float64 dfDutyCycle_R,
                                                [in] float64 dfDutyCycle_G,
                                                [in] float64 dfDutyCycle_B,
                                                [in] float64 dfDutyCycle_Ir,
                                                [in] int32 iDetectWhite_G,
                                                [in] int32 iDetectFilm_G) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 08 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationPutLightLED

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationGetColorMatrix3By4([in] int32 iColorMatrix,
                                                       [in][out] float64& pdfMatrixValue0_0,
                                                       [in][out] float64& pdfMatrixValue0_1,
                                                       [in][out] float64& pdfMatrixValue0_2,
                                                       [in][out] float64& pdfMatrixValue0_3,
                                                       [in][out] float64& pdfMatrixValue1_0,
                                                       [in][out] float64& pdfMatrixValue1_1,
                                                       [in][out] float64& pdfMatrixValue1_2,
                                                       [in][out] float64& pdfMatrixValue1_3,
                                                       [in][out] float64& pdfMatrixValue2_0,
                                                       [in][out] float64& pdfMatrixValue2_1,
                                                       [in][out] float64& pdfMatrixValue2_2,
                                                       [in][out] float64& pdfMatrixValue2_3) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 09 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationGetColorMatrix3By4

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationPutColorMatrix3By4([in] int32 iColorMatrix,
                                                       [in] int32 bCalibrateGroup,
                                                       [in] float64 dfMatrixValue0_0,
                                                       [in] float64 dfMatrixValue0_1,
                                                       [in] float64 dfMatrixValue0_2,
                                                       [in] float64 dfMatrixValue0_3,
                                                       [in] float64 dfMatrixValue1_0,
                                                       [in] float64 dfMatrixValue1_1,
                                                       [in] float64 dfMatrixValue1_2,
                                                       [in] float64 dfMatrixValue1_3,
                                                       [in] float64 dfMatrixValue2_0,
                                                       [in] float64 dfMatrixValue2_1,
                                                       [in] float64 dfMatrixValue2_2,
                                                       [in] float64 dfMatrixValue2_3) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0A 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationPutColorMatrix3By4

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationGetColorMatrix3By10([in] int32 iFilmColor,
                                                        [in][out] float32& pfMatrixValue0_0,
                                                        [in][out] float32& pfMatrixValue0_1,
                                                        [in][out] float32& pfMatrixValue0_2,
                                                        [in][out] float32& pfMatrixValue0_3,
                                                        [in][out] float32& pfMatrixValue0_4,
                                                        [in][out] float32& pfMatrixValue0_5,
                                                        [in][out] float32& pfMatrixValue0_6,
                                                        [in][out] float32& pfMatrixValue0_7,
                                                        [in][out] float32& pfMatrixValue0_8,
                                                        [in][out] float32& pfMatrixValue0_9,
                                                        [in][out] float32& pfMatrixValue1_0,
                                                        [in][out] float32& pfMatrixValue1_1,
                                                        [in][out] float32& pfMatrixValue1_2,
                                                        [in][out] float32& pfMatrixValue1_3,
                                                        [in][out] float32& pfMatrixValue1_4,
                                                        [in][out] float32& pfMatrixValue1_5,
                                                        [in][out] float32& pfMatrixValue1_6,
                                                        [in][out] float32& pfMatrixValue1_7,
                                                        [in][out] float32& pfMatrixValue1_8,
                                                        [in][out] float32& pfMatrixValue1_9,
                                                        [in][out] float32& pfMatrixValue2_0,
                                                        [in][out] float32& pfMatrixValue2_1,
                                                        [in][out] float32& pfMatrixValue2_2,
                                                        [in][out] float32& pfMatrixValue2_3,
                                                        [in][out] float32& pfMatrixValue2_4,
                                                        [in][out] float32& pfMatrixValue2_5,
                                                        [in][out] float32& pfMatrixValue2_6,
                                                        [in][out] float32& pfMatrixValue2_7,
                                                        [in][out] float32& pfMatrixValue2_8,
                                                        [in][out] float32& pfMatrixValue2_9) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0B 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationGetColorMatrix3By10

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationPutColorMatrix3By10([in] int32 iFilmColor,
                                                        [in] int32 bCalibrateGroup,
                                                        [in] float32 fMatrixValue0_0,
                                                        [in] float32 fMatrixValue0_1,
                                                        [in] float32 fMatrixValue0_2,
                                                        [in] float32 fMatrixValue0_3,
                                                        [in] float32 fMatrixValue0_4,
                                                        [in] float32 fMatrixValue0_5,
                                                        [in] float32 fMatrixValue0_6,
                                                        [in] float32 fMatrixValue0_7,
                                                        [in] float32 fMatrixValue0_8,
                                                        [in] float32 fMatrixValue0_9,
                                                        [in] float32 fMatrixValue1_0,
                                                        [in] float32 fMatrixValue1_1,
                                                        [in] float32 fMatrixValue1_2,
                                                        [in] float32 fMatrixValue1_3,
                                                        [in] float32 fMatrixValue1_4,
                                                        [in] float32 fMatrixValue1_5,
                                                        [in] float32 fMatrixValue1_6,
                                                        [in] float32 fMatrixValue1_7,
                                                        [in] float32 fMatrixValue1_8,
                                                        [in] float32 fMatrixValue1_9,
                                                        [in] float32 fMatrixValue2_0,
                                                        [in] float32 fMatrixValue2_1,
                                                        [in] float32 fMatrixValue2_2,
                                                        [in] float32 fMatrixValue2_3,
                                                        [in] float32 fMatrixValue2_4,
                                                        [in] float32 fMatrixValue2_5,
                                                        [in] float32 fMatrixValue2_6,
                                                        [in] float32 fMatrixValue2_7,
                                                        [in] float32 fMatrixValue2_8,
                                                        [in] float32 fMatrixValue2_9) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0C 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationPutColorMatrix3By10

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationPutIdentification([in] int32 bCalibrateGroup,
                                                      [in] int32 iScannerVersionHw,
                                                      [in] int32 iScannerType,
                                                      [in] int32 iScannerSerialNumber) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0D 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationPutIdentification

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationChange([in] int32 iResolution,
                                           [in] int32 iFilmColor,
                                           [in] int32 iFilmFormat,
                                           [in] int32 bUseScratchRemoval) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0E 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationChange

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationAcquire([in] int32 iScanLines) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 0F 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationAcquire

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationPutFilterWheelPosition([in] int32 iFilmColor) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 10 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationPutFilterWheelPosition

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationPutFilmPressureRollerPosition([in] int32 bEngage) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 11 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationPutFilmPressureRollerPosition

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationAdvanceFilm([in] int32 iAdvanceMilliseconds,
                                                [in] int32 iAdvanceSpeed) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 12 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationAdvanceFilm

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationFocus([in] int32 bFindTiltTurns) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 13 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationFocus

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationFocusResults([in][out] int32& piCalibrateFocusErrorCenter,
                                                 [in][out] int32& piCalibrateFocusErrorLeft,
                                                 [in][out] int32& piCalibrateFocusErrorRight,
                                                 [in][out] int32& piCalibrateFocusOffsetCenter,
                                                 [in][out] int32& piCalibrateFocusOffsetLeft,
                                                 [in][out] int32& piCalibrateFocusOffsetRight,
                                                 [in][out] int32& piCalibrateTiltEighthTurns) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 14 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationFocusResults

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationPutEEProm() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 15 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationPutEEProm

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationEnd() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 16 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationEnd

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationMofReader([in] int32 iCalibrateMofControl,
                                              [in][out] int32& piValue) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 17 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationMofReader

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationStepperTest() runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 18 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationStepperTest

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationStepperTestResults([in][out] int32& piCCDExpected,
                                                       [in][out] int32& piCCDActual,
                                                       [in][out] int32& piLensExpected,
                                                       [in][out] int32& piLensActual) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 19 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationStepperTestResults

  .method public hidebysig newslot abstract virtual 
          instance void  CalibrationDotNet([in] valuetype TLXLib.CALIBRATE_CONTROL_000 Unused1,
                                           [in] valuetype TLXLib.COLOR_PORTRAIT_MODE_000 Unused2,
                                           [in] valuetype TLXLib.ERROR_CODES_000 Unused3,
                                           [in] valuetype TLXLib.FACTORY_RESET_CONTROL_000 Unused4,
                                           [in] valuetype TLXLib.FILE_FORMAT_000 Unused5,
                                           [in] valuetype TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 Unused6,
                                           [in] valuetype TLXLib.FILM_COLOR_000 Unused7,
                                           [in] valuetype TLXLib.FILM_FORMAT_000 Unused8,
                                           [in] valuetype TLXLib.FILM_TRACK_TEST_ERRORS_000 Unused9,
                                           [in] valuetype TLXLib.FRAME_SIZES_000 Unused10,
                                           [in] valuetype TLXLib.FRAME_TYPE_000 Unused11,
                                           [in] valuetype TLXLib.FRAMING_RISK_000 Unused12,
                                           [in] valuetype TLXLib.HARDWARE_CB_000 Unused13,
                                           [in] valuetype TLXLib.HARDWARE_CB_APS_000 Unused14,
                                           [in] valuetype TLXLib.INDEX_000 Unused15,
                                           [in] valuetype TLXLib.INITIALIZE_CONTROL_000 Unused16,
                                           [in] valuetype TLXLib.INITIALIZE_WARNINGS_000 Unused17,
                                           [in] valuetype TLXLib.INT_IID_000 Unused18,
                                           [in] valuetype TLXLib.RESOLUTION_000 Unused19,
                                           [in] valuetype TLXLib.ROTATE_000 Unused20,
                                           [in] valuetype TLXLib.S_OR_H_000 Unused21,
                                           [in] valuetype TLXLib.SAVE_CONTROL_000 Unused22,
                                           [in] valuetype TLXLib.SCALING_METHOD_000 Unused23,
                                           [in] valuetype TLXLib.SCAN_CONTROL_000 Unused24,
                                           [in] valuetype TLXLib.SCAN_WARNINGS_000 Unused25,
                                           [in] valuetype TLXLib.SCANNER_TYPE_000 Unused26,
                                           [in] valuetype TLXLib.SCANNER_VERSION_HW_000 Unused27,
                                           [in] valuetype TLXLib.STRIP_MODE_000 Unused28,
                                           [in] valuetype TLXLib.WORKER_THREAD_OPERATION_000 Unused29,
                                           [in] valuetype TLXLib.WORKER_THREAD_PROGRESS_000 Unused30) runtime managed internalcall
  {
    .custom instance void [mscorlib]System.Runtime.InteropServices.DispIdAttribute::.ctor(int32) = ( 01 00 1A 00 00 00 00 00 ) 
  } // end of method ICalibrationWizard::CalibrationDotNet

} // end of class TLXLib.ICalibrationWizard

.class public auto ansi sealed TLXLib.CALIBRATE_CONTROL_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 37 42 46 45 35 31 36 43 2D 35 38 46 39   // ..$7BFE516C-58F9
                                                                                                  2D 34 38 36 39 2D 38 42 41 31 2D 35 37 42 36 32   // -4869-8BA1-57B62
                                                                                                  33 31 41 31 42 43 44 00 00 )                      // 31A1BCD..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.CALIBRATE_CONTROL_000 CALIBRATE_Light = int32(0x00000001)
  .field public static literal valuetype TLXLib.CALIBRATE_CONTROL_000 CALIBRATE_Focus = int32(0x00000004)
  .field public static literal valuetype TLXLib.CALIBRATE_CONTROL_000 CALIBRATE_FocusAdvanceFilm = int32(0x00000008)
  .field public static literal valuetype TLXLib.CALIBRATE_CONTROL_000 CALIBRATE_Wizard = int32(0x00000010)
  .field public static literal valuetype TLXLib.CALIBRATE_CONTROL_000 CALIBRATE_ExerciseSteppers = int32(0x00000040)
  .field public static literal valuetype TLXLib.CALIBRATE_CONTROL_000 CALIBRATE_UseScratchRemoval = int32(0x00000080)
} // end of class TLXLib.CALIBRATE_CONTROL_000

.class public auto ansi sealed TLXLib.COLOR_PORTRAIT_MODE_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 42 33 38 30 36 38 35 44 2D 45 36 31 45   // ..$B380685D-E61E
                                                                                                  2D 34 37 37 42 2D 39 41 36 42 2D 42 36 35 30 30   // -477B-9A6B-B6500
                                                                                                  44 42 41 41 46 37 39 00 00 )                      // DBAAF79..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.COLOR_PORTRAIT_MODE_000 COLOR_PORTRAIT_MODE_NOT = int32(0x00000000)
  .field public static literal valuetype TLXLib.COLOR_PORTRAIT_MODE_000 COLOR_PORTRAIT_MODE_PORTRAIT = int32(0x00000001)
} // end of class TLXLib.COLOR_PORTRAIT_MODE_000

.class public auto ansi sealed TLXLib.ERROR_CODES_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 35 41 38 41 36 35 44 37 2D 41 34 43 39   // ..$5A8A65D7-A4C9
                                                                                                  2D 34 30 44 43 2D 41 34 32 42 2D 42 31 31 46 43   // -40DC-A42B-B11FC
                                                                                                  37 34 42 35 39 31 31 00 00 )                      // 74B5911..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_InvalidPtrToClientCallback = int32(0x00000001)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WorkerThreadExists = int32(0x00000002)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterface = int32(0x00000003)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_CoMarshalInterThreadInterfaceInStream = int32(0x00000004)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_UnableToCreateWorkerThread = int32(0x00000005)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WorkerThreadCoInitialize = int32(0x00000006)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WorkerThreadCoGetInterfaceAndReleaseStream = int32(0x00000007)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WorkerThreadClientSignal = int32(0x00000008)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WorkerThreadStartTimeout = int32(0x00000009)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ScannerNotInitialized = int32(0x0000000A)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_NoPicturesOrStrips = int32(0x0000000B)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_TooManyRolls = int32(0x0000000C)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_InvalidIndex = int32(0x0000000D)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_InvalidMemberVariable = int32(0x0000000E)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_InvalidParameter = int32(0x0000000F)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_NoWorkerThreadForMultipleSaveToMemory = int32(0x00000010)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_NoClientMemoryBuffer = int32(0x00000011)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_OneFileNameForMultipleSaves = int32(0x00000012)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_StartUpError = int32(0x00000013)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_CBAdviseAlreadyCalled = int32(0x00000014)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_CBAdviseNotCalled = int32(0x00000015)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_InitializeScannerAlreadyCalled = int32(0x00000016)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_AdjustMotorSpeedIsZero = int32(0x00000017)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_NotSupportedByHW = int32(0x00000018)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PreviousError = int32(0x00000019)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_CallEnableFullCalibration = int32(0x0000001A)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_FileNameListEmpty = int32(0x0000001B)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_LampError = int32(0x0000001C)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ChangingFrameNumberWithAps = int32(0x0000001D)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_NotAllowedWithAps = int32(0x0000001E)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_AidNoRoll = int32(0x00000064)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ApsCartridgeUnpacked = int32(0x00000065)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ApsEjectButtonPressed = int32(0x00000066)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ApsFilmEndError = int32(0x00000067)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ApsFilmJamExtract = int32(0x00000068)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ApsFilmJamScan = int32(0x00000069)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ApsFilmJamRetract = int32(0x0000006A)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ApsNoCartridge = int32(0x0000006B)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ApsOverflow = int32(0x0000006C)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ApsPark = int32(0x0000006D)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ApsParkInit = int32(0x0000006E)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ApsUnprocessedFilm = int32(0x0000006F)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BadFileData = int32(0x00000070)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BadSimulatorFile = int32(0x00000071)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BufferDriveMegabytesRollTooSmall = int32(0x00000072)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_CalibratingWizardBusyOrNotRunning = int32(0x00000073)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ClientMemoryBufferInUse = int32(0x00000074)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_CreateDirectoryInvalidForm = int32(0x00000075)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_CS_DoubleUnlock = int32(0x00000076)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_CS_InvalidUnlock = int32(0x00000077)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_CS_NotUnlockedAtExit = int32(0x00000078)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DllInitialize = int32(0x00000079)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_EEPromAddress = int32(0x0000007A)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_EEPromCorrupted = int32(0x0000007B)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_EEPromLength = int32(0x0000007C)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_EEPromMemoryAddress = int32(0x0000007D)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_EEPromWarningBlank = int32(0x0000007E)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_EEPromWarningCheckSumBad = int32(0x0000007F)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_FileNotFound = int32(0x00000080)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_FilmInGuides = int32(0x00000081)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_FirmwareVerification = int32(0x00000082)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_FocusCurvatureThreshold = int32(0x00000083)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_FocusOutsideRegionOfInterest = int32(0x00000084)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_FocusPredictorThreshold = int32(0x00000085)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_FocusQuadRegress = int32(0x00000086)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_HardwareFault = int32(0x00000087)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ImageNotPlanar = int32(0x00000088)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ImportedFileColor = int32(0x00000089)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_InsufficientMemoryForSaveToMemory = int32(0x0000008A)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_InsufficientMemoryPassedIn = int32(0x0000008B)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_LampWarmUpFailure = int32(0x0000008C)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_MemoryNew = int32(0x0000008D)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_MissingDllFunction = int32(0x0000008E)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_NoFixedPatternCorrection = int32(0x0000008F)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_NoHighResolutionBuffer = int32(0x00000090)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_NoStripsScanned = int32(0x00000091)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ParsingError = int32(0x00000092)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PicVersion = int32(0x00000093)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PreviousHardwareFaultAps = int32(0x00000094)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ProcessedRingTailOverflow = int32(0x00000095)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_RegistryRead = int32(0x00000096)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ScanLineAcquisition = int32(0x00000097)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_SelfTestFailedCcdStepper = int32(0x00000098)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_SelfTestFailedFilmDrive = int32(0x00000099)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_SelfTestFailedLensStepper = int32(0x0000009A)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_StepperAlreadyMoving = int32(0x0000009B)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_StepperDidNotStop = int32(0x0000009C)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_StepperPosition = int32(0x0000009D)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_SystemInfo = int32(0x0000009E)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_TimeOut = int32(0x0000009F)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WrongByteCount = int32(0x000000A0)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_CancelIo = int32(0x000000A1)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_CreateDirectory = int32(0x000000A2)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_CreateEvent = int32(0x000000A3)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_CreateFileMapping = int32(0x000000A4)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_DeviceIoControl = int32(0x000000A5)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_FileClose = int32(0x000000A6)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_FileOpen = int32(0x000000A7)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_FileRead = int32(0x000000A8)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_FileSetPointer = int32(0x000000A9)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_FileTimeToSystemTime = int32(0x000000AA)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_FileWrite = int32(0x000000AB)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_FindFirstFile = int32(0x000000AC)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_FreeLibrary = int32(0x000000AD)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_GetDiskFreeSpace = int32(0x000000AE)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_GetDiskFreeSpaceEx = int32(0x000000AF)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_GetFileSize = int32(0x000000B0)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_GetOverlappedResult = int32(0x000000B1)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_LoadLibrary = int32(0x000000B2)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_MapViewOfFile = int32(0x000000B3)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_OpenEvent = int32(0x000000B4)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_OpenFileMapping = int32(0x000000B5)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_ResetEvent = int32(0x000000B6)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_SetEndOfFile = int32(0x000000B7)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_SetEvent = int32(0x000000B8)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_SetFilePointerEx = int32(0x000000B9)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_SetProcessWorkingSetSize = int32(0x000000BA)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_UnmapViewOfFile = int32(0x000000BB)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_VirtualAlloc = int32(0x000000BC)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_VirtualFree = int32(0x000000BD)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_VirtualLock = int32(0x000000BE)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_VirtualUnlock = int32(0x000000BF)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_WaitForSingleObject = int32(0x000000C0)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DXPotsWillNotAdjust = int32(0x000000C1)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DXNoFilmFound = int32(0x000000C2)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DXNoGoodBrightSpotFound = int32(0x000000C3)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DXAdjustingPotsForGoodSignal = int32(0x000000C4)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DXBadSwing = int32(0x000000C5)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_NoFilmTimeOut = int32(0x000000C6)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPicmMotorFail = int32(0x000000C7)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPicmVinFail = int32(0x000000C8)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPicm13VFail = int32(0x000000C9)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPicm12VFail = int32(0x000000CA)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPicm6VFail = int32(0x000000CB)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPicm5VFail = int32(0x000000CC)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPicm3VFail = int32(0x000000CD)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPicmCcdCommFail = int32(0x000000CE)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPiclTeCoolerFail = int32(0x000000CF)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPiclLightBdTempSensorFail = int32(0x000000D0)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPiclMotherBdTempSensorFail = int32(0x000000D1)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPiclCurrentDriversCommFail = int32(0x000000D2)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPiclMotherBdFpgaCommFail = int32(0x000000D3)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPiclDxEntryFail = int32(0x000000D4)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_BistPiclDxExitFail = int32(0x000000D5)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_MMX_SSE_NotSupported = int32(0x000000D6)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_CcdAtoDGainLimit = int32(0x000000D7)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ColorCalibrationFromFile = int32(0x000000D8)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_FocusBoardNotFound = int32(0x000000D9)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_InsufficientLight = int32(0x000000DA)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PicF_NotFound = int32(0x000000DB)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PollPPBStopped = int32(0x000000DC)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_WIN_GetProcessWorkingSetSize = int32(0x000000DD)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_CCD_VoltageError = int32(0x000000DE)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_VerifyFailed = int32(0x000000DF)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PollPpbNotOutOfService = int32(0x000000E0)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_LogHardwareString = int32(0x000000E1)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_InvalidAdjustValue = int32(0x000000E2)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ResolutionOrFilmFormatChanged = int32(0x000000E3)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_UseScratchRemovalChanged = int32(0x000000E4)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ApplyDragChanged = int32(0x000000E5)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_MotorFault_PowerFail = int32(0x000000E6)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_MotorFault_FilmDrive = int32(0x000000E7)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_MotorFault_CCD_Stepper = int32(0x000000E8)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_MotorFault_Lens_Stepper = int32(0x000000E9)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_MotorFault_FilmGuide = int32(0x000000EA)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_MotorFault_FilterWheel = int32(0x000000EB)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PicM_NotFound = int32(0x000000EC)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_Unknown = int32(0x000003E8)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_CannotFindStartOfScanLine = int32(0x000003E9)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_RingTailOverflow = int32(0x000003EA)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_LostSync = int32(0x000003EB)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_InvalidPacketType = int32(0x000003EC)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketBusy = int32(0x000003ED)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_FifoOverflow = int32(0x000003EE)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketChecksumErr = int32(0x000003EF)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketOverFlowErr = int32(0x000003F0)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketCommErr = int32(0x000003F1)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketCmdErr = int32(0x000003F2)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketHostErrorNoAck = int32(0x000003F3)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketHostErrorFormat = int32(0x000003F4)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketHostErrorCkSum = int32(0x000003F5)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketHostErrorEndPointFormat = int32(0x000003F6)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketHostErrorEndPointTimeOut = int32(0x000003F7)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketHostErrorEndPointLength = int32(0x000003F8)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketHostErrorAlgo = int32(0x000003F9)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketHostErrorBus = int32(0x000003FA)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketHostErrorUndefined = int32(0x000003FB)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_PacketReadWriteMismatch = int32(0x000003FC)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_InfoBufferString = int32(0x000003FD)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DRV_TransferInProgress = int32(0x000003FE)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_UNKNOWN = int32(0x000007D0)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_MEMORY = int32(0x000007D1)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_CANT_WRITE_PAKONERRORLOGPI = int32(0x000007D2)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_CR_INPUT_PROFILE = int32(0x000007D3)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_INPUT_PROFILE = int32(0x000007D4)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_OUTPUT_PROFILE = int32(0x000007D5)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_RPD2ROMM_PROFILE = int32(0x000007D6)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_NO_MMX_PROCESSOR = int32(0x000007D7)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_MIN_MAX_RANGE_RED = int32(0x000007D8)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_MIN_MAX_RANGE_GREEN = int32(0x000007D9)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_MIN_MAX_RANGE_BLUE = int32(0x000007DA)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_MIN_MAX_RANGE_BRIGHTNESS = int32(0x000007DB)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_MIN_MAX_RANGE_CONTRAST = int32(0x000007DC)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_INVALID_ORIENTATION = int32(0x000007DD)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_ERROR_SETTING_LOCKBEAM = int32(0x000007DE)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_INVALID_FILE_FORMAT = int32(0x000007DF)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_COMBINE_INPUT_OUTPUT_PROFILE = int32(0x000007E0)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_CR_COMBINE_INPUT_OUTPUT_PROFILE = int32(0x000007E1)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_KNOWN_EXCEPTION_RECORDED = int32(0x000007E2)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_UNKNOWN_EXCEPTION_RECORDED = int32(0x000007E3)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_CR_LUTS6 = int32(0x000007E4)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_KCDFS_INIT_FAILED = int32(0x000007E5)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PI_NO_DISK_SPACE = int32(0x000007E6)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_PartitionAlreadySelected = int32(0x00000BB8)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_FileSystemExists = int32(0x00000BB9)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_PartitionSelected = int32(0x00000BBA)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_FileSystemNotEmpty = int32(0x00000BBB)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_NullFilePointer = int32(0x00000BBC)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_FileAlreadyDeleted = int32(0x00000BBD)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_FilePointerDeleted = int32(0x00000BBE)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_ReadPastEOF = int32(0x00000BBF)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_NotLastStripInFile = int32(0x00000BC0)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_FileLengthNotSet = int32(0x00000BC1)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_FileSystemFull = int32(0x00000BC2)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_WriteSizeInvalid = int32(0x00000BC3)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_WritePastEOF = int32(0x00000BC4)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_BadDrive = int32(0x00000BC5)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_InvalidPointer = int32(0x00000BC6)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_WritingToCompletedStrip = int32(0x00000BC7)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_NotEnoughDiskSpace = int32(0x00000BC8)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_InvalidFileHandle = int32(0x00000BC9)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_ReadBeforeBOF = int32(0x00000BCA)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_PFS_RollAlreadyRecycled = int32(0x00000BCB)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DICE_MemErr = int32(0x00000FA0)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DICE_InProgress = int32(0x00000FA1)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DICE_NotInProgress = int32(0x00000FA2)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DICE_InvalidThread = int32(0x00000FA3)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DICE_InvalidParameter = int32(0x00000FA4)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DICE_QueueFull = int32(0x00000FA5)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DICE_InternalErr = int32(0x00000FA6)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DICE_CodeErr = int32(0x00000FA7)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DICE_CouldNotLoad = int32(0x00000FA8)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_DICE_Unknown = int32(0x00000FA9)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_NoScannerDetected = int32(0x00002AF8)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_CoCreateInstanceTLA = int32(0x00002AF9)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_CoCreateInstanceTLB = int32(0x00002AFA)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_CoCreateInstanceTLC = int32(0x00002AFB)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceITLAMain = int32(0x00002AFC)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceITLBMain = int32(0x00002AFD)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceITLCMain = int32(0x00002AFE)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceIScanPicturesTLA = int32(0x00002AFF)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceIScanPicturesTLB = int32(0x00002B00)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceIScanPicturesTLC = int32(0x00002B01)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceISavePicturesTLA = int32(0x00002B02)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceISavePicturesTLB = int32(0x00002B03)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceISavePicturesTLC = int32(0x00002B04)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ScannerNotInitializedTLA = int32(0x00002B05)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ScannerNotInitializedTLB = int32(0x00002B06)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_ScannerNotInitializedTLC = int32(0x00002B07)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_FunctionNotSupportedTLB = int32(0x00002B08)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_FunctionNotSupportedTLC = int32(0x00002B09)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_FeatureNotSupportedTLA = int32(0x00002B0A)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_FeatureNotSupportedTLB = int32(0x00002B0B)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_FeatureNotSupportedTLC = int32(0x00002B0C)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceIScanPictures1TLA = int32(0x00002B0D)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceIScanPictures1TLB = int32(0x00002B0E)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceIScanPictures1TLC = int32(0x00002B0F)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceISavePictures1TLA = int32(0x00002B10)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceISavePictures1TLB = int32(0x00002B11)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceISavePictures1TLC = int32(0x00002B12)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceISavePictures2TLA = int32(0x00002B13)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceISavePictures2TLB = int32(0x00002B14)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceISavePictures2TLC = int32(0x00002B15)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceIScanPictures2TLA = int32(0x00002B16)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceIScanPictures2TLB = int32(0x00002B17)
  .field public static literal valuetype TLXLib.ERROR_CODES_000 EC_QueryInterfaceIScanPictures2TLC = int32(0x00002B18)
} // end of class TLXLib.ERROR_CODES_000

.class public auto ansi sealed TLXLib.FACTORY_RESET_CONTROL_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 37 41 34 38 46 45 38 45 2D 41 35 36 36   // ..$7A48FE8E-A566
                                                                                                  2D 34 33 37 42 2D 41 42 39 44 2D 46 39 38 31 45   // -437B-AB9D-F981E
                                                                                                  42 43 41 42 44 35 39 00 00 )                      // BCABD59..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.FACTORY_RESET_CONTROL_000 FACTORY_RESET_Focus = int32(0x00000001)
  .field public static literal valuetype TLXLib.FACTORY_RESET_CONTROL_000 FACTORY_RESET_MotorSpeed = int32(0x00000002)
} // end of class TLXLib.FACTORY_RESET_CONTROL_000

.class public auto ansi sealed TLXLib.FILE_FORMAT_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 39 32 38 33 31 37 30 39 2D 33 38 31 42   // ..$92831709-381B
                                                                                                  2D 34 30 46 30 2D 42 36 41 46 2D 44 30 44 30 31   // -40F0-B6AF-D0D01
                                                                                                  43 31 39 32 33 42 35 00 00 )                      // C1923B5..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.FILE_FORMAT_000 iFILE_FORMAT_JPG = int32(0x00000000)
  .field public static literal valuetype TLXLib.FILE_FORMAT_000 iFILE_FORMAT_BMP = int32(0x00000001)
  .field public static literal valuetype TLXLib.FILE_FORMAT_000 iFILE_FORMAT_TIF = int32(0x00000002)
  .field public static literal valuetype TLXLib.FILE_FORMAT_000 iFILE_FORMAT_EXIF = int32(0x00000003)
  .field public static literal valuetype TLXLib.FILE_FORMAT_000 iFILE_FORMAT_JPG_2000 = int32(0x00000004)
  .field public static literal valuetype TLXLib.FILE_FORMAT_000 iFILE_FORMAT_RAW = int32(0x00000005)
  .field public static literal valuetype TLXLib.FILE_FORMAT_000 iFILE_FORMAT_ROLL = int32(0x00000006)
  .field public static literal valuetype TLXLib.FILE_FORMAT_000 iMAX_FILE_FORMATS_000 = int32(0x00000007)
} // end of class TLXLib.FILE_FORMAT_000

.class public auto ansi sealed TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 33 46 36 42 45 30 46 39 2D 39 38 42 39   // ..$3F6BE0F9-98B9
                                                                                                  2D 34 31 31 45 2D 39 38 46 34 2D 42 44 34 46 33   // -411E-98F4-BD4F3
                                                                                                  36 38 31 36 30 30 46 00 00 )                      // 681600F..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 iFILE_FORMAT_SAVE_TO_MEMORY_PLANAR_16 = int32(0x00000000)
  .field public static literal valuetype TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 iFILE_FORMAT_SAVE_TO_MEMORY_PLANAR_8 = int32(0x00000001)
  .field public static literal valuetype TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 iFILE_FORMAT_SAVE_TO_MEMORY_DIB_8 = int32(0x00000002)
} // end of class TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000

.class public auto ansi sealed TLXLib.FILM_COLOR_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 37 42 36 44 30 42 34 37 2D 45 34 31 44   // ..$7B6D0B47-E41D
                                                                                                  2D 34 32 44 43 2D 39 45 45 32 2D 42 41 36 35 30   // -42DC-9EE2-BA650
                                                                                                  30 34 41 45 43 35 30 00 00 )                      // 04AEC50..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.FILM_COLOR_000 FILM_COLOR_NEGATIVE = int32(0x00000001)
  .field public static literal valuetype TLXLib.FILM_COLOR_000 FILM_COLOR_POSITIVE = int32(0x00000002)
  .field public static literal valuetype TLXLib.FILM_COLOR_000 FILM_COLOR_BnW_NORMAL = int32(0x00000004)
  .field public static literal valuetype TLXLib.FILM_COLOR_000 FILM_COLOR_BnW_C41 = int32(0x00000008)
  .field public static literal valuetype TLXLib.FILM_COLOR_000 FILM_COLOR_BnW_ANY = int32(0x0000000C)
  .field public static literal valuetype TLXLib.FILM_COLOR_000 FILM_COLOR_LAMP_OFF = int32(0x00001000)
  .field public static literal valuetype TLXLib.FILM_COLOR_000 FILM_COLOR_LAMP_STANDBY = int32(0x00002000)
  .field public static literal valuetype TLXLib.FILM_COLOR_000 FILM_COLOR_FILTER_WHEEL_BLOCKED = int32(0x00004000)
  .field public static literal valuetype TLXLib.FILM_COLOR_000 FILM_COLOR_IMPORTED_BnW = int32(0x01000000)
  .field public static literal valuetype TLXLib.FILM_COLOR_000 FILM_COLOR_IMPORTED_Color = int32(0x02000000)
  .field public static literal valuetype TLXLib.FILM_COLOR_000 FILM_COLOR_IMPORTED = int32(0x03000000)
} // end of class TLXLib.FILM_COLOR_000

.class public auto ansi sealed TLXLib.FILM_FORMAT_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 38 46 32 35 37 35 46 44 2D 37 37 33 31   // ..$8F2575FD-7731
                                                                                                  2D 34 35 36 41 2D 39 42 36 35 2D 42 43 39 42 37   // -456A-9B65-BC9B7
                                                                                                  44 30 42 39 46 39 44 00 00 )                      // D0B9F9D..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.FILM_FORMAT_000 FILM_FORMAT_INDETERMINATE = int32(0xFFFFFFFF)
  .field public static literal valuetype TLXLib.FILM_FORMAT_000 FILM_FORMAT_24MM = int32(0x00000000)
  .field public static literal valuetype TLXLib.FILM_FORMAT_000 FILM_FORMAT_35MM = int32(0x00000001)
  .field public static literal valuetype TLXLib.FILM_FORMAT_000 FILM_FORMAT_70MM = int32(0x00000002)
  .field public static literal valuetype TLXLib.FILM_FORMAT_000 FILM_FORMAT_MOUNTED = int32(0x00002000)
  .field public static literal valuetype TLXLib.FILM_FORMAT_000 FILM_FORMAT_IMPORTED = int32(0x00004000)
} // end of class TLXLib.FILM_FORMAT_000

.class public auto ansi sealed TLXLib.FILM_TRACK_TEST_ERRORS_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 38 33 38 46 38 44 44 44 2D 33 46 36 31   // ..$838F8DDD-3F61
                                                                                                  2D 34 43 33 30 2D 42 39 33 31 2D 39 30 37 41 30   // -4C30-B931-907A0
                                                                                                  31 37 39 41 44 37 34 00 00 )                      // 179AD74..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.FILM_TRACK_TEST_ERRORS_000 FILM_TRACK_TEST_ERRORS_ClockTop = int32(0x00000001)
  .field public static literal valuetype TLXLib.FILM_TRACK_TEST_ERRORS_000 FILM_TRACK_TEST_ERRORS_DataTop = int32(0x00000002)
  .field public static literal valuetype TLXLib.FILM_TRACK_TEST_ERRORS_000 FILM_TRACK_TEST_ERRORS_ClockBottom = int32(0x00000004)
  .field public static literal valuetype TLXLib.FILM_TRACK_TEST_ERRORS_000 FILM_TRACK_TEST_ERRORS_DataBottom = int32(0x00000008)
  .field public static literal valuetype TLXLib.FILM_TRACK_TEST_ERRORS_000 FILM_TRACK_TEST_ERRORS_FilmEntry = int32(0x00000010)
  .field public static literal valuetype TLXLib.FILM_TRACK_TEST_ERRORS_000 FILM_TRACK_TEST_ERRORS_FilmExit = int32(0x00000020)
} // end of class TLXLib.FILM_TRACK_TEST_ERRORS_000

.class public auto ansi sealed TLXLib.FRAME_SIZES_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 32 45 46 31 30 30 46 42 2D 37 38 41 34   // ..$2EF100FB-78A4
                                                                                                  2D 34 38 37 45 2D 38 39 37 36 2D 30 41 46 38 41   // -487E-8976-0AF8A
                                                                                                  38 33 38 36 35 44 31 00 00 )                      // 83865D1..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_HR_HEIGHT_BASE4_24 = int32(0x00000359)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_HR_WIDTH_BASE4_24 = int32(0x000005DC)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_HR_HEIGHT_BASE8_24 = int32(0x000004B0)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_HR_WIDTH_BASE8_24 = int32(0x00000834)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_HR_HEIGHT_BASE16_24 = int32(0x000006B2)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_HR_WIDTH_BASE16_24 = int32(0x00000BB8)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_HR_HEIGHT_BASE4_35 = int32(0x000003E8)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_HR_WIDTH_BASE4_35 = int32(0x000005DC)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_HR_HEIGHT_BASE8_35 = int32(0x00000578)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_HR_WIDTH_BASE8_35 = int32(0x00000834)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_HR_HEIGHT_BASE8_35_135 = int32(0x000005DC)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_HR_WIDTH_BASE8_35_135 = int32(0x000008CA)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_HR_HEIGHT_BASE16_35 = int32(0x000007D0)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_HR_WIDTH_BASE16_35 = int32(0x00000BB8)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_HEIGHT_BASE4_24 = int32(0x000000D6)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_WIDTH_BASE4_24 = int32(0x00000177)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_HEIGHT_BASE8_24 = int32(0x00000096)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_WIDTH_BASE8_24 = int32(0x00000106)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_HEIGHT_BASE8_L_24 = int32(0x0000012C)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_WIDTH_BASE8_L_24 = int32(0x0000020D)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_HEIGHT_BASE16_24 = int32(0x000000D6)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_WIDTH_BASE16_24 = int32(0x00000177)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_HEIGHT_BASE4_35 = int32(0x000000FA)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_WIDTH_BASE4_35 = int32(0x00000177)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_HEIGHT_BASE8_35 = int32(0x000000AF)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_WIDTH_BASE8_35 = int32(0x00000106)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_HEIGHT_BASE8_35_135 = int32(0x000000FA)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_WIDTH_BASE8_35_135 = int32(0x00000177)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_HEIGHT_BASE8_L_35 = int32(0x0000015E)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_WIDTH_BASE8_L_35 = int32(0x0000020D)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_HEIGHT_BASE16_35 = int32(0x000000FA)
  .field public static literal valuetype TLXLib.FRAME_SIZES_000 FRAME_SIZES_LR_WIDTH_BASE16_35 = int32(0x00000177)
} // end of class TLXLib.FRAME_SIZES_000

.class public auto ansi sealed TLXLib.FRAME_TYPE_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 43 42 32 34 43 41 34 43 2D 33 38 34 39   // ..$CB24CA4C-3849
                                                                                                  2D 34 37 36 30 2D 38 37 44 43 2D 37 39 43 44 41   // -4760-87DC-79CDA
                                                                                                  44 38 45 38 35 46 46 00 00 )                      // D8E85FF..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.FRAME_TYPE_000 PRINT_ASPECT_RATIO_H = int32(0x00000000)
  .field public static literal valuetype TLXLib.FRAME_TYPE_000 PRINT_ASPECT_RATIO_P = int32(0x00000001)
  .field public static literal valuetype TLXLib.FRAME_TYPE_000 PRINT_ASPECT_RATIO_C = int32(0x00000002)
} // end of class TLXLib.FRAME_TYPE_000

.class public auto ansi sealed TLXLib.FRAMING_RISK_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 38 36 41 45 34 37 32 42 2D 38 35 45 31   // ..$86AE472B-85E1
                                                                                                  2D 34 41 32 41 2D 39 34 44 44 2D 39 33 45 36 31   // -4A2A-94DD-93E61
                                                                                                  35 34 32 33 43 33 35 00 00 )                      // 5423C35..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.FRAMING_RISK_000 FRAMING_RISK_VERY_LOW = int32(0x00000000)
  .field public static literal valuetype TLXLib.FRAMING_RISK_000 FRAMING_RISK_LOW = int32(0x00000001)
  .field public static literal valuetype TLXLib.FRAMING_RISK_000 FRAMING_RISK_MED = int32(0x00000002)
  .field public static literal valuetype TLXLib.FRAMING_RISK_000 FRAMING_RISK_HIGH = int32(0x00000003)
  .field public static literal valuetype TLXLib.FRAMING_RISK_000 FRAMING_RISK_VERY_HIGH = int32(0x00000004)
  .field public static literal valuetype TLXLib.FRAMING_RISK_000 FRAMING_RISK_INS = int32(0x00000005)
} // end of class TLXLib.FRAMING_RISK_000

.class public auto ansi sealed TLXLib.HARDWARE_CB_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 45 42 34 43 41 30 31 45 2D 37 37 38 41   // ..$EB4CA01E-778A
                                                                                                  2D 34 44 34 36 2D 38 45 36 31 2D 31 46 31 36 35   // -4D46-8E61-1F165
                                                                                                  34 44 42 30 44 32 44 00 00 )                      // 4DB0D2D..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_HOST_FAULT = int32(0x00000001)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_DX_FAULT = int32(0x00000002)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_LAMP_FAULT = int32(0x00000004)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_CCD_FAULT = int32(0x00000008)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_MOTOR_FAULT = int32(0x00000010)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_HARDWARE_ERROR = int32(0x00000040)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_LAMP_WARNING = int32(0x00000100)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_LAMP_ERROR = int32(0x00000200)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_TEMP_WARNING = int32(0x00000400)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_TEMP_ERROR = int32(0x00000800)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_LAMP_BURN_OUT_ERROR = int32(0x00001000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_LAMP_FAN_WARNING = int32(0x00002000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_LAMP_FAN_ERROR = int32(0x00004000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_POWER_WARNING = int32(0x00040000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_POWER_ERROR = int32(0x00080000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_MOTOR_STEPPER_CCD = int32(0x00200000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_MOTOR_STEPPER_LENS = int32(0x00400000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_MOTOR_FILTER_WHEEL = int32(0x00800000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_MOTOR_FILM_GUIDE = int32(0x01000000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_FILM_IN_GUIDES_ERROR = int32(0x02000000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_BLOWER_WARNING = int32(0x04000000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_CLEANING_REQUIRED = int32(0x08000000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_FILM_EMULSION_DOWN = int32(0x10000000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_FILM_TAIL_FIRST = int32(0x20000000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_FILM_SENSE_ENTRY = int32(0x40000000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_000 HARDWARE_CB_FILM_SENSE_EXIT = int32(0x80000000)
} // end of class TLXLib.HARDWARE_CB_000

.class public auto ansi sealed TLXLib.HARDWARE_CB_APS_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 33 43 32 44 42 30 32 44 2D 39 33 46 36   // ..$3C2DB02D-93F6
                                                                                                  2D 34 32 45 35 2D 42 44 32 31 2D 41 45 33 41 42   // -42E5-BD21-AE3AB
                                                                                                  30 34 43 42 43 31 39 00 00 )                      // 04CBC19..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.HARDWARE_CB_APS_000 HARDWARE_CB_APS_FAULT = int32(0x00000002)
  .field public static literal valuetype TLXLib.HARDWARE_CB_APS_000 HARDWARE_CB_APS_CARTRIDGE_LOADED = int32(0x00000080)
  .field public static literal valuetype TLXLib.HARDWARE_CB_APS_000 HARDWARE_CB_APS_FILM_JAM_EXTRACT = int32(0x00000100)
  .field public static literal valuetype TLXLib.HARDWARE_CB_APS_000 HARDWARE_CB_APS_FILM_JAM_SCAN = int32(0x00000200)
  .field public static literal valuetype TLXLib.HARDWARE_CB_APS_000 HARDWARE_CB_APS_FILM_JAM_RETRACT = int32(0x00000400)
  .field public static literal valuetype TLXLib.HARDWARE_CB_APS_000 HARDWARE_CB_APS_EJECT_ERROR = int32(0x00000800)
  .field public static literal valuetype TLXLib.HARDWARE_CB_APS_000 HARDWARE_CB_APS_UNPROCESSED_ERROR = int32(0x00001000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_APS_000 HARDWARE_CB_APS_CART_UNPACKED_ERROR = int32(0x00002000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_APS_000 HARDWARE_CB_APS_PARK_INIT_ERROR = int32(0x00004000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_APS_000 HARDWARE_CB_APS_PARK_ERROR = int32(0x00008000)
  .field public static literal valuetype TLXLib.HARDWARE_CB_APS_000 HARDWARE_CB_APS_INFO_BITS = int32(0x00000080)
  .field public static literal valuetype TLXLib.HARDWARE_CB_APS_000 HARDWARE_CB_APS_FILM_JAM_BITS = int32(0x00000700)
  .field public static literal valuetype TLXLib.HARDWARE_CB_APS_000 HARDWARE_CB_APS_ERROR_BITS = int32(0xFFFFFF7F)
} // end of class TLXLib.HARDWARE_CB_APS_000

.class public auto ansi sealed TLXLib.INDEX_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 38 39 46 45 42 34 36 37 2D 31 43 34 35   // ..$89FEB467-1C45
                                                                                                  2D 34 36 37 35 2D 38 44 45 30 2D 36 41 38 34 43   // -4675-8DE0-6A84C
                                                                                                  43 33 36 42 45 35 36 00 00 )                      // C36BE56..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.INDEX_000 INDEX_First = int32(0x00000000)
  .field public static literal valuetype TLXLib.INDEX_000 INDEX_InsertPictureAtEnd = int32(0x7FFFFFFF)
  .field public static literal valuetype TLXLib.INDEX_000 INDEX_Current = int32(0xFFFFFFFF)
  .field public static literal valuetype TLXLib.INDEX_000 INDEX_AllSelected = int32(0xFFFFFFFE)
  .field public static literal valuetype TLXLib.INDEX_000 INDEX_All = int32(0xFFFFFFFD)
} // end of class TLXLib.INDEX_000

.class public auto ansi sealed TLXLib.INITIALIZE_CONTROL_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 38 45 32 32 30 30 33 42 2D 44 45 30 31   // ..$8E22003B-DE01
                                                                                                  2D 34 31 34 34 2D 42 38 41 46 2D 31 45 42 34 35   // -4144-B8AF-1EB45
                                                                                                  33 43 44 42 35 33 30 00 00 )                      // 3CDB530..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.INITIALIZE_CONTROL_000 INITIALIZE_ProgressUpdatesAsPercent = int32(0x00000001)
  .field public static literal valuetype TLXLib.INITIALIZE_CONTROL_000 INITIALIZE_FirmwareUpdate = int32(0x00000002)
  .field public static literal valuetype TLXLib.INITIALIZE_CONTROL_000 INITIALIZE_MotorSelfTest = int32(0x00000004)
  .field public static literal valuetype TLXLib.INITIALIZE_CONTROL_000 INITIALIZE_ReportDminAsTmax = int32(0x20000000)
  .field public static literal valuetype TLXLib.INITIALIZE_CONTROL_000 INITIALIZE_CSharpClient = int32(0x40000000)
  .field public static literal valuetype TLXLib.INITIALIZE_CONTROL_000 INITIALIZE_FocusBoardConnected = int32(0x80000000)
} // end of class TLXLib.INITIALIZE_CONTROL_000

.class public auto ansi sealed TLXLib.INITIALIZE_WARNINGS_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 38 44 37 42 42 30 39 41 2D 36 45 43 38   // ..$8D7BB09A-6EC8
                                                                                                  2D 34 31 39 35 2D 38 39 46 35 2D 32 43 30 44 30   // -4195-89F5-2C0D0
                                                                                                  32 41 41 36 44 44 44 00 00 )                      // 2AA6DDD..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.INITIALIZE_WARNINGS_000 INITIALIZEW_NONE = int32(0x00000000)
  .field public static literal valuetype TLXLib.INITIALIZE_WARNINGS_000 INITIALIZEW_EEPROM_BLANK = int32(0x00000001)
  .field public static literal valuetype TLXLib.INITIALIZE_WARNINGS_000 INITIALIZEW_EEPROM_CHECKSUM_BAD = int32(0x00000002)
} // end of class TLXLib.INITIALIZE_WARNINGS_000

.class public auto ansi sealed TLXLib.INT_IID_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 44 33 34 38 41 39 34 31 2D 44 45 33 37   // ..$D348A941-DE37
                                                                                                  2D 34 34 44 45 2D 42 38 41 31 2D 38 30 42 37 44   // -44DE-B8A1-80B7D
                                                                                                  39 38 36 34 32 34 34 00 00 )                      // 9864244..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.INT_IID_000 INT_IID_ITLAMain = int32(0x00000000)
  .field public static literal valuetype TLXLib.INT_IID_000 INT_IID_IScanPictures = int32(0x00000001)
  .field public static literal valuetype TLXLib.INT_IID_000 INT_IID_ISavePictures = int32(0x00000002)
  .field public static literal valuetype TLXLib.INT_IID_000 INT_IID_ICalibrationWizard = int32(0x00000003)
  .field public static literal valuetype TLXLib.INT_IID_000 INT_IID_ITLXMain = int32(0x00000004)
  .field public static literal valuetype TLXLib.INT_IID_000 INT_IID_ISavePictures1 = int32(0x00000005)
  .field public static literal valuetype TLXLib.INT_IID_000 INT_IID_IScanPictures2 = int32(0x00000006)
  .field public static literal valuetype TLXLib.INT_IID_000 INT_IID_ISavePictures2 = int32(0x00000007)
  .field public static literal valuetype TLXLib.INT_IID_000 INT_IID_ISavePictures3 = int32(0x00000008)
} // end of class TLXLib.INT_IID_000

.class public auto ansi sealed TLXLib.RESOLUTION_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 45 42 32 32 42 33 32 44 2D 39 33 46 45   // ..$EB22B32D-93FE
                                                                                                  2D 34 30 36 44 2D 42 30 43 38 2D 44 32 34 44 39   // -406D-B0C8-D24D9
                                                                                                  32 34 41 32 36 38 33 00 00 )                      // 24A2683..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.RESOLUTION_000 RESOLUTION_BASE_4 = int32(0x00000000)
  .field public static literal valuetype TLXLib.RESOLUTION_000 RESOLUTION_BASE_8 = int32(0x00000001)
  .field public static literal valuetype TLXLib.RESOLUTION_000 RESOLUTION_BASE_16 = int32(0x00000002)
} // end of class TLXLib.RESOLUTION_000

.class public auto ansi sealed TLXLib.ROTATE_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 33 46 36 45 41 44 44 37 2D 41 42 39 44   // ..$3F6EADD7-AB9D
                                                                                                  2D 34 38 37 37 2D 38 39 32 33 2D 38 36 35 33 36   // -4877-8923-86536
                                                                                                  44 38 42 39 43 33 35 00 00 )                      // D8B9C35..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.ROTATE_000 ROTATE_0 = int32(0x00000000)
  .field public static literal valuetype TLXLib.ROTATE_000 ROTATE_90L = int32(0x00000001)
  .field public static literal valuetype TLXLib.ROTATE_000 ROTATE_180 = int32(0x00000002)
  .field public static literal valuetype TLXLib.ROTATE_000 ROTATE_90R = int32(0x00000003)
  .field public static literal valuetype TLXLib.ROTATE_000 ROTATED_90_L_OR_R = int32(0x00000001)
  .field public static literal valuetype TLXLib.ROTATE_000 MIRROR_L_R = int32(0x00000004)
} // end of class TLXLib.ROTATE_000

.class public auto ansi sealed TLXLib.S_OR_H_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 43 34 41 37 42 35 44 44 2D 39 38 44 34   // ..$C4A7B5DD-98D4
                                                                                                  2D 34 35 34 46 2D 42 44 32 37 2D 34 30 36 35 37   // -454F-BD27-40657
                                                                                                  41 35 38 38 34 37 33 00 00 )                      // A588473..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.S_OR_H_000 S_OR_H_NONE = int32(0x00000000)
  .field public static literal valuetype TLXLib.S_OR_H_000 S_OR_H_SELECTED = int32(0x00000001)
  .field public static literal valuetype TLXLib.S_OR_H_000 S_OR_H_HIDDEN = int32(0x00000002)
} // end of class TLXLib.S_OR_H_000

.class public auto ansi sealed TLXLib.SAVE_CONTROL_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 37 34 34 31 46 46 41 36 2D 36 45 36 43   // ..$7441FFA6-6E6C
                                                                                                  2D 34 31 35 38 2D 39 46 35 36 2D 33 31 43 41 39   // -4158-9F56-31CA9
                                                                                                  46 33 42 44 44 45 30 00 00 )                      // F3BDDE0..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_SizeOriginal = int32(0x00000000)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_SizeLimitForDisplay = int32(0x00000001)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_SizeLimitForSave = int32(0x00000002)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_SizeBitMask = int32(0x00000003)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_UseCurrentRotation = int32(0x00000004)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_UseLoResBuffer = int32(0x00000008)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_UseColorCorrection = int32(0x00000010)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_UseColorSceneBalance = int32(0x00000020)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_UseColorAdjustments = int32(0x00000040)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_UseScratchRemovalIfAvailable = int32(0x00000080)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_FastUpdate8BitDib = int32(0x00000100)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_TopDownDib = int32(0x00000200)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_FileHeader = int32(0x00000400)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_DoNotScaleUp = int32(0x00000800)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_ObsoleteUseColorKcdfs = int32(0x00001000)
  .field public static literal valuetype TLXLib.SAVE_CONTROL_000 SAV_ObsoleteUseColorSceneBalanceDigital = int32(0x00002000)
} // end of class TLXLib.SAVE_CONTROL_000

.class public auto ansi sealed TLXLib.SCALING_METHOD_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 32 37 45 35 35 30 34 38 2D 44 32 31 30   // ..$27E55048-D210
                                                                                                  2D 34 38 32 33 2D 39 43 45 37 2D 42 35 37 30 45   // -4823-9CE7-B570E
                                                                                                  30 43 43 39 43 46 33 00 00 )                      // 0CC9CF3..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.SCALING_METHOD_000 SCALING_METHOD_NEAREST = int32(0x00000000)
  .field public static literal valuetype TLXLib.SCALING_METHOD_000 SCALING_METHOD_BILINEAR = int32(0x00000001)
  .field public static literal valuetype TLXLib.SCALING_METHOD_000 SCALING_METHOD_BICUBIC = int32(0x00000002)
} // end of class TLXLib.SCALING_METHOD_000

.class public auto ansi sealed TLXLib.SCAN_CONTROL_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 41 32 33 37 39 32 36 30 2D 33 37 32 44   // ..$A2379260-372D
                                                                                                  2D 34 32 46 44 2D 41 41 36 45 2D 46 34 36 39 34   // -42FD-AA6E-F4694
                                                                                                  37 35 36 32 44 38 36 00 00 )                      // 7562D86..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.SCAN_CONTROL_000 SCAN_None = int32(0x00000000)
  .field public static literal valuetype TLXLib.SCAN_CONTROL_000 SCAN_AggressiveFraming = int32(0x00000002)
  .field public static literal valuetype TLXLib.SCAN_CONTROL_000 SCAN_RFT_SenseSplice = int32(0x00000004)
  .field public static literal valuetype TLXLib.SCAN_CONTROL_000 SCAN_UseScratchRemoval = int32(0x00000008)
  .field public static literal valuetype TLXLib.SCAN_CONTROL_000 SCAN_Use24mmAutoLoader = int32(0x00000010)
  .field public static literal valuetype TLXLib.SCAN_CONTROL_000 SCAN_HasFilmDrag = int32(0x00001000)
  .field public static literal valuetype TLXLib.SCAN_CONTROL_000 SCAN_PreScan = int32(0x00010000)
  .field public static literal valuetype TLXLib.SCAN_CONTROL_000 SCAN_UsePremiumColorPath = int32(0x00100000)
  .field public static literal valuetype TLXLib.SCAN_CONTROL_000 SCAN_UseOrderAnalysisCallbacks = int32(0x00200000)
} // end of class TLXLib.SCAN_CONTROL_000

.class public auto ansi sealed TLXLib.SCAN_WARNINGS_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 44 44 31 31 31 44 37 44 2D 34 45 31 42   // ..$DD111D7D-4E1B
                                                                                                  2D 34 41 30 34 2D 41 42 33 35 2D 46 44 33 36 32   // -4A04-AB35-FD362
                                                                                                  39 34 41 46 46 45 39 00 00 )                      // 94AFFE9..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_DX_GOOD = int32(0x00000000)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_DX_BAD = int32(0x00000001)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_FILM_PRODUCT_AND_SPECIFIER_GOOD = int32(0x00000000)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_FILM_PRODUCT_AND_SPECIFIER_BAD = int32(0x00000002)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_MOTOR_SPEED_GOOD = int32(0x00000000)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_MOTOR_SPEED_HALF_PERCENT_SLOW = int32(0x00000010)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_MOTOR_SPEED_ONE_PERCENT_SLOW = int32(0x00000020)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_MOTOR_SPEED_HALF_PERCENT_FAST = int32(0x00000040)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_MOTOR_SPEED_ONE_PERCENT_FAST = int32(0x00000080)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_MOTOR_SPEED_FAIR = int32(0x00000050)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_MOTOR_SPEED_BAD = int32(0x000000A0)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_FRAMING_GOOD = int32(0x00000000)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_FRAMING_IN_MIDDLE = int32(0x00000100)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_FRAMING_AT_END = int32(0x00000200)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_FRAMING_AT_BEGINNING = int32(0x00000400)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_FRAMING_FAIR = int32(0x00000700)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_FRAMING_BAD = int32(0x00000800)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_MAX_FILM_LENGTH_EXCEEDED = int32(0x00001000)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_LIGHT_DIM = int32(0x00002000)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_MOF_FAILED_MAGNETICS = int32(0x10000000)
  .field public static literal valuetype TLXLib.SCAN_WARNINGS_000 SCANW_MOF_FAILED_PERFORATIONS = int32(0x20000000)
} // end of class TLXLib.SCAN_WARNINGS_000

.class public auto ansi sealed TLXLib.SCANNER_TYPE_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 39 39 32 39 39 31 42 35 2D 45 37 41 45   // ..$992991B5-E7AE
                                                                                                  2D 34 45 34 46 2D 41 41 32 45 2D 45 39 33 39 41   // -4E4F-AA2E-E939A
                                                                                                  46 38 41 44 31 36 33 00 00 )                      // F8AD163..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.SCANNER_TYPE_000 SCANNER_TYPE_UNKNOWN = int32(0x00000000)
  .field public static literal valuetype TLXLib.SCANNER_TYPE_000 SCANNER_TYPE_F_235 = int32(0x00000007)
  .field public static literal valuetype TLXLib.SCANNER_TYPE_000 SCANNER_TYPE_F_235C = int32(0x00000008)
  .field public static literal valuetype TLXLib.SCANNER_TYPE_000 SCANNER_TYPE_F_135 = int32(0x00000546)
  .field public static literal valuetype TLXLib.SCANNER_TYPE_000 SCANNER_TYPE_F_135_PLUS = int32(0x00000547)
  .field public static literal valuetype TLXLib.SCANNER_TYPE_000 SCANNER_TYPE_F_335 = int32(0x00000D16)
  .field public static literal valuetype TLXLib.SCANNER_TYPE_000 SCANNER_TYPE_F_335C = int32(0x00000D17)
} // end of class TLXLib.SCANNER_TYPE_000

.class public auto ansi sealed TLXLib.SCANNER_VERSION_HW_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 31 44 32 41 46 33 45 33 2D 46 43 41 31   // ..$1D2AF3E3-FCA1
                                                                                                  2D 34 44 31 39 2D 38 38 34 34 2D 41 34 39 46 36   // -4D19-8844-A49F6
                                                                                                  36 43 31 35 43 32 32 00 00 )                      // 6C15C22..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.SCANNER_VERSION_HW_000 SCANNER_VERSION_HW_UNKNOWN = int32(0x00000000)
  .field public static literal valuetype TLXLib.SCANNER_VERSION_HW_000 SCANNER_VERSION_HW_PRODUCTION = int32(0x00000003)
  .field public static literal valuetype TLXLib.SCANNER_VERSION_HW_000 SCANNER_VERSION_HW_ALPHA_000 = int32(0x0000000A)
  .field public static literal valuetype TLXLib.SCANNER_VERSION_HW_000 SCANNER_VERSION_HW_BRIDGE = int32(0x00000032)
  .field public static literal valuetype TLXLib.SCANNER_VERSION_HW_000 SCANNER_VERSION_HW_BETA_000 = int32(0x00000064)
  .field public static literal valuetype TLXLib.SCANNER_VERSION_HW_000 SCANNER_VERSION_HW_CHARLIE_000 = int32(0x000000C8)
  .field public static literal valuetype TLXLib.SCANNER_VERSION_HW_000 SCANNER_VERSION_HW_PRE_PRODUCTION_000 = int32(0x0000012C)
  .field public static literal valuetype TLXLib.SCANNER_VERSION_HW_000 SCANNER_VERSION_HW_PRODUCTION_000 = int32(0x00000190)
  .field public static literal valuetype TLXLib.SCANNER_VERSION_HW_000 SCANNER_VERSION_HW_FLATBELT = int32(0x000003E8)
  .field public static literal valuetype TLXLib.SCANNER_VERSION_HW_000 SCANNER_VERSION_HW_RFT_SPLICE_235 = int32(0x0000044C)
  .field public static literal valuetype TLXLib.SCANNER_VERSION_HW_000 SCANNER_VERSION_HW_RFT_SPLICE_335 = int32(0x000007D0)
} // end of class TLXLib.SCANNER_VERSION_HW_000

.class public auto ansi sealed TLXLib.STRIP_MODE_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 33 46 36 33 31 35 31 35 2D 34 43 36 45   // ..$3F631515-4C6E
                                                                                                  2D 34 31 37 32 2D 39 34 43 38 2D 30 46 30 34 34   // -4172-94C8-0F044
                                                                                                  30 37 34 35 44 33 33 00 00 )                      // 0745D33..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.STRIP_MODE_000 STRIP_MODE_FULL_ROLL = int32(0x00000000)
  .field public static literal valuetype TLXLib.STRIP_MODE_000 STRIP_MODE_MULTI_STRIPS_4_FRAMES = int32(0x00000004)
  .field public static literal valuetype TLXLib.STRIP_MODE_000 STRIP_MODE_MULTI_STRIPS_5_FRAMES = int32(0x00000005)
  .field public static literal valuetype TLXLib.STRIP_MODE_000 STRIP_MODE_MULTI_STRIPS_6_FRAMES = int32(0x00000006)
} // end of class TLXLib.STRIP_MODE_000

.class public auto ansi sealed TLXLib.WORKER_THREAD_OPERATION_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 39 44 33 45 46 42 39 36 2D 34 31 34 37   // ..$9D3EFB96-4147
                                                                                                  2D 34 31 37 43 2D 39 45 41 34 2D 37 32 32 30 42   // -417C-9EA4-7220B
                                                                                                  34 41 33 31 35 41 33 00 00 )                      // 4A315A3..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_InitializeProgress = int32(0x00000000)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_InitializeError = int32(0x00000001)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateApsProgress = int32(0x00000002)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateApsError = int32(0x00000003)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateCcdProgress = int32(0x00000004)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateCcdError = int32(0x00000005)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateDxProgress = int32(0x00000006)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateDxError = int32(0x00000007)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateLampProgress = int32(0x00000008)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateLampError = int32(0x00000009)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateMotorProgress = int32(0x0000000A)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_FirmwareUpdateMotorError = int32(0x0000000B)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_HardwareProgress = int32(0x0000000C)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_HardwareError = int32(0x0000000D)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_HardwareAPSProgress = int32(0x0000000E)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_HardwareAPSError = int32(0x0000000F)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_FilmTrackTestProgress = int32(0x00000010)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_FilmTrackTestError = int32(0x00000011)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_DiagnosticsProgress = int32(0x00000012)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_DiagnosticsError = int32(0x00000013)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_CorrectionsProgress = int32(0x00000014)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_CorrectionsError = int32(0x00000015)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_ExerciseSteppersProgress = int32(0x00000016)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_ExerciseSteppersError = int32(0x00000017)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_LampWarmUpProgress = int32(0x00000018)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_LampWarmUpError = int32(0x00000019)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_AdvanceFilmProgress = int32(0x0000001A)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_AdvanceFilmError = int32(0x0000001B)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_PutFilmGuidePositionProgress = int32(0x0000001C)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_PutFilmGuidePositionError = int32(0x0000001D)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_PutFilmPressureRollersPositionProgress = int32(0x0000001E)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_PutFilmPressureRollersPositionError = int32(0x0000001F)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_FX35C_ManualRetractProgress = int32(0x00000020)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_FX35C_ManualRetractError = int32(0x00000021)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_ScanProgress = int32(0x00000022)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_ScanError = int32(0x00000023)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_ImportFromFileProgress = int32(0x00000024)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_ImportFromFileError = int32(0x00000025)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_SaveProgress = int32(0x00000026)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_SaveError = int32(0x00000027)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_TLXProgress = int32(0x00000028)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_TLXError = int32(0x00000029)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_OrderAnalysisProgress = int32(0x0000002A)
  .field public static literal valuetype TLXLib.WORKER_THREAD_OPERATION_000 WTO_Last = int32(0x0000002A)
} // end of class TLXLib.WORKER_THREAD_OPERATION_000

.class public auto ansi sealed TLXLib.WORKER_THREAD_PROGRESS_000
       extends [mscorlib]System.Enum
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.GuidAttribute::.ctor(string) = ( 01 00 24 43 45 30 38 46 44 39 39 2D 31 43 36 35   // ..$CE08FD99-1C65
                                                                                                  2D 34 46 38 30 2D 41 45 31 46 2D 38 37 36 45 45   // -4F80-AE1F-876EE
                                                                                                  45 38 42 34 34 34 36 00 00 )                      // E8B4446..
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype TLXLib.WORKER_THREAD_PROGRESS_000 WTP_Initialize = int32(0x00000000)
  .field public static literal valuetype TLXLib.WORKER_THREAD_PROGRESS_000 WTP_ProgressStart = int32(0x000003E8)
  .field public static literal valuetype TLXLib.WORKER_THREAD_PROGRESS_000 WTP_ProgressEnd = int32(0x000007D0)
  .field public static literal valuetype TLXLib.WORKER_THREAD_PROGRESS_000 WTP_ProgressComplete = int32(0x00000BB8)
} // end of class TLXLib.WORKER_THREAD_PROGRESS_000

.class public auto ansi sealed TLXLib._ITLXMainEvents_SinkHelper
       extends [mscorlib]System.Object
       implements TLXLib._ITLXMainEvents
{
  .custom instance void [mscorlib]System.Runtime.InteropServices.ClassInterfaceAttribute::.ctor([mscorlib]System.Runtime.InteropServices.ClassInterfaceType) = ( 01 00 00 00 00 00 00 00 ) 
  .field public int32 m_dwCookie
  .method assembly specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       24 (0x18)
    .maxstack  4
    IL_0000:  ldarg      0
    IL_0004:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0009:  ldarg      0
    IL_000d:  ldc.i4     0x0
    IL_0012:  stfld      int32 TLXLib._ITLXMainEvents_SinkHelper::m_dwCookie
    IL_0017:  ret
  } // end of method _ITLXMainEvents_SinkHelper::.ctor

} // end of class TLXLib._ITLXMainEvents_SinkHelper

.class private auto ansi sealed TLXLib._ITLXMainEvents_EventProvider
       extends [mscorlib]System.Object
       implements TLXLib._ITLXMainEvents_Event,
                  [mscorlib]System.IDisposable
{
  .field private [mscorlib]System.Runtime.InteropServices.UCOMIConnectionPointContainer m_ConnectionPointContainer
  .field private [mscorlib]System.Collections.ArrayList m_aEventSinkHelpers
  .field private [mscorlib]System.Runtime.InteropServices.UCOMIConnectionPoint m_ConnectionPoint
  .method private instance void  Init() cil managed
  {
    // Code size       261 (0x105)
    .maxstack  5
    .locals init ([mscorlib]System.Runtime.InteropServices.UCOMIConnectionPoint V_0,
             [mscorlib]System.Guid V_1,
             uint8[] V_2)
    IL_0000:  ldnull
    IL_0001:  stloc.0
    IL_0002:  ldc.i4     0x10
    IL_0007:  newarr     [mscorlib]System.Byte
    IL_000c:  stloc.2
    IL_000d:  ldloc.2
    IL_000e:  ldc.i4     0x0
    IL_0013:  ldc.i4     0x8f
    IL_0018:  stelem.i1
    IL_0019:  ldloc.2
    IL_001a:  ldc.i4     0x1
    IL_001f:  ldc.i4     0xde
    IL_0024:  stelem.i1
    IL_0025:  ldloc.2
    IL_0026:  ldc.i4     0x2
    IL_002b:  ldc.i4     0x30
    IL_0030:  stelem.i1
    IL_0031:  ldloc.2
    IL_0032:  ldc.i4     0x3
    IL_0037:  ldc.i4     0xb
    IL_003c:  stelem.i1
    IL_003d:  ldloc.2
    IL_003e:  ldc.i4     0x4
    IL_0043:  ldc.i4     0xfa
    IL_0048:  stelem.i1
    IL_0049:  ldloc.2
    IL_004a:  ldc.i4     0x5
    IL_004f:  ldc.i4     0xfd
    IL_0054:  stelem.i1
    IL_0055:  ldloc.2
    IL_0056:  ldc.i4     0x6
    IL_005b:  ldc.i4     0xae
    IL_0060:  stelem.i1
    IL_0061:  ldloc.2
    IL_0062:  ldc.i4     0x7
    IL_0067:  ldc.i4     0x40
    IL_006c:  stelem.i1
    IL_006d:  ldloc.2
    IL_006e:  ldc.i4     0x8
    IL_0073:  ldc.i4     0x85
    IL_0078:  stelem.i1
    IL_0079:  ldloc.2
    IL_007a:  ldc.i4     0x9
    IL_007f:  ldc.i4     0xdf
    IL_0084:  stelem.i1
    IL_0085:  ldloc.2
    IL_0086:  ldc.i4     0xa
    IL_008b:  ldc.i4     0xff
    IL_0090:  stelem.i1
    IL_0091:  ldloc.2
    IL_0092:  ldc.i4     0xb
    IL_0097:  ldc.i4     0x18
    IL_009c:  stelem.i1
    IL_009d:  ldloc.2
    IL_009e:  ldc.i4     0xc
    IL_00a3:  ldc.i4     0xa0
    IL_00a8:  stelem.i1
    IL_00a9:  ldloc.2
    IL_00aa:  ldc.i4     0xd
    IL_00af:  ldc.i4     0x7a
    IL_00b4:  stelem.i1
    IL_00b5:  ldloc.2
    IL_00b6:  ldc.i4     0xe
    IL_00bb:  ldc.i4     0xb0
    IL_00c0:  stelem.i1
    IL_00c1:  ldloc.2
    IL_00c2:  ldc.i4     0xf
    IL_00c7:  ldc.i4     0x12
    IL_00cc:  stelem.i1
    IL_00cd:  ldloca.s   V_1
    IL_00cf:  ldloc.2
    IL_00d0:  call       instance void [mscorlib]System.Guid::.ctor(uint8[])
    IL_00d5:  ldarg      0
    IL_00d9:  ldfld      [mscorlib]System.Runtime.InteropServices.UCOMIConnectionPointContainer TLXLib._ITLXMainEvents_EventProvider::m_ConnectionPointContainer
    IL_00de:  ldloca.s   V_1
    IL_00e0:  ldloca.s   V_0
    IL_00e2:  callvirt   instance void [mscorlib]System.Runtime.InteropServices.UCOMIConnectionPointContainer::FindConnectionPoint([mscorlib]System.Guid&,
                                                                                                                                   [mscorlib]System.Runtime.InteropServices.UCOMIConnectionPoint&)
    IL_00e7:  ldarg      0
    IL_00eb:  ldloc.0
    IL_00ec:  castclass  [mscorlib]System.Runtime.InteropServices.UCOMIConnectionPoint
    IL_00f1:  stfld      [mscorlib]System.Runtime.InteropServices.UCOMIConnectionPoint TLXLib._ITLXMainEvents_EventProvider::m_ConnectionPoint
    IL_00f6:  ldarg      0
    IL_00fa:  newobj     instance void [mscorlib]System.Collections.ArrayList::.ctor()
    IL_00ff:  stfld      [mscorlib]System.Collections.ArrayList TLXLib._ITLXMainEvents_EventProvider::m_aEventSinkHelpers
    IL_0104:  ret
  } // end of method _ITLXMainEvents_EventProvider::Init

  .method public specialname rtspecialname 
          instance void  .ctor(object A_1) cil managed
  {
    // Code size       28 (0x1c)
    .maxstack  4
    IL_0000:  ldarg      0
    IL_0004:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0009:  ldarg      0
    IL_000d:  ldarg      A_1
    IL_0011:  castclass  [mscorlib]System.Runtime.InteropServices.UCOMIConnectionPointContainer
    IL_0016:  stfld      [mscorlib]System.Runtime.InteropServices.UCOMIConnectionPointContainer TLXLib._ITLXMainEvents_EventProvider::m_ConnectionPointContainer
    IL_001b:  ret
  } // end of method _ITLXMainEvents_EventProvider::.ctor

  .method public virtual instance void  Finalize() cil managed
  {
    // Code size       153 (0x99)
    .maxstack  5
    .locals init (int32 V_0,
             int32 V_1,
             class TLXLib._ITLXMainEvents_SinkHelper V_2)
    IL_0000:  ldarg      0
    IL_0004:  call       void [mscorlib]System.Threading.Monitor::Enter(object)
    .try
    {
      .try
      {
        IL_0009:  ldarg      0
        IL_000d:  ldfld      [mscorlib]System.Runtime.InteropServices.UCOMIConnectionPoint TLXLib._ITLXMainEvents_EventProvider::m_ConnectionPoint
        IL_0012:  brfalse    IL_007e

        IL_0017:  ldarg      0
        IL_001b:  ldfld      [mscorlib]System.Collections.ArrayList TLXLib._ITLXMainEvents_EventProvider::m_aEventSinkHelpers
        IL_0020:  callvirt   instance int32 [mscorlib]System.Collections.ArrayList::get_Count()
        IL_0025:  stloc.0
        IL_0026:  ldc.i4     0x0
        IL_002b:  stloc.1
        IL_002c:  ldc.i4     0x0
        IL_0031:  ldloc.0
        IL_0032:  bge        IL_006f

        IL_0037:  ldarg      0
        IL_003b:  ldfld      [mscorlib]System.Collections.ArrayList TLXLib._ITLXMainEvents_EventProvider::m_aEventSinkHelpers
        IL_0040:  ldloc.1
        IL_0041:  callvirt   instance object [mscorlib]System.Collections.ArrayList::get_Item(int32)
        IL_0046:  castclass  TLXLib._ITLXMainEvents_SinkHelper
        IL_004b:  stloc.2
        IL_004c:  ldarg      0
        IL_0050:  ldfld      [mscorlib]System.Runtime.InteropServices.UCOMIConnectionPoint TLXLib._ITLXMainEvents_EventProvider::m_ConnectionPoint
        IL_0055:  ldloc.2
        IL_0056:  ldfld      int32 TLXLib._ITLXMainEvents_SinkHelper::m_dwCookie
        IL_005b:  callvirt   instance void [mscorlib]System.Runtime.InteropServices.UCOMIConnectionPoint::Unadvise(int32)
        IL_0060:  ldloc.1
        IL_0061:  ldc.i4     0x1
        IL_0066:  add
        IL_0067:  stloc.1
        IL_0068:  ldloc.1
        IL_0069:  ldloc.0
        IL_006a:  blt        IL_0037

        IL_006f:  ldarg      0
        IL_0073:  ldfld      [mscorlib]System.Runtime.InteropServices.UCOMIConnectionPoint TLXLib._ITLXMainEvents_EventProvider::m_ConnectionPoint
        IL_0078:  call       int32 [mscorlib]System.Runtime.InteropServices.Marshal::ReleaseComObject(object)
        IL_007d:  pop
        IL_007e:  leave      IL_0089

      }  // end .try
      catch [mscorlib]System.Exception 
      {
        IL_0083:  pop
        IL_0084:  leave      IL_0089

      }  // end handler
      IL_0089:  leave      IL_0098

    }  // end .try
    finally
    {
      IL_008e:  ldarg      0
      IL_0092:  call       void [mscorlib]System.Threading.Monitor::Exit(object)
      IL_0097:  endfinally
    }  // end handler
    IL_0098:  ret
  } // end of method _ITLXMainEvents_EventProvider::Finalize

  .method public virtual instance void  Dispose() cil managed
  {
    // Code size       19 (0x13)
    .maxstack  2
    IL_0000:  ldarg      0
    IL_0004:  callvirt   instance void TLXLib._ITLXMainEvents_EventProvider::Finalize()
    IL_0009:  ldarg      0
    IL_000d:  call       void [mscorlib]System.GC::SuppressFinalize(object)
    IL_0012:  ret
  } // end of method _ITLXMainEvents_EventProvider::Dispose

} // end of class TLXLib._ITLXMainEvents_EventProvider


// =============================================================

// *********** DISASSEMBLY COMPLETE ***********************
