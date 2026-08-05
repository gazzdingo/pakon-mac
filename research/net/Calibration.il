
// Metadata version: v1.1.4322
.assembly extern mscorlib
{
  .publickeytoken = (B7 7A 5C 56 19 34 E0 89 )                         // .z\V.4..
  .ver 1:0:5000:0
}
.assembly extern System.Windows.Forms
{
  .publickeytoken = (B7 7A 5C 56 19 34 E0 89 )                         // .z\V.4..
  .ver 1:0:5000:0
}
.assembly extern Interop.LLCLib
{
  .ver 1:0:0:0
}
.assembly extern Pakon
{
  .ver 3:1:0:28
}
.assembly extern Interop.TLXLib
{
  .ver 1:1:0:0
}
.assembly extern System.Drawing
{
  .publickeytoken = (B0 3F 5F 7F 11 D5 0A 3A )                         // .?_....:
  .ver 1:0:5000:0
}
.assembly extern System
{
  .publickeytoken = (B7 7A 5C 56 19 34 E0 89 )                         // .z\V.4..
  .ver 1:0:5000:0
}
.assembly Calibration
{
  .custom instance void [mscorlib]System.Reflection.AssemblyDescriptionAttribute::.ctor(string) = ( 01 00 1A 43 61 6C 69 62 72 61 74 69 6F 6E 20 53   // ...Calibration S
                                                                                                    63 61 6E 6E 65 72 20 41 63 63 65 73 73 00 00 )    // canner Access..
  .custom instance void [mscorlib]System.Reflection.AssemblyKeyNameAttribute::.ctor(string) = ( 01 00 00 00 00 ) 
  .custom instance void [mscorlib]System.Reflection.AssemblyConfigurationAttribute::.ctor(string) = ( 01 00 00 00 00 ) 
  .custom instance void [mscorlib]System.Reflection.AssemblyTitleAttribute::.ctor(string) = ( 01 00 1A 43 61 6C 69 62 72 61 74 69 6F 6E 20 53   // ...Calibration S
                                                                                              63 61 6E 6E 65 72 20 41 63 63 65 73 73 00 00 )    // canner Access..
  .custom instance void [mscorlib]System.Reflection.AssemblyTrademarkAttribute::.ctor(string) = ( 01 00 00 00 00 ) 
  .custom instance void [mscorlib]System.Reflection.AssemblyCompanyAttribute::.ctor(string) = ( 01 00 05 50 61 6B 6F 6E 00 00 )                   // ...Pakon..
  .custom instance void [mscorlib]System.Reflection.AssemblyDelaySignAttribute::.ctor(bool) = ( 01 00 00 00 00 ) 
  .custom instance void [mscorlib]System.Reflection.AssemblyKeyFileAttribute::.ctor(string) = ( 01 00 00 00 00 ) 
  .custom instance void [mscorlib]System.Reflection.AssemblyCopyrightAttribute::.ctor(string) = ( 01 00 12 43 6F 70 79 72 69 67 68 74 20 28 43 29   // ...Copyright (C)
                                                                                                  20 32 30 30 35 00 00 )                            //  2005..
  .custom instance void [mscorlib]System.Reflection.AssemblyProductAttribute::.ctor(string) = ( 01 00 0F 43 61 6C 69 62 72 61 74 69 6F 6E 20 44   // ...Calibration D
                                                                                                4C 4C 00 00 )                                     // LL..
  .permissionset reqmin
            "<PermissionSet class=\"System.Security.PermissionSe"
  + "t\"\r\n               version=\"1\">\r\n   <IPermission class=\"Syst"
  + "em.Security.Permissions.SecurityPermission, mscorlib, Versio"
  + "n=1.0.5000.0, Culture=neutral, PublicKeyToken=b77a5c561934e0"
  + "89\"\r\n                version=\"1\"\r\n                Flags=\"Ski"
  + "pVerification\"/>\r\n</PermissionSet>\r\n"
  .hash algorithm 0x00008004
  .ver 3:1:0:28
}
.mresource public Calibration.Scanline.resources
{
  // Offset: 0x00000000 Length: 0x00000359
  // WARNING: managed resource file Calibration.Scanline.resources created
}
.mresource public Calibration.LED.resources
{
  // Offset: 0x00000360 Length: 0x000000BC
  // WARNING: managed resource file Calibration.LED.resources created
}
.module Calibration.dll
// MVID: {735D0D7F-2493-487A-8FF8-E8EE21A8F6B2}
.custom instance void [mscorlib]System.Security.UnverifiableCodeAttribute::.ctor() = ( 01 00 00 00 ) 
.imagebase 0x11000000
.file alignment 0x00001000
.stackreserve 0x00100000
.subsystem 0x0003       // WINDOWS_CUI
.corflags 0x00000001    //  ILONLY


// =============== CLASS MEMBERS DECLARATION ===================

.class public auto ansi sealed Calibration.Constants
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Calibration.Constants AcquisitionOffset = int32(0x00000006)
  .field public static literal valuetype Calibration.Constants AcquisitionHeight = int32(0x00000841)
  .field public static literal valuetype Calibration.Constants PutDPISleep = int32(0x00000258)
  .field public static literal valuetype Calibration.Constants ThreeQuarterHeightToCCD = int32(0x00000840)
  .field public static literal valuetype Calibration.Constants ThreeQuarterHeight = int32(0x00000630)
  .field public static literal valuetype Calibration.Constants HalfFocusDistance = int32(0x00000032)
  .field public static literal valuetype Calibration.Constants StepPerPoint = int32(0x00000001)
  .field public static literal valuetype Calibration.Constants TiltError = int32(0xFFFFFC18)
} // end of class Calibration.Constants

.class public auto ansi beforefieldinit Calibration.Descriptor
       extends [mscorlib]System.Object
{
  .field public static literal string BootLoader = "Boot"
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0006:  ret
  } // end of method Descriptor::.ctor

} // end of class Calibration.Descriptor

.class public auto ansi sealed Calibration.EEPromState
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Calibration.EEPromState Unknown = int32(0x00000000)
  .field public static literal valuetype Calibration.EEPromState Valid = int32(0x00000001)
  .field public static literal valuetype Calibration.EEPromState Invalid = int32(0x00000002)
  .field public static literal valuetype Calibration.EEPromState Corrupt = int32(0x00000003)
  .field public static literal valuetype Calibration.EEPromState Blank = int32(0x00000004)
} // end of class Calibration.EEPromState

.class public auto ansi sealed Calibration.LEDState
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Calibration.LEDState Empty = int32(0x00000000)
  .field public static literal valuetype Calibration.LEDState Fail = int32(0x00000001)
  .field public static literal valuetype Calibration.LEDState Pass = int32(0x00000002)
} // end of class Calibration.LEDState

.class public auto ansi sealed Calibration.ColorMatrixType
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Calibration.ColorMatrixType Empty = int32(0x00000000)
  .field public static literal valuetype Calibration.ColorMatrixType ThreeByFour = int32(0x00000001)
  .field public static literal valuetype Calibration.ColorMatrixType ThreeByTen = int32(0x00000002)
} // end of class Calibration.ColorMatrixType

.class public auto ansi sealed Calibration.ScannerFirmware
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Calibration.ScannerFirmware USB = int32(0x00000000)
  .field public static literal valuetype Calibration.ScannerFirmware Motor = int32(0x00000001)
  .field public static literal valuetype Calibration.ScannerFirmware DX = int32(0x00000002)
  .field public static literal valuetype Calibration.ScannerFirmware Lamp = int32(0x00000003)
  .field public static literal valuetype Calibration.ScannerFirmware CCD = int32(0x00000004)
  .field public static literal valuetype Calibration.ScannerFirmware APS = int32(0x00000005)
} // end of class Calibration.ScannerFirmware

.class public auto ansi sealed Calibration.USB135
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Calibration.USB135 Unknown = int32(0x00000000)
  .field public static literal valuetype Calibration.USB135 DDR = int32(0x00000003)
} // end of class Calibration.USB135

.class public auto ansi sealed Calibration.USB235
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Calibration.USB235 Unknown = int32(0x00000000)
  .field public static literal valuetype Calibration.USB235 FIFO = int32(0x00000001)
  .field public static literal valuetype Calibration.USB235 DDR = int32(0x00000002)
} // end of class Calibration.USB235

.class public auto ansi sealed Calibration.USB335
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Calibration.USB335 Unknown = int32(0x00000000)
  .field public static literal valuetype Calibration.USB335 DDR = int32(0x00000004)
} // end of class Calibration.USB335

.class public auto ansi sealed Calibration.EEPromValue
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Calibration.EEPromValue Offset24mm4b = int32(0x00000000)
  .field public static literal valuetype Calibration.EEPromValue Offset24mm8b = int32(0x00000001)
  .field public static literal valuetype Calibration.EEPromValue Offset24mm16b = int32(0x00000002)
  .field public static literal valuetype Calibration.EEPromValue Offset35mm4b = int32(0x00000003)
  .field public static literal valuetype Calibration.EEPromValue Offset35mm8b = int32(0x00000004)
  .field public static literal valuetype Calibration.EEPromValue Offset35mm16b = int32(0x00000005)
  .field public static literal valuetype Calibration.EEPromValue Stepper24mm4bLens = int32(0x00000006)
  .field public static literal valuetype Calibration.EEPromValue Stepper24mm4bCCD = int32(0x00000007)
  .field public static literal valuetype Calibration.EEPromValue Stepper24mm8bLens = int32(0x00000008)
  .field public static literal valuetype Calibration.EEPromValue Stepper24mm8bCCD = int32(0x00000009)
  .field public static literal valuetype Calibration.EEPromValue Stepper24mm16bLens = int32(0x0000000A)
  .field public static literal valuetype Calibration.EEPromValue Stepper24mm16bCCD = int32(0x0000000B)
  .field public static literal valuetype Calibration.EEPromValue Stepper35mm4bLens = int32(0x0000000C)
  .field public static literal valuetype Calibration.EEPromValue Stepper35mm4bCCD = int32(0x0000000D)
  .field public static literal valuetype Calibration.EEPromValue Stepper35mm8bLens = int32(0x0000000E)
  .field public static literal valuetype Calibration.EEPromValue Stepper35mm8bCCD = int32(0x0000000F)
  .field public static literal valuetype Calibration.EEPromValue Stepper35mm16bLens = int32(0x00000010)
  .field public static literal valuetype Calibration.EEPromValue Stepper35mm16bCCD = int32(0x00000011)
  .field public static literal valuetype Calibration.EEPromValue MotorSpeed24mm4b3c = int32(0x00000012)
  .field public static literal valuetype Calibration.EEPromValue MotorSpeed24mm4b4c = int32(0x00000013)
  .field public static literal valuetype Calibration.EEPromValue MotorSpeed24mm8b3c = int32(0x00000014)
  .field public static literal valuetype Calibration.EEPromValue MotorSpeed24mm8b4c = int32(0x00000015)
  .field public static literal valuetype Calibration.EEPromValue MotorSpeed24mm16b3c = int32(0x00000016)
  .field public static literal valuetype Calibration.EEPromValue MotorSpeed24mm16b4c = int32(0x00000017)
  .field public static literal valuetype Calibration.EEPromValue MotorSpeed35mm4b3c = int32(0x00000018)
  .field public static literal valuetype Calibration.EEPromValue MotorSpeed35mm4b4c = int32(0x00000019)
  .field public static literal valuetype Calibration.EEPromValue MotorSpeed35mm8b3c = int32(0x0000001A)
  .field public static literal valuetype Calibration.EEPromValue MotorSpeed35mm8b4c = int32(0x0000001B)
  .field public static literal valuetype Calibration.EEPromValue MotorSpeed35mm16b3c = int32(0x0000001C)
  .field public static literal valuetype Calibration.EEPromValue MotorSpeed35mm16b4c = int32(0x0000001D)
} // end of class Calibration.EEPromValue

.class public sequential ansi sealed beforefieldinit Calibration.OffsetNominalValues
       extends [mscorlib]System.ValueType
{
  .field public uint16 m_us24mm4b
  .field public uint16 m_us24mm8b
  .field public uint16 m_us24mm16b
  .field public uint16 m_us35mm4b
  .field public uint16 m_us35mm8b
  .field public uint16 m_us35mm16b
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(uint16 us24mm4b,
                               uint16 us24mm8b,
                               uint16 us24mm16b,
                               uint16 us35mm4b,
                               uint16 us35mm8b,
                               uint16 us35mm16b) cil managed
  {
    // Code size       46 (0x2e)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      uint16 Calibration.OffsetNominalValues::m_us24mm4b
    IL_0007:  ldarg.0
    IL_0008:  ldarg.2
    IL_0009:  stfld      uint16 Calibration.OffsetNominalValues::m_us24mm8b
    IL_000e:  ldarg.0
    IL_000f:  ldarg.3
    IL_0010:  stfld      uint16 Calibration.OffsetNominalValues::m_us24mm16b
    IL_0015:  ldarg.0
    IL_0016:  ldarg.s    us35mm4b
    IL_0018:  stfld      uint16 Calibration.OffsetNominalValues::m_us35mm4b
    IL_001d:  ldarg.0
    IL_001e:  ldarg.s    us35mm8b
    IL_0020:  stfld      uint16 Calibration.OffsetNominalValues::m_us35mm8b
    IL_0025:  ldarg.0
    IL_0026:  ldarg.s    us35mm16b
    IL_0028:  stfld      uint16 Calibration.OffsetNominalValues::m_us35mm16b
    IL_002d:  ret
  } // end of method OffsetNominalValues::.ctor

} // end of class Calibration.OffsetNominalValues

.class public sequential ansi sealed beforefieldinit Calibration.StepperNominalValues
       extends [mscorlib]System.ValueType
{
  .field public uint16 m_us24mm4b16bLens
  .field public uint16 m_us24mm4b16bCCD
  .field public uint16 m_us24mm8bLens
  .field public uint16 m_us24mm8bCCD
  .field public uint16 m_us35mm4b16bLens
  .field public uint16 m_us35mm4b16bCCD
  .field public uint16 m_us35mm8bLens
  .field public uint16 m_us35mm8bCCD
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(uint16 us24mm4b16bLens,
                               uint16 us24mm4b16bCCD,
                               uint16 us24mm8bLens,
                               uint16 us24mm8bCCD,
                               uint16 us35mm4b16bLens,
                               uint16 us35mm4b16bCCD,
                               uint16 us35mm8bLens,
                               uint16 us35mm8bCCD) cil managed
  {
    // Code size       62 (0x3e)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      uint16 Calibration.StepperNominalValues::m_us24mm4b16bLens
    IL_0007:  ldarg.0
    IL_0008:  ldarg.2
    IL_0009:  stfld      uint16 Calibration.StepperNominalValues::m_us24mm4b16bCCD
    IL_000e:  ldarg.0
    IL_000f:  ldarg.3
    IL_0010:  stfld      uint16 Calibration.StepperNominalValues::m_us24mm8bLens
    IL_0015:  ldarg.0
    IL_0016:  ldarg.s    us24mm8bCCD
    IL_0018:  stfld      uint16 Calibration.StepperNominalValues::m_us24mm8bCCD
    IL_001d:  ldarg.0
    IL_001e:  ldarg.s    us35mm4b16bLens
    IL_0020:  stfld      uint16 Calibration.StepperNominalValues::m_us35mm4b16bLens
    IL_0025:  ldarg.0
    IL_0026:  ldarg.s    us35mm4b16bCCD
    IL_0028:  stfld      uint16 Calibration.StepperNominalValues::m_us35mm4b16bCCD
    IL_002d:  ldarg.0
    IL_002e:  ldarg.s    us35mm8bLens
    IL_0030:  stfld      uint16 Calibration.StepperNominalValues::m_us35mm8bLens
    IL_0035:  ldarg.0
    IL_0036:  ldarg.s    us35mm8bCCD
    IL_0038:  stfld      uint16 Calibration.StepperNominalValues::m_us35mm8bCCD
    IL_003d:  ret
  } // end of method StepperNominalValues::.ctor

} // end of class Calibration.StepperNominalValues

.class public sequential ansi sealed beforefieldinit Calibration.MotorSpeedNominalValues
       extends [mscorlib]System.ValueType
{
  .field public uint16 m_us24mm4b3c
  .field public uint16 m_us24mm4b4c
  .field public uint16 m_us24mm8b3c
  .field public uint16 m_us24mm8b4c
  .field public uint16 m_us24mm16b3c
  .field public uint16 m_us24mm16b4c
  .field public uint16 m_us35mm4b3c
  .field public uint16 m_us35mm4b4c
  .field public uint16 m_us35mm8b3c
  .field public uint16 m_us35mm8b4c
  .field public uint16 m_us35mm16b3c
  .field public uint16 m_us35mm16b4c
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(uint16 us24mm4b3c,
                               uint16 us24mm4b4c,
                               uint16 us24mm8b3c,
                               uint16 us24mm8b4c,
                               uint16 us24mm16b3c,
                               uint16 us24mm16b4c,
                               uint16 us35mm4b3c,
                               uint16 us35mm4b4c,
                               uint16 us35mm8b3c,
                               uint16 us35mm8b4c,
                               uint16 us35mm16b3c,
                               uint16 us35mm16b4c) cil managed
  {
    // Code size       94 (0x5e)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm4b3c
    IL_0007:  ldarg.0
    IL_0008:  ldarg.2
    IL_0009:  stfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm4b4c
    IL_000e:  ldarg.0
    IL_000f:  ldarg.3
    IL_0010:  stfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm8b3c
    IL_0015:  ldarg.0
    IL_0016:  ldarg.s    us24mm8b4c
    IL_0018:  stfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm8b4c
    IL_001d:  ldarg.0
    IL_001e:  ldarg.s    us24mm16b3c
    IL_0020:  stfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm16b3c
    IL_0025:  ldarg.0
    IL_0026:  ldarg.s    us24mm16b4c
    IL_0028:  stfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm16b4c
    IL_002d:  ldarg.0
    IL_002e:  ldarg.s    us35mm4b3c
    IL_0030:  stfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm4b3c
    IL_0035:  ldarg.0
    IL_0036:  ldarg.s    us35mm4b4c
    IL_0038:  stfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm4b4c
    IL_003d:  ldarg.0
    IL_003e:  ldarg.s    us35mm8b3c
    IL_0040:  stfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm8b3c
    IL_0045:  ldarg.0
    IL_0046:  ldarg.s    us35mm8b4c
    IL_0048:  stfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm8b4c
    IL_004d:  ldarg.0
    IL_004e:  ldarg.s    us35mm16b3c
    IL_0050:  stfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm16b3c
    IL_0055:  ldarg.0
    IL_0056:  ldarg.s    us35mm16b4c
    IL_0058:  stfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm16b4c
    IL_005d:  ret
  } // end of method MotorSpeedNominalValues::.ctor

} // end of class Calibration.MotorSpeedNominalValues

.class public sequential ansi sealed beforefieldinit Calibration.ColorMatrixConfig
       extends [mscorlib]System.ValueType
{
  .field public valuetype Calibration.ColorMatrixType m_cmType
  .field public float64 m_dfMatrixValue0_0
  .field public float64 m_dfMatrixValue0_1
  .field public float64 m_dfMatrixValue0_2
  .field public float64 m_dfMatrixValue0_3
  .field public float64 m_dfMatrixValue1_0
  .field public float64 m_dfMatrixValue1_1
  .field public float64 m_dfMatrixValue1_2
  .field public float64 m_dfMatrixValue1_3
  .field public float64 m_dfMatrixValue2_0
  .field public float64 m_dfMatrixValue2_1
  .field public float64 m_dfMatrixValue2_2
  .field public float64 m_dfMatrixValue2_3
  .field public float32 m_fMatrixValue0_0
  .field public float32 m_fMatrixValue0_1
  .field public float32 m_fMatrixValue0_2
  .field public float32 m_fMatrixValue0_3
  .field public float32 m_fMatrixValue0_4
  .field public float32 m_fMatrixValue0_5
  .field public float32 m_fMatrixValue0_6
  .field public float32 m_fMatrixValue0_7
  .field public float32 m_fMatrixValue0_8
  .field public float32 m_fMatrixValue0_9
  .field public float32 m_fMatrixValue1_0
  .field public float32 m_fMatrixValue1_1
  .field public float32 m_fMatrixValue1_2
  .field public float32 m_fMatrixValue1_3
  .field public float32 m_fMatrixValue1_4
  .field public float32 m_fMatrixValue1_5
  .field public float32 m_fMatrixValue1_6
  .field public float32 m_fMatrixValue1_7
  .field public float32 m_fMatrixValue1_8
  .field public float32 m_fMatrixValue1_9
  .field public float32 m_fMatrixValue2_0
  .field public float32 m_fMatrixValue2_1
  .field public float32 m_fMatrixValue2_2
  .field public float32 m_fMatrixValue2_3
  .field public float32 m_fMatrixValue2_4
  .field public float32 m_fMatrixValue2_5
  .field public float32 m_fMatrixValue2_6
  .field public float32 m_fMatrixValue2_7
  .field public float32 m_fMatrixValue2_8
  .field public float32 m_fMatrixValue2_9
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(float64 dfMatrixValue0_0,
                               float64 dfMatrixValue0_1,
                               float64 dfMatrixValue0_2,
                               float64 dfMatrixValue0_3,
                               float64 dfMatrixValue1_0,
                               float64 dfMatrixValue1_1,
                               float64 dfMatrixValue1_2,
                               float64 dfMatrixValue1_3,
                               float64 dfMatrixValue2_0,
                               float64 dfMatrixValue2_1,
                               float64 dfMatrixValue2_2,
                               float64 dfMatrixValue2_3) cil managed
  {
    // Code size       373 (0x175)
    .maxstack  32
    .locals (float32 V_0)
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.1
    IL_0002:  stfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_0007:  ldarg.0
    IL_0008:  ldarg.1
    IL_0009:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_0
    IL_000e:  ldarg.0
    IL_000f:  ldarg.2
    IL_0010:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_1
    IL_0015:  ldarg.0
    IL_0016:  ldarg.3
    IL_0017:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_2
    IL_001c:  ldarg.0
    IL_001d:  ldarg.s    dfMatrixValue0_3
    IL_001f:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_3
    IL_0024:  ldarg.0
    IL_0025:  ldarg.s    dfMatrixValue1_0
    IL_0027:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_0
    IL_002c:  ldarg.0
    IL_002d:  ldarg.s    dfMatrixValue1_1
    IL_002f:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_1
    IL_0034:  ldarg.0
    IL_0035:  ldarg.s    dfMatrixValue1_2
    IL_0037:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_2
    IL_003c:  ldarg.0
    IL_003d:  ldarg.s    dfMatrixValue1_3
    IL_003f:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_3
    IL_0044:  ldarg.0
    IL_0045:  ldarg.s    dfMatrixValue2_0
    IL_0047:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_0
    IL_004c:  ldarg.0
    IL_004d:  ldarg.s    dfMatrixValue2_1
    IL_004f:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_1
    IL_0054:  ldarg.0
    IL_0055:  ldarg.s    dfMatrixValue2_2
    IL_0057:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_2
    IL_005c:  ldarg.0
    IL_005d:  ldarg.s    dfMatrixValue2_3
    IL_005f:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_3
    IL_0064:  ldarg.0
    IL_0065:  ldarg.0
    IL_0066:  ldarg.0
    IL_0067:  ldarg.0
    IL_0068:  ldarg.0
    IL_0069:  ldarg.0
    IL_006a:  ldarg.0
    IL_006b:  ldarg.0
    IL_006c:  ldarg.0
    IL_006d:  ldarg.0
    IL_006e:  ldarg.0
    IL_006f:  ldarg.0
    IL_0070:  ldarg.0
    IL_0071:  ldarg.0
    IL_0072:  ldarg.0
    IL_0073:  ldarg.0
    IL_0074:  ldarg.0
    IL_0075:  ldarg.0
    IL_0076:  ldarg.0
    IL_0077:  ldarg.0
    IL_0078:  ldarg.0
    IL_0079:  ldarg.0
    IL_007a:  ldarg.0
    IL_007b:  ldarg.0
    IL_007c:  ldarg.0
    IL_007d:  ldarg.0
    IL_007e:  ldarg.0
    IL_007f:  ldarg.0
    IL_0080:  ldarg.0
    IL_0081:  ldarg.0
    IL_0082:  ldc.r4     0.0
    IL_0087:  dup
    IL_0088:  stloc.0
    IL_0089:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_9
    IL_008e:  ldloc.0
    IL_008f:  dup
    IL_0090:  stloc.0
    IL_0091:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_8
    IL_0096:  ldloc.0
    IL_0097:  dup
    IL_0098:  stloc.0
    IL_0099:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_7
    IL_009e:  ldloc.0
    IL_009f:  dup
    IL_00a0:  stloc.0
    IL_00a1:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_6
    IL_00a6:  ldloc.0
    IL_00a7:  dup
    IL_00a8:  stloc.0
    IL_00a9:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_5
    IL_00ae:  ldloc.0
    IL_00af:  dup
    IL_00b0:  stloc.0
    IL_00b1:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_4
    IL_00b6:  ldloc.0
    IL_00b7:  dup
    IL_00b8:  stloc.0
    IL_00b9:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_3
    IL_00be:  ldloc.0
    IL_00bf:  dup
    IL_00c0:  stloc.0
    IL_00c1:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_2
    IL_00c6:  ldloc.0
    IL_00c7:  dup
    IL_00c8:  stloc.0
    IL_00c9:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_1
    IL_00ce:  ldloc.0
    IL_00cf:  dup
    IL_00d0:  stloc.0
    IL_00d1:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_0
    IL_00d6:  ldloc.0
    IL_00d7:  dup
    IL_00d8:  stloc.0
    IL_00d9:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_9
    IL_00de:  ldloc.0
    IL_00df:  dup
    IL_00e0:  stloc.0
    IL_00e1:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_8
    IL_00e6:  ldloc.0
    IL_00e7:  dup
    IL_00e8:  stloc.0
    IL_00e9:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_7
    IL_00ee:  ldloc.0
    IL_00ef:  dup
    IL_00f0:  stloc.0
    IL_00f1:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_6
    IL_00f6:  ldloc.0
    IL_00f7:  dup
    IL_00f8:  stloc.0
    IL_00f9:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_5
    IL_00fe:  ldloc.0
    IL_00ff:  dup
    IL_0100:  stloc.0
    IL_0101:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_4
    IL_0106:  ldloc.0
    IL_0107:  dup
    IL_0108:  stloc.0
    IL_0109:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_3
    IL_010e:  ldloc.0
    IL_010f:  dup
    IL_0110:  stloc.0
    IL_0111:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_2
    IL_0116:  ldloc.0
    IL_0117:  dup
    IL_0118:  stloc.0
    IL_0119:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_1
    IL_011e:  ldloc.0
    IL_011f:  dup
    IL_0120:  stloc.0
    IL_0121:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_0
    IL_0126:  ldloc.0
    IL_0127:  dup
    IL_0128:  stloc.0
    IL_0129:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_9
    IL_012e:  ldloc.0
    IL_012f:  dup
    IL_0130:  stloc.0
    IL_0131:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_8
    IL_0136:  ldloc.0
    IL_0137:  dup
    IL_0138:  stloc.0
    IL_0139:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_7
    IL_013e:  ldloc.0
    IL_013f:  dup
    IL_0140:  stloc.0
    IL_0141:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_6
    IL_0146:  ldloc.0
    IL_0147:  dup
    IL_0148:  stloc.0
    IL_0149:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_5
    IL_014e:  ldloc.0
    IL_014f:  dup
    IL_0150:  stloc.0
    IL_0151:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_4
    IL_0156:  ldloc.0
    IL_0157:  dup
    IL_0158:  stloc.0
    IL_0159:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_3
    IL_015e:  ldloc.0
    IL_015f:  dup
    IL_0160:  stloc.0
    IL_0161:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_2
    IL_0166:  ldloc.0
    IL_0167:  dup
    IL_0168:  stloc.0
    IL_0169:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_1
    IL_016e:  ldloc.0
    IL_016f:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_0
    IL_0174:  ret
  } // end of method ColorMatrixConfig::.ctor

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(float32 fMatrixValue0_0,
                               float32 fMatrixValue0_1,
                               float32 fMatrixValue0_2,
                               float32 fMatrixValue0_3,
                               float32 fMatrixValue0_4,
                               float32 fMatrixValue0_5,
                               float32 fMatrixValue0_6,
                               float32 fMatrixValue0_7,
                               float32 fMatrixValue0_8,
                               float32 fMatrixValue0_9,
                               float32 fMatrixValue1_0,
                               float32 fMatrixValue1_1,
                               float32 fMatrixValue1_2,
                               float32 fMatrixValue1_3,
                               float32 fMatrixValue1_4,
                               float32 fMatrixValue1_5,
                               float32 fMatrixValue1_6,
                               float32 fMatrixValue1_7,
                               float32 fMatrixValue1_8,
                               float32 fMatrixValue1_9,
                               float32 fMatrixValue2_0,
                               float32 fMatrixValue2_1,
                               float32 fMatrixValue2_2,
                               float32 fMatrixValue2_3,
                               float32 fMatrixValue2_4,
                               float32 fMatrixValue2_5,
                               float32 fMatrixValue2_6,
                               float32 fMatrixValue2_7,
                               float32 fMatrixValue2_8,
                               float32 fMatrixValue2_9) cil managed
  {
    // Code size       359 (0x167)
    .maxstack  14
    .locals (float64 V_0)
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.2
    IL_0002:  stfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_0007:  ldarg.0
    IL_0008:  ldarg.0
    IL_0009:  ldarg.0
    IL_000a:  ldarg.0
    IL_000b:  ldarg.0
    IL_000c:  ldarg.0
    IL_000d:  ldarg.0
    IL_000e:  ldarg.0
    IL_000f:  ldarg.0
    IL_0010:  ldarg.0
    IL_0011:  ldarg.0
    IL_0012:  ldarg.0
    IL_0013:  ldc.r8     0.0
    IL_001c:  dup
    IL_001d:  stloc.0
    IL_001e:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_3
    IL_0023:  ldloc.0
    IL_0024:  dup
    IL_0025:  stloc.0
    IL_0026:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_2
    IL_002b:  ldloc.0
    IL_002c:  dup
    IL_002d:  stloc.0
    IL_002e:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_1
    IL_0033:  ldloc.0
    IL_0034:  dup
    IL_0035:  stloc.0
    IL_0036:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_0
    IL_003b:  ldloc.0
    IL_003c:  dup
    IL_003d:  stloc.0
    IL_003e:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_3
    IL_0043:  ldloc.0
    IL_0044:  dup
    IL_0045:  stloc.0
    IL_0046:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_2
    IL_004b:  ldloc.0
    IL_004c:  dup
    IL_004d:  stloc.0
    IL_004e:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_1
    IL_0053:  ldloc.0
    IL_0054:  dup
    IL_0055:  stloc.0
    IL_0056:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_0
    IL_005b:  ldloc.0
    IL_005c:  dup
    IL_005d:  stloc.0
    IL_005e:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_3
    IL_0063:  ldloc.0
    IL_0064:  dup
    IL_0065:  stloc.0
    IL_0066:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_2
    IL_006b:  ldloc.0
    IL_006c:  dup
    IL_006d:  stloc.0
    IL_006e:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_1
    IL_0073:  ldloc.0
    IL_0074:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_0
    IL_0079:  ldarg.0
    IL_007a:  ldarg.1
    IL_007b:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_0
    IL_0080:  ldarg.0
    IL_0081:  ldarg.2
    IL_0082:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_1
    IL_0087:  ldarg.0
    IL_0088:  ldarg.3
    IL_0089:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_2
    IL_008e:  ldarg.0
    IL_008f:  ldarg.s    fMatrixValue0_3
    IL_0091:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_3
    IL_0096:  ldarg.0
    IL_0097:  ldarg.s    fMatrixValue0_4
    IL_0099:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_4
    IL_009e:  ldarg.0
    IL_009f:  ldarg.s    fMatrixValue0_5
    IL_00a1:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_5
    IL_00a6:  ldarg.0
    IL_00a7:  ldarg.s    fMatrixValue0_6
    IL_00a9:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_6
    IL_00ae:  ldarg.0
    IL_00af:  ldarg.s    fMatrixValue0_7
    IL_00b1:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_7
    IL_00b6:  ldarg.0
    IL_00b7:  ldarg.s    fMatrixValue0_8
    IL_00b9:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_8
    IL_00be:  ldarg.0
    IL_00bf:  ldarg.s    fMatrixValue0_9
    IL_00c1:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_9
    IL_00c6:  ldarg.0
    IL_00c7:  ldarg.s    fMatrixValue1_0
    IL_00c9:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_0
    IL_00ce:  ldarg.0
    IL_00cf:  ldarg.s    fMatrixValue1_1
    IL_00d1:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_1
    IL_00d6:  ldarg.0
    IL_00d7:  ldarg.s    fMatrixValue1_2
    IL_00d9:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_2
    IL_00de:  ldarg.0
    IL_00df:  ldarg.s    fMatrixValue1_3
    IL_00e1:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_3
    IL_00e6:  ldarg.0
    IL_00e7:  ldarg.s    fMatrixValue1_4
    IL_00e9:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_4
    IL_00ee:  ldarg.0
    IL_00ef:  ldarg.s    fMatrixValue1_5
    IL_00f1:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_5
    IL_00f6:  ldarg.0
    IL_00f7:  ldarg.s    fMatrixValue1_6
    IL_00f9:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_6
    IL_00fe:  ldarg.0
    IL_00ff:  ldarg.s    fMatrixValue1_7
    IL_0101:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_7
    IL_0106:  ldarg.0
    IL_0107:  ldarg.s    fMatrixValue1_8
    IL_0109:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_8
    IL_010e:  ldarg.0
    IL_010f:  ldarg.s    fMatrixValue1_9
    IL_0111:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_9
    IL_0116:  ldarg.0
    IL_0117:  ldarg.s    fMatrixValue2_0
    IL_0119:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_0
    IL_011e:  ldarg.0
    IL_011f:  ldarg.s    fMatrixValue2_1
    IL_0121:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_1
    IL_0126:  ldarg.0
    IL_0127:  ldarg.s    fMatrixValue2_2
    IL_0129:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_2
    IL_012e:  ldarg.0
    IL_012f:  ldarg.s    fMatrixValue2_3
    IL_0131:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_3
    IL_0136:  ldarg.0
    IL_0137:  ldarg.s    fMatrixValue2_4
    IL_0139:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_4
    IL_013e:  ldarg.0
    IL_013f:  ldarg.s    fMatrixValue2_5
    IL_0141:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_5
    IL_0146:  ldarg.0
    IL_0147:  ldarg.s    fMatrixValue2_6
    IL_0149:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_6
    IL_014e:  ldarg.0
    IL_014f:  ldarg.s    fMatrixValue2_7
    IL_0151:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_7
    IL_0156:  ldarg.0
    IL_0157:  ldarg.s    fMatrixValue2_8
    IL_0159:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_8
    IL_015e:  ldarg.0
    IL_015f:  ldarg.s    fMatrixValue2_9
    IL_0161:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_9
    IL_0166:  ret
  } // end of method ColorMatrixConfig::.ctor

} // end of class Calibration.ColorMatrixConfig

.class public sequential ansi sealed beforefieldinit Calibration.DPIConfig
       extends [mscorlib]System.ValueType
{
  .field public uint16 m_usLensStepper
  .field public uint16 m_usCCDStepper
  .field public int16 m_sCCDStepperAdjust
  .field public uint16 m_usOffset
  .field public uint16 m_usMotorSpeed
  .field public uint16 m_usMotorSpeedAdjust
  .field public uint16 m_usMotorSpeed_Ir
  .field public uint16 m_usMotorSpeedAdjust_Ir
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(uint16 usLens,
                               uint16 usCCD,
                               int16 sCCDAdjust,
                               uint16 usOffset,
                               uint16 usSpeed,
                               uint16 usSpeedAdjust,
                               uint16 usSpeedIR,
                               uint16 usSpeedIRAdjust) cil managed
  {
    // Code size       62 (0x3e)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_0007:  ldarg.0
    IL_0008:  ldarg.2
    IL_0009:  stfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_000e:  ldarg.0
    IL_000f:  ldarg.3
    IL_0010:  stfld      int16 Calibration.DPIConfig::m_sCCDStepperAdjust
    IL_0015:  ldarg.0
    IL_0016:  ldarg.s    usOffset
    IL_0018:  stfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_001d:  ldarg.0
    IL_001e:  ldarg.s    usSpeed
    IL_0020:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_0025:  ldarg.0
    IL_0026:  ldarg.s    usSpeedAdjust
    IL_0028:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust
    IL_002d:  ldarg.0
    IL_002e:  ldarg.s    usSpeedIR
    IL_0030:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_0035:  ldarg.0
    IL_0036:  ldarg.s    usSpeedIRAdjust
    IL_0038:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust_Ir
    IL_003d:  ret
  } // end of method DPIConfig::.ctor

} // end of class Calibration.DPIConfig

.class public auto ansi beforefieldinit Calibration.Global
       extends [mscorlib]System.Object
{
  .field private static bool m_bSaveIrInPlaner135
  .field private static bool m_bSaveIrInPlaner235
  .field private static bool m_bSaveIrInPlaner335
  .field public static valuetype Calibration.OffsetNominalValues m_ovF135
  .field public static valuetype Calibration.OffsetNominalValues m_ovFX35
  .field public static valuetype Calibration.StepperNominalValues m_svFX35
  .field public static valuetype Calibration.MotorSpeedNominalValues m_msF135
  .field public static valuetype Calibration.MotorSpeedNominalValues m_msF135Plus
  .field public static valuetype Calibration.MotorSpeedNominalValues m_msF235
  .field public static valuetype Calibration.MotorSpeedNominalValues m_msF235Plus
  .field public static valuetype Calibration.MotorSpeedNominalValues m_msF335
  .field public static valuetype Calibration.ColorMatrixConfig m_cmF235DefaultNegatve
  .field public static valuetype Calibration.ColorMatrixConfig m_cmF235DefaultPositive
  .method public hidebysig static void  MessageHardware([System.Windows.Forms]System.Windows.Forms.Form formOwner,
                                                        class Calibration.Scanner csScanner,
                                                        [Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                                                        int32 lStatus,
                                                        string strCaption) cil managed
  {
    // Code size       1 (0x1)
    .maxstack  8
    IL_0000:  ret
  } // end of method Global::MessageHardware

  .method public hidebysig static void  ErrorCOM([System.Windows.Forms]System.Windows.Forms.Form formOwner,
                                                 class Calibration.Scanner csScanner,
                                                 [mscorlib]System.Runtime.InteropServices.COMException caught,
                                                 string strCaption) cil managed
  {
    // Code size       65 (0x41)
    .maxstack  5
    .locals (int32 V_0,
             string V_1,
             string V_2)
    IL_0000:  ldstr      ""
    IL_0005:  stloc.1
    IL_0006:  ldstr      ""
    IL_000b:  stloc.2
    IL_000c:  ldarg.1
    IL_000d:  ldc.i4.1
    IL_000e:  ldloca.s   V_1
    IL_0010:  ldloca.s   V_2
    IL_0012:  ldloca.s   V_0
    IL_0014:  callvirt   instance void Calibration.Scanner::GetAndClearLastErrorLLC([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000,
                                                                                    string&,
                                                                                    string&,
                                                                                    int32&)
    IL_0019:  ldloc.0
    IL_001a:  brtrue.s   IL_0038

    IL_001c:  ldstr      "Error Code is : {0:X}. Error message is : {1}."
    IL_0021:  ldarg.2
    IL_0022:  callvirt   instance int32 [mscorlib]System.Runtime.InteropServices.ExternalException::get_ErrorCode()
    IL_0027:  box        [mscorlib]System.Int32
    IL_002c:  ldarg.2
    IL_002d:  callvirt   instance string [mscorlib]System.Exception::get_Message()
    IL_0032:  call       string [mscorlib]System.String::Format(string,
                                                                object,
                                                                object)
    IL_0037:  stloc.1
    IL_0038:  ldarg.0
    IL_0039:  ldloc.1
    IL_003a:  ldarg.3
    IL_003b:  call       void Calibration.LLCErrorMessageBox::Show([System.Windows.Forms]System.Windows.Forms.Form,
                                                                   string,
                                                                   string)
    IL_0040:  ret
  } // end of method Global::ErrorCOM

  .method public hidebysig static float64 
          GainToDouble(int32 uiGain) cil managed
  {
    // Code size       42 (0x2a)
    .maxstack  8
    IL_0000:  ldc.i4.s   63
    IL_0002:  ldarg.0
    IL_0003:  bge.s      IL_0009

    IL_0005:  ldc.i4.s   63
    IL_0007:  starg.s    uiGain
    IL_0009:  ldc.r8     1
    IL_0012:  ldc.r8     1
    IL_001b:  ldarg.0
    IL_001c:  conv.r8
    IL_001d:  ldc.r8     76.125
    IL_0026:  div
    IL_0027:  sub
    IL_0028:  div
    IL_0029:  ret
  } // end of method Global::GainToDouble

  .method public hidebysig static float64 
          LightPower(int32 nCurrent,
                     float64 dDutyCycle,
                     float64 dGain) cil managed
  {
    // Code size       23 (0x17)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.s   16
    IL_0003:  ble.s      IL_0010

    IL_0005:  ldc.i4.s   16
    IL_0007:  ldc.i4.2
    IL_0008:  ldarg.0
    IL_0009:  ldc.i4.s   16
    IL_000b:  sub
    IL_000c:  mul
    IL_000d:  add
    IL_000e:  starg.s    nCurrent
    IL_0010:  ldarg.0
    IL_0011:  conv.r8
    IL_0012:  ldarg.1
    IL_0013:  mul
    IL_0014:  ldarg.2
    IL_0015:  mul
    IL_0016:  ret
  } // end of method Global::LightPower

  .method public hidebysig static int32  GetPixelWidthToCCD([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iType,
                                                            [Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution) cil managed
  {
    // Code size       123 (0x7b)
    .maxstack  2
    .locals ([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_0)
    IL_0000:  ldarg.0
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  ldc.i4.7
    IL_0004:  sub
    IL_0005:  switch     ( 
                          IL_0056,
                          IL_0056)
    IL_0012:  ldloc.0
    IL_0013:  ldc.i4     0x546
    IL_0018:  sub
    IL_0019:  switch     ( 
                          IL_003c,
                          IL_003c)
    IL_0026:  ldloc.0
    IL_0027:  ldc.i4     0xd16
    IL_002c:  sub
    IL_002d:  switch     ( 
                          IL_0056,
                          IL_0056)
    IL_003a:  br.s       IL_0070

    IL_003c:  ldarg.1
    IL_003d:  ldc.i4.2
    IL_003e:  bne.un.s   IL_0046

    IL_0040:  ldc.i4     0x7d0
    IL_0045:  ret

    IL_0046:  ldarg.1
    IL_0047:  ldc.i4.1
    IL_0048:  bne.un.s   IL_0050

    IL_004a:  ldc.i4     0x5dc
    IL_004f:  ret

    IL_0050:  ldc.i4     0x3e8
    IL_0055:  ret

    IL_0056:  ldarg.1
    IL_0057:  ldc.i4.2
    IL_0058:  bne.un.s   IL_0060

    IL_005a:  ldc.i4     0x7d0
    IL_005f:  ret

    IL_0060:  ldarg.1
    IL_0061:  ldc.i4.1
    IL_0062:  bne.un.s   IL_006a

    IL_0064:  ldc.i4     0x578
    IL_0069:  ret

    IL_006a:  ldc.i4     0x3e8
    IL_006f:  ret

    IL_0070:  ldstr      "Scanner Type invalid"
    IL_0075:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_007a:  throw
  } // end of method Global::GetPixelWidthToCCD

  .method public hidebysig static [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 
          Convert([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 stType) cil managed
  {
    // Code size       70 (0x46)
    .maxstack  2
    .locals ([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_0)
    IL_0000:  ldarg.0
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  ldc.i4.7
    IL_0004:  sub
    IL_0005:  switch     ( 
                          IL_0040,
                          IL_0040)
    IL_0012:  ldloc.0
    IL_0013:  ldc.i4     0x546
    IL_0018:  sub
    IL_0019:  switch     ( 
                          IL_003c,
                          IL_003e)
    IL_0026:  ldloc.0
    IL_0027:  ldc.i4     0xd16
    IL_002c:  sub
    IL_002d:  switch     ( 
                          IL_0042,
                          IL_0042)
    IL_003a:  br.s       IL_0044

    IL_003c:  ldc.i4.3
    IL_003d:  ret

    IL_003e:  ldc.i4.1
    IL_003f:  ret

    IL_0040:  ldc.i4.0
    IL_0041:  ret

    IL_0042:  ldc.i4.2
    IL_0043:  ret

    IL_0044:  ldc.i4.4
    IL_0045:  ret
  } // end of method Global::Convert

  .method public hidebysig static [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 
          Convert([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 wtoOperation) cil managed
  {
    // Code size       195 (0xc3)
    .maxstack  1
    .locals ([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 V_0)
    IL_0000:  ldarg.0
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  switch     ( 
                          IL_0078,
                          IL_007a,
                          IL_007c,
                          IL_007e,
                          IL_0080,
                          IL_0082,
                          IL_0084,
                          IL_0086,
                          IL_0088,
                          IL_008a,
                          IL_008d,
                          IL_0090,
                          IL_0093,
                          IL_0096,
                          IL_0099,
                          IL_009c,
                          IL_009f,
                          IL_00a2,
                          IL_00a5,
                          IL_00a8,
                          IL_00ab,
                          IL_00ae,
                          IL_00b1,
                          IL_00b4,
                          IL_00b7,
                          IL_00ba,
                          IL_00bd,
                          IL_00c0)
    IL_0078:  ldc.i4.0
    IL_0079:  ret

    IL_007a:  ldc.i4.1
    IL_007b:  ret

    IL_007c:  ldc.i4.2
    IL_007d:  ret

    IL_007e:  ldc.i4.3
    IL_007f:  ret

    IL_0080:  ldc.i4.4
    IL_0081:  ret

    IL_0082:  ldc.i4.5
    IL_0083:  ret

    IL_0084:  ldc.i4.6
    IL_0085:  ret

    IL_0086:  ldc.i4.7
    IL_0087:  ret

    IL_0088:  ldc.i4.8
    IL_0089:  ret

    IL_008a:  ldc.i4.s   9
    IL_008c:  ret

    IL_008d:  ldc.i4.s   10
    IL_008f:  ret

    IL_0090:  ldc.i4.s   11
    IL_0092:  ret

    IL_0093:  ldc.i4.s   12
    IL_0095:  ret

    IL_0096:  ldc.i4.s   13
    IL_0098:  ret

    IL_0099:  ldc.i4.s   22
    IL_009b:  ret

    IL_009c:  ldc.i4.s   23
    IL_009e:  ret

    IL_009f:  ldc.i4.s   24
    IL_00a1:  ret

    IL_00a2:  ldc.i4.s   25
    IL_00a4:  ret

    IL_00a5:  ldc.i4.s   26
    IL_00a7:  ret

    IL_00a8:  ldc.i4.s   27
    IL_00aa:  ret

    IL_00ab:  ldc.i4.s   28
    IL_00ad:  ret

    IL_00ae:  ldc.i4.s   29
    IL_00b0:  ret

    IL_00b1:  ldc.i4.s   30
    IL_00b3:  ret

    IL_00b4:  ldc.i4.s   31
    IL_00b6:  ret

    IL_00b7:  ldc.i4.s   34
    IL_00b9:  ret

    IL_00ba:  ldc.i4.s   35
    IL_00bc:  ret

    IL_00bd:  ldc.i4.s   40
    IL_00bf:  ret

    IL_00c0:  ldc.i4.s   41
    IL_00c2:  ret
  } // end of method Global::Convert

  .method public hidebysig static void  ReadIrChannelSavedInPlanarFile() cil managed
  {
    // Code size       193 (0xc1)
    .maxstack  2
    .locals ([mscorlib]Microsoft.Win32.RegistryKey V_0,
             string V_1,
             string V_2,
             string V_3,
             [mscorlib]Microsoft.Win32.RegistryKey V_4,
             [mscorlib]Microsoft.Win32.RegistryKey V_5,
             [mscorlib]Microsoft.Win32.RegistryKey V_6)
    IL_0000:  ldsfld     [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.Registry::LocalMachine
    IL_0005:  stloc.0
    IL_0006:  ldstr      "Software\\Pakon\\TLA\\Scan\\Test"
    IL_000b:  stloc.1
    IL_000c:  ldstr      "Software\\Pakon\\TLB\\Scan\\Test"
    IL_0011:  stloc.2
    IL_0012:  ldstr      "Software\\Pakon\\TLC\\Scan\\Test"
    IL_0017:  stloc.3
    .try
    {
      IL_0018:  ldloc.0
      IL_0019:  ldloc.1
      IL_001a:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string)
      IL_001f:  stloc.s    V_4
      IL_0021:  ldloc.s    V_4
      IL_0023:  ldstr      "IrChannelSavedInPlanarFile"
      IL_0028:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
      IL_002d:  unbox      [mscorlib]System.Int32
      IL_0032:  ldind.i4
      IL_0033:  brfalse.s  IL_0038

      IL_0035:  ldc.i4.1
      IL_0036:  br.s       IL_0039

      IL_0038:  ldc.i4.0
      IL_0039:  stsfld     bool Calibration.Global::m_bSaveIrInPlaner235
      IL_003e:  ldloc.s    V_4
      IL_0040:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::Close()
      IL_0045:  leave.s    IL_0050

    }  // end .try
    catch [mscorlib]System.Object 
    {
      IL_0047:  pop
      IL_0048:  ldc.i4.0
      IL_0049:  stsfld     bool Calibration.Global::m_bSaveIrInPlaner235
      IL_004e:  leave.s    IL_0050

    }  // end handler
    .try
    {
      IL_0050:  ldloc.0
      IL_0051:  ldloc.2
      IL_0052:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string)
      IL_0057:  stloc.s    V_5
      IL_0059:  ldloc.s    V_5
      IL_005b:  ldstr      "IrChannelSavedInPlanarFile"
      IL_0060:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
      IL_0065:  unbox      [mscorlib]System.Int32
      IL_006a:  ldind.i4
      IL_006b:  brfalse.s  IL_0070

      IL_006d:  ldc.i4.1
      IL_006e:  br.s       IL_0071

      IL_0070:  ldc.i4.0
      IL_0071:  stsfld     bool Calibration.Global::m_bSaveIrInPlaner135
      IL_0076:  ldloc.s    V_5
      IL_0078:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::Close()
      IL_007d:  leave.s    IL_0088

    }  // end .try
    catch [mscorlib]System.Object 
    {
      IL_007f:  pop
      IL_0080:  ldc.i4.0
      IL_0081:  stsfld     bool Calibration.Global::m_bSaveIrInPlaner135
      IL_0086:  leave.s    IL_0088

    }  // end handler
    .try
    {
      IL_0088:  ldloc.0
      IL_0089:  ldloc.3
      IL_008a:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string)
      IL_008f:  stloc.s    V_6
      IL_0091:  ldloc.s    V_6
      IL_0093:  ldstr      "IrChannelSavedInPlanarFile"
      IL_0098:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
      IL_009d:  unbox      [mscorlib]System.Int32
      IL_00a2:  ldind.i4
      IL_00a3:  brfalse.s  IL_00a8

      IL_00a5:  ldc.i4.1
      IL_00a6:  br.s       IL_00a9

      IL_00a8:  ldc.i4.0
      IL_00a9:  stsfld     bool Calibration.Global::m_bSaveIrInPlaner335
      IL_00ae:  ldloc.s    V_6
      IL_00b0:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::Close()
      IL_00b5:  leave.s    IL_00c0

    }  // end .try
    catch [mscorlib]System.Object 
    {
      IL_00b7:  pop
      IL_00b8:  ldc.i4.0
      IL_00b9:  stsfld     bool Calibration.Global::m_bSaveIrInPlaner335
      IL_00be:  leave.s    IL_00c0

    }  // end handler
    IL_00c0:  ret
  } // end of method Global::ReadIrChannelSavedInPlanarFile

  .method public hidebysig static void  SetIrChannelSavedInPlanarFile() cil managed
  {
    // Code size       145 (0x91)
    .maxstack  3
    .locals ([mscorlib]Microsoft.Win32.RegistryKey V_0,
             string V_1,
             string V_2,
             string V_3,
             [mscorlib]Microsoft.Win32.RegistryKey V_4)
    IL_0000:  ldsfld     [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.Registry::LocalMachine
    IL_0005:  stloc.0
    IL_0006:  ldstr      "Software\\Pakon\\TLA\\Scan\\Test"
    IL_000b:  stloc.1
    IL_000c:  ldstr      "Software\\Pakon\\TLB\\Scan\\Test"
    IL_0011:  stloc.2
    IL_0012:  ldstr      "Software\\Pakon\\TLC\\Scan\\Test"
    IL_0017:  stloc.3
    IL_0018:  ldloc.0
    IL_0019:  ldloc.1
    IL_001a:  ldc.i4.1
    IL_001b:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string,
                                                                                                                          bool)
    IL_0020:  stloc.s    V_4
    .try
    {
      IL_0022:  ldloc.s    V_4
      IL_0024:  ldstr      "IrChannelSavedInPlanarFile"
      IL_0029:  ldc.i4.1
      IL_002a:  box        [mscorlib]System.Int32
      IL_002f:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::SetValue(string,
                                                                                         object)
      IL_0034:  leave.s    IL_0039

    }  // end .try
    catch [mscorlib]System.Object 
    {
      IL_0036:  pop
      IL_0037:  leave.s    IL_0039

    }  // end handler
    IL_0039:  ldloc.s    V_4
    IL_003b:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::Close()
    IL_0040:  ldloc.0
    IL_0041:  ldloc.2
    IL_0042:  ldc.i4.1
    IL_0043:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string,
                                                                                                                          bool)
    IL_0048:  stloc.s    V_4
    .try
    {
      IL_004a:  ldloc.s    V_4
      IL_004c:  ldstr      "IrChannelSavedInPlanarFile"
      IL_0051:  ldc.i4.1
      IL_0052:  box        [mscorlib]System.Int32
      IL_0057:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::SetValue(string,
                                                                                         object)
      IL_005c:  leave.s    IL_0061

    }  // end .try
    catch [mscorlib]System.Object 
    {
      IL_005e:  pop
      IL_005f:  leave.s    IL_0061

    }  // end handler
    IL_0061:  ldloc.s    V_4
    IL_0063:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::Close()
    IL_0068:  ldloc.0
    IL_0069:  ldloc.3
    IL_006a:  ldc.i4.1
    IL_006b:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string,
                                                                                                                          bool)
    IL_0070:  stloc.s    V_4
    .try
    {
      IL_0072:  ldloc.s    V_4
      IL_0074:  ldstr      "IrChannelSavedInPlanarFile"
      IL_0079:  ldc.i4.1
      IL_007a:  box        [mscorlib]System.Int32
      IL_007f:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::SetValue(string,
                                                                                         object)
      IL_0084:  leave.s    IL_0089

    }  // end .try
    catch [mscorlib]System.Object 
    {
      IL_0086:  pop
      IL_0087:  leave.s    IL_0089

    }  // end handler
    IL_0089:  ldloc.s    V_4
    IL_008b:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::Close()
    IL_0090:  ret
  } // end of method Global::SetIrChannelSavedInPlanarFile

  .method public hidebysig static void  ResetIrChannelSavedInPlanarFile() cil managed
  {
    // Code size       175 (0xaf)
    .maxstack  4
    .locals ([mscorlib]Microsoft.Win32.RegistryKey V_0,
             string V_1,
             string V_2,
             string V_3,
             [mscorlib]Microsoft.Win32.RegistryKey V_4,
             [mscorlib]Microsoft.Win32.RegistryKey V_5,
             [mscorlib]Microsoft.Win32.RegistryKey V_6)
    IL_0000:  ldsfld     [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.Registry::LocalMachine
    IL_0005:  stloc.0
    IL_0006:  ldstr      "Software\\Pakon\\TLA\\Scan\\Test"
    IL_000b:  stloc.1
    IL_000c:  ldstr      "Software\\Pakon\\TLB\\Scan\\Test"
    IL_0011:  stloc.2
    IL_0012:  ldstr      "Software\\Pakon\\TLC\\Scan\\Test"
    IL_0017:  stloc.3
    .try
    {
      IL_0018:  ldloc.0
      IL_0019:  ldloc.1
      IL_001a:  ldc.i4.1
      IL_001b:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string,
                                                                                                                            bool)
      IL_0020:  stloc.s    V_4
      IL_0022:  ldloc.s    V_4
      IL_0024:  ldstr      "IrChannelSavedInPlanarFile"
      IL_0029:  ldsfld     bool Calibration.Global::m_bSaveIrInPlaner235
      IL_002e:  brtrue.s   IL_0033

      IL_0030:  ldc.i4.0
      IL_0031:  br.s       IL_0034

      IL_0033:  ldc.i4.1
      IL_0034:  box        [mscorlib]System.Int32
      IL_0039:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::SetValue(string,
                                                                                         object)
      IL_003e:  ldloc.s    V_4
      IL_0040:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::Close()
      IL_0045:  leave.s    IL_004a

    }  // end .try
    catch [mscorlib]System.Object 
    {
      IL_0047:  pop
      IL_0048:  leave.s    IL_004a

    }  // end handler
    .try
    {
      IL_004a:  ldloc.0
      IL_004b:  ldloc.2
      IL_004c:  ldc.i4.1
      IL_004d:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string,
                                                                                                                            bool)
      IL_0052:  stloc.s    V_5
      IL_0054:  ldloc.s    V_5
      IL_0056:  ldstr      "IrChannelSavedInPlanarFile"
      IL_005b:  ldsfld     bool Calibration.Global::m_bSaveIrInPlaner135
      IL_0060:  brtrue.s   IL_0065

      IL_0062:  ldc.i4.0
      IL_0063:  br.s       IL_0066

      IL_0065:  ldc.i4.1
      IL_0066:  box        [mscorlib]System.Int32
      IL_006b:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::SetValue(string,
                                                                                         object)
      IL_0070:  ldloc.s    V_5
      IL_0072:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::Close()
      IL_0077:  leave.s    IL_007c

    }  // end .try
    catch [mscorlib]System.Object 
    {
      IL_0079:  pop
      IL_007a:  leave.s    IL_007c

    }  // end handler
    .try
    {
      IL_007c:  ldloc.0
      IL_007d:  ldloc.3
      IL_007e:  ldc.i4.1
      IL_007f:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string,
                                                                                                                            bool)
      IL_0084:  stloc.s    V_6
      IL_0086:  ldloc.s    V_6
      IL_0088:  ldstr      "IrChannelSavedInPlanarFile"
      IL_008d:  ldsfld     bool Calibration.Global::m_bSaveIrInPlaner335
      IL_0092:  brtrue.s   IL_0097

      IL_0094:  ldc.i4.0
      IL_0095:  br.s       IL_0098

      IL_0097:  ldc.i4.1
      IL_0098:  box        [mscorlib]System.Int32
      IL_009d:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::SetValue(string,
                                                                                         object)
      IL_00a2:  ldloc.s    V_6
      IL_00a4:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::Close()
      IL_00a9:  leave.s    IL_00ae

    }  // end .try
    catch [mscorlib]System.Object 
    {
      IL_00ab:  pop
      IL_00ac:  leave.s    IL_00ae

    }  // end handler
    IL_00ae:  ret
  } // end of method Global::ResetIrChannelSavedInPlanarFile

  .method public hidebysig static void  GetRegistryFile([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 eType,
                                                        int32 nSerialNumber,
                                                        string& strFile) cil managed
  {
    // Code size       227 (0xe3)
    .maxstack  4
    .locals (string V_0,
             string V_1,
             string V_2,
             [mscorlib]System.IO.FileInfo V_3,
             string[] V_4,
             [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_5)
    IL_0000:  ldstr      ""
    IL_0005:  stloc.0
    IL_0006:  ldstr      ""
    IL_000b:  stloc.1
    IL_000c:  ldarg.0
    IL_000d:  stloc.s    V_5
    IL_000f:  ldloc.s    V_5
    IL_0011:  ldc.i4.7
    IL_0012:  sub
    IL_0013:  switch     ( 
                          IL_0054,
                          IL_0054)
    IL_0020:  ldloc.s    V_5
    IL_0022:  ldc.i4     0x546
    IL_0027:  sub
    IL_0028:  switch     ( 
                          IL_004c,
                          IL_004c)
    IL_0035:  ldloc.s    V_5
    IL_0037:  ldc.i4     0xd16
    IL_003c:  sub
    IL_003d:  switch     ( 
                          IL_005c,
                          IL_005c)
    IL_004a:  br.s       IL_0064

    IL_004c:  ldstr      "F-135"
    IL_0051:  stloc.0
    IL_0052:  br.s       IL_006f

    IL_0054:  ldstr      "F-235"
    IL_0059:  stloc.0
    IL_005a:  br.s       IL_006f

    IL_005c:  ldstr      "F-335"
    IL_0061:  stloc.0
    IL_0062:  br.s       IL_006f

    IL_0064:  ldstr      "Scanner Type invalid"
    IL_0069:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_006e:  throw

    IL_006f:  call       string [System.Windows.Forms]System.Windows.Forms.Application::get_ExecutablePath()
    IL_0074:  stloc.2
    IL_0075:  ldloc.2
    IL_0076:  newobj     instance void [mscorlib]System.IO.FileInfo::.ctor(string)
    IL_007b:  stloc.3
    IL_007c:  ldstr      "{0}{1}"
    IL_0081:  ldloc.3
    IL_0082:  callvirt   instance [mscorlib]System.IO.DirectoryInfo [mscorlib]System.IO.FileInfo::get_Directory()
    IL_0087:  ldstr      "\\Calibration\\"
    IL_008c:  call       string [mscorlib]System.String::Format(string,
                                                                object,
                                                                object)
    IL_0091:  stloc.2
    IL_0092:  ldarg.2
    IL_0093:  ldstr      "{0}_SN{1:d4}_0.reg"
    IL_0098:  ldloc.0
    IL_0099:  ldarg.1
    IL_009a:  box        [mscorlib]System.Int32
    IL_009f:  call       string [mscorlib]System.String::Format(string,
                                                                object,
                                                                object)
    IL_00a4:  stind.ref
    IL_00a5:  ldstr      "{0}_SN{1:d4}_*.*"
    IL_00aa:  ldloc.0
    IL_00ab:  ldarg.1
    IL_00ac:  box        [mscorlib]System.Int32
    IL_00b1:  call       string [mscorlib]System.String::Format(string,
                                                                object,
                                                                object)
    IL_00b6:  stloc.1
    IL_00b7:  ldloc.2
    IL_00b8:  ldloc.1
    IL_00b9:  call       string[] [mscorlib]System.IO.Directory::GetFiles(string,
                                                                          string)
    IL_00be:  stloc.s    V_4
    IL_00c0:  ldloc.s    V_4
    IL_00c2:  ldlen
    IL_00c3:  conv.i4
    IL_00c4:  ldc.i4.0
    IL_00c5:  ble.s      IL_00d3

    IL_00c7:  ldarg.2
    IL_00c8:  ldloc.s    V_4
    IL_00ca:  ldloc.s    V_4
    IL_00cc:  ldlen
    IL_00cd:  conv.i4
    IL_00ce:  ldc.i4.1
    IL_00cf:  sub
    IL_00d0:  ldelem.ref
    IL_00d1:  stind.ref
    IL_00d2:  ret

    IL_00d3:  ldarg.2
    IL_00d4:  ldstr      "{0}{1}"
    IL_00d9:  ldloc.2
    IL_00da:  ldarg.2
    IL_00db:  ldind.ref
    IL_00dc:  call       string [mscorlib]System.String::Format(string,
                                                                object,
                                                                object)
    IL_00e1:  stind.ref
    IL_00e2:  ret
  } // end of method Global::GetRegistryFile

  .method private hidebysig specialname rtspecialname static 
          void  .cctor() cil managed
  {
    // Code size       654 (0x28e)
    .maxstack  13
    IL_0000:  ldc.i4.0
    IL_0001:  stsfld     bool Calibration.Global::m_bSaveIrInPlaner135
    IL_0006:  ldc.i4.0
    IL_0007:  stsfld     bool Calibration.Global::m_bSaveIrInPlaner235
    IL_000c:  ldc.i4.0
    IL_000d:  stsfld     bool Calibration.Global::m_bSaveIrInPlaner335
    IL_0012:  ldsflda    valuetype Calibration.OffsetNominalValues Calibration.Global::m_ovF135
    IL_0017:  ldc.i4.0
    IL_0018:  ldc.i4.0
    IL_0019:  ldc.i4.0
    IL_001a:  ldc.i4.s   31
    IL_001c:  ldc.i4.s   62
    IL_001e:  ldc.i4.s   62
    IL_0020:  call       instance void Calibration.OffsetNominalValues::.ctor(uint16,
                                                                              uint16,
                                                                              uint16,
                                                                              uint16,
                                                                              uint16,
                                                                              uint16)
    IL_0025:  ldsflda    valuetype Calibration.OffsetNominalValues Calibration.Global::m_ovFX35
    IL_002a:  ldc.i4.s   103
    IL_002c:  ldc.i4     0x1ce
    IL_0031:  ldc.i4     0xce
    IL_0036:  ldc.i4.s   31
    IL_0038:  ldc.i4     0x16a
    IL_003d:  ldc.i4.s   62
    IL_003f:  call       instance void Calibration.OffsetNominalValues::.ctor(uint16,
                                                                              uint16,
                                                                              uint16,
                                                                              uint16,
                                                                              uint16,
                                                                              uint16)
    IL_0044:  ldsflda    valuetype Calibration.StepperNominalValues Calibration.Global::m_svFX35
    IL_0049:  ldc.i4     0x6e5
    IL_004e:  ldc.i4     0x3a6
    IL_0053:  ldc.i4     0x367
    IL_0058:  ldc.i4     0x1bf
    IL_005d:  ldc.i4     0x4d3
    IL_0062:  ldc.i4     0x217
    IL_0067:  ldc.i4.s   115
    IL_0069:  ldc.i4     0x222
    IL_006e:  call       instance void Calibration.StepperNominalValues::.ctor(uint16,
                                                                               uint16,
                                                                               uint16,
                                                                               uint16,
                                                                               uint16,
                                                                               uint16,
                                                                               uint16,
                                                                               uint16)
    IL_0073:  ldsflda    valuetype Calibration.MotorSpeedNominalValues Calibration.Global::m_msF135
    IL_0078:  ldc.i4.0
    IL_0079:  ldc.i4.0
    IL_007a:  ldc.i4.0
    IL_007b:  ldc.i4.0
    IL_007c:  ldc.i4.0
    IL_007d:  ldc.i4.0
    IL_007e:  ldc.i4     0x203e
    IL_0083:  ldc.i4     0x182d
    IL_0088:  ldc.i4     0xe54
    IL_008d:  ldc.i4     0xabf
    IL_0092:  ldc.i4     0x92e
    IL_0097:  ldc.i4     0x60b
    IL_009c:  call       instance void Calibration.MotorSpeedNominalValues::.ctor(uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16)
    IL_00a1:  ldsflda    valuetype Calibration.MotorSpeedNominalValues Calibration.Global::m_msF135Plus
    IL_00a6:  ldc.i4.0
    IL_00a7:  ldc.i4.0
    IL_00a8:  ldc.i4.0
    IL_00a9:  ldc.i4.0
    IL_00aa:  ldc.i4.0
    IL_00ab:  ldc.i4.0
    IL_00ac:  ldc.i4     0x63de
    IL_00b1:  ldc.i4     0x4ae7
    IL_00b6:  ldc.i4     0x2c61
    IL_00bb:  ldc.i4     0x1d55
    IL_00c0:  ldc.i4     0x16e0
    IL_00c5:  ldc.i4     0x12be
    IL_00ca:  call       instance void Calibration.MotorSpeedNominalValues::.ctor(uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16)
    IL_00cf:  ldsflda    valuetype Calibration.MotorSpeedNominalValues Calibration.Global::m_msF235
    IL_00d4:  ldc.i4     0x3a8
    IL_00d9:  ldc.i4     0x1d4
    IL_00de:  ldc.i4     0x2ec
    IL_00e3:  ldc.i4     0x176
    IL_00e8:  ldc.i4     0x1d4
    IL_00ed:  ldc.i4     0xea
    IL_00f2:  ldc.i4     0x498
    IL_00f7:  ldc.i4     0x24c
    IL_00fc:  ldc.i4     0x3ae
    IL_0101:  ldc.i4     0x1d7
    IL_0106:  ldc.i4     0x24c
    IL_010b:  ldc.i4     0x126
    IL_0110:  call       instance void Calibration.MotorSpeedNominalValues::.ctor(uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16)
    IL_0115:  ldsflda    valuetype Calibration.MotorSpeedNominalValues Calibration.Global::m_msF235Plus
    IL_011a:  ldc.i4     0xa3c
    IL_011f:  ldc.i4     0x51e
    IL_0124:  ldc.i4     0x46f
    IL_0129:  ldc.i4     0x237
    IL_012e:  ldc.i4     0x2c6
    IL_0133:  ldc.i4     0x163
    IL_0138:  ldc.i4     0xcd5
    IL_013d:  ldc.i4     0x66a
    IL_0142:  ldc.i4     0x58f
    IL_0147:  ldc.i4     0x2c7
    IL_014c:  ldc.i4     0x37a
    IL_0151:  ldc.i4     0x1bd
    IL_0156:  call       instance void Calibration.MotorSpeedNominalValues::.ctor(uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16)
    IL_015b:  ldsflda    valuetype Calibration.MotorSpeedNominalValues Calibration.Global::m_msF335
    IL_0160:  ldc.i4     0xa52
    IL_0165:  ldc.i4     0x7c4
    IL_016a:  ldc.i4     0x60a
    IL_016f:  ldc.i4     0x487
    IL_0174:  ldc.i4     0x2bf
    IL_0179:  ldc.i4     0x20f
    IL_017e:  ldc.i4     0xce4
    IL_0183:  ldc.i4     0x91a
    IL_0188:  ldc.i4     0x955
    IL_018d:  ldc.i4     0x700
    IL_0192:  ldc.i4     0x51c
    IL_0197:  ldc.i4     0x39f
    IL_019c:  call       instance void Calibration.MotorSpeedNominalValues::.ctor(uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16,
                                                                                  uint16)
    IL_01a1:  ldsflda    valuetype Calibration.ColorMatrixConfig Calibration.Global::m_cmF235DefaultNegatve
    IL_01a6:  ldc.r8     1.21072
    IL_01af:  ldc.r8     -0.02868
    IL_01b8:  ldc.r8     -0.01088
    IL_01c1:  ldc.r8     165.44249
    IL_01ca:  ldc.r8     -0.05304
    IL_01d3:  ldc.r8     1.18184
    IL_01dc:  ldc.r8     -0.02576
    IL_01e5:  ldc.r8     476.6801
    IL_01ee:  ldc.r8     0.01644
    IL_01f7:  ldc.r8     -0.165
    IL_0200:  ldc.r8     1.28608
    IL_0209:  ldc.r8     715.2203
    IL_0212:  call       instance void Calibration.ColorMatrixConfig::.ctor(float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64)
    IL_0217:  ldsflda    valuetype Calibration.ColorMatrixConfig Calibration.Global::m_cmF235DefaultPositive
    IL_021c:  ldc.r8     1.19428
    IL_0225:  ldc.r8     -0.08552
    IL_022e:  ldc.r8     0.03316
    IL_0237:  ldc.r8     -34.73164
    IL_0240:  ldc.r8     -0.27304
    IL_0249:  ldc.r8     1.39032
    IL_0252:  ldc.r8     -0.10932
    IL_025b:  ldc.r8     53.90123
    IL_0264:  ldc.r8     -0.00696
    IL_026d:  ldc.r8     -0.4572
    IL_0276:  ldc.r8     1.57184
    IL_027f:  ldc.r8     -17.46272
    IL_0288:  call       instance void Calibration.ColorMatrixConfig::.ctor(float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64)
    IL_028d:  ret
  } // end of method Global::.cctor

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0006:  ret
  } // end of method Global::.ctor

} // end of class Calibration.Global

.class public auto ansi beforefieldinit Calibration.LED
       extends [System.Windows.Forms]System.Windows.Forms.UserControl
{
  .custom instance void [System]System.ComponentModel.DesignerCategoryAttribute::.ctor(string) = ( 01 00 04 43 6F 64 65 00 00 )                      // ...Code..
  .field private [System.Windows.Forms]System.Windows.Forms.Timer tick
  .field private [System.Windows.Forms]System.Windows.Forms.PaintEventHandler Paint
  .field public int32 tickIndex
  .field private bool _Active
  .field private [System.Drawing]System.Drawing.Color _ColorOn
  .field private [System.Drawing]System.Drawing.Color _ColorOff
  .field private bool _Flash
  .field private string _FlashIntervals
  .field public int32[] flashIntervals
  .field private string _FlashColors
  .field public [System.Drawing]System.Drawing.Color[] flashColors
  .field private [System]System.ComponentModel.Container components
  .method public hidebysig specialname instance void 
          add_Paint([System.Windows.Forms]System.Windows.Forms.PaintEventHandler 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      [System.Windows.Forms]System.Windows.Forms.PaintEventHandler Calibration.LED::Paint
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  [System.Windows.Forms]System.Windows.Forms.PaintEventHandler
    IL_0012:  stfld      [System.Windows.Forms]System.Windows.Forms.PaintEventHandler Calibration.LED::Paint
    IL_0017:  ret
  } // end of method LED::add_Paint

  .method public hidebysig specialname instance void 
          remove_Paint([System.Windows.Forms]System.Windows.Forms.PaintEventHandler 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      [System.Windows.Forms]System.Windows.Forms.PaintEventHandler Calibration.LED::Paint
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  [System.Windows.Forms]System.Windows.Forms.PaintEventHandler
    IL_0012:  stfld      [System.Windows.Forms]System.Windows.Forms.PaintEventHandler Calibration.LED::Paint
    IL_0017:  ret
  } // end of method LED::remove_Paint

  .method public hidebysig specialname instance bool 
          get_Active() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      bool Calibration.LED::_Active
    IL_0006:  ret
  } // end of method LED::get_Active

  .method public hidebysig specialname instance void 
          set_Active(bool 'value') cil managed
  {
    // Code size       14 (0xe)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      bool Calibration.LED::_Active
    IL_0007:  ldarg.0
    IL_0008:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::Invalidate()
    IL_000d:  ret
  } // end of method LED::set_Active

  .method public hidebysig specialname instance [System.Drawing]System.Drawing.Color 
          get_ColorOn() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [System.Drawing]System.Drawing.Color Calibration.LED::_ColorOn
    IL_0006:  ret
  } // end of method LED::get_ColorOn

  .method public hidebysig specialname instance void 
          set_ColorOn([System.Drawing]System.Drawing.Color 'value') cil managed
  {
    // Code size       14 (0xe)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      [System.Drawing]System.Drawing.Color Calibration.LED::_ColorOn
    IL_0007:  ldarg.0
    IL_0008:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::Invalidate()
    IL_000d:  ret
  } // end of method LED::set_ColorOn

  .method public hidebysig specialname instance [System.Drawing]System.Drawing.Color 
          get_ColorOff() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [System.Drawing]System.Drawing.Color Calibration.LED::_ColorOff
    IL_0006:  ret
  } // end of method LED::get_ColorOff

  .method public hidebysig specialname instance void 
          set_ColorOff([System.Drawing]System.Drawing.Color 'value') cil managed
  {
    // Code size       14 (0xe)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      [System.Drawing]System.Drawing.Color Calibration.LED::_ColorOff
    IL_0007:  ldarg.0
    IL_0008:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::Invalidate()
    IL_000d:  ret
  } // end of method LED::set_ColorOff

  .method public hidebysig specialname instance bool 
          get_Flash() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      bool Calibration.LED::_Flash
    IL_0006:  ret
  } // end of method LED::get_Flash

  .method public hidebysig specialname instance void 
          set_Flash(bool 'value') cil managed
  {
    // Code size       79 (0x4f)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  brfalse.s  IL_0011

    IL_0004:  ldarg.0
    IL_0005:  ldfld      int32[] Calibration.LED::flashIntervals
    IL_000a:  ldlen
    IL_000b:  conv.i4
    IL_000c:  ldc.i4.0
    IL_000d:  cgt
    IL_000f:  br.s       IL_0012

    IL_0011:  ldc.i4.0
    IL_0012:  stfld      bool Calibration.LED::_Flash
    IL_0017:  ldarg.0
    IL_0018:  ldc.i4.0
    IL_0019:  stfld      int32 Calibration.LED::tickIndex
    IL_001e:  ldarg.0
    IL_001f:  ldfld      [System.Windows.Forms]System.Windows.Forms.Timer Calibration.LED::tick
    IL_0024:  ldarg.0
    IL_0025:  ldfld      int32[] Calibration.LED::flashIntervals
    IL_002a:  ldarg.0
    IL_002b:  ldfld      int32 Calibration.LED::tickIndex
    IL_0030:  ldelem.i4
    IL_0031:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Timer::set_Interval(int32)
    IL_0036:  ldarg.0
    IL_0037:  ldfld      [System.Windows.Forms]System.Windows.Forms.Timer Calibration.LED::tick
    IL_003c:  ldarg.0
    IL_003d:  ldfld      bool Calibration.LED::_Flash
    IL_0042:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Timer::set_Enabled(bool)
    IL_0047:  ldarg.0
    IL_0048:  ldc.i4.1
    IL_0049:  call       instance void Calibration.LED::set_Active(bool)
    IL_004e:  ret
  } // end of method LED::set_Flash

  .method public hidebysig specialname instance string 
          get_FlashIntervals() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      string Calibration.LED::_FlashIntervals
    IL_0006:  ret
  } // end of method LED::get_FlashIntervals

  .method public hidebysig specialname instance void 
          set_FlashIntervals(string 'value') cil managed
  {
    // Code size       96 (0x60)
    .maxstack  4
    .locals (string[] V_0,
             int32 V_1)
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      string Calibration.LED::_FlashIntervals
    IL_0007:  ldarg.0
    IL_0008:  ldfld      string Calibration.LED::_FlashIntervals
    IL_000d:  ldc.i4.5
    IL_000e:  newarr     [mscorlib]System.Char
    IL_0013:  dup
    IL_0014:  ldtoken    field valuetype '<PrivateImplementationDetails>'/'$$struct0x6000020-1' '<PrivateImplementationDetails>'::'$$method0x6000020-1'
    IL_0019:  call       void [mscorlib]System.Runtime.CompilerServices.RuntimeHelpers::InitializeArray([mscorlib]System.Array,
                                                                                                        [mscorlib]System.RuntimeFieldHandle)
    IL_001e:  callvirt   instance string[] [mscorlib]System.String::Split(char[])
    IL_0023:  stloc.0
    IL_0024:  ldarg.0
    IL_0025:  ldloc.0
    IL_0026:  ldlen
    IL_0027:  conv.i4
    IL_0028:  newarr     [mscorlib]System.Int32
    IL_002d:  stfld      int32[] Calibration.LED::flashIntervals
    IL_0032:  ldc.i4.0
    IL_0033:  stloc.1
    IL_0034:  br.s       IL_0059

    .try
    {
      IL_0036:  ldarg.0
      IL_0037:  ldfld      int32[] Calibration.LED::flashIntervals
      IL_003c:  ldloc.1
      IL_003d:  ldloc.0
      IL_003e:  ldloc.1
      IL_003f:  ldelem.ref
      IL_0040:  call       int32 [mscorlib]System.Int32::Parse(string)
      IL_0045:  stelem.i4
      IL_0046:  leave.s    IL_0055

    }  // end .try
    catch [mscorlib]System.Object 
    {
      IL_0048:  pop
      IL_0049:  ldarg.0
      IL_004a:  ldfld      int32[] Calibration.LED::flashIntervals
      IL_004f:  ldloc.1
      IL_0050:  ldc.i4.s   25
      IL_0052:  stelem.i4
      IL_0053:  leave.s    IL_0055

    }  // end handler
    IL_0055:  ldloc.1
    IL_0056:  ldc.i4.1
    IL_0057:  add
    IL_0058:  stloc.1
    IL_0059:  ldloc.1
    IL_005a:  ldloc.0
    IL_005b:  ldlen
    IL_005c:  conv.i4
    IL_005d:  blt.s      IL_0036

    IL_005f:  ret
  } // end of method LED::set_FlashIntervals

  .method public hidebysig specialname instance string 
          get_FlashColors() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      string Calibration.LED::_FlashColors
    IL_0006:  ret
  } // end of method LED::get_FlashColors

  .method public hidebysig specialname instance void 
          set_FlashColors(string 'value') cil managed
  {
    // Code size       165 (0xa5)
    .maxstack  4
    .locals (string[] V_0,
             int32 V_1)
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      string Calibration.LED::_FlashColors
    IL_0007:  ldarg.0
    IL_0008:  ldfld      string Calibration.LED::_FlashColors
    IL_000d:  ldsfld     string [mscorlib]System.String::Empty
    IL_0012:  call       bool [mscorlib]System.String::op_Equality(string,
                                                                   string)
    IL_0017:  brfalse.s  IL_0021

    IL_0019:  ldarg.0
    IL_001a:  ldnull
    IL_001b:  stfld      [System.Drawing]System.Drawing.Color[] Calibration.LED::flashColors
    IL_0020:  ret

    IL_0021:  ldarg.0
    IL_0022:  ldfld      string Calibration.LED::_FlashColors
    IL_0027:  ldc.i4.5
    IL_0028:  newarr     [mscorlib]System.Char
    IL_002d:  dup
    IL_002e:  ldtoken    field valuetype '<PrivateImplementationDetails>'/'$$struct0x6000022-1' '<PrivateImplementationDetails>'::'$$method0x6000022-1'
    IL_0033:  call       void [mscorlib]System.Runtime.CompilerServices.RuntimeHelpers::InitializeArray([mscorlib]System.Array,
                                                                                                        [mscorlib]System.RuntimeFieldHandle)
    IL_0038:  callvirt   instance string[] [mscorlib]System.String::Split(char[])
    IL_003d:  stloc.0
    IL_003e:  ldarg.0
    IL_003f:  ldloc.0
    IL_0040:  ldlen
    IL_0041:  conv.i4
    IL_0042:  newarr     [System.Drawing]System.Drawing.Color
    IL_0047:  stfld      [System.Drawing]System.Drawing.Color[] Calibration.LED::flashColors
    IL_004c:  ldc.i4.0
    IL_004d:  stloc.1
    IL_004e:  br.s       IL_009e

    .try
    {
      IL_0050:  ldarg.0
      IL_0051:  ldfld      [System.Drawing]System.Drawing.Color[] Calibration.LED::flashColors
      IL_0056:  ldloc.1
      IL_0057:  ldelema    [System.Drawing]System.Drawing.Color
      IL_005c:  ldloc.0
      IL_005d:  ldloc.1
      IL_005e:  ldelem.ref
      IL_005f:  ldstr      ""
      IL_0064:  call       bool [mscorlib]System.String::op_Inequality(string,
                                                                       string)
      IL_0069:  brtrue.s   IL_0072

      IL_006b:  ldsfld     [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::Empty
      IL_0070:  br.s       IL_007a

      IL_0072:  ldloc.0
      IL_0073:  ldloc.1
      IL_0074:  ldelem.ref
      IL_0075:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::FromName(string)
      IL_007a:  stobj      [System.Drawing]System.Drawing.Color
      IL_007f:  leave.s    IL_009a

    }  // end .try
    catch [mscorlib]System.Object 
    {
      IL_0081:  pop
      IL_0082:  ldarg.0
      IL_0083:  ldfld      [System.Drawing]System.Drawing.Color[] Calibration.LED::flashColors
      IL_0088:  ldloc.1
      IL_0089:  ldelema    [System.Drawing]System.Drawing.Color
      IL_008e:  ldsfld     [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::Empty
      IL_0093:  stobj      [System.Drawing]System.Drawing.Color
      IL_0098:  leave.s    IL_009a

    }  // end handler
    IL_009a:  ldloc.1
    IL_009b:  ldc.i4.1
    IL_009c:  add
    IL_009d:  stloc.1
    IL_009e:  ldloc.1
    IL_009f:  ldloc.0
    IL_00a0:  ldlen
    IL_00a1:  conv.i4
    IL_00a2:  blt.s      IL_0050

    IL_00a4:  ret
  } // end of method LED::set_FlashColors

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       226 (0xe2)
    .maxstack  4
    .locals (int32[] V_0)
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.1
    IL_0002:  stfld      bool Calibration.LED::_Active
    IL_0007:  ldarg.0
    IL_0008:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Red()
    IL_000d:  stfld      [System.Drawing]System.Drawing.Color Calibration.LED::_ColorOn
    IL_0012:  ldarg.0
    IL_0013:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_Control()
    IL_0018:  stfld      [System.Drawing]System.Drawing.Color Calibration.LED::_ColorOff
    IL_001d:  ldarg.0
    IL_001e:  ldc.i4.0
    IL_001f:  stfld      bool Calibration.LED::_Flash
    IL_0024:  ldarg.0
    IL_0025:  ldstr      "250"
    IL_002a:  stfld      string Calibration.LED::_FlashIntervals
    IL_002f:  ldarg.0
    IL_0030:  ldc.i4.1
    IL_0031:  newarr     [mscorlib]System.Int32
    IL_0036:  stloc.0
    IL_0037:  ldloc.0
    IL_0038:  ldc.i4.0
    IL_0039:  ldc.i4     0xfa
    IL_003e:  stelem.i4
    IL_003f:  ldloc.0
    IL_0040:  stfld      int32[] Calibration.LED::flashIntervals
    IL_0045:  ldarg.0
    IL_0046:  ldsfld     string [mscorlib]System.String::Empty
    IL_004b:  stfld      string Calibration.LED::_FlashColors
    IL_0050:  ldarg.0
    IL_0051:  ldnull
    IL_0052:  stfld      [System]System.ComponentModel.Container Calibration.LED::components
    IL_0057:  ldarg.0
    IL_0058:  call       instance void [System.Windows.Forms]System.Windows.Forms.UserControl::.ctor()
    IL_005d:  ldarg.0
    IL_005e:  call       instance void Calibration.LED::InitializeComponent()
    IL_0063:  ldarg.0
    IL_0064:  ldc.i4     0x2000
    IL_0069:  ldc.i4.1
    IL_006a:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::SetStyle([System.Windows.Forms]System.Windows.Forms.ControlStyles,
                                                                                                    bool)
    IL_006f:  ldarg.0
    IL_0070:  ldc.i4     0x10000
    IL_0075:  ldc.i4.1
    IL_0076:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::SetStyle([System.Windows.Forms]System.Windows.Forms.ControlStyles,
                                                                                                    bool)
    IL_007b:  ldarg.0
    IL_007c:  ldc.i4     0x800
    IL_0081:  ldc.i4.1
    IL_0082:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::SetStyle([System.Windows.Forms]System.Windows.Forms.ControlStyles,
                                                                                                    bool)
    IL_0087:  ldarg.0
    IL_0088:  ldc.i4.2
    IL_0089:  ldc.i4.1
    IL_008a:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::SetStyle([System.Windows.Forms]System.Windows.Forms.ControlStyles,
                                                                                                    bool)
    IL_008f:  ldarg.0
    IL_0090:  ldc.i4.s   16
    IL_0092:  ldc.i4.1
    IL_0093:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::SetStyle([System.Windows.Forms]System.Windows.Forms.ControlStyles,
                                                                                                    bool)
    IL_0098:  ldarg.0
    IL_0099:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Transparent()
    IL_009e:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_BackColor([System.Drawing]System.Drawing.Color)
    IL_00a3:  ldarg.0
    IL_00a4:  ldc.i4.s   17
    IL_00a6:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Width(int32)
    IL_00ab:  ldarg.0
    IL_00ac:  ldc.i4.s   17
    IL_00ae:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Height(int32)
    IL_00b3:  ldarg.0
    IL_00b4:  newobj     instance void [System.Windows.Forms]System.Windows.Forms.Timer::.ctor()
    IL_00b9:  stfld      [System.Windows.Forms]System.Windows.Forms.Timer Calibration.LED::tick
    IL_00be:  ldarg.0
    IL_00bf:  ldfld      [System.Windows.Forms]System.Windows.Forms.Timer Calibration.LED::tick
    IL_00c4:  ldc.i4.0
    IL_00c5:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Timer::set_Enabled(bool)
    IL_00ca:  ldarg.0
    IL_00cb:  ldfld      [System.Windows.Forms]System.Windows.Forms.Timer Calibration.LED::tick
    IL_00d0:  ldarg.0
    IL_00d1:  ldftn      instance void Calibration.LED::_Tick(object,
                                                              [mscorlib]System.EventArgs)
    IL_00d7:  newobj     instance void [mscorlib]System.EventHandler::.ctor(object,
                                                                            native int)
    IL_00dc:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Timer::add_Tick([mscorlib]System.EventHandler)
    IL_00e1:  ret
  } // end of method LED::.ctor

  .method family hidebysig virtual instance void 
          Dispose(bool disposing) cil managed
  {
    // Code size       30 (0x1e)
    .maxstack  8
    IL_0000:  ldarg.1
    IL_0001:  brfalse.s  IL_0016

    IL_0003:  ldarg.0
    IL_0004:  ldfld      [System]System.ComponentModel.Container Calibration.LED::components
    IL_0009:  brfalse.s  IL_0016

    IL_000b:  ldarg.0
    IL_000c:  ldfld      [System]System.ComponentModel.Container Calibration.LED::components
    IL_0011:  callvirt   instance void [System]System.ComponentModel.Container::Dispose()
    IL_0016:  ldarg.0
    IL_0017:  ldarg.1
    IL_0018:  call       instance void [System.Windows.Forms]System.Windows.Forms.UserControl::Dispose(bool)
    IL_001d:  ret
  } // end of method LED::Dispose

  .method private hidebysig instance void 
          InitializeComponent() cil managed
  {
    // Code size       1 (0x1)
    .maxstack  8
    IL_0000:  ret
  } // end of method LED::InitializeComponent

  .method public hidebysig static [System.Drawing]System.Drawing.Color 
          FadeColor([System.Drawing]System.Drawing.Color c1,
                    [System.Drawing]System.Drawing.Color c2,
                    int32 i1,
                    int32 i2) cil managed
  {
    // Code size       81 (0x51)
    .maxstack  4
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2)
    IL_0000:  ldarg.2
    IL_0001:  ldarga.s   c1
    IL_0003:  call       instance uint8 [System.Drawing]System.Drawing.Color::get_R()
    IL_0008:  mul
    IL_0009:  ldarg.3
    IL_000a:  ldarga.s   c2
    IL_000c:  call       instance uint8 [System.Drawing]System.Drawing.Color::get_R()
    IL_0011:  mul
    IL_0012:  add
    IL_0013:  ldarg.2
    IL_0014:  ldarg.3
    IL_0015:  add
    IL_0016:  div
    IL_0017:  stloc.0
    IL_0018:  ldarg.2
    IL_0019:  ldarga.s   c1
    IL_001b:  call       instance uint8 [System.Drawing]System.Drawing.Color::get_G()
    IL_0020:  mul
    IL_0021:  ldarg.3
    IL_0022:  ldarga.s   c2
    IL_0024:  call       instance uint8 [System.Drawing]System.Drawing.Color::get_G()
    IL_0029:  mul
    IL_002a:  add
    IL_002b:  ldarg.2
    IL_002c:  ldarg.3
    IL_002d:  add
    IL_002e:  div
    IL_002f:  stloc.1
    IL_0030:  ldarg.2
    IL_0031:  ldarga.s   c1
    IL_0033:  call       instance uint8 [System.Drawing]System.Drawing.Color::get_B()
    IL_0038:  mul
    IL_0039:  ldarg.3
    IL_003a:  ldarga.s   c2
    IL_003c:  call       instance uint8 [System.Drawing]System.Drawing.Color::get_B()
    IL_0041:  mul
    IL_0042:  add
    IL_0043:  ldarg.2
    IL_0044:  ldarg.3
    IL_0045:  add
    IL_0046:  div
    IL_0047:  stloc.2
    IL_0048:  ldloc.0
    IL_0049:  ldloc.1
    IL_004a:  ldloc.2
    IL_004b:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::FromArgb(int32,
                                                                                                             int32,
                                                                                                             int32)
    IL_0050:  ret
  } // end of method LED::FadeColor

  .method public hidebysig static [System.Drawing]System.Drawing.Color 
          FadeColor([System.Drawing]System.Drawing.Color c1,
                    [System.Drawing]System.Drawing.Color c2) cil managed
  {
    // Code size       10 (0xa)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  ldc.i4.1
    IL_0003:  ldc.i4.1
    IL_0004:  call       [System.Drawing]System.Drawing.Color Calibration.LED::FadeColor([System.Drawing]System.Drawing.Color,
                                                                                         [System.Drawing]System.Drawing.Color,
                                                                                         int32,
                                                                                         int32)
    IL_0009:  ret
  } // end of method LED::FadeColor

  .method family hidebysig virtual instance void 
          OnPaint([System.Windows.Forms]System.Windows.Forms.PaintEventArgs e) cil managed
  {
    // Code size       442 (0x1ba)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [System.Windows.Forms]System.Windows.Forms.PaintEventHandler Calibration.LED::Paint
    IL_0006:  brfalse.s  IL_0016

    IL_0008:  ldarg.0
    IL_0009:  ldfld      [System.Windows.Forms]System.Windows.Forms.PaintEventHandler Calibration.LED::Paint
    IL_000e:  ldarg.0
    IL_000f:  ldarg.1
    IL_0010:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.PaintEventHandler::Invoke(object,
                                                                                                            [System.Windows.Forms]System.Windows.Forms.PaintEventArgs)
    IL_0015:  ret

    IL_0016:  ldarg.0
    IL_0017:  ldarg.1
    IL_0018:  call       instance void [System.Windows.Forms]System.Windows.Forms.UserControl::OnPaint([System.Windows.Forms]System.Windows.Forms.PaintEventArgs)
    IL_001d:  ldarg.0
    IL_001e:  call       instance bool [System.Windows.Forms]System.Windows.Forms.Control::get_Enabled()
    IL_0023:  brfalse    IL_018d

    IL_0028:  ldarg.0
    IL_0029:  call       instance bool Calibration.LED::get_Active()
    IL_002e:  brfalse    IL_00e0

    IL_0033:  ldarg.1
    IL_0034:  callvirt   instance [System.Drawing]System.Drawing.Graphics [System.Windows.Forms]System.Windows.Forms.PaintEventArgs::get_Graphics()
    IL_0039:  ldarg.0
    IL_003a:  call       instance [System.Drawing]System.Drawing.Color Calibration.LED::get_ColorOn()
    IL_003f:  newobj     instance void [System.Drawing]System.Drawing.SolidBrush::.ctor([System.Drawing]System.Drawing.Color)
    IL_0044:  ldc.i4.1
    IL_0045:  ldc.i4.1
    IL_0046:  ldarg.0
    IL_0047:  call       instance int32 [System.Windows.Forms]System.Windows.Forms.Control::get_Width()
    IL_004c:  ldc.i4.3
    IL_004d:  sub
    IL_004e:  ldarg.0
    IL_004f:  call       instance int32 [System.Windows.Forms]System.Windows.Forms.Control::get_Height()
    IL_0054:  ldc.i4.3
    IL_0055:  sub
    IL_0056:  callvirt   instance void [System.Drawing]System.Drawing.Graphics::FillEllipse([System.Drawing]System.Drawing.Brush,
                                                                                            int32,
                                                                                            int32,
                                                                                            int32,
                                                                                            int32)
    IL_005b:  ldarg.1
    IL_005c:  callvirt   instance [System.Drawing]System.Drawing.Graphics [System.Windows.Forms]System.Windows.Forms.PaintEventArgs::get_Graphics()
    IL_0061:  ldarg.0
    IL_0062:  call       instance [System.Drawing]System.Drawing.Color Calibration.LED::get_ColorOn()
    IL_0067:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_White()
    IL_006c:  ldc.i4.1
    IL_006d:  ldc.i4.2
    IL_006e:  call       [System.Drawing]System.Drawing.Color Calibration.LED::FadeColor([System.Drawing]System.Drawing.Color,
                                                                                         [System.Drawing]System.Drawing.Color,
                                                                                         int32,
                                                                                         int32)
    IL_0073:  ldc.r4     2
    IL_0078:  newobj     instance void [System.Drawing]System.Drawing.Pen::.ctor([System.Drawing]System.Drawing.Color,
                                                                                 float32)
    IL_007d:  ldc.r4     3
    IL_0082:  ldc.r4     3
    IL_0087:  ldarg.0
    IL_0088:  call       instance int32 [System.Windows.Forms]System.Windows.Forms.Control::get_Width()
    IL_008d:  ldc.i4.7
    IL_008e:  sub
    IL_008f:  conv.r4
    IL_0090:  ldarg.0
    IL_0091:  call       instance int32 [System.Windows.Forms]System.Windows.Forms.Control::get_Height()
    IL_0096:  ldc.i4.7
    IL_0097:  sub
    IL_0098:  conv.r4
    IL_0099:  ldc.r4     -90
    IL_009e:  ldc.r4     -90
    IL_00a3:  callvirt   instance void [System.Drawing]System.Drawing.Graphics::DrawArc([System.Drawing]System.Drawing.Pen,
                                                                                        float32,
                                                                                        float32,
                                                                                        float32,
                                                                                        float32,
                                                                                        float32,
                                                                                        float32)
    IL_00a8:  ldarg.1
    IL_00a9:  callvirt   instance [System.Drawing]System.Drawing.Graphics [System.Windows.Forms]System.Windows.Forms.PaintEventArgs::get_Graphics()
    IL_00ae:  ldarg.0
    IL_00af:  call       instance [System.Drawing]System.Drawing.Color Calibration.LED::get_ColorOn()
    IL_00b4:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_White()
    IL_00b9:  call       [System.Drawing]System.Drawing.Color Calibration.LED::FadeColor([System.Drawing]System.Drawing.Color,
                                                                                         [System.Drawing]System.Drawing.Color)
    IL_00be:  ldc.r4     1
    IL_00c3:  newobj     instance void [System.Drawing]System.Drawing.Pen::.ctor([System.Drawing]System.Drawing.Color,
                                                                                 float32)
    IL_00c8:  ldc.i4.1
    IL_00c9:  ldc.i4.1
    IL_00ca:  ldarg.0
    IL_00cb:  call       instance int32 [System.Windows.Forms]System.Windows.Forms.Control::get_Width()
    IL_00d0:  ldc.i4.3
    IL_00d1:  sub
    IL_00d2:  ldarg.0
    IL_00d3:  call       instance int32 [System.Windows.Forms]System.Windows.Forms.Control::get_Height()
    IL_00d8:  ldc.i4.3
    IL_00d9:  sub
    IL_00da:  callvirt   instance void [System.Drawing]System.Drawing.Graphics::DrawEllipse([System.Drawing]System.Drawing.Pen,
                                                                                            int32,
                                                                                            int32,
                                                                                            int32,
                                                                                            int32)
    IL_00df:  ret

    IL_00e0:  ldarg.1
    IL_00e1:  callvirt   instance [System.Drawing]System.Drawing.Graphics [System.Windows.Forms]System.Windows.Forms.PaintEventArgs::get_Graphics()
    IL_00e6:  ldarg.0
    IL_00e7:  call       instance [System.Drawing]System.Drawing.Color Calibration.LED::get_ColorOff()
    IL_00ec:  newobj     instance void [System.Drawing]System.Drawing.SolidBrush::.ctor([System.Drawing]System.Drawing.Color)
    IL_00f1:  ldc.i4.1
    IL_00f2:  ldc.i4.1
    IL_00f3:  ldarg.0
    IL_00f4:  call       instance int32 [System.Windows.Forms]System.Windows.Forms.Control::get_Width()
    IL_00f9:  ldc.i4.3
    IL_00fa:  sub
    IL_00fb:  ldarg.0
    IL_00fc:  call       instance int32 [System.Windows.Forms]System.Windows.Forms.Control::get_Height()
    IL_0101:  ldc.i4.3
    IL_0102:  sub
    IL_0103:  callvirt   instance void [System.Drawing]System.Drawing.Graphics::FillEllipse([System.Drawing]System.Drawing.Brush,
                                                                                            int32,
                                                                                            int32,
                                                                                            int32,
                                                                                            int32)
    IL_0108:  ldarg.1
    IL_0109:  callvirt   instance [System.Drawing]System.Drawing.Graphics [System.Windows.Forms]System.Windows.Forms.PaintEventArgs::get_Graphics()
    IL_010e:  ldarg.0
    IL_010f:  call       instance [System.Drawing]System.Drawing.Color Calibration.LED::get_ColorOff()
    IL_0114:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Black()
    IL_0119:  ldc.i4.2
    IL_011a:  ldc.i4.1
    IL_011b:  call       [System.Drawing]System.Drawing.Color Calibration.LED::FadeColor([System.Drawing]System.Drawing.Color,
                                                                                         [System.Drawing]System.Drawing.Color,
                                                                                         int32,
                                                                                         int32)
    IL_0120:  ldc.r4     2
    IL_0125:  newobj     instance void [System.Drawing]System.Drawing.Pen::.ctor([System.Drawing]System.Drawing.Color,
                                                                                 float32)
    IL_012a:  ldc.r4     3
    IL_012f:  ldc.r4     3
    IL_0134:  ldarg.0
    IL_0135:  call       instance int32 [System.Windows.Forms]System.Windows.Forms.Control::get_Width()
    IL_013a:  ldc.i4.7
    IL_013b:  sub
    IL_013c:  conv.r4
    IL_013d:  ldarg.0
    IL_013e:  call       instance int32 [System.Windows.Forms]System.Windows.Forms.Control::get_Height()
    IL_0143:  ldc.i4.7
    IL_0144:  sub
    IL_0145:  conv.r4
    IL_0146:  ldc.r4     0.0
    IL_014b:  ldc.r4     90
    IL_0150:  callvirt   instance void [System.Drawing]System.Drawing.Graphics::DrawArc([System.Drawing]System.Drawing.Pen,
                                                                                        float32,
                                                                                        float32,
                                                                                        float32,
                                                                                        float32,
                                                                                        float32,
                                                                                        float32)
    IL_0155:  ldarg.1
    IL_0156:  callvirt   instance [System.Drawing]System.Drawing.Graphics [System.Windows.Forms]System.Windows.Forms.PaintEventArgs::get_Graphics()
    IL_015b:  ldarg.0
    IL_015c:  call       instance [System.Drawing]System.Drawing.Color Calibration.LED::get_ColorOff()
    IL_0161:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Black()
    IL_0166:  call       [System.Drawing]System.Drawing.Color Calibration.LED::FadeColor([System.Drawing]System.Drawing.Color,
                                                                                         [System.Drawing]System.Drawing.Color)
    IL_016b:  ldc.r4     1
    IL_0170:  newobj     instance void [System.Drawing]System.Drawing.Pen::.ctor([System.Drawing]System.Drawing.Color,
                                                                                 float32)
    IL_0175:  ldc.i4.1
    IL_0176:  ldc.i4.1
    IL_0177:  ldarg.0
    IL_0178:  call       instance int32 [System.Windows.Forms]System.Windows.Forms.Control::get_Width()
    IL_017d:  ldc.i4.3
    IL_017e:  sub
    IL_017f:  ldarg.0
    IL_0180:  call       instance int32 [System.Windows.Forms]System.Windows.Forms.Control::get_Height()
    IL_0185:  ldc.i4.3
    IL_0186:  sub
    IL_0187:  callvirt   instance void [System.Drawing]System.Drawing.Graphics::DrawEllipse([System.Drawing]System.Drawing.Pen,
                                                                                            int32,
                                                                                            int32,
                                                                                            int32,
                                                                                            int32)
    IL_018c:  ret

    IL_018d:  ldarg.1
    IL_018e:  callvirt   instance [System.Drawing]System.Drawing.Graphics [System.Windows.Forms]System.Windows.Forms.PaintEventArgs::get_Graphics()
    IL_0193:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.SystemColors::get_ControlDark()
    IL_0198:  ldc.r4     1
    IL_019d:  newobj     instance void [System.Drawing]System.Drawing.Pen::.ctor([System.Drawing]System.Drawing.Color,
                                                                                 float32)
    IL_01a2:  ldc.i4.1
    IL_01a3:  ldc.i4.1
    IL_01a4:  ldarg.0
    IL_01a5:  call       instance int32 [System.Windows.Forms]System.Windows.Forms.Control::get_Width()
    IL_01aa:  ldc.i4.3
    IL_01ab:  sub
    IL_01ac:  ldarg.0
    IL_01ad:  call       instance int32 [System.Windows.Forms]System.Windows.Forms.Control::get_Height()
    IL_01b2:  ldc.i4.3
    IL_01b3:  sub
    IL_01b4:  callvirt   instance void [System.Drawing]System.Drawing.Graphics::DrawEllipse([System.Drawing]System.Drawing.Pen,
                                                                                            int32,
                                                                                            int32,
                                                                                            int32,
                                                                                            int32)
    IL_01b9:  ret
  } // end of method LED::OnPaint

  .method private hidebysig instance void 
          _Tick(object sender,
                [mscorlib]System.EventArgs e) cil managed
  {
    // Code size       187 (0xbb)
    .maxstack  4
    .locals (int32 V_0)
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  dup
    IL_0003:  ldfld      int32 Calibration.LED::tickIndex
    IL_0008:  ldc.i4.1
    IL_0009:  add
    IL_000a:  dup
    IL_000b:  stloc.0
    IL_000c:  stfld      int32 Calibration.LED::tickIndex
    IL_0011:  ldloc.0
    IL_0012:  ldarg.0
    IL_0013:  ldfld      int32[] Calibration.LED::flashIntervals
    IL_0018:  ldlen
    IL_0019:  conv.i4
    IL_001a:  rem
    IL_001b:  stfld      int32 Calibration.LED::tickIndex
    IL_0020:  ldarg.0
    IL_0021:  ldfld      [System.Windows.Forms]System.Windows.Forms.Timer Calibration.LED::tick
    IL_0026:  ldarg.0
    IL_0027:  ldfld      int32[] Calibration.LED::flashIntervals
    IL_002c:  ldarg.0
    IL_002d:  ldfld      int32 Calibration.LED::tickIndex
    IL_0032:  ldelem.i4
    IL_0033:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Timer::set_Interval(int32)
    .try
    {
      IL_0038:  ldarg.0
      IL_0039:  ldfld      [System.Drawing]System.Drawing.Color[] Calibration.LED::flashColors
      IL_003e:  brfalse.s  IL_0072

      IL_0040:  ldarg.0
      IL_0041:  ldfld      [System.Drawing]System.Drawing.Color[] Calibration.LED::flashColors
      IL_0046:  ldlen
      IL_0047:  conv.i4
      IL_0048:  ldarg.0
      IL_0049:  ldfld      int32 Calibration.LED::tickIndex
      IL_004e:  blt.s      IL_0072

      IL_0050:  ldarg.0
      IL_0051:  ldfld      [System.Drawing]System.Drawing.Color[] Calibration.LED::flashColors
      IL_0056:  ldarg.0
      IL_0057:  ldfld      int32 Calibration.LED::tickIndex
      IL_005c:  ldelema    [System.Drawing]System.Drawing.Color
      IL_0061:  ldobj      [System.Drawing]System.Drawing.Color
      IL_0066:  ldsfld     [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::Empty
      IL_006b:  call       bool [System.Drawing]System.Drawing.Color::op_Equality([System.Drawing]System.Drawing.Color,
                                                                                  [System.Drawing]System.Drawing.Color)
      IL_0070:  brfalse.s  IL_0083

      IL_0072:  ldarg.0
      IL_0073:  ldarg.0
      IL_0074:  call       instance bool Calibration.LED::get_Active()
      IL_0079:  ldc.i4.0
      IL_007a:  ceq
      IL_007c:  call       instance void Calibration.LED::set_Active(bool)
      IL_0081:  br.s       IL_00a6

      IL_0083:  ldarg.0
      IL_0084:  ldarg.0
      IL_0085:  ldfld      [System.Drawing]System.Drawing.Color[] Calibration.LED::flashColors
      IL_008a:  ldarg.0
      IL_008b:  ldfld      int32 Calibration.LED::tickIndex
      IL_0090:  ldelema    [System.Drawing]System.Drawing.Color
      IL_0095:  ldobj      [System.Drawing]System.Drawing.Color
      IL_009a:  call       instance void Calibration.LED::set_ColorOn([System.Drawing]System.Drawing.Color)
      IL_009f:  ldarg.0
      IL_00a0:  ldc.i4.1
      IL_00a1:  call       instance void Calibration.LED::set_Active(bool)
      IL_00a6:  leave.s    IL_00ba

    }  // end .try
    catch [mscorlib]System.Object 
    {
      IL_00a8:  pop
      IL_00a9:  ldarg.0
      IL_00aa:  ldarg.0
      IL_00ab:  call       instance bool Calibration.LED::get_Active()
      IL_00b0:  ldc.i4.0
      IL_00b1:  ceq
      IL_00b3:  call       instance void Calibration.LED::set_Active(bool)
      IL_00b8:  leave.s    IL_00ba

    }  // end handler
    IL_00ba:  ret
  } // end of method LED::_Tick

  .event [System.Windows.Forms]System.Windows.Forms.PaintEventHandler Paint
  {
    .addon instance void Calibration.LED::add_Paint([System.Windows.Forms]System.Windows.Forms.PaintEventHandler)
    .removeon instance void Calibration.LED::remove_Paint([System.Windows.Forms]System.Windows.Forms.PaintEventHandler)
  } // end of event LED::Paint
  .property instance bool Active()
  {
    .custom instance void [System]System.ComponentModel.CategoryAttribute::.ctor(string) = ( 01 00 08 42 65 68 61 76 69 6F 72 00 00 )          // ...Behavior..
    .custom instance void [System]System.ComponentModel.DefaultValueAttribute::.ctor(bool) = ( 01 00 01 00 00 ) 
    .get instance bool Calibration.LED::get_Active()
    .set instance void Calibration.LED::set_Active(bool)
  } // end of property LED::Active
  .property instance [System.Drawing]System.Drawing.Color
          ColorOn()
  {
    .custom instance void [System]System.ComponentModel.CategoryAttribute::.ctor(string) = ( 01 00 0A 41 70 70 65 61 72 61 6E 63 65 00 00 )    // ...Appearance..
    .get instance [System.Drawing]System.Drawing.Color Calibration.LED::get_ColorOn()
    .set instance void Calibration.LED::set_ColorOn([System.Drawing]System.Drawing.Color)
  } // end of property LED::ColorOn
  .property instance [System.Drawing]System.Drawing.Color
          ColorOff()
  {
    .custom instance void [System]System.ComponentModel.CategoryAttribute::.ctor(string) = ( 01 00 0A 41 70 70 65 61 72 61 6E 63 65 00 00 )    // ...Appearance..
    .get instance [System.Drawing]System.Drawing.Color Calibration.LED::get_ColorOff()
    .set instance void Calibration.LED::set_ColorOff([System.Drawing]System.Drawing.Color)
  } // end of property LED::ColorOff
  .property instance bool Flash()
  {
    .custom instance void [System]System.ComponentModel.DefaultValueAttribute::.ctor(bool) = ( 01 00 00 00 00 ) 
    .custom instance void [System]System.ComponentModel.CategoryAttribute::.ctor(string) = ( 01 00 08 42 65 68 61 76 69 6F 72 00 00 )          // ...Behavior..
    .set instance void Calibration.LED::set_Flash(bool)
    .get instance bool Calibration.LED::get_Flash()
  } // end of property LED::Flash
  .property instance string FlashIntervals()
  {
    .custom instance void [System]System.ComponentModel.DefaultValueAttribute::.ctor(string) = ( 01 00 03 32 35 30 00 00 )                         // ...250..
    .custom instance void [System]System.ComponentModel.CategoryAttribute::.ctor(string) = ( 01 00 0A 41 70 70 65 61 72 61 6E 63 65 00 00 )    // ...Appearance..
    .get instance string Calibration.LED::get_FlashIntervals()
    .set instance void Calibration.LED::set_FlashIntervals(string)
  } // end of property LED::FlashIntervals
  .property instance string FlashColors()
  {
    .custom instance void [System]System.ComponentModel.DefaultValueAttribute::.ctor(string) = ( 01 00 00 00 00 ) 
    .custom instance void [System]System.ComponentModel.CategoryAttribute::.ctor(string) = ( 01 00 0A 41 70 70 65 61 72 61 6E 63 65 00 00 )    // ...Appearance..
    .set instance void Calibration.LED::set_FlashColors(string)
    .get instance string Calibration.LED::get_FlashColors()
  } // end of property LED::FlashColors
} // end of class Calibration.LED

.class public auto ansi sealed Calibration.ErrorType
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Calibration.ErrorType General = int32(0x00000000)
  .field public static literal valuetype Calibration.ErrorType Callback = int32(0x00000001)
} // end of class Calibration.ErrorType

.class public auto ansi beforefieldinit Calibration.LLCErrorMessageBox
       extends [mscorlib]System.Object
{
  .field private valuetype Calibration.ErrorType m_etError
  .field private [System.Windows.Forms]System.Windows.Forms.Form m_formOwner
  .field private class Calibration.Scanner m_csScanner
  .field private [Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 m_wtoOperation
  .field private int32 m_iStatus
  .field private string m_strMessage
  .field private string m_strCaption
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor([System.Windows.Forms]System.Windows.Forms.Form formOwner,
                               valuetype Calibration.ErrorType etError,
                               class Calibration.Scanner csScanner,
                               [Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                               int32 lStatus) cil managed
  {
    // Code size       44 (0x2c)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0006:  ldarg.0
    IL_0007:  ldarg.2
    IL_0008:  stfld      valuetype Calibration.ErrorType Calibration.LLCErrorMessageBox::m_etError
    IL_000d:  ldarg.0
    IL_000e:  ldarg.1
    IL_000f:  stfld      [System.Windows.Forms]System.Windows.Forms.Form Calibration.LLCErrorMessageBox::m_formOwner
    IL_0014:  ldarg.0
    IL_0015:  ldarg.3
    IL_0016:  stfld      class Calibration.Scanner Calibration.LLCErrorMessageBox::m_csScanner
    IL_001b:  ldarg.0
    IL_001c:  ldarg.s    wtoOperation
    IL_001e:  stfld      [Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 Calibration.LLCErrorMessageBox::m_wtoOperation
    IL_0023:  ldarg.0
    IL_0024:  ldarg.s    lStatus
    IL_0026:  stfld      int32 Calibration.LLCErrorMessageBox::m_iStatus
    IL_002b:  ret
  } // end of method LLCErrorMessageBox::.ctor

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor([System.Windows.Forms]System.Windows.Forms.Form formOwner,
                               valuetype Calibration.ErrorType etError,
                               string strMessage,
                               string strCaption) cil managed
  {
    // Code size       36 (0x24)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0006:  ldarg.0
    IL_0007:  ldarg.1
    IL_0008:  stfld      [System.Windows.Forms]System.Windows.Forms.Form Calibration.LLCErrorMessageBox::m_formOwner
    IL_000d:  ldarg.0
    IL_000e:  ldarg.2
    IL_000f:  stfld      valuetype Calibration.ErrorType Calibration.LLCErrorMessageBox::m_etError
    IL_0014:  ldarg.0
    IL_0015:  ldarg.3
    IL_0016:  stfld      string Calibration.LLCErrorMessageBox::m_strMessage
    IL_001b:  ldarg.0
    IL_001c:  ldarg.s    strCaption
    IL_001e:  stfld      string Calibration.LLCErrorMessageBox::m_strCaption
    IL_0023:  ret
  } // end of method LLCErrorMessageBox::.ctor

  .method public hidebysig instance void 
          ThreadEntry() cil managed
  {
    // Code size       121 (0x79)
    .maxstack  5
    .locals (int32 V_0,
             string V_1,
             string V_2)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Calibration.ErrorType Calibration.LLCErrorMessageBox::m_etError
    IL_0006:  ldc.i4.1
    IL_0007:  bne.un.s   IL_0060

    IL_0009:  ldstr      ""
    IL_000e:  stloc.1
    IL_000f:  ldstr      ""
    IL_0014:  stloc.2
    IL_0015:  ldarg.0
    IL_0016:  ldfld      class Calibration.Scanner Calibration.LLCErrorMessageBox::m_csScanner
    IL_001b:  ldarg.0
    IL_001c:  ldfld      [Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 Calibration.LLCErrorMessageBox::m_wtoOperation
    IL_0021:  ldloca.s   V_1
    IL_0023:  ldloca.s   V_2
    IL_0025:  ldloca.s   V_0
    IL_0027:  callvirt   instance void Calibration.Scanner::GetAndClearLastErrorLLC([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000,
                                                                                    string&,
                                                                                    string&,
                                                                                    int32&)
    IL_002c:  ldstr      "Status = "
    IL_0031:  ldarg.0
    IL_0032:  ldfld      int32 Calibration.LLCErrorMessageBox::m_iStatus
    IL_0037:  box        [mscorlib]System.Int32
    IL_003c:  call       string [mscorlib]System.String::Concat(object,
                                                                object)
    IL_0041:  pop
    IL_0042:  ldarg.0
    IL_0043:  ldfld      [System.Windows.Forms]System.Windows.Forms.Form Calibration.LLCErrorMessageBox::m_formOwner
    IL_0048:  ldloc.1
    IL_0049:  ldarg.0
    IL_004a:  ldfld      [Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 Calibration.LLCErrorMessageBox::m_wtoOperation
    IL_004f:  box        [Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000
    IL_0054:  call       instance string [mscorlib]System.Enum::ToString()
    IL_0059:  call       [System.Windows.Forms]System.Windows.Forms.DialogResult [System.Windows.Forms]System.Windows.Forms.MessageBox::Show([System.Windows.Forms]System.Windows.Forms.IWin32Window,
                                                                                                                                             string,
                                                                                                                                             string)
    IL_005e:  pop
    IL_005f:  ret

    IL_0060:  ldarg.0
    IL_0061:  ldfld      [System.Windows.Forms]System.Windows.Forms.Form Calibration.LLCErrorMessageBox::m_formOwner
    IL_0066:  ldarg.0
    IL_0067:  ldfld      string Calibration.LLCErrorMessageBox::m_strMessage
    IL_006c:  ldarg.0
    IL_006d:  ldfld      string Calibration.LLCErrorMessageBox::m_strCaption
    IL_0072:  call       [System.Windows.Forms]System.Windows.Forms.DialogResult [System.Windows.Forms]System.Windows.Forms.MessageBox::Show([System.Windows.Forms]System.Windows.Forms.IWin32Window,
                                                                                                                                             string,
                                                                                                                                             string)
    IL_0077:  pop
    IL_0078:  ret
  } // end of method LLCErrorMessageBox::ThreadEntry

  .method public hidebysig static void  Show([System.Windows.Forms]System.Windows.Forms.Form formOwner,
                                             class Calibration.Scanner csScanner,
                                             [Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                                             int32 lStatus) cil managed
  {
    // Code size       38 (0x26)
    .maxstack  6
    .locals (class Calibration.LLCErrorMessageBox V_0,
             [mscorlib]System.Threading.ThreadStart V_1,
             [mscorlib]System.Threading.Thread V_2)
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.1
    IL_0002:  ldarg.1
    IL_0003:  ldarg.2
    IL_0004:  ldarg.3
    IL_0005:  newobj     instance void Calibration.LLCErrorMessageBox::.ctor([System.Windows.Forms]System.Windows.Forms.Form,
                                                                             valuetype Calibration.ErrorType,
                                                                             class Calibration.Scanner,
                                                                             [Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000,
                                                                             int32)
    IL_000a:  stloc.0
    IL_000b:  ldloc.0
    IL_000c:  ldftn      instance void Calibration.LLCErrorMessageBox::ThreadEntry()
    IL_0012:  newobj     instance void [mscorlib]System.Threading.ThreadStart::.ctor(object,
                                                                                     native int)
    IL_0017:  stloc.1
    IL_0018:  ldloc.1
    IL_0019:  newobj     instance void [mscorlib]System.Threading.Thread::.ctor([mscorlib]System.Threading.ThreadStart)
    IL_001e:  stloc.2
    IL_001f:  ldloc.2
    IL_0020:  callvirt   instance void [mscorlib]System.Threading.Thread::Start()
    IL_0025:  ret
  } // end of method LLCErrorMessageBox::Show

  .method public hidebysig static void  Show([System.Windows.Forms]System.Windows.Forms.Form formOwner,
                                             string strMessage,
                                             string strCaption) cil managed
  {
    // Code size       37 (0x25)
    .maxstack  5
    .locals (class Calibration.LLCErrorMessageBox V_0,
             [mscorlib]System.Threading.ThreadStart V_1,
             [mscorlib]System.Threading.Thread V_2)
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.0
    IL_0002:  ldarg.1
    IL_0003:  ldarg.2
    IL_0004:  newobj     instance void Calibration.LLCErrorMessageBox::.ctor([System.Windows.Forms]System.Windows.Forms.Form,
                                                                             valuetype Calibration.ErrorType,
                                                                             string,
                                                                             string)
    IL_0009:  stloc.0
    IL_000a:  ldloc.0
    IL_000b:  ldftn      instance void Calibration.LLCErrorMessageBox::ThreadEntry()
    IL_0011:  newobj     instance void [mscorlib]System.Threading.ThreadStart::.ctor(object,
                                                                                     native int)
    IL_0016:  stloc.1
    IL_0017:  ldloc.1
    IL_0018:  newobj     instance void [mscorlib]System.Threading.Thread::.ctor([mscorlib]System.Threading.ThreadStart)
    IL_001d:  stloc.2
    IL_001e:  ldloc.2
    IL_001f:  callvirt   instance void [mscorlib]System.Threading.Thread::Start()
    IL_0024:  ret
  } // end of method LLCErrorMessageBox::Show

} // end of class Calibration.LLCErrorMessageBox

.class public auto ansi beforefieldinit Calibration.Scanline
       extends [System.Windows.Forms]System.Windows.Forms.UserControl
{
  .field private int32[] m_aryCursors
  .field private [System.Drawing]System.Drawing.Color m_clrCursor
  .field private bool m_bFullDisplay
  .field private int32 m_nOffset
  .field private uint16[] m_aryPixels
  .field private uint16 m_usLowerBound
  .field private uint16 m_usUpperBound
  .field private bool m_bTestData
  .field private [System]System.ComponentModel.Container components
  .method public hidebysig specialname instance [System.Drawing]System.Drawing.Color 
          get_CursorColor() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [System.Drawing]System.Drawing.Color Calibration.Scanline::m_clrCursor
    IL_0006:  ret
  } // end of method Scanline::get_CursorColor

  .method public hidebysig specialname instance void 
          set_CursorColor([System.Drawing]System.Drawing.Color 'value') cil managed
  {
    // Code size       20 (0x14)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      [System.Drawing]System.Drawing.Color Calibration.Scanline::m_clrCursor
    IL_0007:  ldarg.0
    IL_0008:  ldarg.0
    IL_0009:  call       instance [System.Drawing]System.Drawing.Rectangle [System.Windows.Forms]System.Windows.Forms.Control::get_ClientRectangle()
    IL_000e:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::Invalidate([System.Drawing]System.Drawing.Rectangle)
    IL_0013:  ret
  } // end of method Scanline::set_CursorColor

  .method public hidebysig specialname instance int32 
          get_Offset() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32 Calibration.Scanline::m_nOffset
    IL_0006:  ret
  } // end of method Scanline::get_Offset

  .method public hidebysig specialname instance void 
          set_Offset(int32 'value') cil managed
  {
    // Code size       20 (0x14)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      int32 Calibration.Scanline::m_nOffset
    IL_0007:  ldarg.0
    IL_0008:  ldarg.0
    IL_0009:  call       instance [System.Drawing]System.Drawing.Rectangle [System.Windows.Forms]System.Windows.Forms.Control::get_ClientRectangle()
    IL_000e:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::Invalidate([System.Drawing]System.Drawing.Rectangle)
    IL_0013:  ret
  } // end of method Scanline::set_Offset

  .method public hidebysig specialname instance bool 
          get_FullDisplay() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      bool Calibration.Scanline::m_bFullDisplay
    IL_0006:  ret
  } // end of method Scanline::get_FullDisplay

  .method public hidebysig specialname instance void 
          set_FullDisplay(bool 'value') cil managed
  {
    // Code size       20 (0x14)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      bool Calibration.Scanline::m_bFullDisplay
    IL_0007:  ldarg.0
    IL_0008:  ldarg.0
    IL_0009:  call       instance [System.Drawing]System.Drawing.Rectangle [System.Windows.Forms]System.Windows.Forms.Control::get_ClientRectangle()
    IL_000e:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::Invalidate([System.Drawing]System.Drawing.Rectangle)
    IL_0013:  ret
  } // end of method Scanline::set_FullDisplay

  .method public hidebysig specialname instance int32[] 
          get_Cursors() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32[] Calibration.Scanline::m_aryCursors
    IL_0006:  ret
  } // end of method Scanline::get_Cursors

  .method public hidebysig specialname instance void 
          set_Cursors(int32[] 'value') cil managed
  {
    // Code size       20 (0x14)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      int32[] Calibration.Scanline::m_aryCursors
    IL_0007:  ldarg.0
    IL_0008:  ldarg.0
    IL_0009:  call       instance [System.Drawing]System.Drawing.Rectangle [System.Windows.Forms]System.Windows.Forms.Control::get_ClientRectangle()
    IL_000e:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::Invalidate([System.Drawing]System.Drawing.Rectangle)
    IL_0013:  ret
  } // end of method Scanline::set_Cursors

  .method public hidebysig specialname instance uint16[] 
          get_Pixels() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      uint16[] Calibration.Scanline::m_aryPixels
    IL_0006:  ret
  } // end of method Scanline::get_Pixels

  .method public hidebysig specialname instance void 
          set_Pixels(uint16[] 'value') cil managed
  {
    // Code size       20 (0x14)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      uint16[] Calibration.Scanline::m_aryPixels
    IL_0007:  ldarg.0
    IL_0008:  ldarg.0
    IL_0009:  call       instance [System.Drawing]System.Drawing.Rectangle [System.Windows.Forms]System.Windows.Forms.Control::get_ClientRectangle()
    IL_000e:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::Invalidate([System.Drawing]System.Drawing.Rectangle)
    IL_0013:  ret
  } // end of method Scanline::set_Pixels

  .method public hidebysig specialname instance bool 
          get_TestData() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      bool Calibration.Scanline::m_bTestData
    IL_0006:  ret
  } // end of method Scanline::get_TestData

  .method public hidebysig specialname instance void 
          set_TestData(bool 'value') cil managed
  {
    // Code size       20 (0x14)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      bool Calibration.Scanline::m_bTestData
    IL_0007:  ldarg.0
    IL_0008:  ldarg.0
    IL_0009:  call       instance [System.Drawing]System.Drawing.Rectangle [System.Windows.Forms]System.Windows.Forms.Control::get_ClientRectangle()
    IL_000e:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::Invalidate([System.Drawing]System.Drawing.Rectangle)
    IL_0013:  ret
  } // end of method Scanline::set_TestData

  .method private hidebysig specialname instance uint16 
          get_UpperBound() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      uint16 Calibration.Scanline::m_usUpperBound
    IL_0006:  ret
  } // end of method Scanline::get_UpperBound

  .method private hidebysig specialname instance void 
          set_UpperBound(uint16 'value') cil managed
  {
    // Code size       8 (0x8)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      uint16 Calibration.Scanline::m_usUpperBound
    IL_0007:  ret
  } // end of method Scanline::set_UpperBound

  .method private hidebysig specialname instance uint16 
          get_LowerBound() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      uint16 Calibration.Scanline::m_usLowerBound
    IL_0006:  ret
  } // end of method Scanline::get_LowerBound

  .method private hidebysig specialname instance void 
          set_LowerBound(uint16 'value') cil managed
  {
    // Code size       8 (0x8)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      uint16 Calibration.Scanline::m_usLowerBound
    IL_0007:  ret
  } // end of method Scanline::set_LowerBound

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       84 (0x54)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  ldnull
    IL_0002:  stfld      int32[] Calibration.Scanline::m_aryCursors
    IL_0007:  ldarg.0
    IL_0008:  call       [System.Drawing]System.Drawing.Color [System.Drawing]System.Drawing.Color::get_Yellow()
    IL_000d:  stfld      [System.Drawing]System.Drawing.Color Calibration.Scanline::m_clrCursor
    IL_0012:  ldarg.0
    IL_0013:  ldc.i4.1
    IL_0014:  stfld      bool Calibration.Scanline::m_bFullDisplay
    IL_0019:  ldarg.0
    IL_001a:  ldc.i4.0
    IL_001b:  stfld      int32 Calibration.Scanline::m_nOffset
    IL_0020:  ldarg.0
    IL_0021:  ldnull
    IL_0022:  stfld      uint16[] Calibration.Scanline::m_aryPixels
    IL_0027:  ldarg.0
    IL_0028:  ldc.i4.0
    IL_0029:  stfld      uint16 Calibration.Scanline::m_usLowerBound
    IL_002e:  ldarg.0
    IL_002f:  ldc.i4     0xffff
    IL_0034:  stfld      uint16 Calibration.Scanline::m_usUpperBound
    IL_0039:  ldarg.0
    IL_003a:  ldc.i4.0
    IL_003b:  stfld      bool Calibration.Scanline::m_bTestData
    IL_0040:  ldarg.0
    IL_0041:  ldnull
    IL_0042:  stfld      [System]System.ComponentModel.Container Calibration.Scanline::components
    IL_0047:  ldarg.0
    IL_0048:  call       instance void [System.Windows.Forms]System.Windows.Forms.UserControl::.ctor()
    IL_004d:  ldarg.0
    IL_004e:  call       instance void Calibration.Scanline::InitializeComponent()
    IL_0053:  ret
  } // end of method Scanline::.ctor

  .method public hidebysig instance void 
          GetAttributes(int32 iLeftCursor,
                        int32 iRightCursor,
                        [out] uint16& usMin,
                        [out] uint16& usMax,
                        [out] uint16& usAvg) cil managed
  {
    // Code size       182 (0xb6)
    .maxstack  3
    .locals (int32 V_0,
             int32 V_1,
             int64 V_2,
             int32 V_3,
             uint16 V_4,
             int32 V_5)
    IL_0000:  ldarg.3
    IL_0001:  ldc.i4     0xffff
    IL_0006:  stind.i2
    IL_0007:  ldarg.s    usMax
    IL_0009:  ldc.i4.0
    IL_000a:  stind.i2
    IL_000b:  ldarg.s    usAvg
    IL_000d:  ldc.i4.0
    IL_000e:  stind.i2
    IL_000f:  ldarg.0
    IL_0010:  call       instance int32[] Calibration.Scanline::get_Cursors()
    IL_0015:  brtrue.s   IL_0026

    IL_0017:  ldc.i4.0
    IL_0018:  stloc.0
    IL_0019:  ldarg.0
    IL_001a:  call       instance uint16[] Calibration.Scanline::get_Pixels()
    IL_001f:  ldlen
    IL_0020:  conv.i4
    IL_0021:  ldc.i4.1
    IL_0022:  sub
    IL_0023:  stloc.1
    IL_0024:  br.s       IL_0054

    IL_0026:  ldarg.1
    IL_0027:  ldarg.0
    IL_0028:  call       instance int32[] Calibration.Scanline::get_Cursors()
    IL_002d:  ldlen
    IL_002e:  conv.i4
    IL_002f:  blt.s      IL_0034

    IL_0031:  ldc.i4.0
    IL_0032:  br.s       IL_003c

    IL_0034:  ldarg.0
    IL_0035:  call       instance int32[] Calibration.Scanline::get_Cursors()
    IL_003a:  ldarg.1
    IL_003b:  ldelem.i4
    IL_003c:  stloc.0
    IL_003d:  ldarg.2
    IL_003e:  ldarg.0
    IL_003f:  call       instance int32[] Calibration.Scanline::get_Cursors()
    IL_0044:  ldlen
    IL_0045:  conv.i4
    IL_0046:  blt.s      IL_004b

    IL_0048:  ldc.i4.0
    IL_0049:  br.s       IL_0053

    IL_004b:  ldarg.0
    IL_004c:  call       instance int32[] Calibration.Scanline::get_Cursors()
    IL_0051:  ldarg.2
    IL_0052:  ldelem.i4
    IL_0053:  stloc.1
    IL_0054:  ldc.i4.0
    IL_0055:  conv.i8
    IL_0056:  stloc.2
    IL_0057:  ldloc.0
    IL_0058:  stloc.3
    IL_0059:  br.s       IL_0085

    IL_005b:  ldarg.0
    IL_005c:  call       instance uint16[] Calibration.Scanline::get_Pixels()
    IL_0061:  ldloc.3
    IL_0062:  ldelem.u2
    IL_0063:  stloc.s    V_4
    IL_0065:  ldarg.3
    IL_0066:  ldind.u2
    IL_0067:  ldloc.s    V_4
    IL_0069:  ble.s      IL_006f

    IL_006b:  ldarg.3
    IL_006c:  ldloc.s    V_4
    IL_006e:  stind.i2
    IL_006f:  ldarg.s    usMax
    IL_0071:  ldind.u2
    IL_0072:  ldloc.s    V_4
    IL_0074:  bge.s      IL_007b

    IL_0076:  ldarg.s    usMax
    IL_0078:  ldloc.s    V_4
    IL_007a:  stind.i2
    IL_007b:  ldloc.2
    IL_007c:  ldloc.s    V_4
    IL_007e:  conv.u8
    IL_007f:  add
    IL_0080:  stloc.2
    IL_0081:  ldloc.3
    IL_0082:  ldc.i4.1
    IL_0083:  add
    IL_0084:  stloc.3
    IL_0085:  ldloc.3
    IL_0086:  ldarg.0
    IL_0087:  call       instance uint16[] Calibration.Scanline::get_Pixels()
    IL_008c:  ldlen
    IL_008d:  conv.i4
    IL_008e:  bge.s      IL_0094

    IL_0090:  ldloc.3
    IL_0091:  ldloc.1
    IL_0092:  ble.s      IL_005b

    IL_0094:  ldloc.1
    IL_0095:  ldloc.0
    IL_0096:  sub
    IL_0097:  ldc.i4.1
    IL_0098:  add
    IL_0099:  stloc.s    V_5
    IL_009b:  ldloc.s    V_5
    IL_009d:  ldc.i4.0
    IL_009e:  ble.s      IL_00b5

    IL_00a0:  ldarg.s    usAvg
    IL_00a2:  ldloc.2
    IL_00a3:  conv.r4
    IL_00a4:  ldloc.s    V_5
    IL_00a6:  conv.r4
    IL_00a7:  div
    IL_00a8:  conv.r8
    IL_00a9:  ldc.r8     0.5
    IL_00b2:  add
    IL_00b3:  conv.u2
    IL_00b4:  stind.i2
    IL_00b5:  ret
  } // end of method Scanline::GetAttributes

  .method family hidebysig virtual instance void 
          Dispose(bool disposing) cil managed
  {
    // Code size       30 (0x1e)
    .maxstack  8
    IL_0000:  ldarg.1
    IL_0001:  brfalse.s  IL_0016

    IL_0003:  ldarg.0
    IL_0004:  ldfld      [System]System.ComponentModel.Container Calibration.Scanline::components
    IL_0009:  brfalse.s  IL_0016

    IL_000b:  ldarg.0
    IL_000c:  ldfld      [System]System.ComponentModel.Container Calibration.Scanline::components
    IL_0011:  callvirt   instance void [System]System.ComponentModel.Container::Dispose()
    IL_0016:  ldarg.0
    IL_0017:  ldarg.1
    IL_0018:  call       instance void [System.Windows.Forms]System.Windows.Forms.UserControl::Dispose(bool)
    IL_001d:  ret
  } // end of method Scanline::Dispose

  .method private hidebysig instance void 
          InitializeComponent() cil managed
  {
    // Code size       1 (0x1)
    .maxstack  8
    IL_0000:  ret
  } // end of method Scanline::InitializeComponent

  .method private hidebysig instance bool 
          IsCursor(int32 nOffset,
                   int32 nPixelGrouping) cil managed
  {
    // Code size       56 (0x38)
    .maxstack  3
    .locals (int32 V_0,
             bool V_1,
             int32[] V_2,
             int32 V_3)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32[] Calibration.Scanline::m_aryCursors
    IL_0006:  brtrue.s   IL_000a

    IL_0008:  ldc.i4.0
    IL_0009:  ret

    IL_000a:  ldarg.0
    IL_000b:  ldfld      int32[] Calibration.Scanline::m_aryCursors
    IL_0010:  stloc.2
    IL_0011:  ldc.i4.0
    IL_0012:  stloc.3
    IL_0013:  br.s       IL_002e

    IL_0015:  ldloc.2
    IL_0016:  ldloc.3
    IL_0017:  ldelem.i4
    IL_0018:  stloc.0
    IL_0019:  ldloc.0
    IL_001a:  ldarg.1
    IL_001b:  blt.s      IL_002a

    IL_001d:  ldarg.2
    IL_001e:  brfalse.s  IL_0026

    IL_0020:  ldloc.0
    IL_0021:  ldarg.1
    IL_0022:  ldarg.2
    IL_0023:  add
    IL_0024:  bge.s      IL_002a

    IL_0026:  ldc.i4.1
    IL_0027:  stloc.1
    IL_0028:  leave.s    IL_0036

    IL_002a:  ldloc.3
    IL_002b:  ldc.i4.1
    IL_002c:  add
    IL_002d:  stloc.3
    IL_002e:  ldloc.3
    IL_002f:  ldloc.2
    IL_0030:  ldlen
    IL_0031:  conv.i4
    IL_0032:  blt.s      IL_0015

    IL_0034:  ldc.i4.0
    IL_0035:  ret

    IL_0036:  ldloc.1
    IL_0037:  ret
  } // end of method Scanline::IsCursor

  .method private hidebysig instance uint16 
          PixelAverage(int32 nOffset,
                       int32 nPixelGrouping) cil managed
  {
    // Code size       179 (0xb3)
    .maxstack  3
    .locals (float64 V_0,
             float64 V_1,
             uint16 V_2,
             int32 V_3,
             int32 V_4,
             uint64 V_5,
             uint64 V_6,
             int32 V_7)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      uint16[] Calibration.Scanline::m_aryPixels
    IL_0006:  brtrue.s   IL_0052

    IL_0008:  ldarg.0
    IL_0009:  ldfld      bool Calibration.Scanline::m_bTestData
    IL_000e:  brfalse.s  IL_0050

    IL_0010:  ldarg.1
    IL_0011:  ldarg.2
    IL_0012:  ldc.i4.2
    IL_0013:  div
    IL_0014:  add
    IL_0015:  conv.r8
    IL_0016:  ldc.r8     120
    IL_001f:  div
    IL_0020:  stloc.0
    IL_0021:  ldc.r8     1
    IL_002a:  ldloc.0
    IL_002b:  call       float64 [mscorlib]System.Math::Cos(float64)
    IL_0030:  add
    IL_0031:  ldc.r8     2
    IL_003a:  div
    IL_003b:  stloc.1
    IL_003c:  ldarg.0
    IL_003d:  call       instance uint16 Calibration.Scanline::get_UpperBound()
    IL_0042:  ldarg.0
    IL_0043:  call       instance uint16 Calibration.Scanline::get_LowerBound()
    IL_0048:  sub
    IL_0049:  conv.r8
    IL_004a:  ldloc.1
    IL_004b:  mul
    IL_004c:  conv.u2
    IL_004d:  stloc.2
    IL_004e:  ldloc.2
    IL_004f:  ret

    IL_0050:  ldc.i4.0
    IL_0051:  ret

    IL_0052:  ldc.i4.0
    IL_0053:  ldarg.0
    IL_0054:  ldfld      uint16[] Calibration.Scanline::m_aryPixels
    IL_0059:  ldlen
    IL_005a:  conv.i4
    IL_005b:  ldc.i4.1
    IL_005c:  sub
    IL_005d:  ldarg.1
    IL_005e:  call       int32 [mscorlib]System.Math::Min(int32,
                                                          int32)
    IL_0063:  call       int32 [mscorlib]System.Math::Max(int32,
                                                          int32)
    IL_0068:  stloc.3
    IL_0069:  ldarg.0
    IL_006a:  ldfld      uint16[] Calibration.Scanline::m_aryPixels
    IL_006f:  ldlen
    IL_0070:  conv.i4
    IL_0071:  ldc.i4.1
    IL_0072:  sub
    IL_0073:  ldarg.1
    IL_0074:  ldarg.2
    IL_0075:  add
    IL_0076:  ldc.i4.1
    IL_0077:  sub
    IL_0078:  call       int32 [mscorlib]System.Math::Min(int32,
                                                          int32)
    IL_007d:  stloc.s    V_4
    IL_007f:  ldloc.s    V_4
    IL_0081:  ldc.i4.1
    IL_0082:  add
    IL_0083:  ldloc.3
    IL_0084:  sub
    IL_0085:  conv.i8
    IL_0086:  stloc.s    V_5
    IL_0088:  ldc.i4.0
    IL_0089:  conv.i8
    IL_008a:  stloc.s    V_6
    IL_008c:  ldloc.3
    IL_008d:  stloc.s    V_7
    IL_008f:  br.s       IL_00a6

    IL_0091:  ldloc.s    V_6
    IL_0093:  ldarg.0
    IL_0094:  ldfld      uint16[] Calibration.Scanline::m_aryPixels
    IL_0099:  ldloc.s    V_7
    IL_009b:  ldelem.u2
    IL_009c:  conv.u8
    IL_009d:  add
    IL_009e:  stloc.s    V_6
    IL_00a0:  ldloc.s    V_7
    IL_00a2:  ldc.i4.1
    IL_00a3:  add
    IL_00a4:  stloc.s    V_7
    IL_00a6:  ldloc.s    V_7
    IL_00a8:  ldloc.s    V_4
    IL_00aa:  ble.s      IL_0091

    IL_00ac:  ldloc.s    V_6
    IL_00ae:  ldloc.s    V_5
    IL_00b0:  div.un
    IL_00b1:  conv.u2
    IL_00b2:  ret
  } // end of method Scanline::PixelAverage

  .method private hidebysig instance int32 
          ClientValue(uint16 usValue,
                      int32 nHeight,
                      bool bCursor) cil managed
  {
    // Code size       87 (0x57)
    .maxstack  3
    .locals (uint16 V_0,
             uint16 V_1,
             float64 V_2,
             int32 V_3)
    IL_0000:  ldarg.3
    IL_0001:  brfalse.s  IL_0005

    IL_0003:  ldarg.2
    IL_0004:  ret

    IL_0005:  ldarg.0
    IL_0006:  call       instance uint16 Calibration.Scanline::get_UpperBound()
    IL_000b:  ldarg.0
    IL_000c:  call       instance uint16 Calibration.Scanline::get_LowerBound()
    IL_0011:  ble.s      IL_0023

    IL_0013:  ldarg.0
    IL_0014:  call       instance uint16 Calibration.Scanline::get_UpperBound()
    IL_0019:  ldarg.0
    IL_001a:  call       instance uint16 Calibration.Scanline::get_LowerBound()
    IL_001f:  sub
    IL_0020:  conv.u2
    IL_0021:  br.s       IL_0024

    IL_0023:  ldc.i4.0
    IL_0024:  stloc.0
    IL_0025:  ldarg.1
    IL_0026:  ldarg.0
    IL_0027:  call       instance uint16 Calibration.Scanline::get_LowerBound()
    IL_002c:  ble.s      IL_0039

    IL_002e:  ldarg.1
    IL_002f:  ldarg.0
    IL_0030:  call       instance uint16 Calibration.Scanline::get_LowerBound()
    IL_0035:  sub
    IL_0036:  conv.u2
    IL_0037:  br.s       IL_003a

    IL_0039:  ldc.i4.0
    IL_003a:  stloc.1
    IL_003b:  ldarg.2
    IL_003c:  brfalse.s  IL_0045

    IL_003e:  ldarg.2
    IL_003f:  conv.r8
    IL_0040:  ldloc.0
    IL_0041:  conv.r8
    IL_0042:  div
    IL_0043:  br.s       IL_004e

    IL_0045:  ldc.r8     0.0
    IL_004e:  stloc.2
    IL_004f:  ldloc.2
    IL_0050:  ldloc.1
    IL_0051:  conv.r8
    IL_0052:  mul
    IL_0053:  conv.i4
    IL_0054:  stloc.3
    IL_0055:  ldloc.3
    IL_0056:  ret
  } // end of method Scanline::ClientValue

  .method public hidebysig instance int32 
          PixelCount() cil managed
  {
    // Code size       33 (0x21)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      uint16[] Calibration.Scanline::m_aryPixels
    IL_0006:  brtrue.s   IL_0018

    IL_0008:  ldarg.0
    IL_0009:  ldfld      bool Calibration.Scanline::m_bTestData
    IL_000e:  brfalse.s  IL_0016

    IL_0010:  ldc.i4     0x841
    IL_0015:  ret

    IL_0016:  ldc.i4.0
    IL_0017:  ret

    IL_0018:  ldarg.0
    IL_0019:  ldfld      uint16[] Calibration.Scanline::m_aryPixels
    IL_001e:  ldlen
    IL_001f:  conv.i4
    IL_0020:  ret
  } // end of method Scanline::PixelCount

  .method family hidebysig virtual instance void 
          OnCreateControl() cil managed
  {
    // Code size       25 (0x19)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4     0x12002
    IL_0006:  ldc.i4.1
    IL_0007:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::SetStyle([System.Windows.Forms]System.Windows.Forms.ControlStyles,
                                                                                                    bool)
    IL_000c:  ldarg.0
    IL_000d:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::UpdateStyles()
    IL_0012:  ldarg.0
    IL_0013:  call       instance void [System.Windows.Forms]System.Windows.Forms.UserControl::OnCreateControl()
    IL_0018:  ret
  } // end of method Scanline::OnCreateControl

  .method family hidebysig virtual instance void 
          OnSizeChanged([mscorlib]System.EventArgs e) cil managed
  {
    // Code size       20 (0x14)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  call       instance void [System.Windows.Forms]System.Windows.Forms.UserControl::OnSizeChanged([mscorlib]System.EventArgs)
    IL_0007:  ldarg.0
    IL_0008:  ldarg.0
    IL_0009:  call       instance [System.Drawing]System.Drawing.Rectangle [System.Windows.Forms]System.Windows.Forms.Control::get_ClientRectangle()
    IL_000e:  call       instance void [System.Windows.Forms]System.Windows.Forms.Control::Invalidate([System.Drawing]System.Drawing.Rectangle)
    IL_0013:  ret
  } // end of method Scanline::OnSizeChanged

  .method family hidebysig virtual instance void 
          OnPaint([System.Windows.Forms]System.Windows.Forms.PaintEventArgs pe) cil managed
  {
    // Code size       282 (0x11a)
    .maxstack  8
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2,
             int32 V_3,
             float64 V_4,
             int32 V_5,
             [System.Drawing]System.Drawing.SolidBrush V_6,
             [System.Drawing]System.Drawing.Pen V_7,
             [System.Drawing]System.Drawing.Pen V_8,
             int32 V_9,
             int32 V_10,
             int32 V_11,
             bool V_12,
             uint16 V_13,
             int32 V_14,
             [System.Drawing]System.Drawing.Pen V_15,
             [System.Drawing]System.Drawing.Rectangle V_16)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldarg.0
    IL_0003:  call       instance [System.Drawing]System.Drawing.Rectangle [System.Windows.Forms]System.Windows.Forms.Control::get_ClientRectangle()
    IL_0008:  stloc.s    V_16
    IL_000a:  ldloca.s   V_16
    IL_000c:  call       instance int32 [System.Drawing]System.Drawing.Rectangle::get_Height()
    IL_0011:  stloc.1
    IL_0012:  ldarg.0
    IL_0013:  call       instance [System.Drawing]System.Drawing.Rectangle [System.Windows.Forms]System.Windows.Forms.Control::get_ClientRectangle()
    IL_0018:  stloc.s    V_16
    IL_001a:  ldloca.s   V_16
    IL_001c:  call       instance int32 [System.Drawing]System.Drawing.Rectangle::get_Width()
    IL_0021:  stloc.2
    IL_0022:  ldarg.0
    IL_0023:  call       instance int32 Calibration.Scanline::PixelCount()
    IL_0028:  stloc.3
    IL_0029:  ldloc.3
    IL_002a:  ldloc.2
    IL_002b:  ble.s      IL_003c

    IL_002d:  ldarg.0
    IL_002e:  call       instance bool Calibration.Scanline::get_FullDisplay()
    IL_0033:  brfalse.s  IL_003c

    IL_0035:  ldloc.3
    IL_0036:  conv.r8
    IL_0037:  ldloc.2
    IL_0038:  conv.r8
    IL_0039:  div
    IL_003a:  br.s       IL_0045

    IL_003c:  ldc.r8     1
    IL_0045:  stloc.s    V_4
    IL_0047:  ldarg.0
    IL_0048:  call       instance bool Calibration.Scanline::get_FullDisplay()
    IL_004d:  brtrue.s   IL_0057

    IL_004f:  ldarg.0
    IL_0050:  ldfld      int32 Calibration.Scanline::m_nOffset
    IL_0055:  br.s       IL_0058

    IL_0057:  ldc.i4.0
    IL_0058:  stloc.s    V_5
    IL_005a:  ldarg.0
    IL_005b:  callvirt   instance [System.Drawing]System.Drawing.Color [System.Windows.Forms]System.Windows.Forms.Control::get_BackColor()
    IL_0060:  newobj     instance void [System.Drawing]System.Drawing.SolidBrush::.ctor([System.Drawing]System.Drawing.Color)
    IL_0065:  stloc.s    V_6
    IL_0067:  ldarg.0
    IL_0068:  callvirt   instance [System.Drawing]System.Drawing.Color [System.Windows.Forms]System.Windows.Forms.Control::get_ForeColor()
    IL_006d:  newobj     instance void [System.Drawing]System.Drawing.Pen::.ctor([System.Drawing]System.Drawing.Color)
    IL_0072:  stloc.s    V_7
    IL_0074:  ldarg.0
    IL_0075:  call       instance [System.Drawing]System.Drawing.Color Calibration.Scanline::get_CursorColor()
    IL_007a:  newobj     instance void [System.Drawing]System.Drawing.Pen::.ctor([System.Drawing]System.Drawing.Color)
    IL_007f:  stloc.s    V_8
    IL_0081:  ldarg.1
    IL_0082:  callvirt   instance [System.Drawing]System.Drawing.Graphics [System.Windows.Forms]System.Windows.Forms.PaintEventArgs::get_Graphics()
    IL_0087:  ldloc.s    V_6
    IL_0089:  ldarg.0
    IL_008a:  call       instance [System.Drawing]System.Drawing.Rectangle [System.Windows.Forms]System.Windows.Forms.Control::get_ClientRectangle()
    IL_008f:  callvirt   instance void [System.Drawing]System.Drawing.Graphics::FillRectangle([System.Drawing]System.Drawing.Brush,
                                                                                              [System.Drawing]System.Drawing.Rectangle)
    IL_0094:  ldarg.0
    IL_0095:  call       instance int32 Calibration.Scanline::PixelCount()
    IL_009a:  brfalse.s  IL_0119

    IL_009c:  ldc.i4.0
    IL_009d:  stloc.s    V_9
    IL_009f:  br.s       IL_0114

    IL_00a1:  ldloc.s    V_5
    IL_00a3:  ldloc.s    V_4
    IL_00a5:  ldloc.s    V_9
    IL_00a7:  conv.r8
    IL_00a8:  mul
    IL_00a9:  conv.i4
    IL_00aa:  add
    IL_00ab:  stloc.s    V_10
    IL_00ad:  ldloc.s    V_5
    IL_00af:  ldloc.s    V_4
    IL_00b1:  ldloc.s    V_9
    IL_00b3:  ldc.i4.1
    IL_00b4:  add
    IL_00b5:  conv.r8
    IL_00b6:  mul
    IL_00b7:  conv.i4
    IL_00b8:  add
    IL_00b9:  stloc.s    V_11
    IL_00bb:  ldarg.0
    IL_00bc:  ldloc.s    V_10
    IL_00be:  ldloc.s    V_11
    IL_00c0:  ldloc.s    V_10
    IL_00c2:  sub
    IL_00c3:  call       instance bool Calibration.Scanline::IsCursor(int32,
                                                                      int32)
    IL_00c8:  stloc.s    V_12
    IL_00ca:  ldarg.0
    IL_00cb:  ldloc.s    V_10
    IL_00cd:  ldloc.s    V_11
    IL_00cf:  ldloc.s    V_10
    IL_00d1:  sub
    IL_00d2:  call       instance uint16 Calibration.Scanline::PixelAverage(int32,
                                                                            int32)
    IL_00d7:  stloc.s    V_13
    IL_00d9:  ldarg.0
    IL_00da:  ldloc.s    V_13
    IL_00dc:  ldloc.1
    IL_00dd:  ldloc.0
    IL_00de:  sub
    IL_00df:  ldloc.s    V_12
    IL_00e1:  call       instance int32 Calibration.Scanline::ClientValue(uint16,
                                                                          int32,
                                                                          bool)
    IL_00e6:  stloc.s    V_14
    IL_00e8:  ldloc.s    V_12
    IL_00ea:  brtrue.s   IL_00f0

    IL_00ec:  ldloc.s    V_7
    IL_00ee:  br.s       IL_00f2

    IL_00f0:  ldloc.s    V_8
    IL_00f2:  stloc.s    V_15
    IL_00f4:  ldarg.1
    IL_00f5:  callvirt   instance [System.Drawing]System.Drawing.Graphics [System.Windows.Forms]System.Windows.Forms.PaintEventArgs::get_Graphics()
    IL_00fa:  ldloc.s    V_15
    IL_00fc:  ldloc.s    V_9
    IL_00fe:  ldloc.1
    IL_00ff:  ldloc.0
    IL_0100:  sub
    IL_0101:  ldloc.s    V_9
    IL_0103:  ldloc.1
    IL_0104:  ldloc.0
    IL_0105:  ldloc.s    V_14
    IL_0107:  add
    IL_0108:  sub
    IL_0109:  callvirt   instance void [System.Drawing]System.Drawing.Graphics::DrawLine([System.Drawing]System.Drawing.Pen,
                                                                                         int32,
                                                                                         int32,
                                                                                         int32,
                                                                                         int32)
    IL_010e:  ldloc.s    V_9
    IL_0110:  ldc.i4.1
    IL_0111:  add
    IL_0112:  stloc.s    V_9
    IL_0114:  ldloc.s    V_9
    IL_0116:  ldloc.2
    IL_0117:  blt.s      IL_00a1

    IL_0119:  ret
  } // end of method Scanline::OnPaint

  .property instance [System.Drawing]System.Drawing.Color
          CursorColor()
  {
    .set instance void Calibration.Scanline::set_CursorColor([System.Drawing]System.Drawing.Color)
    .get instance [System.Drawing]System.Drawing.Color Calibration.Scanline::get_CursorColor()
  } // end of property Scanline::CursorColor
  .property instance int32 Offset()
  {
    .set instance void Calibration.Scanline::set_Offset(int32)
    .get instance int32 Calibration.Scanline::get_Offset()
  } // end of property Scanline::Offset
  .property instance bool FullDisplay()
  {
    .get instance bool Calibration.Scanline::get_FullDisplay()
    .set instance void Calibration.Scanline::set_FullDisplay(bool)
  } // end of property Scanline::FullDisplay
  .property instance int32[] Cursors()
  {
    .get instance int32[] Calibration.Scanline::get_Cursors()
    .set instance void Calibration.Scanline::set_Cursors(int32[])
  } // end of property Scanline::Cursors
  .property instance uint16[] Pixels()
  {
    .get instance uint16[] Calibration.Scanline::get_Pixels()
    .set instance void Calibration.Scanline::set_Pixels(uint16[])
  } // end of property Scanline::Pixels
  .property instance bool TestData()
  {
    .set instance void Calibration.Scanline::set_TestData(bool)
    .get instance bool Calibration.Scanline::get_TestData()
  } // end of property Scanline::TestData
  .property instance uint16 UpperBound()
  {
    .get instance uint16 Calibration.Scanline::get_UpperBound()
    .set instance void Calibration.Scanline::set_UpperBound(uint16)
  } // end of property Scanline::UpperBound
  .property instance uint16 LowerBound()
  {
    .set instance void Calibration.Scanline::set_LowerBound(uint16)
    .get instance uint16 Calibration.Scanline::get_LowerBound()
  } // end of property Scanline::LowerBound
} // end of class Calibration.Scanline

.class public auto ansi sealed Calibration.LLCError
       extends [mscorlib]System.MulticastDelegate
{
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(object 'object',
                               native int 'method') runtime managed
  {
  } // end of method LLCError::.ctor

  .method public hidebysig virtual instance void 
          Invoke([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                 int32 lStatus) runtime managed
  {
  } // end of method LLCError::Invoke

  .method public hidebysig newslot virtual 
          instance [mscorlib]System.IAsyncResult 
          BeginInvoke([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                      int32 lStatus,
                      [mscorlib]System.AsyncCallback callback,
                      object 'object') runtime managed
  {
  } // end of method LLCError::BeginInvoke

  .method public hidebysig newslot virtual 
          instance void  EndInvoke([mscorlib]System.IAsyncResult result) runtime managed
  {
  } // end of method LLCError::EndInvoke

} // end of class Calibration.LLCError

.class public auto ansi sealed Calibration.LLCHardware
       extends [mscorlib]System.MulticastDelegate
{
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(object 'object',
                               native int 'method') runtime managed
  {
  } // end of method LLCHardware::.ctor

  .method public hidebysig virtual instance void 
          Invoke([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                 int32 lStatus) runtime managed
  {
  } // end of method LLCHardware::Invoke

  .method public hidebysig newslot virtual 
          instance [mscorlib]System.IAsyncResult 
          BeginInvoke([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                      int32 lStatus,
                      [mscorlib]System.AsyncCallback callback,
                      object 'object') runtime managed
  {
  } // end of method LLCHardware::BeginInvoke

  .method public hidebysig newslot virtual 
          instance void  EndInvoke([mscorlib]System.IAsyncResult result) runtime managed
  {
  } // end of method LLCHardware::EndInvoke

} // end of class Calibration.LLCHardware

.class public auto ansi sealed Calibration.LLCProgress
       extends [mscorlib]System.MulticastDelegate
{
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(object 'object',
                               native int 'method') runtime managed
  {
  } // end of method LLCProgress::.ctor

  .method public hidebysig virtual instance void 
          Invoke([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                 int32 lStatus) runtime managed
  {
  } // end of method LLCProgress::Invoke

  .method public hidebysig newslot virtual 
          instance [mscorlib]System.IAsyncResult 
          BeginInvoke([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                      int32 lStatus,
                      [mscorlib]System.AsyncCallback callback,
                      object 'object') runtime managed
  {
  } // end of method LLCProgress::BeginInvoke

  .method public hidebysig newslot virtual 
          instance void  EndInvoke([mscorlib]System.IAsyncResult result) runtime managed
  {
  } // end of method LLCProgress::EndInvoke

} // end of class Calibration.LLCProgress

.class public auto ansi sealed Calibration.Acquire
       extends [mscorlib]System.MulticastDelegate
{
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(object 'object',
                               native int 'method') runtime managed
  {
  } // end of method Acquire::.ctor

  .method public hidebysig virtual instance void 
          Invoke() runtime managed
  {
  } // end of method Acquire::Invoke

  .method public hidebysig newslot virtual 
          instance [mscorlib]System.IAsyncResult 
          BeginInvoke([mscorlib]System.AsyncCallback callback,
                      object 'object') runtime managed
  {
  } // end of method Acquire::BeginInvoke

  .method public hidebysig newslot virtual 
          instance void  EndInvoke([mscorlib]System.IAsyncResult result) runtime managed
  {
  } // end of method Acquire::EndInvoke

} // end of class Calibration.Acquire

.class public auto ansi beforefieldinit Calibration.CallBackClient
       extends [mscorlib]System.Object
       implements [Interop.LLCLib]LLCLib.ICallBackClient
{
  .field private class Calibration.Scanner m_csScanner
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(class Calibration.Scanner csScanner) cil managed
  {
    // Code size       14 (0xe)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0006:  ldarg.0
    IL_0007:  ldarg.1
    IL_0008:  stfld      class Calibration.Scanner Calibration.CallBackClient::m_csScanner
    IL_000d:  ret
  } // end of method CallBackClient::.ctor

  .method public hidebysig newslot virtual final 
          instance void  Awake(int32 lOperation,
                               int32 lStatus) cil managed
  {
    // Code size       14 (0xe)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      class Calibration.Scanner Calibration.CallBackClient::m_csScanner
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  callvirt   instance void Calibration.Scanner::LLCAwake(int32,
                                                                     int32)
    IL_000d:  ret
  } // end of method CallBackClient::Awake

} // end of class Calibration.CallBackClient

.class public auto ansi beforefieldinit Calibration.Scanner
       extends [Pakon]Pakon.Scanner
{
  .field private class Calibration.LLCError m_evLLCError
  .field private class Calibration.LLCHardware m_evLLCHardware
  .field private class Calibration.LLCProgress m_evLLCProgress
  .field private class Calibration.Acquire m_evAcquire
  .field private class Calibration.ScannerUnsafe m_csUnsafe
  .field private class Calibration.ScannerCalibration m_csScannerCalibration
  .field private [Interop.LLCLib]LLCLib.FWLoaderMainClass m_csLLC
  .field private int32 m_iLLCCookie
  .method public hidebysig specialname instance void 
          add_m_evLLCError(class Calibration.LLCError 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Calibration.LLCError Calibration.Scanner::m_evLLCError
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  Calibration.LLCError
    IL_0012:  stfld      class Calibration.LLCError Calibration.Scanner::m_evLLCError
    IL_0017:  ret
  } // end of method Scanner::add_m_evLLCError

  .method public hidebysig specialname instance void 
          remove_m_evLLCError(class Calibration.LLCError 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Calibration.LLCError Calibration.Scanner::m_evLLCError
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  Calibration.LLCError
    IL_0012:  stfld      class Calibration.LLCError Calibration.Scanner::m_evLLCError
    IL_0017:  ret
  } // end of method Scanner::remove_m_evLLCError

  .method public hidebysig specialname instance void 
          add_m_evLLCHardware(class Calibration.LLCHardware 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Calibration.LLCHardware Calibration.Scanner::m_evLLCHardware
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  Calibration.LLCHardware
    IL_0012:  stfld      class Calibration.LLCHardware Calibration.Scanner::m_evLLCHardware
    IL_0017:  ret
  } // end of method Scanner::add_m_evLLCHardware

  .method public hidebysig specialname instance void 
          remove_m_evLLCHardware(class Calibration.LLCHardware 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Calibration.LLCHardware Calibration.Scanner::m_evLLCHardware
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  Calibration.LLCHardware
    IL_0012:  stfld      class Calibration.LLCHardware Calibration.Scanner::m_evLLCHardware
    IL_0017:  ret
  } // end of method Scanner::remove_m_evLLCHardware

  .method public hidebysig specialname instance void 
          add_m_evLLCProgress(class Calibration.LLCProgress 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Calibration.LLCProgress Calibration.Scanner::m_evLLCProgress
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  Calibration.LLCProgress
    IL_0012:  stfld      class Calibration.LLCProgress Calibration.Scanner::m_evLLCProgress
    IL_0017:  ret
  } // end of method Scanner::add_m_evLLCProgress

  .method public hidebysig specialname instance void 
          remove_m_evLLCProgress(class Calibration.LLCProgress 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Calibration.LLCProgress Calibration.Scanner::m_evLLCProgress
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  Calibration.LLCProgress
    IL_0012:  stfld      class Calibration.LLCProgress Calibration.Scanner::m_evLLCProgress
    IL_0017:  ret
  } // end of method Scanner::remove_m_evLLCProgress

  .method public hidebysig specialname instance void 
          add_m_evAcquire(class Calibration.Acquire 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Calibration.Acquire Calibration.Scanner::m_evAcquire
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  Calibration.Acquire
    IL_0012:  stfld      class Calibration.Acquire Calibration.Scanner::m_evAcquire
    IL_0017:  ret
  } // end of method Scanner::add_m_evAcquire

  .method public hidebysig specialname instance void 
          remove_m_evAcquire(class Calibration.Acquire 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Calibration.Acquire Calibration.Scanner::m_evAcquire
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  Calibration.Acquire
    IL_0012:  stfld      class Calibration.Acquire Calibration.Scanner::m_evAcquire
    IL_0017:  ret
  } // end of method Scanner::remove_m_evAcquire

  .method public hidebysig specialname instance class Calibration.ScannerUnsafe 
          get_CalibrationUnsafe() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      class Calibration.ScannerUnsafe Calibration.Scanner::m_csUnsafe
    IL_0006:  ret
  } // end of method Scanner::get_CalibrationUnsafe

  .method public hidebysig specialname instance class Calibration.ICalibrate 
          get_ICalibration() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      class Calibration.ScannerCalibration Calibration.Scanner::m_csScannerCalibration
    IL_0006:  ret
  } // end of method Scanner::get_ICalibration

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       77 (0x4d)
    .maxstack  4
    IL_0000:  ldarg.0
    IL_0001:  newobj     instance void Calibration.ScannerUnsafe::.ctor()
    IL_0006:  stfld      class Calibration.ScannerUnsafe Calibration.Scanner::m_csUnsafe
    IL_000b:  ldarg.0
    IL_000c:  ldnull
    IL_000d:  stfld      class Calibration.ScannerCalibration Calibration.Scanner::m_csScannerCalibration
    IL_0012:  ldarg.0
    IL_0013:  newobj     instance void [Interop.LLCLib]LLCLib.FWLoaderMainClass::.ctor()
    IL_0018:  stfld      [Interop.LLCLib]LLCLib.FWLoaderMainClass Calibration.Scanner::m_csLLC
    IL_001d:  ldarg.0
    IL_001e:  ldc.i4.0
    IL_001f:  stfld      int32 Calibration.Scanner::m_iLLCCookie
    IL_0024:  ldarg.0
    IL_0025:  call       instance void [Pakon]Pakon.Scanner::.ctor()
    IL_002a:  ldarg.0
    IL_002b:  ldfld      class Calibration.ScannerUnsafe Calibration.Scanner::m_csUnsafe
    IL_0030:  callvirt   instance void Calibration.ScannerUnsafe::Allocate()
    IL_0035:  ldarg.0
    IL_0036:  ldarg.0
    IL_0037:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass [Pakon]Pakon.Scanner::m_csTLX
    IL_003c:  ldarg.0
    IL_003d:  ldfld      class Calibration.ScannerUnsafe Calibration.Scanner::m_csUnsafe
    IL_0042:  newobj     instance void Calibration.ScannerCalibration::.ctor([Interop.TLXLib]TLXLib.TLXMainClass,
                                                                             class Calibration.ScannerUnsafe)
    IL_0047:  stfld      class Calibration.ScannerCalibration Calibration.Scanner::m_csScannerCalibration
    IL_004c:  ret
  } // end of method Scanner::.ctor

  .method public hidebysig instance void 
          LLCAwake(int32 lOperation,
                   int32 lStatus) cil managed
  {
    // Code size       224 (0xe0)
    .maxstack  3
    .locals ([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 V_0,
             bool V_1,
             [Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 V_2)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  box        [Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000
    IL_0008:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_000d:  ldarg.1
    IL_000e:  box        [mscorlib]System.Int32
    IL_0013:  call       bool [mscorlib]System.Enum::IsDefined([mscorlib]System.Type,
                                                               object)
    IL_0018:  stloc.1
    IL_0019:  ldloc.1
    IL_001a:  brfalse    IL_00d4

    IL_001f:  ldarg.1
    IL_0020:  stloc.0
    IL_0021:  ldloc.0
    IL_0022:  stloc.2
    IL_0023:  ldloc.2
    IL_0024:  switch     ( 
                          IL_00be,
                          IL_0092,
                          IL_00be,
                          IL_0092,
                          IL_00be,
                          IL_0092,
                          IL_00be,
                          IL_0092,
                          IL_00be,
                          IL_0092,
                          IL_00be,
                          IL_0092,
                          IL_00a8,
                          IL_00a8,
                          IL_00be,
                          IL_0092,
                          IL_00be,
                          IL_0092,
                          IL_00be,
                          IL_0092,
                          IL_00be,
                          IL_0092,
                          IL_00be,
                          IL_0092,
                          IL_00be,
                          IL_0092)
    IL_0091:  ret

    IL_0092:  ldarg.0
    IL_0093:  ldfld      class Calibration.LLCError Calibration.Scanner::m_evLLCError
    IL_0098:  brfalse.s  IL_00df

    IL_009a:  ldarg.0
    IL_009b:  ldfld      class Calibration.LLCError Calibration.Scanner::m_evLLCError
    IL_00a0:  ldloc.0
    IL_00a1:  ldarg.2
    IL_00a2:  callvirt   instance void Calibration.LLCError::Invoke([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000,
                                                                    int32)
    IL_00a7:  ret

    IL_00a8:  ldarg.0
    IL_00a9:  ldfld      class Calibration.LLCHardware Calibration.Scanner::m_evLLCHardware
    IL_00ae:  brfalse.s  IL_00df

    IL_00b0:  ldarg.0
    IL_00b1:  ldfld      class Calibration.LLCError Calibration.Scanner::m_evLLCError
    IL_00b6:  ldloc.0
    IL_00b7:  ldarg.2
    IL_00b8:  callvirt   instance void Calibration.LLCError::Invoke([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000,
                                                                    int32)
    IL_00bd:  ret

    IL_00be:  ldarg.0
    IL_00bf:  ldfld      class Calibration.LLCProgress Calibration.Scanner::m_evLLCProgress
    IL_00c4:  brfalse.s  IL_00df

    IL_00c6:  ldarg.0
    IL_00c7:  ldfld      class Calibration.LLCProgress Calibration.Scanner::m_evLLCProgress
    IL_00cc:  ldloc.0
    IL_00cd:  ldarg.2
    IL_00ce:  callvirt   instance void Calibration.LLCProgress::Invoke([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000,
                                                                       int32)
    IL_00d3:  ret

    IL_00d4:  ldstr      "Callback operation invalid"
    IL_00d9:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_00de:  throw

    IL_00df:  ret
  } // end of method Scanner::LLCAwake

  .method public hidebysig virtual instance bool 
          IsClosed() cil managed
  {
    // Code size       20 (0x14)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  call       instance bool [Pakon]Pakon.Scanner::IsClosed()
    IL_0006:  brfalse.s  IL_0012

    IL_0008:  ldarg.0
    IL_0009:  ldfld      int32 Calibration.Scanner::m_iLLCCookie
    IL_000e:  ldc.i4.0
    IL_000f:  ceq
    IL_0011:  ret

    IL_0012:  ldc.i4.0
    IL_0013:  ret
  } // end of method Scanner::IsClosed

  .method public hidebysig virtual instance void 
          Closing() cil managed
  {
    // Code size       18 (0x12)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  call       instance void [Pakon]Pakon.Scanner::Closing()
    IL_0006:  ldarg.0
    IL_0007:  ldfld      class Calibration.ScannerUnsafe Calibration.Scanner::m_csUnsafe
    IL_000c:  callvirt   instance void Calibration.ScannerUnsafe::Deallocate()
    IL_0011:  ret
  } // end of method Scanner::Closing

  .method public hidebysig instance void 
          InitializeLLC() cil managed
  {
    // Code size       35 (0x23)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      [Interop.LLCLib]LLCLib.FWLoaderMainClass Calibration.Scanner::m_csLLC
    IL_0007:  ldarg.0
    IL_0008:  newobj     instance void Calibration.CallBackClient::.ctor(class Calibration.Scanner)
    IL_000d:  callvirt   instance int32 [Interop.LLCLib]LLCLib.FWLoaderMainClass::CBAdvise([Interop.LLCLib]LLCLib.ICallBackClient)
    IL_0012:  stfld      int32 Calibration.Scanner::m_iLLCCookie
    IL_0017:  ldarg.0
    IL_0018:  ldfld      [Interop.LLCLib]LLCLib.FWLoaderMainClass Calibration.Scanner::m_csLLC
    IL_001d:  callvirt   instance void [Interop.LLCLib]LLCLib.FWLoaderMainClass::InitializeScanner()
    IL_0022:  ret
  } // end of method Scanner::InitializeLLC

  .method public hidebysig instance void 
          GetAndClearLastErrorLLC([Interop.LLCLib]LLCLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                                  string& strError,
                                  string& strErrorNumbers,
                                  [out] int32& iReturn) cil managed
  {
    // Code size       20 (0x14)
    .maxstack  5
    .locals ([Interop.LLCLib]LLCLib.INT_IID_000 V_0)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldarg.s    iReturn
    IL_0004:  ldarg.0
    IL_0005:  ldfld      [Interop.LLCLib]LLCLib.FWLoaderMainClass Calibration.Scanner::m_csLLC
    IL_000a:  ldloc.0
    IL_000b:  ldarg.2
    IL_000c:  ldarg.3
    IL_000d:  callvirt   instance int32 [Interop.LLCLib]LLCLib.FWLoaderMainClass::GetAndClearLastError(int32,
                                                                                                       string&,
                                                                                                       string&)
    IL_0012:  stind.i4
    IL_0013:  ret
  } // end of method Scanner::GetAndClearLastErrorLLC

  .method public hidebysig instance void 
          FindPersonality([Interop.LLCLib]LLCLib.SCANNER_MODEL_000& smModel,
                          valuetype Calibration.USB135& usb135,
                          valuetype Calibration.USB235& usb235,
                          valuetype Calibration.USB335& usb335,
                          bool& bVerified) cil managed
  {
    // Code size       184 (0xb8)
    .maxstack  4
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2,
             [Interop.LLCLib]LLCLib.PERSONALITY_000 V_3,
             [Interop.LLCLib]LLCLib.PERSONALITY_000 V_4)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldc.i4.0
    IL_0003:  stloc.1
    IL_0004:  ldc.i4.m1
    IL_0005:  stloc.2
    IL_0006:  ldc.i4.m1
    IL_0007:  stloc.3
    IL_0008:  ldarg.0
    IL_0009:  ldfld      [Interop.LLCLib]LLCLib.FWLoaderMainClass Calibration.Scanner::m_csLLC
    IL_000e:  ldloca.s   V_1
    IL_0010:  ldloca.s   V_2
    IL_0012:  ldloca.s   V_0
    IL_0014:  callvirt   instance void [Interop.LLCLib]LLCLib.FWLoaderMainClass::FindPersonality(int32&,
                                                                                                 int32&,
                                                                                                 int32&)
    IL_0019:  ldarg.1
    IL_001a:  ldind.i4
    IL_001b:  box        [Interop.LLCLib]LLCLib.SCANNER_MODEL_000
    IL_0020:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_0025:  ldloc.1
    IL_0026:  box        [mscorlib]System.Int32
    IL_002b:  call       bool [mscorlib]System.Enum::IsDefined([mscorlib]System.Type,
                                                               object)
    IL_0030:  brfalse.s  IL_0037

    IL_0032:  ldarg.1
    IL_0033:  ldloc.1
    IL_0034:  stind.i4
    IL_0035:  br.s       IL_0042

    IL_0037:  ldstr      "Scanner Model unknown"
    IL_003c:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0041:  throw

    IL_0042:  ldloc.3
    IL_0043:  box        [Interop.LLCLib]LLCLib.PERSONALITY_000
    IL_0048:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_004d:  ldloc.2
    IL_004e:  box        [mscorlib]System.Int32
    IL_0053:  call       bool [mscorlib]System.Enum::IsDefined([mscorlib]System.Type,
                                                               object)
    IL_0058:  brfalse.s  IL_005e

    IL_005a:  ldloc.2
    IL_005b:  stloc.3
    IL_005c:  br.s       IL_0069

    IL_005e:  ldstr      "Personality unknown"
    IL_0063:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0068:  throw

    IL_0069:  ldarg.2
    IL_006a:  ldc.i4.0
    IL_006b:  stind.i4
    IL_006c:  ldarg.3
    IL_006d:  ldc.i4.0
    IL_006e:  stind.i4
    IL_006f:  ldarg.s    usb335
    IL_0071:  ldc.i4.0
    IL_0072:  stind.i4
    IL_0073:  ldloc.3
    IL_0074:  stloc.s    V_4
    IL_0076:  ldloc.s    V_4
    IL_0078:  ldc.i4.m1
    IL_0079:  sub
    IL_007a:  switch     ( 
                          IL_00ac,
                          IL_009f,
                          IL_009a,
                          IL_0095,
                          IL_00a8)
    IL_0093:  br.s       IL_00ac

    IL_0095:  ldarg.2
    IL_0096:  ldc.i4.3
    IL_0097:  stind.i4
    IL_0098:  br.s       IL_00ac

    IL_009a:  ldarg.3
    IL_009b:  ldc.i4.2
    IL_009c:  stind.i4
    IL_009d:  br.s       IL_00ac

    IL_009f:  ldarg.1
    IL_00a0:  ldind.i4
    IL_00a1:  brtrue.s   IL_00ac

    IL_00a3:  ldarg.3
    IL_00a4:  ldc.i4.1
    IL_00a5:  stind.i4
    IL_00a6:  br.s       IL_00ac

    IL_00a8:  ldarg.s    usb335
    IL_00aa:  ldc.i4.4
    IL_00ab:  stind.i4
    IL_00ac:  ldarg.s    bVerified
    IL_00ae:  ldloc.0
    IL_00af:  ldc.i4.1
    IL_00b0:  beq.s      IL_00b5

    IL_00b2:  ldc.i4.0
    IL_00b3:  br.s       IL_00b6

    IL_00b5:  ldc.i4.1
    IL_00b6:  stind.i1
    IL_00b7:  ret
  } // end of method Scanner::FindPersonality

  .method public hidebysig instance void 
          FirmwareAssess(int32& iInitializeWarnings0,
                         int32& iInitializeWarnings1,
                         [Interop.TLXLib]TLXLib.SCANNER_TYPE_000& nScannerType,
                         [Pakon]Pakon.ScannerHW135& sh135,
                         [Pakon]Pakon.ScannerHW235& sh235,
                         [Pakon]Pakon.ScannerHW335& sh335,
                         int32& iScannerSerialNumber,
                         int32& iVersionHwUSB,
                         int32& iVersionHwLamp,
                         int32& iVersionHwCCD,
                         int32& iVersionHwDX,
                         int32& iVersionHwMotor,
                         int32& iVersionHwAps,
                         int32& iVersionSwUSB,
                         int32& iVersionSwLamp,
                         int32& iVersionSwCCD,
                         int32& iVersionSwDX,
                         int32& iVersionSwMotor,
                         int32& iVersionSwAps) cil managed
  {
    // Code size       62 (0x3e)
    .maxstack  18
    .locals (int32 V_0,
             int32 V_1)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldc.i4.0
    IL_0003:  stloc.1
    IL_0004:  ldarg.0
    IL_0005:  ldfld      [Interop.LLCLib]LLCLib.FWLoaderMainClass Calibration.Scanner::m_csLLC
    IL_000a:  ldarg.1
    IL_000b:  ldarg.2
    IL_000c:  ldloca.s   V_0
    IL_000e:  ldloca.s   V_1
    IL_0010:  ldarg.s    iScannerSerialNumber
    IL_0012:  ldarg.s    iVersionHwUSB
    IL_0014:  ldarg.s    iVersionHwLamp
    IL_0016:  ldarg.s    iVersionHwCCD
    IL_0018:  ldarg.s    iVersionHwDX
    IL_001a:  ldarg.s    iVersionHwMotor
    IL_001c:  ldarg.s    iVersionHwAps
    IL_001e:  ldarg.s    iVersionSwUSB
    IL_0020:  ldarg.s    iVersionSwLamp
    IL_0022:  ldarg.s    iVersionSwCCD
    IL_0024:  ldarg.s    iVersionSwDX
    IL_0026:  ldarg.s    iVersionSwMotor
    IL_0028:  ldarg.s    iVersionSwAps
    IL_002a:  callvirt   instance void [Interop.LLCLib]LLCLib.FWLoaderMainClass::FirmwareAssess(int32&,
                                                                                                int32&,
                                                                                                int32&,
                                                                                                int32&,
                                                                                                int32&,
                                                                                                int32&,
                                                                                                int32&,
                                                                                                int32&,
                                                                                                int32&,
                                                                                                int32&,
                                                                                                int32&,
                                                                                                int32&,
                                                                                                int32&,
                                                                                                int32&,
                                                                                                int32&,
                                                                                                int32&,
                                                                                                int32&)
    IL_002f:  ldloc.0
    IL_0030:  ldloc.1
    IL_0031:  ldarg.3
    IL_0032:  ldarg.s    sh135
    IL_0034:  ldarg.s    sh235
    IL_0036:  ldarg.s    sh335
    IL_0038:  call       void [Pakon]Pakon.Global::Convert(int32,
                                                           int32,
                                                           [Interop.TLXLib]TLXLib.SCANNER_TYPE_000&,
                                                           [Pakon]Pakon.ScannerHW135&,
                                                           [Pakon]Pakon.ScannerHW235&,
                                                           [Pakon]Pakon.ScannerHW335&)
    IL_003d:  ret
  } // end of method Scanner::FirmwareAssess

  .method public hidebysig instance void 
          SetPersonality(valuetype Calibration.USB135 usb135) cil managed
  {
    // Code size       25 (0x19)
    .maxstack  2
    .locals (valuetype Calibration.USB135 V_0)
    IL_0000:  ldarg.1
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  ldc.i4.3
    IL_0004:  bne.un.s   IL_000e

    IL_0006:  ldarg.0
    IL_0007:  ldc.i4.2
    IL_0008:  call       instance void Calibration.Scanner::SetPersonality([Interop.LLCLib]LLCLib.PERSONALITY_000)
    IL_000d:  ret

    IL_000e:  ldstr      "USB135 not valid"
    IL_0013:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0018:  throw
  } // end of method Scanner::SetPersonality

  .method public hidebysig instance void 
          SetPersonality(valuetype Calibration.USB235 usb235) cil managed
  {
    // Code size       47 (0x2f)
    .maxstack  2
    .locals (valuetype Calibration.USB235 V_0)
    IL_0000:  ldarg.1
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  ldc.i4.1
    IL_0004:  sub
    IL_0005:  switch     ( 
                          IL_0014,
                          IL_001c)
    IL_0012:  br.s       IL_0024

    IL_0014:  ldarg.0
    IL_0015:  ldc.i4.0
    IL_0016:  call       instance void Calibration.Scanner::SetPersonality([Interop.LLCLib]LLCLib.PERSONALITY_000)
    IL_001b:  ret

    IL_001c:  ldarg.0
    IL_001d:  ldc.i4.1
    IL_001e:  call       instance void Calibration.Scanner::SetPersonality([Interop.LLCLib]LLCLib.PERSONALITY_000)
    IL_0023:  ret

    IL_0024:  ldstr      "USB235 not valid"
    IL_0029:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_002e:  throw
  } // end of method Scanner::SetPersonality

  .method public hidebysig instance void 
          SetPersonality(valuetype Calibration.USB335 usb335) cil managed
  {
    // Code size       25 (0x19)
    .maxstack  2
    .locals (valuetype Calibration.USB335 V_0)
    IL_0000:  ldarg.1
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  ldc.i4.4
    IL_0004:  bne.un.s   IL_000e

    IL_0006:  ldarg.0
    IL_0007:  ldc.i4.3
    IL_0008:  call       instance void Calibration.Scanner::SetPersonality([Interop.LLCLib]LLCLib.PERSONALITY_000)
    IL_000d:  ret

    IL_000e:  ldstr      "USB335 not valid"
    IL_0013:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0018:  throw
  } // end of method Scanner::SetPersonality

  .method private hidebysig instance void 
          SetPersonality([Interop.LLCLib]LLCLib.PERSONALITY_000 iPersonality) cil managed
  {
    // Code size       13 (0xd)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.LLCLib]LLCLib.FWLoaderMainClass Calibration.Scanner::m_csLLC
    IL_0006:  ldarg.1
    IL_0007:  callvirt   instance void [Interop.LLCLib]LLCLib.FWLoaderMainClass::SetPersonality(int32)
    IL_000c:  ret
  } // end of method Scanner::SetPersonality

  .method public hidebysig instance void 
          LoadFirmware([Interop.LLCLib]LLCLib.PIC_000 iPicIndex,
                       string strFirmwareFileName) cil managed
  {
    // Code size       17 (0x11)
    .maxstack  4
    .locals (int32 V_0)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldarg.0
    IL_0003:  ldfld      [Interop.LLCLib]LLCLib.FWLoaderMainClass Calibration.Scanner::m_csLLC
    IL_0008:  ldarg.1
    IL_0009:  ldarg.2
    IL_000a:  ldloc.0
    IL_000b:  callvirt   instance void [Interop.LLCLib]LLCLib.FWLoaderMainClass::LoadFirmware(int32,
                                                                                              string,
                                                                                              int32)
    IL_0010:  ret
  } // end of method Scanner::LoadFirmware

  .method public hidebysig instance void 
          DriveMotorRun(int32 iSpeedPercent) cil managed
  {
    // Code size       13 (0xd)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.LLCLib]LLCLib.FWLoaderMainClass Calibration.Scanner::m_csLLC
    IL_0006:  ldarg.1
    IL_0007:  callvirt   instance void [Interop.LLCLib]LLCLib.FWLoaderMainClass::DriveMotorRun(int32)
    IL_000c:  ret
  } // end of method Scanner::DriveMotorRun

  .method public hidebysig instance void 
          MoveFilmGuides([Interop.LLCLib]LLCLib.FILM_FORMAT_000 iFilmFormat) cil managed
  {
    // Code size       58 (0x3a)
    .maxstack  2
    .locals (int32 V_0,
             [Interop.LLCLib]LLCLib.FILM_FORMAT_000 V_1)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldarg.1
    IL_0003:  stloc.1
    IL_0004:  ldloc.1
    IL_0005:  ldc.i4.m1
    IL_0006:  sub
    IL_0007:  switch     ( 
                          IL_0022,
                          IL_001a,
                          IL_001e)
    IL_0018:  br.s       IL_002d

    IL_001a:  ldc.i4.1
    IL_001b:  stloc.0
    IL_001c:  br.s       IL_002d

    IL_001e:  ldc.i4.0
    IL_001f:  stloc.0
    IL_0020:  br.s       IL_002d

    IL_0022:  ldstr      "Indeterminate not available"
    IL_0027:  newobj     instance void [mscorlib]System.NotImplementedException::.ctor(string)
    IL_002c:  throw

    IL_002d:  ldarg.0
    IL_002e:  ldfld      [Interop.LLCLib]LLCLib.FWLoaderMainClass Calibration.Scanner::m_csLLC
    IL_0033:  ldloc.0
    IL_0034:  callvirt   instance void [Interop.LLCLib]LLCLib.FWLoaderMainClass::MoveFilmGuides(int32)
    IL_0039:  ret
  } // end of method Scanner::MoveFilmGuides

  .method public hidebysig instance void 
          ReleasePressureRollers() cil managed
  {
    // Code size       12 (0xc)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.LLCLib]LLCLib.FWLoaderMainClass Calibration.Scanner::m_csLLC
    IL_0006:  callvirt   instance void [Interop.LLCLib]LLCLib.FWLoaderMainClass::ReleasePressureRollers()
    IL_000b:  ret
  } // end of method Scanner::ReleasePressureRollers

  .method public hidebysig instance void 
          EraseEEPROM() cil managed
  {
    // Code size       12 (0xc)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.LLCLib]LLCLib.FWLoaderMainClass Calibration.Scanner::m_csLLC
    IL_0006:  callvirt   instance void [Interop.LLCLib]LLCLib.FWLoaderMainClass::EraseEEPROM()
    IL_000b:  ret
  } // end of method Scanner::EraseEEPROM

  .method public hidebysig instance void 
          CBUnadviseLLC() cil managed
  {
    // Code size       33 (0x21)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32 Calibration.Scanner::m_iLLCCookie
    IL_0006:  brfalse.s  IL_0020

    IL_0008:  ldarg.0
    IL_0009:  ldfld      [Interop.LLCLib]LLCLib.FWLoaderMainClass Calibration.Scanner::m_csLLC
    IL_000e:  ldarg.0
    IL_000f:  ldfld      int32 Calibration.Scanner::m_iLLCCookie
    IL_0014:  callvirt   instance void [Interop.LLCLib]LLCLib.FWLoaderMainClass::CBUnadvise(int32)
    IL_0019:  ldarg.0
    IL_001a:  ldc.i4.0
    IL_001b:  stfld      int32 Calibration.Scanner::m_iLLCCookie
    IL_0020:  ret
  } // end of method Scanner::CBUnadviseLLC

  .method public hidebysig instance void 
          Acquire(bool bIRChannel) cil managed
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      class Calibration.ScannerUnsafe Calibration.Scanner::m_csUnsafe
    IL_0006:  ldarg.1
    IL_0007:  callvirt   instance void Calibration.ScannerUnsafe::Acquire(bool)
    IL_000c:  ldarg.0
    IL_000d:  ldfld      class Calibration.Acquire Calibration.Scanner::m_evAcquire
    IL_0012:  callvirt   instance void Calibration.Acquire::Invoke()
    IL_0017:  ret
  } // end of method Scanner::Acquire

  .event Calibration.LLCError m_evLLCError
  {
    .removeon instance void Calibration.Scanner::remove_m_evLLCError(class Calibration.LLCError)
    .addon instance void Calibration.Scanner::add_m_evLLCError(class Calibration.LLCError)
  } // end of event Scanner::m_evLLCError
  .event Calibration.LLCHardware m_evLLCHardware
  {
    .removeon instance void Calibration.Scanner::remove_m_evLLCHardware(class Calibration.LLCHardware)
    .addon instance void Calibration.Scanner::add_m_evLLCHardware(class Calibration.LLCHardware)
  } // end of event Scanner::m_evLLCHardware
  .event Calibration.LLCProgress m_evLLCProgress
  {
    .removeon instance void Calibration.Scanner::remove_m_evLLCProgress(class Calibration.LLCProgress)
    .addon instance void Calibration.Scanner::add_m_evLLCProgress(class Calibration.LLCProgress)
  } // end of event Scanner::m_evLLCProgress
  .event Calibration.Acquire m_evAcquire
  {
    .removeon instance void Calibration.Scanner::remove_m_evAcquire(class Calibration.Acquire)
    .addon instance void Calibration.Scanner::add_m_evAcquire(class Calibration.Acquire)
  } // end of event Scanner::m_evAcquire
  .property instance class Calibration.ScannerUnsafe
          CalibrationUnsafe()
  {
    .get instance class Calibration.ScannerUnsafe Calibration.Scanner::get_CalibrationUnsafe()
  } // end of property Scanner::CalibrationUnsafe
  .property instance class Calibration.ICalibrate
          ICalibration()
  {
    .get instance class Calibration.ICalibrate Calibration.Scanner::get_ICalibration()
  } // end of property Scanner::ICalibration
} // end of class Calibration.Scanner

.class public auto ansi sealed Calibration.ColorMatrix
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Calibration.ColorMatrix Negative = int32(0x00000000)
  .field public static literal valuetype Calibration.ColorMatrix Reversal = int32(0x00000001)
  .field public static literal valuetype Calibration.ColorMatrix Kodachrome = int32(0x00000002)
} // end of class Calibration.ColorMatrix

.class public auto ansi sealed Calibration.LightLevel
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Calibration.LightLevel OpenGate = int32(0x00000000)
  .field public static literal valuetype Calibration.LightLevel Nominal = int32(0x00000001)
} // end of class Calibration.LightLevel

.class interface public abstract auto ansi Calibration.ICalibrate
{
  .method public hidebysig newslot specialname abstract virtual 
          instance float64  get_AmbientTemperature() cil managed
  {
  } // end of method ICalibrate::get_AmbientTemperature

  .method public hidebysig newslot specialname abstract virtual 
          instance float64  get_LockedTemperature() cil managed
  {
  } // end of method ICalibrate::get_LockedTemperature

  .method public hidebysig newslot specialname abstract virtual 
          instance float64  get_VisibleTemperature() cil managed
  {
  } // end of method ICalibrate::get_VisibleTemperature

  .method public hidebysig newslot specialname abstract virtual 
          instance float64  get_IrTemperature() cil managed
  {
  } // end of method ICalibrate::get_IrTemperature

  .method public hidebysig newslot abstract virtual 
          instance void  Enable(string strLicense) cil managed
  {
  } // end of method ICalibrate::Enable

  .method public hidebysig newslot abstract virtual 
          instance void  Begin([Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                               [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                               bool bUseScratchRemoval) cil managed
  {
  } // end of method ICalibrate::Begin

  .method public hidebysig newslot abstract virtual 
          instance void  GetDpi([Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                int32& iHeightToCcd,
                                int32& iHeight,
                                int32& iOffset,
                                int32& iMotorAdjust,
                                int32& iMotorAdjust_Ir,
                                int32& iMotorAdjustDrag,
                                int32& iMotorAdjustDrag_Ir,
                                int32& iMotorSpeed,
                                int32& iMotorSpeed_Ir,
                                int32& iStepperLens,
                                int32& iStepperCCD,
                                int32& iStepperCCDAdjust) cil managed
  {
  } // end of method ICalibrate::GetDpi

  .method public hidebysig newslot abstract virtual 
          instance void  PutDpi([Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                bool bCalibrateGroup,
                                int32 iHeightToCcd,
                                int32 iHeight,
                                int32 iOffset,
                                int32 iMotorSpeed,
                                int32 iMotorSpeed_Ir,
                                int32 iStepperLens,
                                int32 iStepperCCD) cil managed
  {
  } // end of method ICalibrate::PutDpi

  .method public hidebysig newslot abstract virtual 
          instance void  SetLight([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iType,
                                  [Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                  [Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor,
                                  [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                  bool bIR,
                                  valuetype Calibration.LightLevel llSet,
                                  bool bCalibrateGroup) cil managed
  {
  } // end of method ICalibrate::SetLight

  .method public hidebysig newslot abstract virtual 
          instance void  GetColorMatrix3By4(valuetype Calibration.ColorMatrix iColorMatrix,
                                            float64& dfMatrixValue0_0,
                                            float64& dfMatrixValue0_1,
                                            float64& dfMatrixValue0_2,
                                            float64& dfMatrixValue0_3,
                                            float64& dfMatrixValue1_0,
                                            float64& dfMatrixValue1_1,
                                            float64& dfMatrixValue1_2,
                                            float64& dfMatrixValue1_3,
                                            float64& dfMatrixValue2_0,
                                            float64& dfMatrixValue2_1,
                                            float64& dfMatrixValue2_2,
                                            float64& dfMatrixValue2_3) cil managed
  {
  } // end of method ICalibrate::GetColorMatrix3By4

  .method public hidebysig newslot abstract virtual 
          instance void  PutColorMatrix3By4(valuetype Calibration.ColorMatrix iColorMatrix,
                                            bool bCalibrateGroup,
                                            float64 dfMatrixValue0_0,
                                            float64 dfMatrixValue0_1,
                                            float64 dfMatrixValue0_2,
                                            float64 dfMatrixValue0_3,
                                            float64 dfMatrixValue1_0,
                                            float64 dfMatrixValue1_1,
                                            float64 dfMatrixValue1_2,
                                            float64 dfMatrixValue1_3,
                                            float64 dfMatrixValue2_0,
                                            float64 dfMatrixValue2_1,
                                            float64 dfMatrixValue2_2,
                                            float64 dfMatrixValue2_3) cil managed
  {
  } // end of method ICalibrate::PutColorMatrix3By4

  .method public hidebysig newslot abstract virtual 
          instance void  GetColorMatrix3By10(valuetype Calibration.ColorMatrix iColorMatrix,
                                             float32& fMatrixValue0_0,
                                             float32& fMatrixValue0_1,
                                             float32& fMatrixValue0_2,
                                             float32& fMatrixValue0_3,
                                             float32& fMatrixValue0_4,
                                             float32& fMatrixValue0_5,
                                             float32& fMatrixValue0_6,
                                             float32& fMatrixValue0_7,
                                             float32& fMatrixValue0_8,
                                             float32& fMatrixValue0_9,
                                             float32& fMatrixValue1_0,
                                             float32& fMatrixValue1_1,
                                             float32& fMatrixValue1_2,
                                             float32& fMatrixValue1_3,
                                             float32& fMatrixValue1_4,
                                             float32& fMatrixValue1_5,
                                             float32& fMatrixValue1_6,
                                             float32& fMatrixValue1_7,
                                             float32& fMatrixValue1_8,
                                             float32& fMatrixValue1_9,
                                             float32& fMatrixValue2_0,
                                             float32& fMatrixValue2_1,
                                             float32& fMatrixValue2_2,
                                             float32& fMatrixValue2_3,
                                             float32& fMatrixValue2_4,
                                             float32& fMatrixValue2_5,
                                             float32& fMatrixValue2_6,
                                             float32& fMatrixValue2_7,
                                             float32& fMatrixValue2_8,
                                             float32& fMatrixValue2_9) cil managed
  {
  } // end of method ICalibrate::GetColorMatrix3By10

  .method public hidebysig newslot abstract virtual 
          instance void  PutColorMatrix3By10(valuetype Calibration.ColorMatrix iColorMatrix,
                                             bool bCalibrateGroup,
                                             float32 fMatrixValue0_0,
                                             float32 fMatrixValue0_1,
                                             float32 fMatrixValue0_2,
                                             float32 fMatrixValue0_3,
                                             float32 fMatrixValue0_4,
                                             float32 fMatrixValue0_5,
                                             float32 fMatrixValue0_6,
                                             float32 fMatrixValue0_7,
                                             float32 fMatrixValue0_8,
                                             float32 fMatrixValue0_9,
                                             float32 fMatrixValue1_0,
                                             float32 fMatrixValue1_1,
                                             float32 fMatrixValue1_2,
                                             float32 fMatrixValue1_3,
                                             float32 fMatrixValue1_4,
                                             float32 fMatrixValue1_5,
                                             float32 fMatrixValue1_6,
                                             float32 fMatrixValue1_7,
                                             float32 fMatrixValue1_8,
                                             float32 fMatrixValue1_9,
                                             float32 fMatrixValue2_0,
                                             float32 fMatrixValue2_1,
                                             float32 fMatrixValue2_2,
                                             float32 fMatrixValue2_3,
                                             float32 fMatrixValue2_4,
                                             float32 fMatrixValue2_5,
                                             float32 fMatrixValue2_6,
                                             float32 fMatrixValue2_7,
                                             float32 fMatrixValue2_8,
                                             float32 fMatrixValue2_9) cil managed
  {
  } // end of method ICalibrate::PutColorMatrix3By10

  .method public hidebysig newslot abstract virtual 
          instance void  PutIdentification(bool bCalibrateGroup,
                                           [Interop.TLXLib]TLXLib.SCANNER_VERSION_HW_000 iScannerVersionHw,
                                           [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iScannerType,
                                           int32 iScannerSerialNumber) cil managed
  {
  } // end of method ICalibrate::PutIdentification

  .method public hidebysig newslot abstract virtual 
          instance void  Acquire(int32 iScanLines,
                                 [Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                 [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                 [Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor,
                                 bool bUseScratchRemoval,
                                 [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iScannerType) cil managed
  {
  } // end of method ICalibrate::Acquire

  .method public hidebysig newslot abstract virtual 
          instance void  PutFilterWheelPosition([Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor) cil managed
  {
  } // end of method ICalibrate::PutFilterWheelPosition

  .method public hidebysig newslot abstract virtual 
          instance void  PutFilmPressureRollerPosition(bool bEngage) cil managed
  {
  } // end of method ICalibrate::PutFilmPressureRollerPosition

  .method public hidebysig newslot abstract virtual 
          instance void  AdvanceFilm(int32 iAdvanceMilliseconds,
                                     int32 iAdvanceSpeed) cil managed
  {
  } // end of method ICalibrate::AdvanceFilm

  .method public hidebysig newslot abstract virtual 
          instance void  Focus(bool bFindTiltTurns) cil managed
  {
  } // end of method ICalibrate::Focus

  .method public hidebysig newslot abstract virtual 
          instance void  FocusResults(int32& iCalibrateFocusErrorCenter,
                                      int32& iCalibrateFocusErrorLeft,
                                      int32& iCalibrateFocusErrorRight,
                                      int32& iCalibrateFocusOffsetCenter,
                                      int32& iCalibrateFocusOffsetLeft,
                                      int32& iCalibrateFocusOffsetRight,
                                      int32& iCalibrateTiltEighthTurns) cil managed
  {
  } // end of method ICalibrate::FocusResults

  .method public hidebysig newslot abstract virtual 
          instance void  PutEEProm() cil managed
  {
  } // end of method ICalibrate::PutEEProm

  .method public hidebysig newslot abstract virtual 
          instance void  End() cil managed
  {
  } // end of method ICalibrate::End

  .method public hidebysig newslot abstract virtual 
          instance void  StepperTest() cil managed
  {
  } // end of method ICalibrate::StepperTest

  .method public hidebysig newslot abstract virtual 
          instance void  StepperTestResults(int32& iCCDExpected,
                                            int32& iCCDActual,
                                            int32& iLensExpected,
                                            int32& iLensActual) cil managed
  {
  } // end of method ICalibrate::StepperTestResults

  .property instance float64 AmbientTemperature()
  {
    .get instance float64 Calibration.ICalibrate::get_AmbientTemperature()
  } // end of property ICalibrate::AmbientTemperature
  .property instance float64 LockedTemperature()
  {
    .get instance float64 Calibration.ICalibrate::get_LockedTemperature()
  } // end of property ICalibrate::LockedTemperature
  .property instance float64 VisibleTemperature()
  {
    .get instance float64 Calibration.ICalibrate::get_VisibleTemperature()
  } // end of property ICalibrate::VisibleTemperature
  .property instance float64 IrTemperature()
  {
    .get instance float64 Calibration.ICalibrate::get_IrTemperature()
  } // end of property ICalibrate::IrTemperature
} // end of class Calibration.ICalibrate

.class public auto ansi beforefieldinit Calibration.ScannerCalibration
       extends [mscorlib]System.Object
       implements Calibration.ICalibrate
{
  .field private [Interop.TLXLib]TLXLib.TLXMainClass m_csTLX
  .field private class Calibration.ScannerUnsafe m_csUnsafe
  .field private float64 m_dfAmbientTemperature
  .field private float64 m_dfLockedTemperature
  .field private float64 m_dfVisibleTemperature
  .field private float64 m_dfIrTemperature
  .method public hidebysig newslot specialname virtual final 
          instance float64  get_AmbientTemperature() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      float64 Calibration.ScannerCalibration::m_dfAmbientTemperature
    IL_0006:  ret
  } // end of method ScannerCalibration::get_AmbientTemperature

  .method public hidebysig newslot specialname virtual final 
          instance float64  get_LockedTemperature() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      float64 Calibration.ScannerCalibration::m_dfLockedTemperature
    IL_0006:  ret
  } // end of method ScannerCalibration::get_LockedTemperature

  .method public hidebysig newslot specialname virtual final 
          instance float64  get_VisibleTemperature() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      float64 Calibration.ScannerCalibration::m_dfVisibleTemperature
    IL_0006:  ret
  } // end of method ScannerCalibration::get_VisibleTemperature

  .method public hidebysig newslot specialname virtual final 
          instance float64  get_IrTemperature() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      float64 Calibration.ScannerCalibration::m_dfIrTemperature
    IL_0006:  ret
  } // end of method ScannerCalibration::get_IrTemperature

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor([Interop.TLXLib]TLXLib.TLXMainClass csTLX,
                               class Calibration.ScannerUnsafe csUnsafe) cil managed
  {
    // Code size       95 (0x5f)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  ldnull
    IL_0002:  stfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0007:  ldarg.0
    IL_0008:  ldnull
    IL_0009:  stfld      class Calibration.ScannerUnsafe Calibration.ScannerCalibration::m_csUnsafe
    IL_000e:  ldarg.0
    IL_000f:  ldc.r8     0.0
    IL_0018:  stfld      float64 Calibration.ScannerCalibration::m_dfAmbientTemperature
    IL_001d:  ldarg.0
    IL_001e:  ldc.r8     0.0
    IL_0027:  stfld      float64 Calibration.ScannerCalibration::m_dfLockedTemperature
    IL_002c:  ldarg.0
    IL_002d:  ldc.r8     0.0
    IL_0036:  stfld      float64 Calibration.ScannerCalibration::m_dfVisibleTemperature
    IL_003b:  ldarg.0
    IL_003c:  ldc.r8     0.0
    IL_0045:  stfld      float64 Calibration.ScannerCalibration::m_dfIrTemperature
    IL_004a:  ldarg.0
    IL_004b:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0050:  ldarg.0
    IL_0051:  ldarg.1
    IL_0052:  stfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0057:  ldarg.0
    IL_0058:  ldarg.2
    IL_0059:  stfld      class Calibration.ScannerUnsafe Calibration.ScannerCalibration::m_csUnsafe
    IL_005e:  ret
  } // end of method ScannerCalibration::.ctor

  .method public hidebysig newslot virtual final 
          instance void  Enable(string strLicense) cil managed
  {
    // Code size       13 (0xd)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationEnable(string)
    IL_000c:  ret
  } // end of method ScannerCalibration::Enable

  .method public hidebysig newslot virtual final 
          instance void  Begin([Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                               [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                               bool bUseScratchRemoval) cil managed
  {
    // Code size       35 (0x23)
    .maxstack  7
    .locals ([Interop.TLXLib]TLXLib.FILM_COLOR_000 V_0)
    IL_0000:  ldc.i4.1
    IL_0001:  stloc.0
    IL_0002:  ldarg.0
    IL_0003:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0008:  ldarg.1
    IL_0009:  ldloc.0
    IL_000a:  ldarg.2
    IL_000b:  ldarg.3
    IL_000c:  brtrue.s   IL_0011

    IL_000e:  ldc.i4.0
    IL_000f:  br.s       IL_0012

    IL_0011:  ldc.i4.1
    IL_0012:  ldarg.0
    IL_0013:  ldfld      class Calibration.ScannerUnsafe Calibration.ScannerCalibration::m_csUnsafe
    IL_0018:  callvirt   instance int32 Calibration.ScannerUnsafe::get_Pixels()
    IL_001d:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationBegin(int32,
                                                                                             int32,
                                                                                             int32,
                                                                                             int32,
                                                                                             int32)
    IL_0022:  ret
  } // end of method ScannerCalibration::Begin

  .method public hidebysig newslot virtual final 
          instance void  GetDpi([Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                int32& iHeightToCcd,
                                int32& iHeight,
                                int32& iOffset,
                                int32& iMotorAdjust,
                                int32& iMotorAdjust_Ir,
                                int32& iMotorAdjustDrag,
                                int32& iMotorAdjustDrag_Ir,
                                int32& iMotorSpeed,
                                int32& iMotorSpeed_Ir,
                                int32& iStepperLens,
                                int32& iStepperCCD,
                                int32& iStepperCCDAdjust) cil managed
  {
    // Code size       37 (0x25)
    .maxstack  15
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  ldarg.3
    IL_0009:  ldarg.s    iHeight
    IL_000b:  ldarg.s    iOffset
    IL_000d:  ldarg.s    iMotorAdjust
    IL_000f:  ldarg.s    iMotorAdjust_Ir
    IL_0011:  ldarg.s    iMotorAdjustDrag
    IL_0013:  ldarg.s    iMotorAdjustDrag_Ir
    IL_0015:  ldarg.s    iMotorSpeed
    IL_0017:  ldarg.s    iMotorSpeed_Ir
    IL_0019:  ldarg.s    iStepperLens
    IL_001b:  ldarg.s    iStepperCCD
    IL_001d:  ldarg.s    iStepperCCDAdjust
    IL_001f:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationGetDpi(int32,
                                                                                              int32,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              int32&)
    IL_0024:  ret
  } // end of method ScannerCalibration::GetDpi

  .method public hidebysig newslot virtual final 
          instance void  PutDpi([Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                bool bCalibrateGroup,
                                int32 iHeightToCcd,
                                int32 iHeight,
                                int32 iOffset,
                                int32 iMotorSpeed,
                                int32 iMotorSpeed_Ir,
                                int32 iStepperLens,
                                int32 iStepperCCD) cil managed
  {
    // Code size       35 (0x23)
    .maxstack  11
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  ldarg.3
    IL_0009:  brtrue.s   IL_000e

    IL_000b:  ldc.i4.0
    IL_000c:  br.s       IL_000f

    IL_000e:  ldc.i4.1
    IL_000f:  ldarg.s    iHeightToCcd
    IL_0011:  ldarg.s    iHeight
    IL_0013:  ldarg.s    iOffset
    IL_0015:  ldarg.s    iMotorSpeed
    IL_0017:  ldarg.s    iMotorSpeed_Ir
    IL_0019:  ldarg.s    iStepperLens
    IL_001b:  ldarg.s    iStepperCCD
    IL_001d:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationPutDpi(int32,
                                                                                              int32,
                                                                                              int32,
                                                                                              int32,
                                                                                              int32,
                                                                                              int32,
                                                                                              int32,
                                                                                              int32,
                                                                                              int32,
                                                                                              int32)
    IL_0022:  ret
  } // end of method ScannerCalibration::PutDpi

  .method public hidebysig newslot virtual final 
          instance void  SetLight([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iType,
                                  [Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                  [Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor,
                                  [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                  bool bIR,
                                  valuetype Calibration.LightLevel llSet,
                                  bool bCalibrateGroup) cil managed
  {
    // Code size       107 (0x6b)
    .maxstack  8
    .locals ([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_0)
    IL_0000:  ldarg.1
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  ldc.i4.7
    IL_0004:  sub
    IL_0005:  switch     ( 
                          IL_004e,
                          IL_004e)
    IL_0012:  ldloc.0
    IL_0013:  ldc.i4     0x546
    IL_0018:  sub
    IL_0019:  switch     ( 
                          IL_003c,
                          IL_003c)
    IL_0026:  ldloc.0
    IL_0027:  ldc.i4     0xd16
    IL_002c:  sub
    IL_002d:  switch     ( 
                          IL_003c,
                          IL_003c)
    IL_003a:  br.s       IL_0060

    IL_003c:  ldarg.0
    IL_003d:  ldarg.1
    IL_003e:  ldarg.2
    IL_003f:  ldarg.3
    IL_0040:  ldarg.s    iFilmFormat
    IL_0042:  ldarg.s    bIR
    IL_0044:  ldarg.s    llSet
    IL_0046:  ldarg.s    bCalibrateGroup
    IL_0048:  call       instance void Calibration.ScannerCalibration::SetLightLED([Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                                   [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                   [Interop.TLXLib]TLXLib.FILM_COLOR_000,
                                                                                   [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                   bool,
                                                                                   valuetype Calibration.LightLevel,
                                                                                   bool)
    IL_004d:  ret

    IL_004e:  ldarg.0
    IL_004f:  ldarg.1
    IL_0050:  ldarg.2
    IL_0051:  ldarg.3
    IL_0052:  ldarg.s    iFilmFormat
    IL_0054:  ldarg.s    bIR
    IL_0056:  ldarg.s    llSet
    IL_0058:  ldarg.s    bCalibrateGroup
    IL_005a:  call       instance void Calibration.ScannerCalibration::SetLightIncandescent([Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                                            [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                            [Interop.TLXLib]TLXLib.FILM_COLOR_000,
                                                                                            [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                            bool,
                                                                                            valuetype Calibration.LightLevel,
                                                                                            bool)
    IL_005f:  ret

    IL_0060:  ldstr      "Scanner Type Invalid"
    IL_0065:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_006a:  throw
  } // end of method ScannerCalibration::SetLight

  .method private hidebysig instance void 
          SetLightIncandescent([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iType,
                               [Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                               [Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor,
                               [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                               bool bIR,
                               valuetype Calibration.LightLevel llSet,
                               bool bCalibrateGroup) cil managed
  {
    // Code size       311 (0x137)
    .maxstack  23
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2,
             int32 V_3,
             int32 V_4,
             int32 V_5,
             int32 V_6,
             int32 V_7,
             int32 V_8,
             int32 V_9,
             int32 V_10,
             int32 V_11,
             int32 V_12,
             int32 V_13,
             int32 V_14,
             int32 V_15,
             int32 V_16,
             int32 V_17,
             int32 V_18,
             int32 V_19,
             int32 V_20,
             int32 V_21,
             int32 V_22,
             int32 V_23,
             int32 V_24,
             int32 V_25,
             int32 V_26,
             int32 V_27,
             int32 V_28)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldc.i4.0
    IL_0003:  stloc.1
    IL_0004:  ldc.i4.0
    IL_0005:  stloc.2
    IL_0006:  ldc.i4.0
    IL_0007:  stloc.3
    IL_0008:  ldc.i4.0
    IL_0009:  stloc.s    V_4
    IL_000b:  ldc.i4.0
    IL_000c:  stloc.s    V_5
    IL_000e:  ldc.i4.0
    IL_000f:  stloc.s    V_6
    IL_0011:  ldc.i4.0
    IL_0012:  stloc.s    V_7
    IL_0014:  ldc.i4.0
    IL_0015:  stloc.s    V_8
    IL_0017:  ldc.i4.0
    IL_0018:  stloc.s    V_9
    IL_001a:  ldc.i4.0
    IL_001b:  stloc.s    V_10
    IL_001d:  ldc.i4.0
    IL_001e:  stloc.s    V_11
    IL_0020:  ldc.i4.0
    IL_0021:  stloc.s    V_12
    IL_0023:  ldc.i4.0
    IL_0024:  stloc.s    V_13
    IL_0026:  ldc.i4.0
    IL_0027:  stloc.s    V_14
    IL_0029:  ldc.i4.0
    IL_002a:  stloc.s    V_15
    IL_002c:  ldc.i4.0
    IL_002d:  stloc.s    V_16
    IL_002f:  ldc.i4.0
    IL_0030:  stloc.s    V_17
    IL_0032:  ldarg.0
    IL_0033:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0038:  ldarg.2
    IL_0039:  ldarg.s    iFilmFormat
    IL_003b:  ldarg.3
    IL_003c:  ldloca.s   V_0
    IL_003e:  ldloca.s   V_1
    IL_0040:  ldloca.s   V_2
    IL_0042:  ldloca.s   V_3
    IL_0044:  ldloca.s   V_4
    IL_0046:  ldloca.s   V_5
    IL_0048:  ldloca.s   V_6
    IL_004a:  ldloca.s   V_7
    IL_004c:  ldloca.s   V_8
    IL_004e:  ldloca.s   V_9
    IL_0050:  ldloca.s   V_10
    IL_0052:  ldloca.s   V_11
    IL_0054:  ldloca.s   V_12
    IL_0056:  ldloca.s   V_13
    IL_0058:  ldloca.s   V_14
    IL_005a:  ldloca.s   V_15
    IL_005c:  ldloca.s   V_16
    IL_005e:  ldloca.s   V_17
    IL_0060:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationGetLightIncandescent(int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&)
    IL_0065:  ldarg.s    llSet
    IL_0067:  brtrue.s   IL_00b5

    IL_0069:  ldarg.1
    IL_006a:  ldarg.2
    IL_006b:  ldarg.3
    IL_006c:  ldarg.s    iFilmFormat
    IL_006e:  ldarg.s    bIR
    IL_0070:  ldloca.s   V_23
    IL_0072:  ldloca.s   V_24
    IL_0074:  ldloca.s   V_25
    IL_0076:  ldloca.s   V_26
    IL_0078:  ldloca.s   V_27
    IL_007a:  ldloca.s   V_28
    IL_007c:  ldloca.s   V_18
    IL_007e:  ldloca.s   V_19
    IL_0080:  ldloca.s   V_20
    IL_0082:  ldloca.s   V_21
    IL_0084:  ldloca.s   V_22
    IL_0086:  call       void Calibration.TLXRegistry::GetOpenGateIncandescent([Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                               [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                               [Interop.TLXLib]TLXLib.FILM_COLOR_000,
                                                                               [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                               bool,
                                                                               int32&,
                                                                               int32&,
                                                                               int32&,
                                                                               int32&,
                                                                               int32&,
                                                                               int32&,
                                                                               int32&,
                                                                               int32&,
                                                                               int32&,
                                                                               int32&,
                                                                               int32&)
    IL_008b:  ldloc.s    V_23
    IL_008d:  stloc.0
    IL_008e:  ldloc.s    V_24
    IL_0090:  stloc.1
    IL_0091:  ldloc.s    V_25
    IL_0093:  stloc.2
    IL_0094:  ldloc.s    V_26
    IL_0096:  stloc.3
    IL_0097:  ldloc.s    V_27
    IL_0099:  stloc.s    V_4
    IL_009b:  ldloc.s    V_28
    IL_009d:  stloc.s    V_5
    IL_009f:  ldloc.s    V_18
    IL_00a1:  stloc.s    V_6
    IL_00a3:  ldloc.s    V_19
    IL_00a5:  stloc.s    V_7
    IL_00a7:  ldloc.s    V_20
    IL_00a9:  stloc.s    V_8
    IL_00ab:  ldloc.s    V_21
    IL_00ad:  stloc.s    V_10
    IL_00af:  ldloc.s    V_22
    IL_00b1:  stloc.s    V_9
    IL_00b3:  br.s       IL_00ff

    IL_00b5:  ldarg.s    llSet
    IL_00b7:  ldc.i4.1
    IL_00b8:  bne.un.s   IL_00f4

    IL_00ba:  ldc.i4.0
    IL_00bb:  stloc.0
    IL_00bc:  ldc.i4.0
    IL_00bd:  stloc.1
    IL_00be:  ldc.i4.0
    IL_00bf:  stloc.2
    IL_00c0:  ldc.i4.0
    IL_00c1:  stloc.3
    IL_00c2:  ldc.i4.0
    IL_00c3:  stloc.s    V_4
    IL_00c5:  ldc.i4.0
    IL_00c6:  stloc.s    V_5
    IL_00c8:  ldc.i4     0x3e8
    IL_00cd:  stloc.s    V_6
    IL_00cf:  ldc.i4     0x3e8
    IL_00d4:  stloc.s    V_7
    IL_00d6:  ldc.i4     0x6a4
    IL_00db:  stloc.s    V_8
    IL_00dd:  ldc.i4     0x3e8
    IL_00e2:  stloc.s    V_11
    IL_00e4:  ldc.i4     0x3e8
    IL_00e9:  stloc.s    V_12
    IL_00eb:  ldc.i4     0x6a4
    IL_00f0:  stloc.s    V_13
    IL_00f2:  br.s       IL_00ff

    IL_00f4:  ldstr      "Light level not implemented"
    IL_00f9:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_00fe:  throw

    IL_00ff:  ldarg.0
    IL_0100:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0105:  ldarg.2
    IL_0106:  ldarg.s    iFilmFormat
    IL_0108:  ldarg.3
    IL_0109:  ldarg.s    bCalibrateGroup
    IL_010b:  brtrue.s   IL_0110

    IL_010d:  ldc.i4.0
    IL_010e:  br.s       IL_0111

    IL_0110:  ldc.i4.1
    IL_0111:  ldloc.0
    IL_0112:  ldloc.1
    IL_0113:  ldloc.2
    IL_0114:  ldloc.3
    IL_0115:  ldloc.s    V_4
    IL_0117:  ldloc.s    V_5
    IL_0119:  ldloc.s    V_6
    IL_011b:  ldloc.s    V_7
    IL_011d:  ldloc.s    V_8
    IL_011f:  ldloc.s    V_9
    IL_0121:  ldloc.s    V_10
    IL_0123:  ldloc.s    V_11
    IL_0125:  ldloc.s    V_12
    IL_0127:  ldloc.s    V_13
    IL_0129:  ldloc.s    V_14
    IL_012b:  ldloc.s    V_15
    IL_012d:  ldloc.s    V_16
    IL_012f:  ldloc.s    V_17
    IL_0131:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationPutLightIncandescent(int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32,
                                                                                                            int32)
    IL_0136:  ret
  } // end of method ScannerCalibration::SetLightIncandescent

  .method private hidebysig instance void 
          SetLightLED([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iType,
                      [Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                      [Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor,
                      [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                      bool bIR,
                      valuetype Calibration.LightLevel llSet,
                      bool bCalibrateGroup) cil managed
  {
    // Code size       411 (0x19b)
    .maxstack  25
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2,
             int32 V_3,
             int32 V_4,
             int32 V_5,
             int32 V_6,
             int32 V_7,
             int32 V_8,
             int32 V_9,
             float64 V_10,
             float64 V_11,
             float64 V_12,
             float64 V_13,
             int32 V_14,
             int32 V_15,
             float64 V_16,
             float64 V_17,
             float64 V_18,
             float64 V_19,
             float64 V_20,
             float64 V_21,
             float64 V_22,
             float64 V_23,
             int32 V_24,
             int32 V_25,
             int32 V_26,
             int32 V_27,
             int32 V_28,
             int32 V_29,
             int32 V_30,
             int32 V_31,
             int32 V_32,
             int32 V_33)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldc.i4.0
    IL_0003:  stloc.1
    IL_0004:  ldc.i4.0
    IL_0005:  stloc.2
    IL_0006:  ldc.i4.0
    IL_0007:  stloc.3
    IL_0008:  ldc.i4.0
    IL_0009:  stloc.s    V_4
    IL_000b:  ldc.i4.0
    IL_000c:  stloc.s    V_5
    IL_000e:  ldc.i4.0
    IL_000f:  stloc.s    V_6
    IL_0011:  ldc.i4.0
    IL_0012:  stloc.s    V_7
    IL_0014:  ldc.i4.0
    IL_0015:  stloc.s    V_8
    IL_0017:  ldc.i4.0
    IL_0018:  stloc.s    V_9
    IL_001a:  ldc.r8     0.0
    IL_0023:  stloc.s    V_10
    IL_0025:  ldc.r8     0.0
    IL_002e:  stloc.s    V_11
    IL_0030:  ldc.r8     0.0
    IL_0039:  stloc.s    V_12
    IL_003b:  ldc.r8     0.0
    IL_0044:  stloc.s    V_13
    IL_0046:  ldc.i4.0
    IL_0047:  stloc.s    V_14
    IL_0049:  ldc.i4.0
    IL_004a:  stloc.s    V_15
    IL_004c:  ldarg.0
    IL_004d:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0052:  ldarg.2
    IL_0053:  ldarg.s    iFilmFormat
    IL_0055:  ldarg.3
    IL_0056:  ldarg.s    bIR
    IL_0058:  brtrue.s   IL_005d

    IL_005a:  ldc.i4.0
    IL_005b:  br.s       IL_005e

    IL_005d:  ldc.i4.1
    IL_005e:  ldloca.s   V_0
    IL_0060:  ldloca.s   V_1
    IL_0062:  ldloca.s   V_2
    IL_0064:  ldloca.s   V_3
    IL_0066:  ldloca.s   V_4
    IL_0068:  ldloca.s   V_5
    IL_006a:  ldloca.s   V_6
    IL_006c:  ldloca.s   V_7
    IL_006e:  ldloca.s   V_8
    IL_0070:  ldloca.s   V_9
    IL_0072:  ldloca.s   V_10
    IL_0074:  ldloca.s   V_11
    IL_0076:  ldloca.s   V_12
    IL_0078:  ldloca.s   V_13
    IL_007a:  ldloca.s   V_14
    IL_007c:  ldloca.s   V_15
    IL_007e:  ldarg.0
    IL_007f:  ldflda     float64 Calibration.ScannerCalibration::m_dfAmbientTemperature
    IL_0084:  ldarg.0
    IL_0085:  ldflda     float64 Calibration.ScannerCalibration::m_dfLockedTemperature
    IL_008a:  ldarg.0
    IL_008b:  ldflda     float64 Calibration.ScannerCalibration::m_dfVisibleTemperature
    IL_0090:  ldarg.0
    IL_0091:  ldflda     float64 Calibration.ScannerCalibration::m_dfIrTemperature
    IL_0096:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationGetLightLED(int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   float64&,
                                                                                                   float64&,
                                                                                                   float64&,
                                                                                                   float64&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   float64&,
                                                                                                   float64&,
                                                                                                   float64&,
                                                                                                   float64&)
    IL_009b:  ldarg.s    llSet
    IL_009d:  brtrue.s   IL_0105

    IL_009f:  ldarg.1
    IL_00a0:  ldarg.2
    IL_00a1:  ldarg.3
    IL_00a2:  ldarg.s    iFilmFormat
    IL_00a4:  ldarg.s    bIR
    IL_00a6:  ldloca.s   V_24
    IL_00a8:  ldloca.s   V_25
    IL_00aa:  ldloca.s   V_26
    IL_00ac:  ldloca.s   V_27
    IL_00ae:  ldloca.s   V_28
    IL_00b0:  ldloca.s   V_29
    IL_00b2:  ldloca.s   V_30
    IL_00b4:  ldloca.s   V_31
    IL_00b6:  ldloca.s   V_32
    IL_00b8:  ldloca.s   V_33
    IL_00ba:  ldloca.s   V_16
    IL_00bc:  ldloca.s   V_17
    IL_00be:  ldloca.s   V_18
    IL_00c0:  ldloca.s   V_19
    IL_00c2:  ldloca.s   V_20
    IL_00c4:  ldloca.s   V_21
    IL_00c6:  ldloca.s   V_22
    IL_00c8:  ldloca.s   V_23
    IL_00ca:  call       void Calibration.TLXRegistry::GetOpenGateLED([Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                      [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                      [Interop.TLXLib]TLXLib.FILM_COLOR_000,
                                                                      [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                      bool,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      float64&,
                                                                      float64&,
                                                                      float64&,
                                                                      float64&,
                                                                      float64&,
                                                                      float64&,
                                                                      float64&,
                                                                      float64&)
    IL_00cf:  ldloc.s    V_24
    IL_00d1:  stloc.0
    IL_00d2:  ldloc.s    V_25
    IL_00d4:  stloc.1
    IL_00d5:  ldloc.s    V_26
    IL_00d7:  stloc.2
    IL_00d8:  ldloc.s    V_27
    IL_00da:  stloc.3
    IL_00db:  ldloc.s    V_28
    IL_00dd:  stloc.s    V_4
    IL_00df:  ldloc.s    V_29
    IL_00e1:  stloc.s    V_5
    IL_00e3:  ldloc.s    V_30
    IL_00e5:  stloc.s    V_6
    IL_00e7:  ldloc.s    V_31
    IL_00e9:  stloc.s    V_7
    IL_00eb:  ldloc.s    V_32
    IL_00ed:  stloc.s    V_8
    IL_00ef:  ldloc.s    V_33
    IL_00f1:  stloc.s    V_9
    IL_00f3:  ldloc.s    V_20
    IL_00f5:  stloc.s    V_10
    IL_00f7:  ldloc.s    V_21
    IL_00f9:  stloc.s    V_11
    IL_00fb:  ldloc.s    V_22
    IL_00fd:  stloc.s    V_12
    IL_00ff:  ldloc.s    V_23
    IL_0101:  stloc.s    V_13
    IL_0103:  br.s       IL_015f

    IL_0105:  ldarg.s    llSet
    IL_0107:  ldc.i4.1
    IL_0108:  bne.un.s   IL_0154

    IL_010a:  ldc.i4.0
    IL_010b:  stloc.0
    IL_010c:  ldc.i4.0
    IL_010d:  stloc.1
    IL_010e:  ldc.i4.0
    IL_010f:  stloc.2
    IL_0110:  ldc.i4.0
    IL_0111:  stloc.3
    IL_0112:  ldc.i4.0
    IL_0113:  stloc.s    V_4
    IL_0115:  ldc.i4.0
    IL_0116:  stloc.s    V_5
    IL_0118:  ldc.i4.4
    IL_0119:  stloc.s    V_6
    IL_011b:  ldc.i4.s   16
    IL_011d:  stloc.s    V_7
    IL_011f:  ldc.i4.s   16
    IL_0121:  stloc.s    V_8
    IL_0123:  ldc.i4.0
    IL_0124:  stloc.s    V_9
    IL_0126:  ldc.r8     0.57
    IL_012f:  stloc.s    V_10
    IL_0131:  ldc.r8     0.36
    IL_013a:  stloc.s    V_11
    IL_013c:  ldc.r8     0.06
    IL_0145:  stloc.s    V_12
    IL_0147:  ldc.r8     0.8
    IL_0150:  stloc.s    V_13
    IL_0152:  br.s       IL_015f

    IL_0154:  ldstr      "Light level not implemented"
    IL_0159:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_015e:  throw

    IL_015f:  ldarg.0
    IL_0160:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0165:  ldarg.2
    IL_0166:  ldarg.s    iFilmFormat
    IL_0168:  ldarg.3
    IL_0169:  ldarg.s    bIR
    IL_016b:  brtrue.s   IL_0170

    IL_016d:  ldc.i4.0
    IL_016e:  br.s       IL_0171

    IL_0170:  ldc.i4.1
    IL_0171:  ldarg.s    bCalibrateGroup
    IL_0173:  brtrue.s   IL_0178

    IL_0175:  ldc.i4.0
    IL_0176:  br.s       IL_0179

    IL_0178:  ldc.i4.1
    IL_0179:  ldloc.0
    IL_017a:  ldloc.1
    IL_017b:  ldloc.2
    IL_017c:  ldloc.3
    IL_017d:  ldloc.s    V_4
    IL_017f:  ldloc.s    V_5
    IL_0181:  ldloc.s    V_6
    IL_0183:  ldloc.s    V_7
    IL_0185:  ldloc.s    V_8
    IL_0187:  ldloc.s    V_9
    IL_0189:  ldloc.s    V_10
    IL_018b:  ldloc.s    V_11
    IL_018d:  ldloc.s    V_12
    IL_018f:  ldloc.s    V_13
    IL_0191:  ldloc.s    V_14
    IL_0193:  ldloc.s    V_15
    IL_0195:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationPutLightLED(int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   float64,
                                                                                                   float64,
                                                                                                   float64,
                                                                                                   float64,
                                                                                                   int32,
                                                                                                   int32)
    IL_019a:  ret
  } // end of method ScannerCalibration::SetLightLED

  .method public hidebysig newslot virtual final 
          instance void  GetColorMatrix3By4(valuetype Calibration.ColorMatrix iColorMatrix,
                                            float64& dfMatrixValue0_0,
                                            float64& dfMatrixValue0_1,
                                            float64& dfMatrixValue0_2,
                                            float64& dfMatrixValue0_3,
                                            float64& dfMatrixValue1_0,
                                            float64& dfMatrixValue1_1,
                                            float64& dfMatrixValue1_2,
                                            float64& dfMatrixValue1_3,
                                            float64& dfMatrixValue2_0,
                                            float64& dfMatrixValue2_1,
                                            float64& dfMatrixValue2_2,
                                            float64& dfMatrixValue2_3) cil managed
  {
    // Code size       35 (0x23)
    .maxstack  14
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  ldarg.3
    IL_0009:  ldarg.s    dfMatrixValue0_2
    IL_000b:  ldarg.s    dfMatrixValue0_3
    IL_000d:  ldarg.s    dfMatrixValue1_0
    IL_000f:  ldarg.s    dfMatrixValue1_1
    IL_0011:  ldarg.s    dfMatrixValue1_2
    IL_0013:  ldarg.s    dfMatrixValue1_3
    IL_0015:  ldarg.s    dfMatrixValue2_0
    IL_0017:  ldarg.s    dfMatrixValue2_1
    IL_0019:  ldarg.s    dfMatrixValue2_2
    IL_001b:  ldarg.s    dfMatrixValue2_3
    IL_001d:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationGetColorMatrix3By4(int32,
                                                                                                          float64&,
                                                                                                          float64&,
                                                                                                          float64&,
                                                                                                          float64&,
                                                                                                          float64&,
                                                                                                          float64&,
                                                                                                          float64&,
                                                                                                          float64&,
                                                                                                          float64&,
                                                                                                          float64&,
                                                                                                          float64&,
                                                                                                          float64&)
    IL_0022:  ret
  } // end of method ScannerCalibration::GetColorMatrix3By4

  .method public hidebysig newslot virtual final 
          instance void  PutColorMatrix3By4(valuetype Calibration.ColorMatrix iColorMatrix,
                                            bool bCalibrateGroup,
                                            float64 dfMatrixValue0_0,
                                            float64 dfMatrixValue0_1,
                                            float64 dfMatrixValue0_2,
                                            float64 dfMatrixValue0_3,
                                            float64 dfMatrixValue1_0,
                                            float64 dfMatrixValue1_1,
                                            float64 dfMatrixValue1_2,
                                            float64 dfMatrixValue1_3,
                                            float64 dfMatrixValue2_0,
                                            float64 dfMatrixValue2_1,
                                            float64 dfMatrixValue2_2,
                                            float64 dfMatrixValue2_3) cil managed
  {
    // Code size       43 (0x2b)
    .maxstack  15
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  brtrue.s   IL_000d

    IL_000a:  ldc.i4.0
    IL_000b:  br.s       IL_000e

    IL_000d:  ldc.i4.1
    IL_000e:  ldarg.3
    IL_000f:  ldarg.s    dfMatrixValue0_1
    IL_0011:  ldarg.s    dfMatrixValue0_2
    IL_0013:  ldarg.s    dfMatrixValue0_3
    IL_0015:  ldarg.s    dfMatrixValue1_0
    IL_0017:  ldarg.s    dfMatrixValue1_1
    IL_0019:  ldarg.s    dfMatrixValue1_2
    IL_001b:  ldarg.s    dfMatrixValue1_3
    IL_001d:  ldarg.s    dfMatrixValue2_0
    IL_001f:  ldarg.s    dfMatrixValue2_1
    IL_0021:  ldarg.s    dfMatrixValue2_2
    IL_0023:  ldarg.s    dfMatrixValue2_3
    IL_0025:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationPutColorMatrix3By4(int32,
                                                                                                          int32,
                                                                                                          float64,
                                                                                                          float64,
                                                                                                          float64,
                                                                                                          float64,
                                                                                                          float64,
                                                                                                          float64,
                                                                                                          float64,
                                                                                                          float64,
                                                                                                          float64,
                                                                                                          float64,
                                                                                                          float64,
                                                                                                          float64)
    IL_002a:  ret
  } // end of method ScannerCalibration::PutColorMatrix3By4

  .method public hidebysig newslot virtual final 
          instance void  GetColorMatrix3By10(valuetype Calibration.ColorMatrix iColorMatrix,
                                             float32& fMatrixValue0_0,
                                             float32& fMatrixValue0_1,
                                             float32& fMatrixValue0_2,
                                             float32& fMatrixValue0_3,
                                             float32& fMatrixValue0_4,
                                             float32& fMatrixValue0_5,
                                             float32& fMatrixValue0_6,
                                             float32& fMatrixValue0_7,
                                             float32& fMatrixValue0_8,
                                             float32& fMatrixValue0_9,
                                             float32& fMatrixValue1_0,
                                             float32& fMatrixValue1_1,
                                             float32& fMatrixValue1_2,
                                             float32& fMatrixValue1_3,
                                             float32& fMatrixValue1_4,
                                             float32& fMatrixValue1_5,
                                             float32& fMatrixValue1_6,
                                             float32& fMatrixValue1_7,
                                             float32& fMatrixValue1_8,
                                             float32& fMatrixValue1_9,
                                             float32& fMatrixValue2_0,
                                             float32& fMatrixValue2_1,
                                             float32& fMatrixValue2_2,
                                             float32& fMatrixValue2_3,
                                             float32& fMatrixValue2_4,
                                             float32& fMatrixValue2_5,
                                             float32& fMatrixValue2_6,
                                             float32& fMatrixValue2_7,
                                             float32& fMatrixValue2_8,
                                             float32& fMatrixValue2_9) cil managed
  {
    // Code size       73 (0x49)
    .maxstack  32
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldc.i4.1
    IL_0008:  add
    IL_0009:  ldarg.2
    IL_000a:  ldarg.3
    IL_000b:  ldarg.s    fMatrixValue0_2
    IL_000d:  ldarg.s    fMatrixValue0_3
    IL_000f:  ldarg.s    fMatrixValue0_4
    IL_0011:  ldarg.s    fMatrixValue0_5
    IL_0013:  ldarg.s    fMatrixValue0_6
    IL_0015:  ldarg.s    fMatrixValue0_7
    IL_0017:  ldarg.s    fMatrixValue0_8
    IL_0019:  ldarg.s    fMatrixValue0_9
    IL_001b:  ldarg.s    fMatrixValue1_0
    IL_001d:  ldarg.s    fMatrixValue1_1
    IL_001f:  ldarg.s    fMatrixValue1_2
    IL_0021:  ldarg.s    fMatrixValue1_3
    IL_0023:  ldarg.s    fMatrixValue1_4
    IL_0025:  ldarg.s    fMatrixValue1_5
    IL_0027:  ldarg.s    fMatrixValue1_6
    IL_0029:  ldarg.s    fMatrixValue1_7
    IL_002b:  ldarg.s    fMatrixValue1_8
    IL_002d:  ldarg.s    fMatrixValue1_9
    IL_002f:  ldarg.s    fMatrixValue2_0
    IL_0031:  ldarg.s    fMatrixValue2_1
    IL_0033:  ldarg.s    fMatrixValue2_2
    IL_0035:  ldarg.s    fMatrixValue2_3
    IL_0037:  ldarg.s    fMatrixValue2_4
    IL_0039:  ldarg.s    fMatrixValue2_5
    IL_003b:  ldarg.s    fMatrixValue2_6
    IL_003d:  ldarg.s    fMatrixValue2_7
    IL_003f:  ldarg.s    fMatrixValue2_8
    IL_0041:  ldarg.s    fMatrixValue2_9
    IL_0043:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationGetColorMatrix3By10(int32,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&,
                                                                                                           float32&)
    IL_0048:  ret
  } // end of method ScannerCalibration::GetColorMatrix3By10

  .method public hidebysig newslot virtual final 
          instance void  PutColorMatrix3By10(valuetype Calibration.ColorMatrix iColorMatrix,
                                             bool bCalibrateGroup,
                                             float32 fMatrixValue0_0,
                                             float32 fMatrixValue0_1,
                                             float32 fMatrixValue0_2,
                                             float32 fMatrixValue0_3,
                                             float32 fMatrixValue0_4,
                                             float32 fMatrixValue0_5,
                                             float32 fMatrixValue0_6,
                                             float32 fMatrixValue0_7,
                                             float32 fMatrixValue0_8,
                                             float32 fMatrixValue0_9,
                                             float32 fMatrixValue1_0,
                                             float32 fMatrixValue1_1,
                                             float32 fMatrixValue1_2,
                                             float32 fMatrixValue1_3,
                                             float32 fMatrixValue1_4,
                                             float32 fMatrixValue1_5,
                                             float32 fMatrixValue1_6,
                                             float32 fMatrixValue1_7,
                                             float32 fMatrixValue1_8,
                                             float32 fMatrixValue1_9,
                                             float32 fMatrixValue2_0,
                                             float32 fMatrixValue2_1,
                                             float32 fMatrixValue2_2,
                                             float32 fMatrixValue2_3,
                                             float32 fMatrixValue2_4,
                                             float32 fMatrixValue2_5,
                                             float32 fMatrixValue2_6,
                                             float32 fMatrixValue2_7,
                                             float32 fMatrixValue2_8,
                                             float32 fMatrixValue2_9) cil managed
  {
    // Code size       79 (0x4f)
    .maxstack  33
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  brtrue.s   IL_000d

    IL_000a:  ldc.i4.0
    IL_000b:  br.s       IL_000e

    IL_000d:  ldc.i4.1
    IL_000e:  ldarg.3
    IL_000f:  ldarg.s    fMatrixValue0_1
    IL_0011:  ldarg.s    fMatrixValue0_2
    IL_0013:  ldarg.s    fMatrixValue0_3
    IL_0015:  ldarg.s    fMatrixValue0_4
    IL_0017:  ldarg.s    fMatrixValue0_5
    IL_0019:  ldarg.s    fMatrixValue0_6
    IL_001b:  ldarg.s    fMatrixValue0_7
    IL_001d:  ldarg.s    fMatrixValue0_8
    IL_001f:  ldarg.s    fMatrixValue0_9
    IL_0021:  ldarg.s    fMatrixValue1_0
    IL_0023:  ldarg.s    fMatrixValue1_1
    IL_0025:  ldarg.s    fMatrixValue1_2
    IL_0027:  ldarg.s    fMatrixValue1_3
    IL_0029:  ldarg.s    fMatrixValue1_4
    IL_002b:  ldarg.s    fMatrixValue1_5
    IL_002d:  ldarg.s    fMatrixValue1_6
    IL_002f:  ldarg.s    fMatrixValue1_7
    IL_0031:  ldarg.s    fMatrixValue1_8
    IL_0033:  ldarg.s    fMatrixValue1_9
    IL_0035:  ldarg.s    fMatrixValue2_0
    IL_0037:  ldarg.s    fMatrixValue2_1
    IL_0039:  ldarg.s    fMatrixValue2_2
    IL_003b:  ldarg.s    fMatrixValue2_3
    IL_003d:  ldarg.s    fMatrixValue2_4
    IL_003f:  ldarg.s    fMatrixValue2_5
    IL_0041:  ldarg.s    fMatrixValue2_6
    IL_0043:  ldarg.s    fMatrixValue2_7
    IL_0045:  ldarg.s    fMatrixValue2_8
    IL_0047:  ldarg.s    fMatrixValue2_9
    IL_0049:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationPutColorMatrix3By10(int32,
                                                                                                           int32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32,
                                                                                                           float32)
    IL_004e:  ret
  } // end of method ScannerCalibration::PutColorMatrix3By10

  .method public hidebysig newslot virtual final 
          instance void  PutIdentification(bool bCalibrateGroup,
                                           [Interop.TLXLib]TLXLib.SCANNER_VERSION_HW_000 iScannerVersionHw,
                                           [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iScannerType,
                                           int32 iScannerSerialNumber) cil managed
  {
    // Code size       23 (0x17)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  brtrue.s   IL_000c

    IL_0009:  ldc.i4.0
    IL_000a:  br.s       IL_000d

    IL_000c:  ldc.i4.1
    IL_000d:  ldarg.2
    IL_000e:  ldarg.3
    IL_000f:  ldarg.s    iScannerSerialNumber
    IL_0011:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationPutIdentification(int32,
                                                                                                         int32,
                                                                                                         int32,
                                                                                                         int32)
    IL_0016:  ret
  } // end of method ScannerCalibration::PutIdentification

  .method public hidebysig newslot virtual final 
          instance void  Acquire(int32 iScanLines,
                                 [Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                 [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                 [Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor,
                                 bool bUseScratchRemoval,
                                 [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iScannerType) cil managed
  {
    // Code size       225 (0xe1)
    .maxstack  25
    .locals (int32 V_0,
             float64 V_1)
    IL_0000:  ldarg.s    iScannerType
    IL_0002:  ldc.i4     0x546
    IL_0007:  beq.s      IL_0012

    IL_0009:  ldarg.s    iScannerType
    IL_000b:  ldc.i4     0x547
    IL_0010:  bne.un.s   IL_0030

    IL_0012:  ldarg.2
    IL_0013:  ldc.i4.1
    IL_0014:  bne.un.s   IL_0030

    IL_0016:  ldarg.0
    IL_0017:  ldfld      class Calibration.ScannerUnsafe Calibration.ScannerCalibration::m_csUnsafe
    IL_001c:  ldc.i4.1
    IL_001d:  callvirt   instance void Calibration.ScannerUnsafe::set_ThreeQuarters(bool)
    IL_0022:  ldarg.0
    IL_0023:  ldfld      class Calibration.ScannerUnsafe Calibration.ScannerCalibration::m_csUnsafe
    IL_0028:  ldc.i4.1
    IL_0029:  callvirt   instance void Calibration.ScannerUnsafe::set_Binning(bool)
    IL_002e:  br.s       IL_0065

    IL_0030:  ldarg.2
    IL_0031:  brtrue.s   IL_004d

    IL_0033:  ldarg.0
    IL_0034:  ldfld      class Calibration.ScannerUnsafe Calibration.ScannerCalibration::m_csUnsafe
    IL_0039:  ldc.i4.0
    IL_003a:  callvirt   instance void Calibration.ScannerUnsafe::set_ThreeQuarters(bool)
    IL_003f:  ldarg.0
    IL_0040:  ldfld      class Calibration.ScannerUnsafe Calibration.ScannerCalibration::m_csUnsafe
    IL_0045:  ldc.i4.1
    IL_0046:  callvirt   instance void Calibration.ScannerUnsafe::set_Binning(bool)
    IL_004b:  br.s       IL_0065

    IL_004d:  ldarg.0
    IL_004e:  ldfld      class Calibration.ScannerUnsafe Calibration.ScannerCalibration::m_csUnsafe
    IL_0053:  ldc.i4.0
    IL_0054:  callvirt   instance void Calibration.ScannerUnsafe::set_ThreeQuarters(bool)
    IL_0059:  ldarg.0
    IL_005a:  ldfld      class Calibration.ScannerUnsafe Calibration.ScannerCalibration::m_csUnsafe
    IL_005f:  ldc.i4.0
    IL_0060:  callvirt   instance void Calibration.ScannerUnsafe::set_Binning(bool)
    IL_0065:  ldarg.0
    IL_0066:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_006b:  ldarg.1
    IL_006c:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationAcquire(int32)
    IL_0071:  ldc.i4     0xfa
    IL_0076:  call       void [mscorlib]System.Threading.Thread::Sleep(int32)
    IL_007b:  ldarg.s    iScannerType
    IL_007d:  ldc.i4.7
    IL_007e:  beq.s      IL_00e0

    IL_0080:  ldarg.s    iScannerType
    IL_0082:  ldc.i4.8
    IL_0083:  beq.s      IL_00e0

    IL_0085:  ldc.i4.0
    IL_0086:  stloc.0
    IL_0087:  ldc.r8     0.0
    IL_0090:  stloc.1
    IL_0091:  ldarg.0
    IL_0092:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0097:  ldarg.2
    IL_0098:  ldarg.3
    IL_0099:  ldarg.s    iFilmColor
    IL_009b:  ldarg.s    bUseScratchRemoval
    IL_009d:  brtrue.s   IL_00a2

    IL_009f:  ldc.i4.0
    IL_00a0:  br.s       IL_00a3

    IL_00a2:  ldc.i4.1
    IL_00a3:  ldloca.s   V_0
    IL_00a5:  ldloca.s   V_0
    IL_00a7:  ldloca.s   V_0
    IL_00a9:  ldloca.s   V_0
    IL_00ab:  ldloca.s   V_0
    IL_00ad:  ldloca.s   V_0
    IL_00af:  ldloca.s   V_0
    IL_00b1:  ldloca.s   V_0
    IL_00b3:  ldloca.s   V_0
    IL_00b5:  ldloca.s   V_0
    IL_00b7:  ldloca.s   V_1
    IL_00b9:  ldloca.s   V_1
    IL_00bb:  ldloca.s   V_1
    IL_00bd:  ldloca.s   V_1
    IL_00bf:  ldloca.s   V_0
    IL_00c1:  ldloca.s   V_0
    IL_00c3:  ldarg.0
    IL_00c4:  ldflda     float64 Calibration.ScannerCalibration::m_dfAmbientTemperature
    IL_00c9:  ldarg.0
    IL_00ca:  ldflda     float64 Calibration.ScannerCalibration::m_dfLockedTemperature
    IL_00cf:  ldarg.0
    IL_00d0:  ldflda     float64 Calibration.ScannerCalibration::m_dfVisibleTemperature
    IL_00d5:  ldarg.0
    IL_00d6:  ldflda     float64 Calibration.ScannerCalibration::m_dfIrTemperature
    IL_00db:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationGetLightLED(int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   float64&,
                                                                                                   float64&,
                                                                                                   float64&,
                                                                                                   float64&,
                                                                                                   int32&,
                                                                                                   int32&,
                                                                                                   float64&,
                                                                                                   float64&,
                                                                                                   float64&,
                                                                                                   float64&)
    IL_00e0:  ret
  } // end of method ScannerCalibration::Acquire

  .method public hidebysig newslot virtual final 
          instance void  PutFilterWheelPosition([Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor) cil managed
  {
    // Code size       13 (0xd)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationPutFilterWheelPosition(int32)
    IL_000c:  ret
  } // end of method ScannerCalibration::PutFilterWheelPosition

  .method public hidebysig newslot virtual final 
          instance void  PutFilmPressureRollerPosition(bool bEngage) cil managed
  {
    // Code size       19 (0x13)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  brtrue.s   IL_000c

    IL_0009:  ldc.i4.0
    IL_000a:  br.s       IL_000d

    IL_000c:  ldc.i4.1
    IL_000d:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationPutFilmPressureRollerPosition(int32)
    IL_0012:  ret
  } // end of method ScannerCalibration::PutFilmPressureRollerPosition

  .method public hidebysig newslot virtual final 
          instance void  AdvanceFilm(int32 iAdvanceMilliseconds,
                                     int32 iAdvanceSpeed) cil managed
  {
    // Code size       14 (0xe)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationAdvanceFilm(int32,
                                                                                                   int32)
    IL_000d:  ret
  } // end of method ScannerCalibration::AdvanceFilm

  .method public hidebysig newslot virtual final 
          instance void  Focus(bool bFindTiltTurns) cil managed
  {
    // Code size       19 (0x13)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  brtrue.s   IL_000c

    IL_0009:  ldc.i4.0
    IL_000a:  br.s       IL_000d

    IL_000c:  ldc.i4.1
    IL_000d:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationFocus(int32)
    IL_0012:  ret
  } // end of method ScannerCalibration::Focus

  .method public hidebysig newslot virtual final 
          instance void  FocusResults(int32& iCalibrateFocusErrorCenter,
                                      int32& iCalibrateFocusErrorLeft,
                                      int32& iCalibrateFocusErrorRight,
                                      int32& iCalibrateFocusOffsetCenter,
                                      int32& iCalibrateFocusOffsetLeft,
                                      int32& iCalibrateFocusOffsetRight,
                                      int32& iCalibrateTiltEighthTurns) cil managed
  {
    // Code size       23 (0x17)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  ldarg.3
    IL_0009:  ldarg.s    iCalibrateFocusOffsetCenter
    IL_000b:  ldarg.s    iCalibrateFocusOffsetLeft
    IL_000d:  ldarg.s    iCalibrateFocusOffsetRight
    IL_000f:  ldarg.s    iCalibrateTiltEighthTurns
    IL_0011:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationFocusResults(int32&,
                                                                                                    int32&,
                                                                                                    int32&,
                                                                                                    int32&,
                                                                                                    int32&,
                                                                                                    int32&,
                                                                                                    int32&)
    IL_0016:  ret
  } // end of method ScannerCalibration::FocusResults

  .method public hidebysig newslot virtual final 
          instance void  PutEEProm() cil managed
  {
    // Code size       12 (0xc)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationPutEEProm()
    IL_000b:  ret
  } // end of method ScannerCalibration::PutEEProm

  .method public hidebysig newslot virtual final 
          instance void  End() cil managed
  {
    // Code size       12 (0xc)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationEnd()
    IL_000b:  ret
  } // end of method ScannerCalibration::End

  .method public hidebysig newslot virtual final 
          instance void  StepperTest() cil managed
  {
    // Code size       12 (0xc)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationStepperTest()
    IL_000b:  ret
  } // end of method ScannerCalibration::StepperTest

  .method public hidebysig newslot virtual final 
          instance void  StepperTestResults(int32& iCCDExpected,
                                            int32& iCCDActual,
                                            int32& iLensExpected,
                                            int32& iLensActual) cil managed
  {
    // Code size       17 (0x11)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Calibration.ScannerCalibration::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  ldarg.3
    IL_0009:  ldarg.s    iLensActual
    IL_000b:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CalibrationStepperTestResults(int32&,
                                                                                                          int32&,
                                                                                                          int32&,
                                                                                                          int32&)
    IL_0010:  ret
  } // end of method ScannerCalibration::StepperTestResults

  .property instance float64 AmbientTemperature()
  {
    .get instance float64 Calibration.ScannerCalibration::get_AmbientTemperature()
  } // end of property ScannerCalibration::AmbientTemperature
  .property instance float64 LockedTemperature()
  {
    .get instance float64 Calibration.ScannerCalibration::get_LockedTemperature()
  } // end of property ScannerCalibration::LockedTemperature
  .property instance float64 VisibleTemperature()
  {
    .get instance float64 Calibration.ScannerCalibration::get_VisibleTemperature()
  } // end of property ScannerCalibration::VisibleTemperature
  .property instance float64 IrTemperature()
  {
    .get instance float64 Calibration.ScannerCalibration::get_IrTemperature()
  } // end of property ScannerCalibration::IrTemperature
} // end of class Calibration.ScannerCalibration

.class public auto ansi beforefieldinit Calibration.ScannerSettings
       extends [Pakon]Pakon.ScannerSettings
{
  .custom instance void [mscorlib]System.Reflection.DefaultMemberAttribute::.ctor(string) = ( 01 00 04 49 74 65 6D 00 00 )                      // ...Item..
  .field private class Calibration.ScannerSettingsFirmware m_csFirmwareSettings
  .field private [Pakon]Pakon.IntBits m_ibEEPromInvalid
  .field private [Pakon]Pakon.IntBits m_ibColorNegInvalid
  .field private [Pakon]Pakon.IntBits m_ibColorPosInvalid
  .field private valuetype Calibration.DPIConfig m_dpi35mm16Base
  .field private valuetype Calibration.DPIConfig m_dpi35mm8Base
  .field private valuetype Calibration.DPIConfig m_dpi35mm4Base
  .field private valuetype Calibration.DPIConfig m_dpi24mm16Base
  .field private valuetype Calibration.DPIConfig m_dpi24mm8Base
  .field private valuetype Calibration.DPIConfig m_dpi24mm4Base
  .field private valuetype Calibration.ColorMatrixConfig m_cmNegative
  .field private valuetype Calibration.ColorMatrixConfig m_cmPositive
  .method public hidebysig specialname instance class Calibration.ScannerSettingsFirmware 
          get_Firmware() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      class Calibration.ScannerSettingsFirmware Calibration.ScannerSettings::m_csFirmwareSettings
    IL_0006:  ret
  } // end of method ScannerSettings::get_Firmware

  .method public hidebysig specialname instance [Pakon]Pakon.IntBits 
          get_ColorNegativeInvalid() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibColorNegInvalid
    IL_0006:  ret
  } // end of method ScannerSettings::get_ColorNegativeInvalid

  .method public hidebysig specialname instance [Pakon]Pakon.IntBits 
          get_ColorPositiveInvalid() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibColorPosInvalid
    IL_0006:  ret
  } // end of method ScannerSettings::get_ColorPositiveInvalid

  .method public hidebysig specialname instance bool 
          get_Item(valuetype Calibration.EEPromValue iEEPromValue) cil managed
  {
    // Code size       16 (0x10)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibEEPromInvalid
    IL_0006:  ldarg.1
    IL_0007:  callvirt   instance bool [Pakon]Pakon.IntBits::get_Item(int32)
    IL_000c:  ldc.i4.0
    IL_000d:  ceq
    IL_000f:  ret
  } // end of method ScannerSettings::get_Item

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       147 (0x93)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  newobj     instance void Calibration.ScannerSettingsFirmware::.ctor()
    IL_0006:  stfld      class Calibration.ScannerSettingsFirmware Calibration.ScannerSettings::m_csFirmwareSettings
    IL_000b:  ldarg.0
    IL_000c:  newobj     instance void [Pakon]Pakon.IntBits::.ctor()
    IL_0011:  stfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibEEPromInvalid
    IL_0016:  ldarg.0
    IL_0017:  newobj     instance void [Pakon]Pakon.IntBits::.ctor()
    IL_001c:  stfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibColorNegInvalid
    IL_0021:  ldarg.0
    IL_0022:  newobj     instance void [Pakon]Pakon.IntBits::.ctor()
    IL_0027:  stfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibColorPosInvalid
    IL_002c:  ldarg.0
    IL_002d:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm16Base
    IL_0032:  initobj    Calibration.DPIConfig
    IL_0038:  ldarg.0
    IL_0039:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_003e:  initobj    Calibration.DPIConfig
    IL_0044:  ldarg.0
    IL_0045:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm4Base
    IL_004a:  initobj    Calibration.DPIConfig
    IL_0050:  ldarg.0
    IL_0051:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm16Base
    IL_0056:  initobj    Calibration.DPIConfig
    IL_005c:  ldarg.0
    IL_005d:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm8Base
    IL_0062:  initobj    Calibration.DPIConfig
    IL_0068:  ldarg.0
    IL_0069:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm4Base
    IL_006e:  initobj    Calibration.DPIConfig
    IL_0074:  ldarg.0
    IL_0075:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_007a:  initobj    Calibration.ColorMatrixConfig
    IL_0080:  ldarg.0
    IL_0081:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0086:  initobj    Calibration.ColorMatrixConfig
    IL_008c:  ldarg.0
    IL_008d:  call       instance void [Pakon]Pakon.ScannerSettings::.ctor()
    IL_0092:  ret
  } // end of method ScannerSettings::.ctor

  .method public hidebysig virtual instance void 
          Reset() cil managed
  {
    // Code size       125 (0x7d)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  call       instance void [Pakon]Pakon.ScannerSettings::Reset()
    IL_0006:  ldarg.0
    IL_0007:  ldfld      class Calibration.ScannerSettingsFirmware Calibration.ScannerSettings::m_csFirmwareSettings
    IL_000c:  callvirt   instance void Calibration.ScannerSettingsFirmware::Reset()
    IL_0011:  ldarg.0
    IL_0012:  newobj     instance void [Pakon]Pakon.IntBits::.ctor()
    IL_0017:  stfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibEEPromInvalid
    IL_001c:  ldarg.0
    IL_001d:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm16Base
    IL_0022:  initobj    Calibration.DPIConfig
    IL_0028:  ldarg.0
    IL_0029:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_002e:  initobj    Calibration.DPIConfig
    IL_0034:  ldarg.0
    IL_0035:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm4Base
    IL_003a:  initobj    Calibration.DPIConfig
    IL_0040:  ldarg.0
    IL_0041:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm16Base
    IL_0046:  initobj    Calibration.DPIConfig
    IL_004c:  ldarg.0
    IL_004d:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm8Base
    IL_0052:  initobj    Calibration.DPIConfig
    IL_0058:  ldarg.0
    IL_0059:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm4Base
    IL_005e:  initobj    Calibration.DPIConfig
    IL_0064:  ldarg.0
    IL_0065:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_006a:  initobj    Calibration.ColorMatrixConfig
    IL_0070:  ldarg.0
    IL_0071:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0076:  initobj    Calibration.ColorMatrixConfig
    IL_007c:  ret
  } // end of method ScannerSettings::Reset

  .method public hidebysig instance void 
          OpenLLC(class Calibration.Scanner csScanner) cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.1
    IL_0001:  callvirt   instance void Calibration.Scanner::InitializeLLC()
    IL_0006:  ret
  } // end of method ScannerSettings::OpenLLC

  .method public hidebysig instance void 
          CloseLLC(class Calibration.Scanner csScanner) cil managed
  {
    // Code size       33 (0x21)
    .maxstack  8
    IL_0000:  ldarg.1
    IL_0001:  ldc.i4.s   26
    IL_0003:  ldc.i4     0x3e8
    IL_0008:  callvirt   instance void Calibration.Scanner::LLCAwake(int32,
                                                                     int32)
    IL_000d:  ldarg.1
    IL_000e:  callvirt   instance void Calibration.Scanner::CBUnadviseLLC()
    IL_0013:  ldarg.1
    IL_0014:  ldc.i4.s   26
    IL_0016:  ldc.i4     0xbb8
    IL_001b:  callvirt   instance void Calibration.Scanner::LLCAwake(int32,
                                                                     int32)
    IL_0020:  ret
  } // end of method ScannerSettings::CloseLLC

  .method public hidebysig instance void 
          PutIdentification(class Calibration.Scanner csScanner,
                            bool bCalibrateGroup) cil managed
  {
    // Code size       131 (0x83)
    .maxstack  6
    .locals ([Interop.TLXLib]TLXLib.SCANNER_VERSION_HW_000 V_0,
             [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_1)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldarg.0
    IL_0003:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0008:  stloc.1
    IL_0009:  ldloc.1
    IL_000a:  ldc.i4.7
    IL_000b:  sub
    IL_000c:  switch     ( 
                          IL_004c,
                          IL_004c)
    IL_0019:  ldloc.1
    IL_001a:  ldc.i4     0x546
    IL_001f:  sub
    IL_0020:  switch     ( 
                          IL_0043,
                          IL_0043)
    IL_002d:  ldloc.1
    IL_002e:  ldc.i4     0xd16
    IL_0033:  sub
    IL_0034:  switch     ( 
                          IL_0055,
                          IL_0055)
    IL_0041:  br.s       IL_005e

    IL_0043:  ldarg.0
    IL_0044:  call       instance [Pakon]Pakon.ScannerHW135 [Pakon]Pakon.ScannerSettings::get_Hardware135()
    IL_0049:  stloc.0
    IL_004a:  br.s       IL_0069

    IL_004c:  ldarg.0
    IL_004d:  call       instance [Pakon]Pakon.ScannerHW235 [Pakon]Pakon.ScannerSettings::get_Hardware235()
    IL_0052:  stloc.0
    IL_0053:  br.s       IL_0069

    IL_0055:  ldarg.0
    IL_0056:  call       instance [Pakon]Pakon.ScannerHW335 [Pakon]Pakon.ScannerSettings::get_Hardware335()
    IL_005b:  stloc.0
    IL_005c:  br.s       IL_0069

    IL_005e:  ldstr      "Scanner Type not supported"
    IL_0063:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0068:  throw

    IL_0069:  ldarg.1
    IL_006a:  callvirt   instance class Calibration.ICalibrate Calibration.Scanner::get_ICalibration()
    IL_006f:  ldarg.2
    IL_0070:  ldloc.0
    IL_0071:  ldarg.0
    IL_0072:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0077:  ldarg.0
    IL_0078:  call       instance int32 [Pakon]Pakon.ScannerSettings::get_SerialNumber()
    IL_007d:  callvirt   instance void Calibration.ICalibrate::PutIdentification(bool,
                                                                                 [Interop.TLXLib]TLXLib.SCANNER_VERSION_HW_000,
                                                                                 [Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                                 int32)
    IL_0082:  ret
  } // end of method ScannerSettings::PutIdentification

  .method public hidebysig instance void 
          PutData(class Calibration.Scanner csScanner) cil managed
  {
    // Code size       1160 (0x488)
    .maxstack  33
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  ldc.i4.0
    IL_0003:  call       instance void Calibration.ScannerSettings::PutIdentification(class Calibration.Scanner,
                                                                                      bool)
    IL_0008:  ldarg.0
    IL_0009:  ldarg.1
    IL_000a:  ldarg.0
    IL_000b:  ldc.i4.2
    IL_000c:  ldc.i4.1
    IL_000d:  ldc.i4.0
    IL_000e:  ldc.i4.0
    IL_000f:  ldc.i4.0
    IL_0010:  call       instance void Calibration.ScannerSettings::PutDpi(class Calibration.Scanner,
                                                                           class Calibration.ScannerSettings,
                                                                           [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                           [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                           bool,
                                                                           bool,
                                                                           bool)
    IL_0015:  ldarg.0
    IL_0016:  ldarg.1
    IL_0017:  ldarg.0
    IL_0018:  ldc.i4.1
    IL_0019:  ldc.i4.1
    IL_001a:  ldc.i4.0
    IL_001b:  ldc.i4.0
    IL_001c:  ldc.i4.0
    IL_001d:  call       instance void Calibration.ScannerSettings::PutDpi(class Calibration.Scanner,
                                                                           class Calibration.ScannerSettings,
                                                                           [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                           [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                           bool,
                                                                           bool,
                                                                           bool)
    IL_0022:  ldarg.0
    IL_0023:  ldarg.1
    IL_0024:  ldarg.0
    IL_0025:  ldc.i4.0
    IL_0026:  ldc.i4.1
    IL_0027:  ldc.i4.0
    IL_0028:  ldc.i4.0
    IL_0029:  ldc.i4.0
    IL_002a:  call       instance void Calibration.ScannerSettings::PutDpi(class Calibration.Scanner,
                                                                           class Calibration.ScannerSettings,
                                                                           [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                           [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                           bool,
                                                                           bool,
                                                                           bool)
    IL_002f:  ldarg.0
    IL_0030:  ldc.i4.s   24
    IL_0032:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_0037:  brfalse.s  IL_0060

    IL_0039:  ldarg.0
    IL_003a:  ldarg.1
    IL_003b:  ldarg.0
    IL_003c:  ldc.i4.2
    IL_003d:  ldc.i4.0
    IL_003e:  ldc.i4.0
    IL_003f:  ldc.i4.0
    IL_0040:  ldc.i4.0
    IL_0041:  call       instance void Calibration.ScannerSettings::PutDpi(class Calibration.Scanner,
                                                                           class Calibration.ScannerSettings,
                                                                           [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                           [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                           bool,
                                                                           bool,
                                                                           bool)
    IL_0046:  ldarg.0
    IL_0047:  ldarg.1
    IL_0048:  ldarg.0
    IL_0049:  ldc.i4.1
    IL_004a:  ldc.i4.0
    IL_004b:  ldc.i4.0
    IL_004c:  ldc.i4.0
    IL_004d:  ldc.i4.0
    IL_004e:  call       instance void Calibration.ScannerSettings::PutDpi(class Calibration.Scanner,
                                                                           class Calibration.ScannerSettings,
                                                                           [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                           [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                           bool,
                                                                           bool,
                                                                           bool)
    IL_0053:  ldarg.0
    IL_0054:  ldarg.1
    IL_0055:  ldarg.0
    IL_0056:  ldc.i4.0
    IL_0057:  ldc.i4.0
    IL_0058:  ldc.i4.0
    IL_0059:  ldc.i4.0
    IL_005a:  ldc.i4.0
    IL_005b:  call       instance void Calibration.ScannerSettings::PutDpi(class Calibration.Scanner,
                                                                           class Calibration.ScannerSettings,
                                                                           [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                           [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                           bool,
                                                                           bool,
                                                                           bool)
    IL_0060:  ldarg.0
    IL_0061:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0066:  ldfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_006b:  ldc.i4.1
    IL_006c:  bne.un     IL_0107

    IL_0071:  ldarg.1
    IL_0072:  callvirt   instance class Calibration.ICalibrate Calibration.Scanner::get_ICalibration()
    IL_0077:  ldc.i4.0
    IL_0078:  ldc.i4.0
    IL_0079:  ldarg.0
    IL_007a:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_007f:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_0
    IL_0084:  ldarg.0
    IL_0085:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_008a:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_1
    IL_008f:  ldarg.0
    IL_0090:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0095:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_2
    IL_009a:  ldarg.0
    IL_009b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_00a0:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_3
    IL_00a5:  ldarg.0
    IL_00a6:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_00ab:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_0
    IL_00b0:  ldarg.0
    IL_00b1:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_00b6:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_1
    IL_00bb:  ldarg.0
    IL_00bc:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_00c1:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_2
    IL_00c6:  ldarg.0
    IL_00c7:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_00cc:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_3
    IL_00d1:  ldarg.0
    IL_00d2:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_00d7:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_0
    IL_00dc:  ldarg.0
    IL_00dd:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_00e2:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_1
    IL_00e7:  ldarg.0
    IL_00e8:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_00ed:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_2
    IL_00f2:  ldarg.0
    IL_00f3:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_00f8:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_3
    IL_00fd:  callvirt   instance void Calibration.ICalibrate::PutColorMatrix3By4(valuetype Calibration.ColorMatrix,
                                                                                  bool,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64)
    IL_0102:  br         IL_026f

    IL_0107:  ldarg.0
    IL_0108:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_010d:  ldfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_0112:  ldc.i4.2
    IL_0113:  bne.un     IL_026f

    IL_0118:  ldarg.1
    IL_0119:  callvirt   instance class Calibration.ICalibrate Calibration.Scanner::get_ICalibration()
    IL_011e:  ldc.i4.0
    IL_011f:  ldc.i4.0
    IL_0120:  ldarg.0
    IL_0121:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0126:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_0
    IL_012b:  ldarg.0
    IL_012c:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0131:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_1
    IL_0136:  ldarg.0
    IL_0137:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_013c:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_2
    IL_0141:  ldarg.0
    IL_0142:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0147:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_3
    IL_014c:  ldarg.0
    IL_014d:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0152:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_4
    IL_0157:  ldarg.0
    IL_0158:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_015d:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_5
    IL_0162:  ldarg.0
    IL_0163:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0168:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_6
    IL_016d:  ldarg.0
    IL_016e:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0173:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_7
    IL_0178:  ldarg.0
    IL_0179:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_017e:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_8
    IL_0183:  ldarg.0
    IL_0184:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0189:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_9
    IL_018e:  ldarg.0
    IL_018f:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0194:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_0
    IL_0199:  ldarg.0
    IL_019a:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_019f:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_1
    IL_01a4:  ldarg.0
    IL_01a5:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_01aa:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_2
    IL_01af:  ldarg.0
    IL_01b0:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_01b5:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_3
    IL_01ba:  ldarg.0
    IL_01bb:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_01c0:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_4
    IL_01c5:  ldarg.0
    IL_01c6:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_01cb:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_5
    IL_01d0:  ldarg.0
    IL_01d1:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_01d6:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_6
    IL_01db:  ldarg.0
    IL_01dc:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_01e1:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_7
    IL_01e6:  ldarg.0
    IL_01e7:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_01ec:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_8
    IL_01f1:  ldarg.0
    IL_01f2:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_01f7:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_9
    IL_01fc:  ldarg.0
    IL_01fd:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0202:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_0
    IL_0207:  ldarg.0
    IL_0208:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_020d:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_1
    IL_0212:  ldarg.0
    IL_0213:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0218:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_2
    IL_021d:  ldarg.0
    IL_021e:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0223:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_3
    IL_0228:  ldarg.0
    IL_0229:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_022e:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_4
    IL_0233:  ldarg.0
    IL_0234:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0239:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_5
    IL_023e:  ldarg.0
    IL_023f:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0244:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_6
    IL_0249:  ldarg.0
    IL_024a:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_024f:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_7
    IL_0254:  ldarg.0
    IL_0255:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_025a:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_8
    IL_025f:  ldarg.0
    IL_0260:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0265:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_9
    IL_026a:  callvirt   instance void Calibration.ICalibrate::PutColorMatrix3By10(valuetype Calibration.ColorMatrix,
                                                                                   bool,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32)
    IL_026f:  ldarg.0
    IL_0270:  ldc.i4.s   23
    IL_0272:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_0277:  brfalse    IL_0487

    IL_027c:  ldarg.0
    IL_027d:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0282:  ldfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_0287:  ldc.i4.1
    IL_0288:  bne.un     IL_031f

    IL_028d:  ldarg.1
    IL_028e:  callvirt   instance class Calibration.ICalibrate Calibration.Scanner::get_ICalibration()
    IL_0293:  ldc.i4.1
    IL_0294:  ldc.i4.0
    IL_0295:  ldarg.0
    IL_0296:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_029b:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_0
    IL_02a0:  ldarg.0
    IL_02a1:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_02a6:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_1
    IL_02ab:  ldarg.0
    IL_02ac:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_02b1:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_2
    IL_02b6:  ldarg.0
    IL_02b7:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_02bc:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_3
    IL_02c1:  ldarg.0
    IL_02c2:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_02c7:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_0
    IL_02cc:  ldarg.0
    IL_02cd:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_02d2:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_1
    IL_02d7:  ldarg.0
    IL_02d8:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_02dd:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_2
    IL_02e2:  ldarg.0
    IL_02e3:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_02e8:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_3
    IL_02ed:  ldarg.0
    IL_02ee:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_02f3:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_0
    IL_02f8:  ldarg.0
    IL_02f9:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_02fe:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_1
    IL_0303:  ldarg.0
    IL_0304:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0309:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_2
    IL_030e:  ldarg.0
    IL_030f:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0314:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_3
    IL_0319:  callvirt   instance void Calibration.ICalibrate::PutColorMatrix3By4(valuetype Calibration.ColorMatrix,
                                                                                  bool,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64,
                                                                                  float64)
    IL_031e:  ret

    IL_031f:  ldarg.0
    IL_0320:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0325:  ldfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_032a:  ldc.i4.2
    IL_032b:  bne.un     IL_0487

    IL_0330:  ldarg.1
    IL_0331:  callvirt   instance class Calibration.ICalibrate Calibration.Scanner::get_ICalibration()
    IL_0336:  ldc.i4.1
    IL_0337:  ldc.i4.0
    IL_0338:  ldarg.0
    IL_0339:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_033e:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_0
    IL_0343:  ldarg.0
    IL_0344:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0349:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_1
    IL_034e:  ldarg.0
    IL_034f:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0354:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_2
    IL_0359:  ldarg.0
    IL_035a:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_035f:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_3
    IL_0364:  ldarg.0
    IL_0365:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_036a:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_4
    IL_036f:  ldarg.0
    IL_0370:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0375:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_5
    IL_037a:  ldarg.0
    IL_037b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0380:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_6
    IL_0385:  ldarg.0
    IL_0386:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_038b:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_7
    IL_0390:  ldarg.0
    IL_0391:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0396:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_8
    IL_039b:  ldarg.0
    IL_039c:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_03a1:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_9
    IL_03a6:  ldarg.0
    IL_03a7:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_03ac:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_0
    IL_03b1:  ldarg.0
    IL_03b2:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_03b7:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_1
    IL_03bc:  ldarg.0
    IL_03bd:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_03c2:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_2
    IL_03c7:  ldarg.0
    IL_03c8:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_03cd:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_3
    IL_03d2:  ldarg.0
    IL_03d3:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_03d8:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_4
    IL_03dd:  ldarg.0
    IL_03de:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_03e3:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_5
    IL_03e8:  ldarg.0
    IL_03e9:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_03ee:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_6
    IL_03f3:  ldarg.0
    IL_03f4:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_03f9:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_7
    IL_03fe:  ldarg.0
    IL_03ff:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0404:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_8
    IL_0409:  ldarg.0
    IL_040a:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_040f:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_9
    IL_0414:  ldarg.0
    IL_0415:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_041a:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_0
    IL_041f:  ldarg.0
    IL_0420:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0425:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_1
    IL_042a:  ldarg.0
    IL_042b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0430:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_2
    IL_0435:  ldarg.0
    IL_0436:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_043b:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_3
    IL_0440:  ldarg.0
    IL_0441:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0446:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_4
    IL_044b:  ldarg.0
    IL_044c:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0451:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_5
    IL_0456:  ldarg.0
    IL_0457:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_045c:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_6
    IL_0461:  ldarg.0
    IL_0462:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0467:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_7
    IL_046c:  ldarg.0
    IL_046d:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0472:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_8
    IL_0477:  ldarg.0
    IL_0478:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_047d:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_9
    IL_0482:  callvirt   instance void Calibration.ICalibrate::PutColorMatrix3By10(valuetype Calibration.ColorMatrix,
                                                                                   bool,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32,
                                                                                   float32)
    IL_0487:  ret
  } // end of method ScannerSettings::PutData

  .method public hidebysig instance valuetype Calibration.DPIConfig 
          GetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000 ffFormat,
                       [Interop.TLXLib]TLXLib.RESOLUTION_000 prResolution) cil managed
  {
    // Code size       136 (0x88)
    .maxstack  2
    .locals (valuetype Calibration.DPIConfig V_0,
             [Interop.TLXLib]TLXLib.FILM_FORMAT_000 V_1,
             [Interop.TLXLib]TLXLib.RESOLUTION_000 V_2)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_0006:  stloc.0
    IL_0007:  ldarg.1
    IL_0008:  stloc.1
    IL_0009:  ldloc.1
    IL_000a:  switch     ( 
                          IL_0019,
                          IL_004a)
    IL_0017:  br.s       IL_007b

    IL_0019:  ldarg.2
    IL_001a:  stloc.2
    IL_001b:  ldloc.2
    IL_001c:  switch     ( 
                          IL_002f,
                          IL_0038,
                          IL_0041)
    IL_002d:  br.s       IL_0086

    IL_002f:  ldarg.0
    IL_0030:  ldfld      valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm4Base
    IL_0035:  stloc.0
    IL_0036:  br.s       IL_0086

    IL_0038:  ldarg.0
    IL_0039:  ldfld      valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm8Base
    IL_003e:  stloc.0
    IL_003f:  br.s       IL_0086

    IL_0041:  ldarg.0
    IL_0042:  ldfld      valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm16Base
    IL_0047:  stloc.0
    IL_0048:  br.s       IL_0086

    IL_004a:  ldarg.2
    IL_004b:  stloc.2
    IL_004c:  ldloc.2
    IL_004d:  switch     ( 
                          IL_0060,
                          IL_0069,
                          IL_0072)
    IL_005e:  br.s       IL_0086

    IL_0060:  ldarg.0
    IL_0061:  ldfld      valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm4Base
    IL_0066:  stloc.0
    IL_0067:  br.s       IL_0086

    IL_0069:  ldarg.0
    IL_006a:  ldfld      valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_006f:  stloc.0
    IL_0070:  br.s       IL_0086

    IL_0072:  ldarg.0
    IL_0073:  ldfld      valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm16Base
    IL_0078:  stloc.0
    IL_0079:  br.s       IL_0086

    IL_007b:  ldstr      "GetDPIConfig Film Format not supported"
    IL_0080:  newobj     instance void [mscorlib]System.FormatException::.ctor(string)
    IL_0085:  throw

    IL_0086:  ldloc.0
    IL_0087:  ret
  } // end of method ScannerSettings::GetDPIConfig

  .method private hidebysig instance void 
          SetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000 ffFormat,
                       [Interop.TLXLib]TLXLib.RESOLUTION_000 prResolution,
                       valuetype Calibration.DPIConfig dpiConfig) cil managed
  {
    // Code size       182 (0xb6)
    .maxstack  9
    .locals (valuetype Calibration.DPIConfig V_0,
             [Interop.TLXLib]TLXLib.FILM_FORMAT_000 V_1,
             [Interop.TLXLib]TLXLib.RESOLUTION_000 V_2)
    IL_0000:  ldloca.s   V_0
    IL_0002:  ldarga.s   dpiConfig
    IL_0004:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_0009:  ldarga.s   dpiConfig
    IL_000b:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0010:  ldarga.s   dpiConfig
    IL_0012:  ldfld      int16 Calibration.DPIConfig::m_sCCDStepperAdjust
    IL_0017:  ldarga.s   dpiConfig
    IL_0019:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_001e:  ldarga.s   dpiConfig
    IL_0020:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_0025:  ldarga.s   dpiConfig
    IL_0027:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust
    IL_002c:  ldarga.s   dpiConfig
    IL_002e:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_0033:  ldarga.s   dpiConfig
    IL_0035:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust_Ir
    IL_003a:  call       instance void Calibration.DPIConfig::.ctor(uint16,
                                                                    uint16,
                                                                    int16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16)
    IL_003f:  ldarg.1
    IL_0040:  stloc.1
    IL_0041:  ldloc.1
    IL_0042:  switch     ( 
                          IL_0051,
                          IL_007e)
    IL_004f:  br.s       IL_00ab

    IL_0051:  ldarg.2
    IL_0052:  stloc.2
    IL_0053:  ldloc.2
    IL_0054:  switch     ( 
                          IL_0066,
                          IL_006e,
                          IL_0076)
    IL_0065:  ret

    IL_0066:  ldarg.0
    IL_0067:  ldloc.0
    IL_0068:  stfld      valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm4Base
    IL_006d:  ret

    IL_006e:  ldarg.0
    IL_006f:  ldloc.0
    IL_0070:  stfld      valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm8Base
    IL_0075:  ret

    IL_0076:  ldarg.0
    IL_0077:  ldloc.0
    IL_0078:  stfld      valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm16Base
    IL_007d:  ret

    IL_007e:  ldarg.2
    IL_007f:  stloc.2
    IL_0080:  ldloc.2
    IL_0081:  switch     ( 
                          IL_0093,
                          IL_009b,
                          IL_00a3)
    IL_0092:  ret

    IL_0093:  ldarg.0
    IL_0094:  ldloc.0
    IL_0095:  stfld      valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm4Base
    IL_009a:  ret

    IL_009b:  ldarg.0
    IL_009c:  ldloc.0
    IL_009d:  stfld      valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_00a2:  ret

    IL_00a3:  ldarg.0
    IL_00a4:  ldloc.0
    IL_00a5:  stfld      valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm16Base
    IL_00aa:  ret

    IL_00ab:  ldstr      "SetDPIConfig Film Format not supported"
    IL_00b0:  newobj     instance void [mscorlib]System.FormatException::.ctor(string)
    IL_00b5:  throw
  } // end of method ScannerSettings::SetDPIConfig

  .method public hidebysig instance uint16 
          GetOffset([Interop.TLXLib]TLXLib.FILM_FORMAT_000 ffFormat,
                    [Interop.TLXLib]TLXLib.RESOLUTION_000 prResolution) cil managed
  {
    // Code size       100 (0x64)
    .maxstack  3
    .locals (uint16 V_0,
             valuetype Calibration.DPIConfig V_1,
             valuetype Calibration.DPIConfig V_2)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::m_stType
    IL_0006:  ldc.i4     0x546
    IL_000b:  beq.s      IL_001a

    IL_000d:  ldarg.0
    IL_000e:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::m_stType
    IL_0013:  ldc.i4     0x547
    IL_0018:  bne.un.s   IL_0051

    IL_001a:  ldarg.0
    IL_001b:  ldarg.1
    IL_001c:  ldc.i4.2
    IL_001d:  call       instance valuetype Calibration.DPIConfig Calibration.ScannerSettings::GetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                                            [Interop.TLXLib]TLXLib.RESOLUTION_000)
    IL_0022:  stloc.1
    IL_0023:  ldarg.2
    IL_0024:  ldc.i4.2
    IL_0025:  bne.un.s   IL_0031

    IL_0027:  ldloca.s   V_1
    IL_0029:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_002e:  stloc.0
    IL_002f:  br.s       IL_0062

    IL_0031:  ldarg.2
    IL_0032:  ldc.i4.1
    IL_0033:  bne.un.s   IL_0044

    IL_0035:  ldloca.s   V_1
    IL_0037:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_003c:  ldc.i4.3
    IL_003d:  mul
    IL_003e:  ldc.i4.4
    IL_003f:  div
    IL_0040:  conv.u2
    IL_0041:  stloc.0
    IL_0042:  br.s       IL_0062

    IL_0044:  ldloca.s   V_1
    IL_0046:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_004b:  ldc.i4.2
    IL_004c:  div
    IL_004d:  conv.u2
    IL_004e:  stloc.0
    IL_004f:  br.s       IL_0062

    IL_0051:  ldarg.0
    IL_0052:  ldarg.1
    IL_0053:  ldarg.2
    IL_0054:  call       instance valuetype Calibration.DPIConfig Calibration.ScannerSettings::GetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                                            [Interop.TLXLib]TLXLib.RESOLUTION_000)
    IL_0059:  stloc.2
    IL_005a:  ldloca.s   V_2
    IL_005c:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0061:  stloc.0
    IL_0062:  ldloc.0
    IL_0063:  ret
  } // end of method ScannerSettings::GetOffset

  .method public hidebysig instance void 
          SetOffset([Interop.TLXLib]TLXLib.FILM_FORMAT_000 ffFormat,
                    [Interop.TLXLib]TLXLib.RESOLUTION_000 prResolution,
                    uint16 usOffset) cil managed
  {
    // Code size       116 (0x74)
    .maxstack  4
    .locals (valuetype Calibration.DPIConfig V_0,
             valuetype Calibration.DPIConfig V_1)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::m_stType
    IL_0006:  ldc.i4     0x546
    IL_000b:  beq.s      IL_001a

    IL_000d:  ldarg.0
    IL_000e:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::m_stType
    IL_0013:  ldc.i4     0x547
    IL_0018:  bne.un.s   IL_0059

    IL_001a:  ldarg.0
    IL_001b:  ldarg.1
    IL_001c:  ldc.i4.2
    IL_001d:  call       instance valuetype Calibration.DPIConfig Calibration.ScannerSettings::GetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                                            [Interop.TLXLib]TLXLib.RESOLUTION_000)
    IL_0022:  stloc.0
    IL_0023:  ldarg.2
    IL_0024:  ldc.i4.2
    IL_0025:  bne.un.s   IL_0031

    IL_0027:  ldloca.s   V_0
    IL_0029:  ldarg.3
    IL_002a:  stfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_002f:  br.s       IL_004f

    IL_0031:  ldarg.2
    IL_0032:  ldc.i4.1
    IL_0033:  bne.un.s   IL_0044

    IL_0035:  ldloca.s   V_0
    IL_0037:  ldarg.3
    IL_0038:  ldc.i4.4
    IL_0039:  mul
    IL_003a:  ldc.i4.3
    IL_003b:  div
    IL_003c:  conv.u2
    IL_003d:  stfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0042:  br.s       IL_004f

    IL_0044:  ldloca.s   V_0
    IL_0046:  ldarg.3
    IL_0047:  ldc.i4.2
    IL_0048:  mul
    IL_0049:  conv.u2
    IL_004a:  stfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_004f:  ldarg.0
    IL_0050:  ldarg.1
    IL_0051:  ldc.i4.2
    IL_0052:  ldloc.0
    IL_0053:  call       instance void Calibration.ScannerSettings::SetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                 [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                 valuetype Calibration.DPIConfig)
    IL_0058:  ret

    IL_0059:  ldarg.0
    IL_005a:  ldarg.1
    IL_005b:  ldarg.2
    IL_005c:  call       instance valuetype Calibration.DPIConfig Calibration.ScannerSettings::GetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                                            [Interop.TLXLib]TLXLib.RESOLUTION_000)
    IL_0061:  stloc.1
    IL_0062:  ldloca.s   V_1
    IL_0064:  ldarg.3
    IL_0065:  stfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_006a:  ldarg.0
    IL_006b:  ldarg.1
    IL_006c:  ldarg.2
    IL_006d:  ldloc.1
    IL_006e:  call       instance void Calibration.ScannerSettings::SetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                 [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                 valuetype Calibration.DPIConfig)
    IL_0073:  ret
  } // end of method ScannerSettings::SetOffset

  .method public hidebysig instance valuetype Calibration.ColorMatrixConfig 
          GetColorMatrix(valuetype Calibration.ColorMatrix cmMatrix) cil managed
  {
    // Code size       47 (0x2f)
    .maxstack  2
    .locals (valuetype Calibration.ColorMatrix V_0)
    IL_0000:  ldarg.1
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  switch     ( 
                          IL_0016,
                          IL_001d,
                          IL_0024)
    IL_0014:  br.s       IL_0024

    IL_0016:  ldarg.0
    IL_0017:  ldfld      valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_001c:  ret

    IL_001d:  ldarg.0
    IL_001e:  ldfld      valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0023:  ret

    IL_0024:  ldstr      "Color Matrix not supported"
    IL_0029:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_002e:  throw
  } // end of method ScannerSettings::GetColorMatrix

  .method public hidebysig instance void 
          LoadColorMatrices(class Calibration.Scanner csScanner) cil managed
  {
    // Code size       183 (0xb7)
    .maxstack  4
    .locals ([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_0)
    IL_0000:  ldarg.0
    IL_0001:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0006:  stloc.0
    IL_0007:  ldloc.0
    IL_0008:  ldc.i4.8
    IL_0009:  bgt.s      IL_0021

    IL_000b:  ldloc.0
    IL_000c:  ldc.i4.0
    IL_000d:  beq.s      IL_0049

    IL_000f:  ldloc.0
    IL_0010:  ldc.i4.7
    IL_0011:  sub
    IL_0012:  switch     ( 
                          IL_007d,
                          IL_007d)
    IL_001f:  br.s       IL_0049

    IL_0021:  ldloc.0
    IL_0022:  ldc.i4     0x546
    IL_0027:  sub
    IL_0028:  switch     ( 
                          IL_0062,
                          IL_0062)
    IL_0035:  ldloc.0
    IL_0036:  ldc.i4     0xd16
    IL_003b:  sub
    IL_003c:  switch     ( 
                          IL_009a,
                          IL_009a)
    IL_0049:  ldarg.0
    IL_004a:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_004f:  initobj    Calibration.ColorMatrixConfig
    IL_0055:  ldarg.0
    IL_0056:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_005b:  initobj    Calibration.ColorMatrixConfig
    IL_0061:  ret

    IL_0062:  ldarg.0
    IL_0063:  ldarg.1
    IL_0064:  ldc.i4.0
    IL_0065:  ldarg.0
    IL_0066:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_006b:  call       instance void Calibration.ScannerSettings::GetColorMatrix3by10(class Calibration.Scanner,
                                                                                        valuetype Calibration.ColorMatrix,
                                                                                        valuetype Calibration.ColorMatrixConfig&)
    IL_0070:  ldarg.0
    IL_0071:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0076:  initobj    Calibration.ColorMatrixConfig
    IL_007c:  ret

    IL_007d:  ldarg.0
    IL_007e:  ldarg.1
    IL_007f:  ldc.i4.0
    IL_0080:  ldarg.0
    IL_0081:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0086:  call       instance void Calibration.ScannerSettings::GetColorMatrix3by4(class Calibration.Scanner,
                                                                                       valuetype Calibration.ColorMatrix,
                                                                                       valuetype Calibration.ColorMatrixConfig&)
    IL_008b:  ldarg.0
    IL_008c:  ldarg.1
    IL_008d:  ldc.i4.1
    IL_008e:  ldarg.0
    IL_008f:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0094:  call       instance void Calibration.ScannerSettings::GetColorMatrix3by4(class Calibration.Scanner,
                                                                                       valuetype Calibration.ColorMatrix,
                                                                                       valuetype Calibration.ColorMatrixConfig&)
    IL_0099:  ret

    IL_009a:  ldarg.0
    IL_009b:  ldarg.1
    IL_009c:  ldc.i4.0
    IL_009d:  ldarg.0
    IL_009e:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_00a3:  call       instance void Calibration.ScannerSettings::GetColorMatrix3by10(class Calibration.Scanner,
                                                                                        valuetype Calibration.ColorMatrix,
                                                                                        valuetype Calibration.ColorMatrixConfig&)
    IL_00a8:  ldarg.0
    IL_00a9:  ldarg.1
    IL_00aa:  ldc.i4.1
    IL_00ab:  ldarg.0
    IL_00ac:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_00b1:  call       instance void Calibration.ScannerSettings::GetColorMatrix3by10(class Calibration.Scanner,
                                                                                        valuetype Calibration.ColorMatrix,
                                                                                        valuetype Calibration.ColorMatrixConfig&)
    IL_00b6:  ret
  } // end of method ScannerSettings::LoadColorMatrices

  .method public hidebysig instance void 
          GetColorMatrix3by4(class Calibration.Scanner csScanner,
                             valuetype Calibration.ColorMatrix cmType,
                             valuetype Calibration.ColorMatrixConfig& cmMatrix) cil managed
  {
    // Code size       191 (0xbf)
    .maxstack  14
    .locals (float64 V_0,
             float64 V_1,
             float64 V_2,
             float64 V_3,
             float64 V_4,
             float64 V_5,
             float64 V_6,
             float64 V_7,
             float64 V_8,
             float64 V_9,
             float64 V_10,
             float64 V_11)
    IL_0000:  ldc.r8     0.0
    IL_0009:  stloc.0
    IL_000a:  ldc.r8     0.0
    IL_0013:  stloc.1
    IL_0014:  ldc.r8     0.0
    IL_001d:  stloc.2
    IL_001e:  ldc.r8     0.0
    IL_0027:  stloc.3
    IL_0028:  ldc.r8     0.0
    IL_0031:  stloc.s    V_4
    IL_0033:  ldc.r8     0.0
    IL_003c:  stloc.s    V_5
    IL_003e:  ldc.r8     0.0
    IL_0047:  stloc.s    V_6
    IL_0049:  ldc.r8     0.0
    IL_0052:  stloc.s    V_7
    IL_0054:  ldc.r8     0.0
    IL_005d:  stloc.s    V_8
    IL_005f:  ldc.r8     0.0
    IL_0068:  stloc.s    V_9
    IL_006a:  ldc.r8     0.0
    IL_0073:  stloc.s    V_10
    IL_0075:  ldc.r8     0.0
    IL_007e:  stloc.s    V_11
    IL_0080:  ldarg.1
    IL_0081:  callvirt   instance class Calibration.ICalibrate Calibration.Scanner::get_ICalibration()
    IL_0086:  ldarg.2
    IL_0087:  ldloca.s   V_0
    IL_0089:  ldloca.s   V_1
    IL_008b:  ldloca.s   V_2
    IL_008d:  ldloca.s   V_3
    IL_008f:  ldloca.s   V_4
    IL_0091:  ldloca.s   V_5
    IL_0093:  ldloca.s   V_6
    IL_0095:  ldloca.s   V_7
    IL_0097:  ldloca.s   V_8
    IL_0099:  ldloca.s   V_9
    IL_009b:  ldloca.s   V_10
    IL_009d:  ldloca.s   V_11
    IL_009f:  callvirt   instance void Calibration.ICalibrate::GetColorMatrix3By4(valuetype Calibration.ColorMatrix,
                                                                                  float64&,
                                                                                  float64&,
                                                                                  float64&,
                                                                                  float64&,
                                                                                  float64&,
                                                                                  float64&,
                                                                                  float64&,
                                                                                  float64&,
                                                                                  float64&,
                                                                                  float64&,
                                                                                  float64&,
                                                                                  float64&)
    IL_00a4:  ldarg.3
    IL_00a5:  ldloc.0
    IL_00a6:  ldloc.1
    IL_00a7:  ldloc.2
    IL_00a8:  ldloc.3
    IL_00a9:  ldloc.s    V_4
    IL_00ab:  ldloc.s    V_5
    IL_00ad:  ldloc.s    V_6
    IL_00af:  ldloc.s    V_7
    IL_00b1:  ldloc.s    V_8
    IL_00b3:  ldloc.s    V_9
    IL_00b5:  ldloc.s    V_10
    IL_00b7:  ldloc.s    V_11
    IL_00b9:  call       instance void Calibration.ColorMatrixConfig::.ctor(float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64)
    IL_00be:  ret
  } // end of method ScannerSettings::GetColorMatrix3by4

  .method public hidebysig instance void 
          GetColorMatrix3by10(class Calibration.Scanner csScanner,
                              valuetype Calibration.ColorMatrix cmType,
                              valuetype Calibration.ColorMatrixConfig& cmMatrix) cil managed
  {
    // Code size       341 (0x155)
    .maxstack  32
    .locals (float32 V_0,
             float32 V_1,
             float32 V_2,
             float32 V_3,
             float32 V_4,
             float32 V_5,
             float32 V_6,
             float32 V_7,
             float32 V_8,
             float32 V_9,
             float32 V_10,
             float32 V_11,
             float32 V_12,
             float32 V_13,
             float32 V_14,
             float32 V_15,
             float32 V_16,
             float32 V_17,
             float32 V_18,
             float32 V_19,
             float32 V_20,
             float32 V_21,
             float32 V_22,
             float32 V_23,
             float32 V_24,
             float32 V_25,
             float32 V_26,
             float32 V_27,
             float32 V_28,
             float32 V_29)
    IL_0000:  ldc.r4     0.0
    IL_0005:  stloc.0
    IL_0006:  ldc.r4     0.0
    IL_000b:  stloc.1
    IL_000c:  ldc.r4     0.0
    IL_0011:  stloc.2
    IL_0012:  ldc.r4     0.0
    IL_0017:  stloc.3
    IL_0018:  ldc.r4     0.0
    IL_001d:  stloc.s    V_4
    IL_001f:  ldc.r4     0.0
    IL_0024:  stloc.s    V_5
    IL_0026:  ldc.r4     0.0
    IL_002b:  stloc.s    V_6
    IL_002d:  ldc.r4     0.0
    IL_0032:  stloc.s    V_7
    IL_0034:  ldc.r4     0.0
    IL_0039:  stloc.s    V_8
    IL_003b:  ldc.r4     0.0
    IL_0040:  stloc.s    V_9
    IL_0042:  ldc.r4     0.0
    IL_0047:  stloc.s    V_10
    IL_0049:  ldc.r4     0.0
    IL_004e:  stloc.s    V_11
    IL_0050:  ldc.r4     0.0
    IL_0055:  stloc.s    V_12
    IL_0057:  ldc.r4     0.0
    IL_005c:  stloc.s    V_13
    IL_005e:  ldc.r4     0.0
    IL_0063:  stloc.s    V_14
    IL_0065:  ldc.r4     0.0
    IL_006a:  stloc.s    V_15
    IL_006c:  ldc.r4     0.0
    IL_0071:  stloc.s    V_16
    IL_0073:  ldc.r4     0.0
    IL_0078:  stloc.s    V_17
    IL_007a:  ldc.r4     0.0
    IL_007f:  stloc.s    V_18
    IL_0081:  ldc.r4     0.0
    IL_0086:  stloc.s    V_19
    IL_0088:  ldc.r4     0.0
    IL_008d:  stloc.s    V_20
    IL_008f:  ldc.r4     0.0
    IL_0094:  stloc.s    V_21
    IL_0096:  ldc.r4     0.0
    IL_009b:  stloc.s    V_22
    IL_009d:  ldc.r4     0.0
    IL_00a2:  stloc.s    V_23
    IL_00a4:  ldc.r4     0.0
    IL_00a9:  stloc.s    V_24
    IL_00ab:  ldc.r4     0.0
    IL_00b0:  stloc.s    V_25
    IL_00b2:  ldc.r4     0.0
    IL_00b7:  stloc.s    V_26
    IL_00b9:  ldc.r4     0.0
    IL_00be:  stloc.s    V_27
    IL_00c0:  ldc.r4     0.0
    IL_00c5:  stloc.s    V_28
    IL_00c7:  ldc.r4     0.0
    IL_00cc:  stloc.s    V_29
    IL_00ce:  ldarg.1
    IL_00cf:  callvirt   instance class Calibration.ICalibrate Calibration.Scanner::get_ICalibration()
    IL_00d4:  ldarg.2
    IL_00d5:  ldloca.s   V_0
    IL_00d7:  ldloca.s   V_1
    IL_00d9:  ldloca.s   V_2
    IL_00db:  ldloca.s   V_3
    IL_00dd:  ldloca.s   V_4
    IL_00df:  ldloca.s   V_5
    IL_00e1:  ldloca.s   V_6
    IL_00e3:  ldloca.s   V_7
    IL_00e5:  ldloca.s   V_8
    IL_00e7:  ldloca.s   V_9
    IL_00e9:  ldloca.s   V_10
    IL_00eb:  ldloca.s   V_11
    IL_00ed:  ldloca.s   V_12
    IL_00ef:  ldloca.s   V_13
    IL_00f1:  ldloca.s   V_14
    IL_00f3:  ldloca.s   V_15
    IL_00f5:  ldloca.s   V_16
    IL_00f7:  ldloca.s   V_17
    IL_00f9:  ldloca.s   V_18
    IL_00fb:  ldloca.s   V_19
    IL_00fd:  ldloca.s   V_20
    IL_00ff:  ldloca.s   V_21
    IL_0101:  ldloca.s   V_22
    IL_0103:  ldloca.s   V_23
    IL_0105:  ldloca.s   V_24
    IL_0107:  ldloca.s   V_25
    IL_0109:  ldloca.s   V_26
    IL_010b:  ldloca.s   V_27
    IL_010d:  ldloca.s   V_28
    IL_010f:  ldloca.s   V_29
    IL_0111:  callvirt   instance void Calibration.ICalibrate::GetColorMatrix3By10(valuetype Calibration.ColorMatrix,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&,
                                                                                   float32&)
    IL_0116:  ldarg.3
    IL_0117:  ldloc.0
    IL_0118:  ldloc.1
    IL_0119:  ldloc.2
    IL_011a:  ldloc.3
    IL_011b:  ldloc.s    V_4
    IL_011d:  ldloc.s    V_5
    IL_011f:  ldloc.s    V_6
    IL_0121:  ldloc.s    V_7
    IL_0123:  ldloc.s    V_8
    IL_0125:  ldloc.s    V_9
    IL_0127:  ldloc.s    V_10
    IL_0129:  ldloc.s    V_11
    IL_012b:  ldloc.s    V_12
    IL_012d:  ldloc.s    V_13
    IL_012f:  ldloc.s    V_14
    IL_0131:  ldloc.s    V_15
    IL_0133:  ldloc.s    V_16
    IL_0135:  ldloc.s    V_17
    IL_0137:  ldloc.s    V_18
    IL_0139:  ldloc.s    V_19
    IL_013b:  ldloc.s    V_20
    IL_013d:  ldloc.s    V_21
    IL_013f:  ldloc.s    V_22
    IL_0141:  ldloc.s    V_23
    IL_0143:  ldloc.s    V_24
    IL_0145:  ldloc.s    V_25
    IL_0147:  ldloc.s    V_26
    IL_0149:  ldloc.s    V_27
    IL_014b:  ldloc.s    V_28
    IL_014d:  ldloc.s    V_29
    IL_014f:  call       instance void Calibration.ColorMatrixConfig::.ctor(float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32)
    IL_0154:  ret
  } // end of method ScannerSettings::GetColorMatrix3by10

  .method public hidebysig instance void 
          LoadDpiSettings(class Calibration.Scanner csScanner) cil managed
  {
    // Code size       137 (0x89)
    .maxstack  6
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  ldarg.0
    IL_0003:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0008:  ldc.i4.2
    IL_0009:  ldc.i4.1
    IL_000a:  ldarg.0
    IL_000b:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm16Base
    IL_0010:  call       instance void Calibration.ScannerSettings::LoadDPISetting(class Calibration.Scanner,
                                                                                   [Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                                   [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                   [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                   valuetype Calibration.DPIConfig&)
    IL_0015:  ldarg.0
    IL_0016:  ldarg.1
    IL_0017:  ldarg.0
    IL_0018:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_001d:  ldc.i4.1
    IL_001e:  ldc.i4.1
    IL_001f:  ldarg.0
    IL_0020:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_0025:  call       instance void Calibration.ScannerSettings::LoadDPISetting(class Calibration.Scanner,
                                                                                   [Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                                   [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                   [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                   valuetype Calibration.DPIConfig&)
    IL_002a:  ldarg.0
    IL_002b:  ldarg.1
    IL_002c:  ldarg.0
    IL_002d:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0032:  ldc.i4.0
    IL_0033:  ldc.i4.1
    IL_0034:  ldarg.0
    IL_0035:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm4Base
    IL_003a:  call       instance void Calibration.ScannerSettings::LoadDPISetting(class Calibration.Scanner,
                                                                                   [Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                                   [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                   [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                   valuetype Calibration.DPIConfig&)
    IL_003f:  ldarg.0
    IL_0040:  ldc.i4.s   24
    IL_0042:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_0047:  brfalse.s  IL_0088

    IL_0049:  ldarg.0
    IL_004a:  ldarg.1
    IL_004b:  ldarg.0
    IL_004c:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0051:  ldc.i4.2
    IL_0052:  ldc.i4.0
    IL_0053:  ldarg.0
    IL_0054:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm16Base
    IL_0059:  call       instance void Calibration.ScannerSettings::LoadDPISetting(class Calibration.Scanner,
                                                                                   [Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                                   [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                   [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                   valuetype Calibration.DPIConfig&)
    IL_005e:  ldarg.0
    IL_005f:  ldarg.1
    IL_0060:  ldarg.0
    IL_0061:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0066:  ldc.i4.1
    IL_0067:  ldc.i4.0
    IL_0068:  ldarg.0
    IL_0069:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm8Base
    IL_006e:  call       instance void Calibration.ScannerSettings::LoadDPISetting(class Calibration.Scanner,
                                                                                   [Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                                   [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                   [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                   valuetype Calibration.DPIConfig&)
    IL_0073:  ldarg.0
    IL_0074:  ldarg.1
    IL_0075:  ldarg.0
    IL_0076:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_007b:  ldc.i4.0
    IL_007c:  ldc.i4.0
    IL_007d:  ldarg.0
    IL_007e:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm4Base
    IL_0083:  call       instance void Calibration.ScannerSettings::LoadDPISetting(class Calibration.Scanner,
                                                                                   [Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                                   [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                   [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                   valuetype Calibration.DPIConfig&)
    IL_0088:  ret
  } // end of method ScannerSettings::LoadDpiSettings

  .method private hidebysig instance void 
          LoadDPISetting(class Calibration.Scanner csScanner,
                         [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iType,
                         [Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                         [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                         valuetype Calibration.DPIConfig& dpiConfig) cil managed
  {
    // Code size       133 (0x85)
    .maxstack  15
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2,
             int32 V_3,
             int32 V_4,
             int32 V_5,
             int32 V_6,
             int32 V_7,
             int32 V_8,
             int32 V_9,
             int32 V_10,
             int32 V_11)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldc.i4.0
    IL_0003:  stloc.1
    IL_0004:  ldc.i4.0
    IL_0005:  stloc.2
    IL_0006:  ldc.i4.0
    IL_0007:  stloc.3
    IL_0008:  ldc.i4.0
    IL_0009:  stloc.s    V_4
    IL_000b:  ldc.i4.0
    IL_000c:  stloc.s    V_5
    IL_000e:  ldc.i4.0
    IL_000f:  stloc.s    V_6
    IL_0011:  ldc.i4.0
    IL_0012:  stloc.s    V_7
    IL_0014:  ldc.i4.0
    IL_0015:  stloc.s    V_8
    IL_0017:  ldc.i4.0
    IL_0018:  stloc.s    V_9
    IL_001a:  ldc.i4.0
    IL_001b:  stloc.s    V_10
    IL_001d:  ldc.i4.0
    IL_001e:  stloc.s    V_11
    IL_0020:  ldarg.1
    IL_0021:  callvirt   instance class Calibration.ICalibrate Calibration.Scanner::get_ICalibration()
    IL_0026:  ldarg.3
    IL_0027:  ldarg.s    iFilmFormat
    IL_0029:  ldloca.s   V_0
    IL_002b:  ldloca.s   V_1
    IL_002d:  ldloca.s   V_2
    IL_002f:  ldloca.s   V_3
    IL_0031:  ldloca.s   V_4
    IL_0033:  ldloca.s   V_5
    IL_0035:  ldloca.s   V_6
    IL_0037:  ldloca.s   V_7
    IL_0039:  ldloca.s   V_8
    IL_003b:  ldloca.s   V_9
    IL_003d:  ldloca.s   V_10
    IL_003f:  ldloca.s   V_11
    IL_0041:  callvirt   instance void Calibration.ICalibrate::GetDpi([Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                      [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&,
                                                                      int32&)
    IL_0046:  ldarg.2
    IL_0047:  ldc.i4.7
    IL_0048:  beq.s      IL_0067

    IL_004a:  ldarg.2
    IL_004b:  ldc.i4.8
    IL_004c:  beq.s      IL_0067

    IL_004e:  ldloc.s    V_7
    IL_0050:  ldloc.3
    IL_0051:  mul
    IL_0052:  ldc.i4     0x3e8
    IL_0057:  div
    IL_0058:  stloc.s    V_7
    IL_005a:  ldloc.s    V_8
    IL_005c:  ldloc.s    V_4
    IL_005e:  mul
    IL_005f:  ldc.i4     0x3e8
    IL_0064:  div
    IL_0065:  stloc.s    V_8
    IL_0067:  ldarg.s    dpiConfig
    IL_0069:  ldloc.s    V_9
    IL_006b:  conv.u2
    IL_006c:  ldloc.s    V_10
    IL_006e:  conv.u2
    IL_006f:  ldloc.s    V_11
    IL_0071:  conv.i2
    IL_0072:  ldloc.2
    IL_0073:  conv.u2
    IL_0074:  ldloc.s    V_7
    IL_0076:  conv.u2
    IL_0077:  ldloc.3
    IL_0078:  conv.u2
    IL_0079:  ldloc.s    V_8
    IL_007b:  conv.u2
    IL_007c:  ldloc.s    V_4
    IL_007e:  conv.u2
    IL_007f:  call       instance void Calibration.DPIConfig::.ctor(uint16,
                                                                    uint16,
                                                                    int16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16)
    IL_0084:  ret
  } // end of method ScannerSettings::LoadDPISetting

  .method public hidebysig instance void 
          PutDpi(class Calibration.Scanner csScanner,
                 class Calibration.ScannerSettings csScannerSettings,
                 [Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                 [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                 bool bCalibrateGroup,
                 bool bCalibrating,
                 bool bWindowing) cil managed
  {
    // Code size       214 (0xd6)
    .maxstack  11
    .locals (valuetype Calibration.DPIConfig V_0,
             int32 V_1,
             int32 V_2,
             int32 V_3,
             int32 V_4,
             int32 V_5)
    IL_0000:  ldarg.0
    IL_0001:  ldarg.s    iFilmFormat
    IL_0003:  ldarg.3
    IL_0004:  call       instance valuetype Calibration.DPIConfig Calibration.ScannerSettings::GetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                                            [Interop.TLXLib]TLXLib.RESOLUTION_000)
    IL_0009:  stloc.0
    IL_000a:  ldarg.s    bCalibrating
    IL_000c:  brtrue.s   IL_0017

    IL_000e:  ldloca.s   V_0
    IL_0010:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0015:  br.s       IL_0018

    IL_0017:  ldc.i4.6
    IL_0018:  stloc.1
    IL_0019:  ldarg.s    bCalibrating
    IL_001b:  brtrue.s   IL_002d

    IL_001d:  ldarg.0
    IL_001e:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0023:  ldarg.3
    IL_0024:  ldarg.s    iFilmFormat
    IL_0026:  call       int32 [Pakon]Pakon.Global::GetResolutionHeight([Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                        [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                        [Interop.TLXLib]TLXLib.FILM_FORMAT_000)
    IL_002b:  br.s       IL_0032

    IL_002d:  ldc.i4     0x841
    IL_0032:  stloc.2
    IL_0033:  ldarg.s    bCalibrating
    IL_0035:  brtrue.s   IL_0045

    IL_0037:  ldarg.0
    IL_0038:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_003d:  ldarg.3
    IL_003e:  call       int32 Calibration.Global::GetPixelWidthToCCD([Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                      [Interop.TLXLib]TLXLib.RESOLUTION_000)
    IL_0043:  br.s       IL_004a

    IL_0045:  ldc.i4     0x841
    IL_004a:  stloc.3
    IL_004b:  ldarg.s    bCalibrating
    IL_004d:  brfalse.s  IL_0079

    IL_004f:  ldarg.3
    IL_0050:  ldc.i4.1
    IL_0051:  bne.un.s   IL_0079

    IL_0053:  ldarg.2
    IL_0054:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0059:  ldc.i4     0x546
    IL_005e:  beq.s      IL_006d

    IL_0060:  ldarg.2
    IL_0061:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0066:  ldc.i4     0x547
    IL_006b:  bne.un.s   IL_0079

    IL_006d:  ldc.i4     0x840
    IL_0072:  stloc.3
    IL_0073:  ldc.i4     0x630
    IL_0078:  stloc.2
    IL_0079:  ldarg.s    bCalibrating
    IL_007b:  brfalse.s  IL_008c

    IL_007d:  ldarg.3
    IL_007e:  brtrue.s   IL_008c

    IL_0080:  ldloc.1
    IL_0081:  ldc.i4.2
    IL_0082:  div
    IL_0083:  stloc.1
    IL_0084:  ldloc.2
    IL_0085:  ldc.i4.2
    IL_0086:  div
    IL_0087:  stloc.2
    IL_0088:  ldloc.3
    IL_0089:  ldc.i4.2
    IL_008a:  div
    IL_008b:  stloc.3
    IL_008c:  ldarg.s    bWindowing
    IL_008e:  brtrue.s   IL_0099

    IL_0090:  ldloca.s   V_0
    IL_0092:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0097:  br.s       IL_009e

    IL_0099:  ldc.i4     0x258
    IL_009e:  stloc.s    V_4
    IL_00a0:  ldarg.s    bWindowing
    IL_00a2:  brtrue.s   IL_00ad

    IL_00a4:  ldloca.s   V_0
    IL_00a6:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_00ab:  br.s       IL_00ae

    IL_00ad:  ldc.i4.0
    IL_00ae:  stloc.s    V_5
    IL_00b0:  ldarg.1
    IL_00b1:  callvirt   instance class Calibration.ICalibrate Calibration.Scanner::get_ICalibration()
    IL_00b6:  ldarg.3
    IL_00b7:  ldarg.s    iFilmFormat
    IL_00b9:  ldarg.s    bCalibrateGroup
    IL_00bb:  ldloc.3
    IL_00bc:  ldloc.2
    IL_00bd:  ldloc.1
    IL_00be:  ldloca.s   V_0
    IL_00c0:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_00c5:  ldloca.s   V_0
    IL_00c7:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_00cc:  ldloc.s    V_5
    IL_00ce:  ldloc.s    V_4
    IL_00d0:  callvirt   instance void Calibration.ICalibrate::PutDpi([Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                      [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                      bool,
                                                                      int32,
                                                                      int32,
                                                                      int32,
                                                                      int32,
                                                                      int32,
                                                                      int32,
                                                                      int32)
    IL_00d5:  ret
  } // end of method ScannerSettings::PutDpi

  .method public hidebysig instance void 
          AdvanceFilm(class Calibration.Scanner csScanner,
                      bool bLongTime) cil managed
  {
    // Code size       150 (0x96)
    .maxstack  3
    .locals (int32 V_0,
             int32 V_1,
             [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_2,
             [Pakon]Pakon.ScannerHW235 V_3)
    IL_0000:  ldarg.2
    IL_0001:  brtrue.s   IL_000a

    IL_0003:  ldc.i4     0xbb8
    IL_0008:  br.s       IL_000f

    IL_000a:  ldc.i4     0x2ee0
    IL_000f:  stloc.0
    IL_0010:  ldc.i4.0
    IL_0011:  stloc.1
    IL_0012:  ldarg.0
    IL_0013:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0018:  stloc.2
    IL_0019:  ldloc.2
    IL_001a:  ldc.i4.7
    IL_001b:  sub
    IL_001c:  switch     ( 
                          IL_005b,
                          IL_005b)
    IL_0029:  ldloc.2
    IL_002a:  ldc.i4     0x546
    IL_002f:  sub
    IL_0030:  switch     ( 
                          IL_0053,
                          IL_0053)
    IL_003d:  ldloc.2
    IL_003e:  ldc.i4     0xd16
    IL_0043:  sub
    IL_0044:  switch     ( 
                          IL_0082,
                          IL_0082)
    IL_0051:  br.s       IL_0088

    IL_0053:  ldc.i4     0x2710
    IL_0058:  stloc.1
    IL_0059:  br.s       IL_0088

    IL_005b:  ldarg.0
    IL_005c:  call       instance [Pakon]Pakon.ScannerHW235 [Pakon]Pakon.ScannerSettings::get_Hardware235()
    IL_0061:  stloc.3
    IL_0062:  ldloc.3
    IL_0063:  ldc.i4     0x3e8
    IL_0068:  beq.s      IL_0072

    IL_006a:  ldloc.3
    IL_006b:  ldc.i4     0x44c
    IL_0070:  bne.un.s   IL_007a

    IL_0072:  ldc.i4     0x6ef
    IL_0077:  stloc.1
    IL_0078:  br.s       IL_0088

    IL_007a:  ldc.i4     0x3f7
    IL_007f:  stloc.1
    IL_0080:  br.s       IL_0088

    IL_0082:  ldc.i4     0x6ef
    IL_0087:  stloc.1
    IL_0088:  ldarg.1
    IL_0089:  callvirt   instance class Calibration.ICalibrate Calibration.Scanner::get_ICalibration()
    IL_008e:  ldloc.0
    IL_008f:  ldloc.1
    IL_0090:  callvirt   instance void Calibration.ICalibrate::AdvanceFilm(int32,
                                                                           int32)
    IL_0095:  ret
  } // end of method ScannerSettings::AdvanceFilm

  .method public hidebysig instance bool 
          FineFocusResults(class Calibration.Scanner csScanner,
                           [Interop.TLXLib]TLXLib.RESOLUTION_000 prResolution,
                           [Interop.TLXLib]TLXLib.FILM_FORMAT_000 ffFormat) cil managed
  {
    // Code size       192 (0xc0)
    .maxstack  8
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2,
             valuetype Calibration.DPIConfig V_3,
             int16 V_4)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldc.i4.0
    IL_0003:  stloc.1
    IL_0004:  ldc.i4.0
    IL_0005:  stloc.2
    IL_0006:  ldarg.1
    IL_0007:  callvirt   instance class Calibration.ICalibrate Calibration.Scanner::get_ICalibration()
    IL_000c:  ldloca.s   V_0
    IL_000e:  ldloca.s   V_2
    IL_0010:  ldloca.s   V_2
    IL_0012:  ldloca.s   V_1
    IL_0014:  ldloca.s   V_2
    IL_0016:  ldloca.s   V_2
    IL_0018:  ldloca.s   V_2
    IL_001a:  callvirt   instance void Calibration.ICalibrate::FocusResults(int32&,
                                                                            int32&,
                                                                            int32&,
                                                                            int32&,
                                                                            int32&,
                                                                            int32&,
                                                                            int32&)
    IL_001f:  ldloc.0
    IL_0020:  brtrue.s   IL_002a

    IL_0022:  ldloc.1
    IL_0023:  ldc.i4.s   50
    IL_0025:  add
    IL_0026:  ldc.i4.s   100
    IL_0028:  div
    IL_0029:  stloc.1
    IL_002a:  ldarg.0
    IL_002b:  ldarg.3
    IL_002c:  ldarg.2
    IL_002d:  call       instance valuetype Calibration.DPIConfig Calibration.ScannerSettings::GetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                                            [Interop.TLXLib]TLXLib.RESOLUTION_000)
    IL_0032:  stloc.3
    IL_0033:  ldloc.1
    IL_0034:  ldc.i4.s   50
    IL_0036:  sub
    IL_0037:  conv.i2
    IL_0038:  stloc.s    V_4
    IL_003a:  ldloc.s    V_4
    IL_003c:  ldc.i4.0
    IL_003d:  ble.s      IL_0053

    IL_003f:  ldloca.s   V_3
    IL_0041:  dup
    IL_0042:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0047:  ldloc.s    V_4
    IL_0049:  conv.u2
    IL_004a:  add
    IL_004b:  conv.u2
    IL_004c:  stfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0051:  br.s       IL_006a

    IL_0053:  ldloca.s   V_3
    IL_0055:  dup
    IL_0056:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_005b:  ldloc.s    V_4
    IL_005d:  call       int16 [mscorlib]System.Math::Abs(int16)
    IL_0062:  conv.u2
    IL_0063:  sub
    IL_0064:  conv.u2
    IL_0065:  stfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_006a:  ldarg.0
    IL_006b:  ldarg.3
    IL_006c:  ldarg.2
    IL_006d:  ldloc.3
    IL_006e:  call       instance void Calibration.ScannerSettings::SetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                 [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                 valuetype Calibration.DPIConfig)
    IL_0073:  ldc.i4.2
    IL_0074:  ldarg.2
    IL_0075:  bne.un.s   IL_00b9

    IL_0077:  ldarg.0
    IL_0078:  ldarg.3
    IL_0079:  ldc.i4.0
    IL_007a:  call       instance valuetype Calibration.DPIConfig Calibration.ScannerSettings::GetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                                            [Interop.TLXLib]TLXLib.RESOLUTION_000)
    IL_007f:  stloc.3
    IL_0080:  ldloc.s    V_4
    IL_0082:  ldc.i4.0
    IL_0083:  ble.s      IL_0099

    IL_0085:  ldloca.s   V_3
    IL_0087:  dup
    IL_0088:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_008d:  ldloc.s    V_4
    IL_008f:  conv.u2
    IL_0090:  add
    IL_0091:  conv.u2
    IL_0092:  stfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0097:  br.s       IL_00b0

    IL_0099:  ldloca.s   V_3
    IL_009b:  dup
    IL_009c:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_00a1:  ldloc.s    V_4
    IL_00a3:  call       int16 [mscorlib]System.Math::Abs(int16)
    IL_00a8:  conv.u2
    IL_00a9:  sub
    IL_00aa:  conv.u2
    IL_00ab:  stfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_00b0:  ldarg.0
    IL_00b1:  ldarg.3
    IL_00b2:  ldc.i4.0
    IL_00b3:  ldloc.3
    IL_00b4:  call       instance void Calibration.ScannerSettings::SetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                 [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                 valuetype Calibration.DPIConfig)
    IL_00b9:  ldloc.0
    IL_00ba:  brfalse.s  IL_00be

    IL_00bc:  ldc.i4.0
    IL_00bd:  ret

    IL_00be:  ldc.i4.1
    IL_00bf:  ret
  } // end of method ScannerSettings::FineFocusResults

  .method public hidebysig instance bool 
          TiltResults(class Calibration.Scanner csScanner,
                      [Interop.TLXLib]TLXLib.RESOLUTION_000 prResolution,
                      [Interop.TLXLib]TLXLib.FILM_FORMAT_000 ffFormat,
                      [out] int32& iEighthsTurns) cil managed
  {
    // Code size       172 (0xac)
    .maxstack  8
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2,
             int32 V_3,
             int32 V_4,
             int32 V_5,
             valuetype Calibration.DPIConfig V_6,
             int16 V_7)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldc.i4.0
    IL_0003:  stloc.1
    IL_0004:  ldc.i4.0
    IL_0005:  stloc.2
    IL_0006:  ldc.i4.0
    IL_0007:  stloc.3
    IL_0008:  ldc.i4.0
    IL_0009:  stloc.s    V_4
    IL_000b:  ldarg.s    iEighthsTurns
    IL_000d:  ldc.i4.0
    IL_000e:  stind.i4
    IL_000f:  ldarg.1
    IL_0010:  callvirt   instance class Calibration.ICalibrate Calibration.Scanner::get_ICalibration()
    IL_0015:  ldloca.s   V_0
    IL_0017:  ldloca.s   V_1
    IL_0019:  ldloca.s   V_2
    IL_001b:  ldloca.s   V_0
    IL_001d:  ldloca.s   V_3
    IL_001f:  ldloca.s   V_4
    IL_0021:  ldarg.s    iEighthsTurns
    IL_0023:  callvirt   instance void Calibration.ICalibrate::FocusResults(int32&,
                                                                            int32&,
                                                                            int32&,
                                                                            int32&,
                                                                            int32&,
                                                                            int32&,
                                                                            int32&)
    IL_0028:  ldloc.1
    IL_0029:  brtrue.s   IL_002e

    IL_002b:  ldloc.2
    IL_002c:  brfalse.s  IL_00a2

    IL_002e:  ldloc.1
    IL_002f:  brtrue.s   IL_0039

    IL_0031:  ldloc.3
    IL_0032:  ldc.i4.s   50
    IL_0034:  add
    IL_0035:  ldc.i4.s   100
    IL_0037:  div
    IL_0038:  stloc.3
    IL_0039:  ldloc.2
    IL_003a:  brtrue.s   IL_0046

    IL_003c:  ldloc.s    V_4
    IL_003e:  ldc.i4.s   50
    IL_0040:  add
    IL_0041:  ldc.i4.s   100
    IL_0043:  div
    IL_0044:  stloc.s    V_4
    IL_0046:  ldloc.3
    IL_0047:  ldloc.s    V_4
    IL_0049:  add
    IL_004a:  ldc.i4.2
    IL_004b:  div
    IL_004c:  stloc.s    V_5
    IL_004e:  ldarg.0
    IL_004f:  ldarg.3
    IL_0050:  ldarg.2
    IL_0051:  call       instance valuetype Calibration.DPIConfig Calibration.ScannerSettings::GetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                                            [Interop.TLXLib]TLXLib.RESOLUTION_000)
    IL_0056:  stloc.s    V_6
    IL_0058:  ldloc.s    V_5
    IL_005a:  ldc.i4.s   50
    IL_005c:  sub
    IL_005d:  conv.i2
    IL_005e:  stloc.s    V_7
    IL_0060:  ldloc.s    V_7
    IL_0062:  ldc.i4.0
    IL_0063:  ble.s      IL_0079

    IL_0065:  ldloca.s   V_6
    IL_0067:  dup
    IL_0068:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_006d:  ldloc.s    V_7
    IL_006f:  conv.u2
    IL_0070:  add
    IL_0071:  conv.u2
    IL_0072:  stfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0077:  br.s       IL_0090

    IL_0079:  ldloca.s   V_6
    IL_007b:  dup
    IL_007c:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0081:  ldloc.s    V_7
    IL_0083:  call       int16 [mscorlib]System.Math::Abs(int16)
    IL_0088:  conv.u2
    IL_0089:  sub
    IL_008a:  conv.u2
    IL_008b:  stfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0090:  ldarg.0
    IL_0091:  ldarg.3
    IL_0092:  ldarg.2
    IL_0093:  ldloc.s    V_6
    IL_0095:  call       instance void Calibration.ScannerSettings::SetDPIConfig([Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                                 [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                 valuetype Calibration.DPIConfig)
    IL_009a:  ldarg.s    iEighthsTurns
    IL_009c:  ldc.i4     0xfffffc18
    IL_00a1:  stind.i4
    IL_00a2:  ldloc.1
    IL_00a3:  brtrue.s   IL_00a8

    IL_00a5:  ldloc.2
    IL_00a6:  brfalse.s  IL_00aa

    IL_00a8:  ldc.i4.0
    IL_00a9:  ret

    IL_00aa:  ldc.i4.1
    IL_00ab:  ret
  } // end of method ScannerSettings::TiltResults

  .method public hidebysig instance bool 
          CompleteLLCInitialization(class Calibration.Scanner csScanner) cil managed
  {
    // Code size       51 (0x33)
    .maxstack  7
    .locals (bool V_0)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      class Calibration.ScannerSettingsFirmware Calibration.ScannerSettings::m_csFirmwareSettings
    IL_0006:  ldarg.1
    IL_0007:  ldarg.0
    IL_0008:  ldflda     [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::m_stType
    IL_000d:  ldarg.0
    IL_000e:  ldflda     int32 [Pakon]Pakon.ScannerSettings::m_nSerialNumber
    IL_0013:  ldarg.0
    IL_0014:  ldflda     [Pakon]Pakon.ScannerHW135 [Pakon]Pakon.ScannerSettings::m_sh135
    IL_0019:  ldarg.0
    IL_001a:  ldflda     [Pakon]Pakon.ScannerHW235 [Pakon]Pakon.ScannerSettings::m_sh235
    IL_001f:  ldarg.0
    IL_0020:  ldflda     [Pakon]Pakon.ScannerHW335 [Pakon]Pakon.ScannerSettings::m_sh335
    IL_0025:  callvirt   instance bool Calibration.ScannerSettingsFirmware::GetInformation(class Calibration.Scanner,
                                                                                           [Interop.TLXLib]TLXLib.SCANNER_TYPE_000&,
                                                                                           int32&,
                                                                                           [Pakon]Pakon.ScannerHW135&,
                                                                                           [Pakon]Pakon.ScannerHW235&,
                                                                                           [Pakon]Pakon.ScannerHW335&)
    IL_002a:  stloc.0
    IL_002b:  ldarg.0
    IL_002c:  call       instance void [Pakon]Pakon.ScannerSettings::SetCapabilities()
    IL_0031:  ldloc.0
    IL_0032:  ret
  } // end of method ScannerSettings::CompleteLLCInitialization

  .method public hidebysig instance void 
          CompleteTLXInitialization(class Calibration.Scanner csScanner) cil managed
  {
    // Code size       26 (0x1a)
    .maxstack  2
    .locals (string V_0)
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  call       instance void [Pakon]Pakon.ScannerSettings::CompleteTLXInitialization([Pakon]Pakon.Scanner)
    IL_0007:  ldstr      "~TLA key to complete calibration~"
    IL_000c:  stloc.0
    IL_000d:  ldarg.1
    IL_000e:  callvirt   instance class Calibration.ICalibrate Calibration.Scanner::get_ICalibration()
    IL_0013:  ldloc.0
    IL_0014:  callvirt   instance void Calibration.ICalibrate::Enable(string)
    IL_0019:  ret
  } // end of method ScannerSettings::CompleteTLXInitialization

  .method public hidebysig instance void 
          SetIntBits([Pakon]Pakon.IntBits ibEEProm,
                     [Pakon]Pakon.IntBits ibColorNeg,
                     [Pakon]Pakon.IntBits ibColorPos) cil managed
  {
    // Code size       37 (0x25)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibEEPromInvalid
    IL_0006:  ldarg.1
    IL_0007:  callvirt   instance void [Pakon]Pakon.IntBits::Equals([Pakon]Pakon.IntBits)
    IL_000c:  ldarg.0
    IL_000d:  ldfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibColorNegInvalid
    IL_0012:  ldarg.2
    IL_0013:  callvirt   instance void [Pakon]Pakon.IntBits::Equals([Pakon]Pakon.IntBits)
    IL_0018:  ldarg.0
    IL_0019:  ldfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibColorPosInvalid
    IL_001e:  ldarg.3
    IL_001f:  callvirt   instance void [Pakon]Pakon.IntBits::Equals([Pakon]Pakon.IntBits)
    IL_0024:  ret
  } // end of method ScannerSettings::SetIntBits

  .method public hidebysig instance void 
          SetData(class Calibration.TLXRegistryFile rf) cil managed
  {
    // Code size       1194 (0x4aa)
    .maxstack  31
    .locals (valuetype Calibration.DPIConfig V_0,
             valuetype Calibration.ColorMatrixConfig V_1)
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  callvirt   instance [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::get_EEProm()
    IL_0007:  ldarg.1
    IL_0008:  callvirt   instance [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::get_ColorNeg()
    IL_000d:  ldarg.1
    IL_000e:  callvirt   instance [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::get_ColorPos()
    IL_0013:  call       instance void Calibration.ScannerSettings::SetIntBits([Pakon]Pakon.IntBits,
                                                                               [Pakon]Pakon.IntBits,
                                                                               [Pakon]Pakon.IntBits)
    IL_0018:  ldarg.0
    IL_0019:  ldarg.1
    IL_001a:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Calibration.TLXRegistryFile::get_ScannerType()
    IL_001f:  stfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::m_stType
    IL_0024:  ldarg.0
    IL_0025:  ldarg.1
    IL_0026:  callvirt   instance int32 Calibration.TLXRegistryFile::get_ScannerSerialNumber()
    IL_002b:  stfld      int32 [Pakon]Pakon.ScannerSettings::m_nSerialNumber
    IL_0030:  ldarg.0
    IL_0031:  ldarg.1
    IL_0032:  callvirt   instance [Pakon]Pakon.ScannerHW135 Calibration.TLXRegistryFile::get_ScannerHW135()
    IL_0037:  stfld      [Pakon]Pakon.ScannerHW135 [Pakon]Pakon.ScannerSettings::m_sh135
    IL_003c:  ldarg.0
    IL_003d:  ldarg.1
    IL_003e:  callvirt   instance [Pakon]Pakon.ScannerHW235 Calibration.TLXRegistryFile::get_ScannerHW235()
    IL_0043:  stfld      [Pakon]Pakon.ScannerHW235 [Pakon]Pakon.ScannerSettings::m_sh235
    IL_0048:  ldarg.0
    IL_0049:  ldarg.1
    IL_004a:  callvirt   instance [Pakon]Pakon.ScannerHW335 Calibration.TLXRegistryFile::get_ScannerHW335()
    IL_004f:  stfld      [Pakon]Pakon.ScannerHW335 [Pakon]Pakon.ScannerSettings::m_sh335
    IL_0054:  ldarg.1
    IL_0055:  callvirt   instance valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::get_Base16_35mm()
    IL_005a:  stloc.0
    IL_005b:  ldarg.0
    IL_005c:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm16Base
    IL_0061:  ldloca.s   V_0
    IL_0063:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_0068:  ldloca.s   V_0
    IL_006a:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_006f:  ldc.i4.0
    IL_0070:  ldloca.s   V_0
    IL_0072:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0077:  ldloca.s   V_0
    IL_0079:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_007e:  ldc.i4     0x3e8
    IL_0083:  ldloca.s   V_0
    IL_0085:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_008a:  ldc.i4     0x3e8
    IL_008f:  call       instance void Calibration.DPIConfig::.ctor(uint16,
                                                                    uint16,
                                                                    int16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16)
    IL_0094:  ldarg.1
    IL_0095:  callvirt   instance valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::get_Base8_35mm()
    IL_009a:  stloc.0
    IL_009b:  ldarg.0
    IL_009c:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_00a1:  ldloca.s   V_0
    IL_00a3:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_00a8:  ldloca.s   V_0
    IL_00aa:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_00af:  ldc.i4.0
    IL_00b0:  ldloca.s   V_0
    IL_00b2:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_00b7:  ldloca.s   V_0
    IL_00b9:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_00be:  ldc.i4     0x3e8
    IL_00c3:  ldloca.s   V_0
    IL_00c5:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_00ca:  ldc.i4     0x3e8
    IL_00cf:  call       instance void Calibration.DPIConfig::.ctor(uint16,
                                                                    uint16,
                                                                    int16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16)
    IL_00d4:  ldarg.1
    IL_00d5:  callvirt   instance valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::get_Base4_35mm()
    IL_00da:  stloc.0
    IL_00db:  ldarg.0
    IL_00dc:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm4Base
    IL_00e1:  ldloca.s   V_0
    IL_00e3:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_00e8:  ldloca.s   V_0
    IL_00ea:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_00ef:  ldc.i4.0
    IL_00f0:  ldloca.s   V_0
    IL_00f2:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_00f7:  ldloca.s   V_0
    IL_00f9:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_00fe:  ldc.i4     0x3e8
    IL_0103:  ldloca.s   V_0
    IL_0105:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_010a:  ldc.i4     0x3e8
    IL_010f:  call       instance void Calibration.DPIConfig::.ctor(uint16,
                                                                    uint16,
                                                                    int16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16)
    IL_0114:  ldarg.1
    IL_0115:  callvirt   instance valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::get_Base16_24mm()
    IL_011a:  stloc.0
    IL_011b:  ldarg.0
    IL_011c:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm16Base
    IL_0121:  ldloca.s   V_0
    IL_0123:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_0128:  ldloca.s   V_0
    IL_012a:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_012f:  ldc.i4.0
    IL_0130:  ldloca.s   V_0
    IL_0132:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0137:  ldloca.s   V_0
    IL_0139:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_013e:  ldc.i4     0x3e8
    IL_0143:  ldloca.s   V_0
    IL_0145:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_014a:  ldc.i4     0x3e8
    IL_014f:  call       instance void Calibration.DPIConfig::.ctor(uint16,
                                                                    uint16,
                                                                    int16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16)
    IL_0154:  ldarg.1
    IL_0155:  callvirt   instance valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::get_Base8_24mm()
    IL_015a:  stloc.0
    IL_015b:  ldarg.0
    IL_015c:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm8Base
    IL_0161:  ldloca.s   V_0
    IL_0163:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_0168:  ldloca.s   V_0
    IL_016a:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_016f:  ldc.i4.0
    IL_0170:  ldloca.s   V_0
    IL_0172:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0177:  ldloca.s   V_0
    IL_0179:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_017e:  ldc.i4     0x3e8
    IL_0183:  ldloca.s   V_0
    IL_0185:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_018a:  ldc.i4     0x3e8
    IL_018f:  call       instance void Calibration.DPIConfig::.ctor(uint16,
                                                                    uint16,
                                                                    int16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16)
    IL_0194:  ldarg.1
    IL_0195:  callvirt   instance valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::get_Base4_24mm()
    IL_019a:  stloc.0
    IL_019b:  ldarg.0
    IL_019c:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm4Base
    IL_01a1:  ldloca.s   V_0
    IL_01a3:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_01a8:  ldloca.s   V_0
    IL_01aa:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_01af:  ldc.i4.0
    IL_01b0:  ldloca.s   V_0
    IL_01b2:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_01b7:  ldloca.s   V_0
    IL_01b9:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_01be:  ldc.i4     0x3e8
    IL_01c3:  ldloca.s   V_0
    IL_01c5:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_01ca:  ldc.i4     0x3e8
    IL_01cf:  call       instance void Calibration.DPIConfig::.ctor(uint16,
                                                                    uint16,
                                                                    int16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16,
                                                                    uint16)
    IL_01d4:  ldarg.1
    IL_01d5:  callvirt   instance valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::get_MatrixNeg()
    IL_01da:  stloc.1
    IL_01db:  ldloca.s   V_1
    IL_01dd:  ldfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_01e2:  ldc.i4.1
    IL_01e3:  bne.un.s   IL_0249

    IL_01e5:  ldarg.0
    IL_01e6:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_01eb:  ldloca.s   V_1
    IL_01ed:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_0
    IL_01f2:  ldloca.s   V_1
    IL_01f4:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_1
    IL_01f9:  ldloca.s   V_1
    IL_01fb:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_2
    IL_0200:  ldloca.s   V_1
    IL_0202:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_3
    IL_0207:  ldloca.s   V_1
    IL_0209:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_0
    IL_020e:  ldloca.s   V_1
    IL_0210:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_1
    IL_0215:  ldloca.s   V_1
    IL_0217:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_2
    IL_021c:  ldloca.s   V_1
    IL_021e:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_3
    IL_0223:  ldloca.s   V_1
    IL_0225:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_0
    IL_022a:  ldloca.s   V_1
    IL_022c:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_1
    IL_0231:  ldloca.s   V_1
    IL_0233:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_2
    IL_0238:  ldloca.s   V_1
    IL_023a:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_3
    IL_023f:  call       instance void Calibration.ColorMatrixConfig::.ctor(float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64)
    IL_0244:  br         IL_0341

    IL_0249:  ldloca.s   V_1
    IL_024b:  ldfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_0250:  ldc.i4.2
    IL_0251:  bne.un     IL_0335

    IL_0256:  ldarg.0
    IL_0257:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_025c:  ldloca.s   V_1
    IL_025e:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_0
    IL_0263:  ldloca.s   V_1
    IL_0265:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_1
    IL_026a:  ldloca.s   V_1
    IL_026c:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_2
    IL_0271:  ldloca.s   V_1
    IL_0273:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_3
    IL_0278:  ldloca.s   V_1
    IL_027a:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_4
    IL_027f:  ldloca.s   V_1
    IL_0281:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_5
    IL_0286:  ldloca.s   V_1
    IL_0288:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_6
    IL_028d:  ldloca.s   V_1
    IL_028f:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_7
    IL_0294:  ldloca.s   V_1
    IL_0296:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_8
    IL_029b:  ldloca.s   V_1
    IL_029d:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_9
    IL_02a2:  ldloca.s   V_1
    IL_02a4:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_0
    IL_02a9:  ldloca.s   V_1
    IL_02ab:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_1
    IL_02b0:  ldloca.s   V_1
    IL_02b2:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_2
    IL_02b7:  ldloca.s   V_1
    IL_02b9:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_3
    IL_02be:  ldloca.s   V_1
    IL_02c0:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_4
    IL_02c5:  ldloca.s   V_1
    IL_02c7:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_5
    IL_02cc:  ldloca.s   V_1
    IL_02ce:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_6
    IL_02d3:  ldloca.s   V_1
    IL_02d5:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_7
    IL_02da:  ldloca.s   V_1
    IL_02dc:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_8
    IL_02e1:  ldloca.s   V_1
    IL_02e3:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_9
    IL_02e8:  ldloca.s   V_1
    IL_02ea:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_0
    IL_02ef:  ldloca.s   V_1
    IL_02f1:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_1
    IL_02f6:  ldloca.s   V_1
    IL_02f8:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_2
    IL_02fd:  ldloca.s   V_1
    IL_02ff:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_3
    IL_0304:  ldloca.s   V_1
    IL_0306:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_4
    IL_030b:  ldloca.s   V_1
    IL_030d:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_5
    IL_0312:  ldloca.s   V_1
    IL_0314:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_6
    IL_0319:  ldloca.s   V_1
    IL_031b:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_7
    IL_0320:  ldloca.s   V_1
    IL_0322:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_8
    IL_0327:  ldloca.s   V_1
    IL_0329:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_9
    IL_032e:  call       instance void Calibration.ColorMatrixConfig::.ctor(float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32)
    IL_0333:  br.s       IL_0341

    IL_0335:  ldarg.0
    IL_0336:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_033b:  initobj    Calibration.ColorMatrixConfig
    IL_0341:  ldarg.1
    IL_0342:  callvirt   instance valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::get_MatrixPos()
    IL_0347:  stloc.1
    IL_0348:  ldloca.s   V_1
    IL_034a:  ldfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_034f:  ldc.i4.1
    IL_0350:  bne.un.s   IL_03b2

    IL_0352:  ldarg.0
    IL_0353:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0358:  ldloca.s   V_1
    IL_035a:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_0
    IL_035f:  ldloca.s   V_1
    IL_0361:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_1
    IL_0366:  ldloca.s   V_1
    IL_0368:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_2
    IL_036d:  ldloca.s   V_1
    IL_036f:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_3
    IL_0374:  ldloca.s   V_1
    IL_0376:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_0
    IL_037b:  ldloca.s   V_1
    IL_037d:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_1
    IL_0382:  ldloca.s   V_1
    IL_0384:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_2
    IL_0389:  ldloca.s   V_1
    IL_038b:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_3
    IL_0390:  ldloca.s   V_1
    IL_0392:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_0
    IL_0397:  ldloca.s   V_1
    IL_0399:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_1
    IL_039e:  ldloca.s   V_1
    IL_03a0:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_2
    IL_03a5:  ldloca.s   V_1
    IL_03a7:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_3
    IL_03ac:  call       instance void Calibration.ColorMatrixConfig::.ctor(float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64,
                                                                            float64)
    IL_03b1:  ret

    IL_03b2:  ldloca.s   V_1
    IL_03b4:  ldfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_03b9:  ldc.i4.2
    IL_03ba:  bne.un     IL_049d

    IL_03bf:  ldarg.0
    IL_03c0:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_03c5:  ldloca.s   V_1
    IL_03c7:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_0
    IL_03cc:  ldloca.s   V_1
    IL_03ce:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_1
    IL_03d3:  ldloca.s   V_1
    IL_03d5:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_2
    IL_03da:  ldloca.s   V_1
    IL_03dc:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_3
    IL_03e1:  ldloca.s   V_1
    IL_03e3:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_4
    IL_03e8:  ldloca.s   V_1
    IL_03ea:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_5
    IL_03ef:  ldloca.s   V_1
    IL_03f1:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_6
    IL_03f6:  ldloca.s   V_1
    IL_03f8:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_7
    IL_03fd:  ldloca.s   V_1
    IL_03ff:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_8
    IL_0404:  ldloca.s   V_1
    IL_0406:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_9
    IL_040b:  ldloca.s   V_1
    IL_040d:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_0
    IL_0412:  ldloca.s   V_1
    IL_0414:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_1
    IL_0419:  ldloca.s   V_1
    IL_041b:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_2
    IL_0420:  ldloca.s   V_1
    IL_0422:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_3
    IL_0427:  ldloca.s   V_1
    IL_0429:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_4
    IL_042e:  ldloca.s   V_1
    IL_0430:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_5
    IL_0435:  ldloca.s   V_1
    IL_0437:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_6
    IL_043c:  ldloca.s   V_1
    IL_043e:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_7
    IL_0443:  ldloca.s   V_1
    IL_0445:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_8
    IL_044a:  ldloca.s   V_1
    IL_044c:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_9
    IL_0451:  ldloca.s   V_1
    IL_0453:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_0
    IL_0458:  ldloca.s   V_1
    IL_045a:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_1
    IL_045f:  ldloca.s   V_1
    IL_0461:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_2
    IL_0466:  ldloca.s   V_1
    IL_0468:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_3
    IL_046d:  ldloca.s   V_1
    IL_046f:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_4
    IL_0474:  ldloca.s   V_1
    IL_0476:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_5
    IL_047b:  ldloca.s   V_1
    IL_047d:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_6
    IL_0482:  ldloca.s   V_1
    IL_0484:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_7
    IL_0489:  ldloca.s   V_1
    IL_048b:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_8
    IL_0490:  ldloca.s   V_1
    IL_0492:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_9
    IL_0497:  call       instance void Calibration.ColorMatrixConfig::.ctor(float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32,
                                                                            float32)
    IL_049c:  ret

    IL_049d:  ldarg.0
    IL_049e:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_04a3:  initobj    Calibration.ColorMatrixConfig
    IL_04a9:  ret
  } // end of method ScannerSettings::SetData

  .method public hidebysig instance void 
          ValidateOffsets([Pakon]Pakon.IntBits ibInvalid) cil managed
  {
    // Code size       439 (0x1b7)
    .maxstack  3
    .locals (valuetype Calibration.OffsetNominalValues V_0,
             [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_1)
    IL_0000:  ldarg.0
    IL_0001:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0006:  stloc.1
    IL_0007:  ldloc.1
    IL_0008:  ldc.i4.7
    IL_0009:  sub
    IL_000a:  switch     ( 
                          IL_0049,
                          IL_0049)
    IL_0017:  ldloc.1
    IL_0018:  ldc.i4     0x546
    IL_001d:  sub
    IL_001e:  switch     ( 
                          IL_0041,
                          IL_0041)
    IL_002b:  ldloc.1
    IL_002c:  ldc.i4     0xd16
    IL_0031:  sub
    IL_0032:  switch     ( 
                          IL_0051,
                          IL_0051)
    IL_003f:  br.s       IL_0059

    IL_0041:  ldsfld     valuetype Calibration.OffsetNominalValues Calibration.Global::m_ovF135
    IL_0046:  stloc.0
    IL_0047:  br.s       IL_0064

    IL_0049:  ldsfld     valuetype Calibration.OffsetNominalValues Calibration.Global::m_ovFX35
    IL_004e:  stloc.0
    IL_004f:  br.s       IL_0064

    IL_0051:  ldsfld     valuetype Calibration.OffsetNominalValues Calibration.Global::m_ovFX35
    IL_0056:  stloc.0
    IL_0057:  br.s       IL_0064

    IL_0059:  ldstr      "Invalid Scanner Type"
    IL_005e:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0063:  throw

    IL_0064:  ldarg.0
    IL_0065:  ldc.i4.s   28
    IL_0067:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_006c:  brfalse.s  IL_00a4

    IL_006e:  ldarg.0
    IL_006f:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm4Base
    IL_0074:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0079:  ldloca.s   V_0
    IL_007b:  ldfld      uint16 Calibration.OffsetNominalValues::m_us24mm4b
    IL_0080:  ldc.i4.s   100
    IL_0082:  sub
    IL_0083:  blt.s      IL_009c

    IL_0085:  ldarg.0
    IL_0086:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm4Base
    IL_008b:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0090:  ldloca.s   V_0
    IL_0092:  ldfld      uint16 Calibration.OffsetNominalValues::m_us24mm4b
    IL_0097:  ldc.i4.s   100
    IL_0099:  add
    IL_009a:  ble.s      IL_00a4

    IL_009c:  ldarg.1
    IL_009d:  ldc.i4.0
    IL_009e:  ldc.i4.1
    IL_009f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_00a4:  ldarg.0
    IL_00a5:  ldc.i4.s   27
    IL_00a7:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_00ac:  brfalse.s  IL_00e4

    IL_00ae:  ldarg.0
    IL_00af:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm8Base
    IL_00b4:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_00b9:  ldloca.s   V_0
    IL_00bb:  ldfld      uint16 Calibration.OffsetNominalValues::m_us24mm8b
    IL_00c0:  ldc.i4.s   100
    IL_00c2:  sub
    IL_00c3:  blt.s      IL_00dc

    IL_00c5:  ldarg.0
    IL_00c6:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm8Base
    IL_00cb:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_00d0:  ldloca.s   V_0
    IL_00d2:  ldfld      uint16 Calibration.OffsetNominalValues::m_us24mm8b
    IL_00d7:  ldc.i4.s   100
    IL_00d9:  add
    IL_00da:  ble.s      IL_00e4

    IL_00dc:  ldarg.1
    IL_00dd:  ldc.i4.1
    IL_00de:  ldc.i4.1
    IL_00df:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_00e4:  ldarg.0
    IL_00e5:  ldc.i4.s   26
    IL_00e7:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_00ec:  brfalse.s  IL_0124

    IL_00ee:  ldarg.0
    IL_00ef:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm16Base
    IL_00f4:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_00f9:  ldloca.s   V_0
    IL_00fb:  ldfld      uint16 Calibration.OffsetNominalValues::m_us24mm16b
    IL_0100:  ldc.i4.s   100
    IL_0102:  sub
    IL_0103:  blt.s      IL_011c

    IL_0105:  ldarg.0
    IL_0106:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm16Base
    IL_010b:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0110:  ldloca.s   V_0
    IL_0112:  ldfld      uint16 Calibration.OffsetNominalValues::m_us24mm16b
    IL_0117:  ldc.i4.s   100
    IL_0119:  add
    IL_011a:  ble.s      IL_0124

    IL_011c:  ldarg.1
    IL_011d:  ldc.i4.2
    IL_011e:  ldc.i4.1
    IL_011f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0124:  ldarg.0
    IL_0125:  ldc.i4.s   31
    IL_0127:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_012c:  brfalse.s  IL_014d

    IL_012e:  ldarg.0
    IL_012f:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm4Base
    IL_0134:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0139:  ldloca.s   V_0
    IL_013b:  ldfld      uint16 Calibration.OffsetNominalValues::m_us35mm4b
    IL_0140:  ldc.i4.s   100
    IL_0142:  add
    IL_0143:  ble.s      IL_014d

    IL_0145:  ldarg.1
    IL_0146:  ldc.i4.3
    IL_0147:  ldc.i4.1
    IL_0148:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_014d:  ldarg.0
    IL_014e:  ldc.i4.s   30
    IL_0150:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_0155:  brfalse.s  IL_018d

    IL_0157:  ldarg.0
    IL_0158:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_015d:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0162:  ldloca.s   V_0
    IL_0164:  ldfld      uint16 Calibration.OffsetNominalValues::m_us35mm8b
    IL_0169:  ldc.i4.s   100
    IL_016b:  sub
    IL_016c:  blt.s      IL_0185

    IL_016e:  ldarg.0
    IL_016f:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_0174:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0179:  ldloca.s   V_0
    IL_017b:  ldfld      uint16 Calibration.OffsetNominalValues::m_us35mm8b
    IL_0180:  ldc.i4.s   100
    IL_0182:  add
    IL_0183:  ble.s      IL_018d

    IL_0185:  ldarg.1
    IL_0186:  ldc.i4.4
    IL_0187:  ldc.i4.1
    IL_0188:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_018d:  ldarg.0
    IL_018e:  ldc.i4.s   29
    IL_0190:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_0195:  brfalse.s  IL_01b6

    IL_0197:  ldarg.0
    IL_0198:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm16Base
    IL_019d:  ldfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_01a2:  ldloca.s   V_0
    IL_01a4:  ldfld      uint16 Calibration.OffsetNominalValues::m_us35mm16b
    IL_01a9:  ldc.i4.s   100
    IL_01ab:  add
    IL_01ac:  ble.s      IL_01b6

    IL_01ae:  ldarg.1
    IL_01af:  ldc.i4.5
    IL_01b0:  ldc.i4.1
    IL_01b1:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_01b6:  ret
  } // end of method ScannerSettings::ValidateOffsets

  .method public hidebysig instance void 
          ValidateSteppers([Pakon]Pakon.IntBits ibInvalid) cil managed
  {
    // Code size       688 (0x2b0)
    .maxstack  3
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2,
             int32 V_3,
             int32 V_4,
             [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_5)
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.6
    IL_0002:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_0007:  brfalse.s  IL_000a

    IL_0009:  ret

    IL_000a:  ldarg.0
    IL_000b:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0010:  stloc.s    V_5
    IL_0012:  ldloc.s    V_5
    IL_0014:  ldc.i4.7
    IL_0015:  sub
    IL_0016:  switch     ( 
                          IL_003a,
                          IL_003a)
    IL_0023:  ldloc.s    V_5
    IL_0025:  ldc.i4     0xd16
    IL_002a:  sub
    IL_002b:  switch     ( 
                          IL_0042,
                          IL_0042)
    IL_0038:  br.s       IL_004a

    IL_003a:  ldsfld     valuetype Calibration.StepperNominalValues Calibration.Global::m_svFX35
    IL_003f:  pop
    IL_0040:  br.s       IL_0055

    IL_0042:  ldsfld     valuetype Calibration.StepperNominalValues Calibration.Global::m_svFX35
    IL_0047:  pop
    IL_0048:  br.s       IL_0055

    IL_004a:  ldstr      "Invalid Scanner Type"
    IL_004f:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0054:  throw

    IL_0055:  ldarg.0
    IL_0056:  ldc.i4.s   30
    IL_0058:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_005d:  brtrue.s   IL_006a

    IL_005f:  ldstr      "ValidateSteppers doesn't work without 35mm 8Base C"
    + "apability"
    IL_0064:  newobj     instance void [mscorlib]System.InvalidProgramException::.ctor(string)
    IL_0069:  throw

    IL_006a:  ldarg.0
    IL_006b:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_0070:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_0075:  ldc.i4     0x190
    IL_007a:  ble.s      IL_0085

    IL_007c:  ldarg.1
    IL_007d:  ldc.i4.s   14
    IL_007f:  ldc.i4.1
    IL_0080:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0085:  ldarg.0
    IL_0086:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_008b:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0090:  ldc.i4     0x320
    IL_0095:  ble.s      IL_00a0

    IL_0097:  ldarg.1
    IL_0098:  ldc.i4.s   15
    IL_009a:  ldc.i4.1
    IL_009b:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_00a0:  ldarg.0
    IL_00a1:  ldc.i4.s   27
    IL_00a3:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_00a8:  brfalse.s  IL_0107

    IL_00aa:  ldarg.0
    IL_00ab:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm8Base
    IL_00b0:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_00b5:  ldarg.0
    IL_00b6:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_00bb:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_00c0:  sub
    IL_00c1:  stloc.0
    IL_00c2:  ldloc.0
    IL_00c3:  ldc.i4     0x28a
    IL_00c8:  blt.s      IL_00d2

    IL_00ca:  ldloc.0
    IL_00cb:  ldc.i4     0x352
    IL_00d0:  ble.s      IL_00da

    IL_00d2:  ldarg.1
    IL_00d3:  ldc.i4.8
    IL_00d4:  ldc.i4.1
    IL_00d5:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_00da:  ldarg.0
    IL_00db:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_00e0:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_00e5:  ldarg.0
    IL_00e6:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm8Base
    IL_00eb:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_00f0:  sub
    IL_00f1:  stloc.0
    IL_00f2:  ldloc.0
    IL_00f3:  ldc.i4.0
    IL_00f4:  blt.s      IL_00fe

    IL_00f6:  ldloc.0
    IL_00f7:  ldc.i4     0xc8
    IL_00fc:  ble.s      IL_0107

    IL_00fe:  ldarg.1
    IL_00ff:  ldc.i4.s   9
    IL_0101:  ldc.i4.1
    IL_0102:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0107:  ldarg.0
    IL_0108:  ldc.i4.s   31
    IL_010a:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_010f:  brfalse.s  IL_016d

    IL_0111:  ldarg.0
    IL_0112:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm4Base
    IL_0117:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_011c:  ldarg.0
    IL_011d:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_0122:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_0127:  sub
    IL_0128:  stloc.1
    IL_0129:  ldloc.1
    IL_012a:  ldc.i4     0x3fc
    IL_012f:  blt.s      IL_0139

    IL_0131:  ldloc.1
    IL_0132:  ldc.i4     0x4c4
    IL_0137:  ble.s      IL_0142

    IL_0139:  ldarg.1
    IL_013a:  ldc.i4.s   12
    IL_013c:  ldc.i4.1
    IL_013d:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0142:  ldarg.0
    IL_0143:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_0148:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_014d:  ldarg.0
    IL_014e:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm4Base
    IL_0153:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0158:  sub
    IL_0159:  stloc.1
    IL_015a:  ldloc.1
    IL_015b:  ldc.i4.s   -100
    IL_015d:  blt.s      IL_0164

    IL_015f:  ldloc.1
    IL_0160:  ldc.i4.s   100
    IL_0162:  ble.s      IL_016d

    IL_0164:  ldarg.1
    IL_0165:  ldc.i4.s   13
    IL_0167:  ldc.i4.1
    IL_0168:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_016d:  ldarg.0
    IL_016e:  ldc.i4.s   28
    IL_0170:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_0175:  brfalse.s  IL_01d7

    IL_0177:  ldarg.0
    IL_0178:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm4Base
    IL_017d:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_0182:  ldarg.0
    IL_0183:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_0188:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_018d:  sub
    IL_018e:  stloc.2
    IL_018f:  ldloc.2
    IL_0190:  ldc.i4     0x60e
    IL_0195:  blt.s      IL_019f

    IL_0197:  ldloc.2
    IL_0198:  ldc.i4     0x6d6
    IL_019d:  ble.s      IL_01a7

    IL_019f:  ldarg.1
    IL_01a0:  ldc.i4.6
    IL_01a1:  ldc.i4.1
    IL_01a2:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_01a7:  ldarg.0
    IL_01a8:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm4Base
    IL_01ad:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_01b2:  ldarg.0
    IL_01b3:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_01b8:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_01bd:  sub
    IL_01be:  stloc.2
    IL_01bf:  ldloc.2
    IL_01c0:  ldc.i4     0x113
    IL_01c5:  blt.s      IL_01cf

    IL_01c7:  ldloc.2
    IL_01c8:  ldc.i4     0x1db
    IL_01cd:  ble.s      IL_01d7

    IL_01cf:  ldarg.1
    IL_01d0:  ldc.i4.7
    IL_01d1:  ldc.i4.1
    IL_01d2:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_01d7:  ldarg.0
    IL_01d8:  ldc.i4.s   29
    IL_01da:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_01df:  brfalse.s  IL_023d

    IL_01e1:  ldarg.0
    IL_01e2:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm16Base
    IL_01e7:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_01ec:  ldarg.0
    IL_01ed:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_01f2:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_01f7:  sub
    IL_01f8:  stloc.3
    IL_01f9:  ldloc.3
    IL_01fa:  ldc.i4     0x3fc
    IL_01ff:  blt.s      IL_0209

    IL_0201:  ldloc.3
    IL_0202:  ldc.i4     0x4c4
    IL_0207:  ble.s      IL_0212

    IL_0209:  ldarg.1
    IL_020a:  ldc.i4.s   16
    IL_020c:  ldc.i4.1
    IL_020d:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0212:  ldarg.0
    IL_0213:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_0218:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_021d:  ldarg.0
    IL_021e:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm16Base
    IL_0223:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0228:  sub
    IL_0229:  stloc.3
    IL_022a:  ldloc.3
    IL_022b:  ldc.i4.s   -100
    IL_022d:  blt.s      IL_0234

    IL_022f:  ldloc.3
    IL_0230:  ldc.i4.s   100
    IL_0232:  ble.s      IL_023d

    IL_0234:  ldarg.1
    IL_0235:  ldc.i4.s   17
    IL_0237:  ldc.i4.1
    IL_0238:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_023d:  ldarg.0
    IL_023e:  ldc.i4.s   26
    IL_0240:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_0245:  brfalse.s  IL_02af

    IL_0247:  ldarg.0
    IL_0248:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm16Base
    IL_024d:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_0252:  ldarg.0
    IL_0253:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_0258:  ldfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_025d:  sub
    IL_025e:  stloc.s    V_4
    IL_0260:  ldloc.s    V_4
    IL_0262:  ldc.i4     0x60e
    IL_0267:  blt.s      IL_0272

    IL_0269:  ldloc.s    V_4
    IL_026b:  ldc.i4     0x6d6
    IL_0270:  ble.s      IL_027b

    IL_0272:  ldarg.1
    IL_0273:  ldc.i4.s   10
    IL_0275:  ldc.i4.1
    IL_0276:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_027b:  ldarg.0
    IL_027c:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm16Base
    IL_0281:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0286:  ldarg.0
    IL_0287:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_028c:  ldfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0291:  sub
    IL_0292:  stloc.s    V_4
    IL_0294:  ldloc.s    V_4
    IL_0296:  ldc.i4     0x113
    IL_029b:  blt.s      IL_02a6

    IL_029d:  ldloc.s    V_4
    IL_029f:  ldc.i4     0x1db
    IL_02a4:  ble.s      IL_02af

    IL_02a6:  ldarg.1
    IL_02a7:  ldc.i4.s   11
    IL_02a9:  ldc.i4.1
    IL_02aa:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_02af:  ret
  } // end of method ScannerSettings::ValidateSteppers

  .method public hidebysig instance void 
          ValidateMotorSpeeds([Pakon]Pakon.IntBits ibInvalid) cil managed
  {
    // Code size       1196 (0x4ac)
    .maxstack  3
    .locals (valuetype Calibration.MotorSpeedNominalValues V_0,
             [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_1)
    IL_0000:  ldarg.0
    IL_0001:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_0006:  stloc.1
    IL_0007:  ldloc.1
    IL_0008:  ldc.i4.7
    IL_0009:  sub
    IL_000a:  switch     ( 
                          IL_0051,
                          IL_0051)
    IL_0017:  ldloc.1
    IL_0018:  ldc.i4     0x546
    IL_001d:  sub
    IL_001e:  switch     ( 
                          IL_0041,
                          IL_0049)
    IL_002b:  ldloc.1
    IL_002c:  ldc.i4     0xd16
    IL_0031:  sub
    IL_0032:  switch     ( 
                          IL_006e,
                          IL_006e)
    IL_003f:  br.s       IL_0076

    IL_0041:  ldsfld     valuetype Calibration.MotorSpeedNominalValues Calibration.Global::m_msF135
    IL_0046:  stloc.0
    IL_0047:  br.s       IL_0081

    IL_0049:  ldsfld     valuetype Calibration.MotorSpeedNominalValues Calibration.Global::m_msF135Plus
    IL_004e:  stloc.0
    IL_004f:  br.s       IL_0081

    IL_0051:  ldarg.0
    IL_0052:  call       instance [Pakon]Pakon.ScannerHW235 [Pakon]Pakon.ScannerSettings::get_Hardware235()
    IL_0057:  ldc.i4     0x3e8
    IL_005c:  bne.un.s   IL_0066

    IL_005e:  ldsfld     valuetype Calibration.MotorSpeedNominalValues Calibration.Global::m_msF235Plus
    IL_0063:  stloc.0
    IL_0064:  br.s       IL_0081

    IL_0066:  ldsfld     valuetype Calibration.MotorSpeedNominalValues Calibration.Global::m_msF235
    IL_006b:  stloc.0
    IL_006c:  br.s       IL_0081

    IL_006e:  ldsfld     valuetype Calibration.MotorSpeedNominalValues Calibration.Global::m_msF335
    IL_0073:  stloc.0
    IL_0074:  br.s       IL_0081

    IL_0076:  ldstr      "Invalid Scanner Type"
    IL_007b:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0080:  throw

    IL_0081:  ldarg.0
    IL_0082:  ldc.i4.s   26
    IL_0084:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_0089:  brfalse    IL_0128

    IL_008e:  ldarg.0
    IL_008f:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm16Base
    IL_0094:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_0099:  conv.r8
    IL_009a:  ldloca.s   V_0
    IL_009c:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm16b3c
    IL_00a1:  conv.r8
    IL_00a2:  conv.u2
    IL_00a3:  conv.r8
    IL_00a4:  ldc.r8     0.9
    IL_00ad:  mul
    IL_00ae:  blt.s      IL_00d2

    IL_00b0:  ldarg.0
    IL_00b1:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm16Base
    IL_00b6:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_00bb:  conv.r8
    IL_00bc:  ldloca.s   V_0
    IL_00be:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm16b3c
    IL_00c3:  conv.r8
    IL_00c4:  conv.u2
    IL_00c5:  conv.r8
    IL_00c6:  ldc.r8     1.1
    IL_00cf:  mul
    IL_00d0:  ble.un.s   IL_00db

    IL_00d2:  ldarg.1
    IL_00d3:  ldc.i4.s   22
    IL_00d5:  ldc.i4.1
    IL_00d6:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_00db:  ldarg.0
    IL_00dc:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm16Base
    IL_00e1:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_00e6:  conv.r8
    IL_00e7:  ldloca.s   V_0
    IL_00e9:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm16b4c
    IL_00ee:  conv.r8
    IL_00ef:  conv.u2
    IL_00f0:  conv.r8
    IL_00f1:  ldc.r8     0.9
    IL_00fa:  mul
    IL_00fb:  blt.s      IL_011f

    IL_00fd:  ldarg.0
    IL_00fe:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm16Base
    IL_0103:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_0108:  conv.r8
    IL_0109:  ldloca.s   V_0
    IL_010b:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm16b4c
    IL_0110:  conv.r8
    IL_0111:  conv.u2
    IL_0112:  conv.r8
    IL_0113:  ldc.r8     1.1
    IL_011c:  mul
    IL_011d:  ble.un.s   IL_0128

    IL_011f:  ldarg.1
    IL_0120:  ldc.i4.s   23
    IL_0122:  ldc.i4.1
    IL_0123:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0128:  ldarg.0
    IL_0129:  ldc.i4.s   29
    IL_012b:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_0130:  brfalse    IL_01cf

    IL_0135:  ldarg.0
    IL_0136:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm16Base
    IL_013b:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_0140:  conv.r8
    IL_0141:  ldloca.s   V_0
    IL_0143:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm16b3c
    IL_0148:  conv.r8
    IL_0149:  conv.u2
    IL_014a:  conv.r8
    IL_014b:  ldc.r8     0.9
    IL_0154:  mul
    IL_0155:  blt.s      IL_0179

    IL_0157:  ldarg.0
    IL_0158:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm16Base
    IL_015d:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_0162:  conv.r8
    IL_0163:  ldloca.s   V_0
    IL_0165:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm16b3c
    IL_016a:  conv.r8
    IL_016b:  conv.u2
    IL_016c:  conv.r8
    IL_016d:  ldc.r8     1.1
    IL_0176:  mul
    IL_0177:  ble.un.s   IL_0182

    IL_0179:  ldarg.1
    IL_017a:  ldc.i4.s   28
    IL_017c:  ldc.i4.1
    IL_017d:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0182:  ldarg.0
    IL_0183:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm16Base
    IL_0188:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_018d:  conv.r8
    IL_018e:  ldloca.s   V_0
    IL_0190:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm16b4c
    IL_0195:  conv.r8
    IL_0196:  conv.u2
    IL_0197:  conv.r8
    IL_0198:  ldc.r8     0.9
    IL_01a1:  mul
    IL_01a2:  blt.s      IL_01c6

    IL_01a4:  ldarg.0
    IL_01a5:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm16Base
    IL_01aa:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_01af:  conv.r8
    IL_01b0:  ldloca.s   V_0
    IL_01b2:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm16b4c
    IL_01b7:  conv.r8
    IL_01b8:  conv.u2
    IL_01b9:  conv.r8
    IL_01ba:  ldc.r8     1.1
    IL_01c3:  mul
    IL_01c4:  ble.un.s   IL_01cf

    IL_01c6:  ldarg.1
    IL_01c7:  ldc.i4.s   29
    IL_01c9:  ldc.i4.1
    IL_01ca:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_01cf:  ldarg.0
    IL_01d0:  ldc.i4.s   28
    IL_01d2:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_01d7:  brfalse    IL_0296

    IL_01dc:  ldarg.0
    IL_01dd:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_01e2:  ldc.i4     0xd16
    IL_01e7:  beq        IL_0296

    IL_01ec:  ldarg.0
    IL_01ed:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_01f2:  ldc.i4     0xd17
    IL_01f7:  beq        IL_0296

    IL_01fc:  ldarg.0
    IL_01fd:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm4Base
    IL_0202:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_0207:  conv.r8
    IL_0208:  ldloca.s   V_0
    IL_020a:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm4b3c
    IL_020f:  conv.r8
    IL_0210:  conv.u2
    IL_0211:  conv.r8
    IL_0212:  ldc.r8     0.9
    IL_021b:  mul
    IL_021c:  blt.s      IL_0240

    IL_021e:  ldarg.0
    IL_021f:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm4Base
    IL_0224:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_0229:  conv.r8
    IL_022a:  ldloca.s   V_0
    IL_022c:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm4b3c
    IL_0231:  conv.r8
    IL_0232:  conv.u2
    IL_0233:  conv.r8
    IL_0234:  ldc.r8     1.1
    IL_023d:  mul
    IL_023e:  ble.un.s   IL_0249

    IL_0240:  ldarg.1
    IL_0241:  ldc.i4.s   18
    IL_0243:  ldc.i4.1
    IL_0244:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0249:  ldarg.0
    IL_024a:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm4Base
    IL_024f:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_0254:  conv.r8
    IL_0255:  ldloca.s   V_0
    IL_0257:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm4b4c
    IL_025c:  conv.r8
    IL_025d:  conv.u2
    IL_025e:  conv.r8
    IL_025f:  ldc.r8     0.9
    IL_0268:  mul
    IL_0269:  blt.s      IL_028d

    IL_026b:  ldarg.0
    IL_026c:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm4Base
    IL_0271:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_0276:  conv.r8
    IL_0277:  ldloca.s   V_0
    IL_0279:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm4b4c
    IL_027e:  conv.r8
    IL_027f:  conv.u2
    IL_0280:  conv.r8
    IL_0281:  ldc.r8     1.1
    IL_028a:  mul
    IL_028b:  ble.un.s   IL_0296

    IL_028d:  ldarg.1
    IL_028e:  ldc.i4.s   19
    IL_0290:  ldc.i4.1
    IL_0291:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0296:  ldarg.0
    IL_0297:  ldc.i4.s   31
    IL_0299:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_029e:  brfalse    IL_035d

    IL_02a3:  ldarg.0
    IL_02a4:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_02a9:  ldc.i4     0xd16
    IL_02ae:  beq        IL_035d

    IL_02b3:  ldarg.0
    IL_02b4:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 [Pakon]Pakon.ScannerSettings::get_Type()
    IL_02b9:  ldc.i4     0xd17
    IL_02be:  beq        IL_035d

    IL_02c3:  ldarg.0
    IL_02c4:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm4Base
    IL_02c9:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_02ce:  conv.r8
    IL_02cf:  ldloca.s   V_0
    IL_02d1:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm4b3c
    IL_02d6:  conv.r8
    IL_02d7:  conv.u2
    IL_02d8:  conv.r8
    IL_02d9:  ldc.r8     0.9
    IL_02e2:  mul
    IL_02e3:  blt.s      IL_0307

    IL_02e5:  ldarg.0
    IL_02e6:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm4Base
    IL_02eb:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_02f0:  conv.r8
    IL_02f1:  ldloca.s   V_0
    IL_02f3:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm4b3c
    IL_02f8:  conv.r8
    IL_02f9:  conv.u2
    IL_02fa:  conv.r8
    IL_02fb:  ldc.r8     1.1
    IL_0304:  mul
    IL_0305:  ble.un.s   IL_0310

    IL_0307:  ldarg.1
    IL_0308:  ldc.i4.s   24
    IL_030a:  ldc.i4.1
    IL_030b:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0310:  ldarg.0
    IL_0311:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm4Base
    IL_0316:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_031b:  conv.r8
    IL_031c:  ldloca.s   V_0
    IL_031e:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm4b4c
    IL_0323:  conv.r8
    IL_0324:  conv.u2
    IL_0325:  conv.r8
    IL_0326:  ldc.r8     0.9
    IL_032f:  mul
    IL_0330:  blt.s      IL_0354

    IL_0332:  ldarg.0
    IL_0333:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm4Base
    IL_0338:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_033d:  conv.r8
    IL_033e:  ldloca.s   V_0
    IL_0340:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm4b4c
    IL_0345:  conv.r8
    IL_0346:  conv.u2
    IL_0347:  conv.r8
    IL_0348:  ldc.r8     1.1
    IL_0351:  mul
    IL_0352:  ble.un.s   IL_035d

    IL_0354:  ldarg.1
    IL_0355:  ldc.i4.s   25
    IL_0357:  ldc.i4.1
    IL_0358:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_035d:  ldarg.0
    IL_035e:  ldc.i4.s   27
    IL_0360:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_0365:  brfalse    IL_0404

    IL_036a:  ldarg.0
    IL_036b:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm8Base
    IL_0370:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_0375:  conv.r8
    IL_0376:  ldloca.s   V_0
    IL_0378:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm8b3c
    IL_037d:  conv.r8
    IL_037e:  conv.u2
    IL_037f:  conv.r8
    IL_0380:  ldc.r8     0.9
    IL_0389:  mul
    IL_038a:  blt.s      IL_03ae

    IL_038c:  ldarg.0
    IL_038d:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm8Base
    IL_0392:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_0397:  conv.r8
    IL_0398:  ldloca.s   V_0
    IL_039a:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm8b3c
    IL_039f:  conv.r8
    IL_03a0:  conv.u2
    IL_03a1:  conv.r8
    IL_03a2:  ldc.r8     1.1
    IL_03ab:  mul
    IL_03ac:  ble.un.s   IL_03b7

    IL_03ae:  ldarg.1
    IL_03af:  ldc.i4.s   20
    IL_03b1:  ldc.i4.1
    IL_03b2:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_03b7:  ldarg.0
    IL_03b8:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm8Base
    IL_03bd:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_03c2:  conv.r8
    IL_03c3:  ldloca.s   V_0
    IL_03c5:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm8b4c
    IL_03ca:  conv.r8
    IL_03cb:  conv.u2
    IL_03cc:  conv.r8
    IL_03cd:  ldc.r8     0.9
    IL_03d6:  mul
    IL_03d7:  blt.s      IL_03fb

    IL_03d9:  ldarg.0
    IL_03da:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi24mm8Base
    IL_03df:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_03e4:  conv.r8
    IL_03e5:  ldloca.s   V_0
    IL_03e7:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us24mm8b4c
    IL_03ec:  conv.r8
    IL_03ed:  conv.u2
    IL_03ee:  conv.r8
    IL_03ef:  ldc.r8     1.1
    IL_03f8:  mul
    IL_03f9:  ble.un.s   IL_0404

    IL_03fb:  ldarg.1
    IL_03fc:  ldc.i4.s   21
    IL_03fe:  ldc.i4.1
    IL_03ff:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0404:  ldarg.0
    IL_0405:  ldc.i4.s   30
    IL_0407:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_040c:  brfalse    IL_04ab

    IL_0411:  ldarg.0
    IL_0412:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_0417:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_041c:  conv.r8
    IL_041d:  ldloca.s   V_0
    IL_041f:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm8b3c
    IL_0424:  conv.r8
    IL_0425:  conv.u2
    IL_0426:  conv.r8
    IL_0427:  ldc.r8     0.9
    IL_0430:  mul
    IL_0431:  blt.s      IL_0455

    IL_0433:  ldarg.0
    IL_0434:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_0439:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_043e:  conv.r8
    IL_043f:  ldloca.s   V_0
    IL_0441:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm8b3c
    IL_0446:  conv.r8
    IL_0447:  conv.u2
    IL_0448:  conv.r8
    IL_0449:  ldc.r8     1.1
    IL_0452:  mul
    IL_0453:  ble.un.s   IL_045e

    IL_0455:  ldarg.1
    IL_0456:  ldc.i4.s   26
    IL_0458:  ldc.i4.1
    IL_0459:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_045e:  ldarg.0
    IL_045f:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_0464:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_0469:  conv.r8
    IL_046a:  ldloca.s   V_0
    IL_046c:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm8b4c
    IL_0471:  conv.r8
    IL_0472:  conv.u2
    IL_0473:  conv.r8
    IL_0474:  ldc.r8     0.9
    IL_047d:  mul
    IL_047e:  blt.s      IL_04a2

    IL_0480:  ldarg.0
    IL_0481:  ldflda     valuetype Calibration.DPIConfig Calibration.ScannerSettings::m_dpi35mm8Base
    IL_0486:  ldfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_048b:  conv.r8
    IL_048c:  ldloca.s   V_0
    IL_048e:  ldfld      uint16 Calibration.MotorSpeedNominalValues::m_us35mm8b4c
    IL_0493:  conv.r8
    IL_0494:  conv.u2
    IL_0495:  conv.r8
    IL_0496:  ldc.r8     1.1
    IL_049f:  mul
    IL_04a0:  ble.un.s   IL_04ab

    IL_04a2:  ldarg.1
    IL_04a3:  ldc.i4.s   27
    IL_04a5:  ldc.i4.1
    IL_04a6:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_04ab:  ret
  } // end of method ScannerSettings::ValidateMotorSpeeds

  .method public hidebysig instance void 
          ValidateColorMatrix(valuetype Calibration.ColorMatrixConfig cmMatrix,
                              [Pakon]Pakon.IntBits& ibInvalid) cil managed
  {
    // Code size       2005 (0x7d5)
    .maxstack  3
    IL_0000:  ldarga.s   cmMatrix
    IL_0002:  ldfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_0007:  ldc.i4.1
    IL_0008:  bne.un     IL_0230

    IL_000d:  ldarga.s   cmMatrix
    IL_000f:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_0
    IL_0014:  ldc.r8     2
    IL_001d:  bgt.s      IL_0031

    IL_001f:  ldarga.s   cmMatrix
    IL_0021:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_0
    IL_0026:  ldc.r8     0.5
    IL_002f:  bge.un.s   IL_003a

    IL_0031:  ldarg.2
    IL_0032:  ldind.ref
    IL_0033:  ldc.i4.0
    IL_0034:  ldc.i4.1
    IL_0035:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_003a:  ldarga.s   cmMatrix
    IL_003c:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_1
    IL_0041:  ldc.r8     0.9
    IL_004a:  bgt.s      IL_005e

    IL_004c:  ldarga.s   cmMatrix
    IL_004e:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_1
    IL_0053:  ldc.r8     -0.9
    IL_005c:  bge.un.s   IL_0067

    IL_005e:  ldarg.2
    IL_005f:  ldind.ref
    IL_0060:  ldc.i4.1
    IL_0061:  ldc.i4.1
    IL_0062:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0067:  ldarga.s   cmMatrix
    IL_0069:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_2
    IL_006e:  ldc.r8     0.9
    IL_0077:  bgt.s      IL_008b

    IL_0079:  ldarga.s   cmMatrix
    IL_007b:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_2
    IL_0080:  ldc.r8     -0.9
    IL_0089:  bge.un.s   IL_0094

    IL_008b:  ldarg.2
    IL_008c:  ldind.ref
    IL_008d:  ldc.i4.2
    IL_008e:  ldc.i4.1
    IL_008f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0094:  ldarga.s   cmMatrix
    IL_0096:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_3
    IL_009b:  ldc.r8     1000
    IL_00a4:  bgt.s      IL_00b8

    IL_00a6:  ldarga.s   cmMatrix
    IL_00a8:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_3
    IL_00ad:  ldc.r8     -1000
    IL_00b6:  bge.un.s   IL_00c1

    IL_00b8:  ldarg.2
    IL_00b9:  ldind.ref
    IL_00ba:  ldc.i4.3
    IL_00bb:  ldc.i4.1
    IL_00bc:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_00c1:  ldarga.s   cmMatrix
    IL_00c3:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_0
    IL_00c8:  ldc.r8     0.9
    IL_00d1:  bgt.s      IL_00e5

    IL_00d3:  ldarga.s   cmMatrix
    IL_00d5:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_0
    IL_00da:  ldc.r8     -0.9
    IL_00e3:  bge.un.s   IL_00ee

    IL_00e5:  ldarg.2
    IL_00e6:  ldind.ref
    IL_00e7:  ldc.i4.4
    IL_00e8:  ldc.i4.1
    IL_00e9:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_00ee:  ldarga.s   cmMatrix
    IL_00f0:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_1
    IL_00f5:  ldc.r8     2
    IL_00fe:  bgt.s      IL_0112

    IL_0100:  ldarga.s   cmMatrix
    IL_0102:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_1
    IL_0107:  ldc.r8     0.5
    IL_0110:  bge.un.s   IL_011b

    IL_0112:  ldarg.2
    IL_0113:  ldind.ref
    IL_0114:  ldc.i4.5
    IL_0115:  ldc.i4.1
    IL_0116:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_011b:  ldarga.s   cmMatrix
    IL_011d:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_2
    IL_0122:  ldc.r8     0.9
    IL_012b:  bgt.s      IL_013f

    IL_012d:  ldarga.s   cmMatrix
    IL_012f:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_2
    IL_0134:  ldc.r8     -0.9
    IL_013d:  bge.un.s   IL_0148

    IL_013f:  ldarg.2
    IL_0140:  ldind.ref
    IL_0141:  ldc.i4.6
    IL_0142:  ldc.i4.1
    IL_0143:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0148:  ldarga.s   cmMatrix
    IL_014a:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_3
    IL_014f:  ldc.r8     1000
    IL_0158:  bgt.s      IL_016c

    IL_015a:  ldarga.s   cmMatrix
    IL_015c:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_3
    IL_0161:  ldc.r8     -1000
    IL_016a:  bge.un.s   IL_0175

    IL_016c:  ldarg.2
    IL_016d:  ldind.ref
    IL_016e:  ldc.i4.7
    IL_016f:  ldc.i4.1
    IL_0170:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0175:  ldarga.s   cmMatrix
    IL_0177:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_0
    IL_017c:  ldc.r8     0.9
    IL_0185:  bgt.s      IL_0199

    IL_0187:  ldarga.s   cmMatrix
    IL_0189:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_0
    IL_018e:  ldc.r8     -0.9
    IL_0197:  bge.un.s   IL_01a2

    IL_0199:  ldarg.2
    IL_019a:  ldind.ref
    IL_019b:  ldc.i4.8
    IL_019c:  ldc.i4.1
    IL_019d:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_01a2:  ldarga.s   cmMatrix
    IL_01a4:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_1
    IL_01a9:  ldc.r8     0.9
    IL_01b2:  bgt.s      IL_01c6

    IL_01b4:  ldarga.s   cmMatrix
    IL_01b6:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_1
    IL_01bb:  ldc.r8     -0.9
    IL_01c4:  bge.un.s   IL_01d0

    IL_01c6:  ldarg.2
    IL_01c7:  ldind.ref
    IL_01c8:  ldc.i4.s   9
    IL_01ca:  ldc.i4.1
    IL_01cb:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_01d0:  ldarga.s   cmMatrix
    IL_01d2:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_2
    IL_01d7:  ldc.r8     2
    IL_01e0:  bgt.s      IL_01f4

    IL_01e2:  ldarga.s   cmMatrix
    IL_01e4:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_2
    IL_01e9:  ldc.r8     0.5
    IL_01f2:  bge.un.s   IL_01fe

    IL_01f4:  ldarg.2
    IL_01f5:  ldind.ref
    IL_01f6:  ldc.i4.s   10
    IL_01f8:  ldc.i4.1
    IL_01f9:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_01fe:  ldarga.s   cmMatrix
    IL_0200:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_3
    IL_0205:  ldc.r8     1000
    IL_020e:  bgt.s      IL_0225

    IL_0210:  ldarga.s   cmMatrix
    IL_0212:  ldfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_3
    IL_0217:  ldc.r8     -1000
    IL_0220:  bge.un     IL_07d4

    IL_0225:  ldarg.2
    IL_0226:  ldind.ref
    IL_0227:  ldc.i4.s   11
    IL_0229:  ldc.i4.1
    IL_022a:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_022f:  ret

    IL_0230:  ldarga.s   cmMatrix
    IL_0232:  ldfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_0237:  ldc.i4.2
    IL_0238:  bne.un     IL_07d4

    IL_023d:  ldarga.s   cmMatrix
    IL_023f:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_0
    IL_0244:  conv.r8
    IL_0245:  ldc.r8     0.65
    IL_024e:  bgt.s      IL_0263

    IL_0250:  ldarga.s   cmMatrix
    IL_0252:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_0
    IL_0257:  conv.r8
    IL_0258:  ldc.r8     0.05
    IL_0261:  bge.un.s   IL_026c

    IL_0263:  ldarg.2
    IL_0264:  ldind.ref
    IL_0265:  ldc.i4.0
    IL_0266:  ldc.i4.1
    IL_0267:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_026c:  ldarga.s   cmMatrix
    IL_026e:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_1
    IL_0273:  conv.r8
    IL_0274:  ldc.r8     0.5
    IL_027d:  bgt.s      IL_0292

    IL_027f:  ldarga.s   cmMatrix
    IL_0281:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_1
    IL_0286:  conv.r8
    IL_0287:  ldc.r8     -0.5
    IL_0290:  bge.un.s   IL_029b

    IL_0292:  ldarg.2
    IL_0293:  ldind.ref
    IL_0294:  ldc.i4.1
    IL_0295:  ldc.i4.1
    IL_0296:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_029b:  ldarga.s   cmMatrix
    IL_029d:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_2
    IL_02a2:  conv.r8
    IL_02a3:  ldc.r8     0.5
    IL_02ac:  bgt.s      IL_02c1

    IL_02ae:  ldarga.s   cmMatrix
    IL_02b0:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_2
    IL_02b5:  conv.r8
    IL_02b6:  ldc.r8     -0.5
    IL_02bf:  bge.un.s   IL_02ca

    IL_02c1:  ldarg.2
    IL_02c2:  ldind.ref
    IL_02c3:  ldc.i4.2
    IL_02c4:  ldc.i4.1
    IL_02c5:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_02ca:  ldarga.s   cmMatrix
    IL_02cc:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_3
    IL_02d1:  conv.r8
    IL_02d2:  ldc.r8     0.5
    IL_02db:  bgt.s      IL_02f0

    IL_02dd:  ldarga.s   cmMatrix
    IL_02df:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_3
    IL_02e4:  conv.r8
    IL_02e5:  ldc.r8     -0.5
    IL_02ee:  bge.un.s   IL_02f9

    IL_02f0:  ldarg.2
    IL_02f1:  ldind.ref
    IL_02f2:  ldc.i4.3
    IL_02f3:  ldc.i4.1
    IL_02f4:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_02f9:  ldarga.s   cmMatrix
    IL_02fb:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_4
    IL_0300:  conv.r8
    IL_0301:  ldc.r8     0.5
    IL_030a:  bgt.s      IL_031f

    IL_030c:  ldarga.s   cmMatrix
    IL_030e:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_4
    IL_0313:  conv.r8
    IL_0314:  ldc.r8     -0.5
    IL_031d:  bge.un.s   IL_0328

    IL_031f:  ldarg.2
    IL_0320:  ldind.ref
    IL_0321:  ldc.i4.4
    IL_0322:  ldc.i4.1
    IL_0323:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0328:  ldarga.s   cmMatrix
    IL_032a:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_5
    IL_032f:  conv.r8
    IL_0330:  ldc.r8     0.5
    IL_0339:  bgt.s      IL_034e

    IL_033b:  ldarga.s   cmMatrix
    IL_033d:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_5
    IL_0342:  conv.r8
    IL_0343:  ldc.r8     -0.5
    IL_034c:  bge.un.s   IL_0357

    IL_034e:  ldarg.2
    IL_034f:  ldind.ref
    IL_0350:  ldc.i4.5
    IL_0351:  ldc.i4.1
    IL_0352:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0357:  ldarga.s   cmMatrix
    IL_0359:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_6
    IL_035e:  conv.r8
    IL_035f:  ldc.r8     0.5
    IL_0368:  bgt.s      IL_037d

    IL_036a:  ldarga.s   cmMatrix
    IL_036c:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_6
    IL_0371:  conv.r8
    IL_0372:  ldc.r8     -0.5
    IL_037b:  bge.un.s   IL_0386

    IL_037d:  ldarg.2
    IL_037e:  ldind.ref
    IL_037f:  ldc.i4.6
    IL_0380:  ldc.i4.1
    IL_0381:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0386:  ldarga.s   cmMatrix
    IL_0388:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_7
    IL_038d:  conv.r8
    IL_038e:  ldc.r8     0.5
    IL_0397:  bgt.s      IL_03ac

    IL_0399:  ldarga.s   cmMatrix
    IL_039b:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_7
    IL_03a0:  conv.r8
    IL_03a1:  ldc.r8     -0.5
    IL_03aa:  bge.un.s   IL_03b5

    IL_03ac:  ldarg.2
    IL_03ad:  ldind.ref
    IL_03ae:  ldc.i4.7
    IL_03af:  ldc.i4.1
    IL_03b0:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_03b5:  ldarga.s   cmMatrix
    IL_03b7:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_8
    IL_03bc:  conv.r8
    IL_03bd:  ldc.r8     0.5
    IL_03c6:  bgt.s      IL_03db

    IL_03c8:  ldarga.s   cmMatrix
    IL_03ca:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_8
    IL_03cf:  conv.r8
    IL_03d0:  ldc.r8     -0.5
    IL_03d9:  bge.un.s   IL_03e4

    IL_03db:  ldarg.2
    IL_03dc:  ldind.ref
    IL_03dd:  ldc.i4.8
    IL_03de:  ldc.i4.1
    IL_03df:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_03e4:  ldarga.s   cmMatrix
    IL_03e6:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_9
    IL_03eb:  conv.r8
    IL_03ec:  ldc.r8     1000
    IL_03f5:  bgt.s      IL_040a

    IL_03f7:  ldarga.s   cmMatrix
    IL_03f9:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_9
    IL_03fe:  conv.r8
    IL_03ff:  ldc.r8     -1000
    IL_0408:  bge.un.s   IL_0414

    IL_040a:  ldarg.2
    IL_040b:  ldind.ref
    IL_040c:  ldc.i4.s   9
    IL_040e:  ldc.i4.1
    IL_040f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0414:  ldarga.s   cmMatrix
    IL_0416:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_0
    IL_041b:  conv.r8
    IL_041c:  ldc.r8     0.5
    IL_0425:  bgt.s      IL_043a

    IL_0427:  ldarga.s   cmMatrix
    IL_0429:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_0
    IL_042e:  conv.r8
    IL_042f:  ldc.r8     -0.5
    IL_0438:  bge.un.s   IL_0444

    IL_043a:  ldarg.2
    IL_043b:  ldind.ref
    IL_043c:  ldc.i4.s   10
    IL_043e:  ldc.i4.1
    IL_043f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0444:  ldarga.s   cmMatrix
    IL_0446:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_1
    IL_044b:  conv.r8
    IL_044c:  ldc.r8     0.65
    IL_0455:  bgt.s      IL_046a

    IL_0457:  ldarga.s   cmMatrix
    IL_0459:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_1
    IL_045e:  conv.r8
    IL_045f:  ldc.r8     0.05
    IL_0468:  bge.un.s   IL_0474

    IL_046a:  ldarg.2
    IL_046b:  ldind.ref
    IL_046c:  ldc.i4.s   11
    IL_046e:  ldc.i4.1
    IL_046f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0474:  ldarga.s   cmMatrix
    IL_0476:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_2
    IL_047b:  conv.r8
    IL_047c:  ldc.r8     0.5
    IL_0485:  bgt.s      IL_049a

    IL_0487:  ldarga.s   cmMatrix
    IL_0489:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_2
    IL_048e:  conv.r8
    IL_048f:  ldc.r8     -0.5
    IL_0498:  bge.un.s   IL_04a4

    IL_049a:  ldarg.2
    IL_049b:  ldind.ref
    IL_049c:  ldc.i4.s   12
    IL_049e:  ldc.i4.1
    IL_049f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_04a4:  ldarga.s   cmMatrix
    IL_04a6:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_3
    IL_04ab:  conv.r8
    IL_04ac:  ldc.r8     0.5
    IL_04b5:  bgt.s      IL_04ca

    IL_04b7:  ldarga.s   cmMatrix
    IL_04b9:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_3
    IL_04be:  conv.r8
    IL_04bf:  ldc.r8     -0.5
    IL_04c8:  bge.un.s   IL_04d4

    IL_04ca:  ldarg.2
    IL_04cb:  ldind.ref
    IL_04cc:  ldc.i4.s   13
    IL_04ce:  ldc.i4.1
    IL_04cf:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_04d4:  ldarga.s   cmMatrix
    IL_04d6:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_4
    IL_04db:  conv.r8
    IL_04dc:  ldc.r8     0.5
    IL_04e5:  bgt.s      IL_04fa

    IL_04e7:  ldarga.s   cmMatrix
    IL_04e9:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_4
    IL_04ee:  conv.r8
    IL_04ef:  ldc.r8     -0.5
    IL_04f8:  bge.un.s   IL_0504

    IL_04fa:  ldarg.2
    IL_04fb:  ldind.ref
    IL_04fc:  ldc.i4.s   14
    IL_04fe:  ldc.i4.1
    IL_04ff:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0504:  ldarga.s   cmMatrix
    IL_0506:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_5
    IL_050b:  conv.r8
    IL_050c:  ldc.r8     0.5
    IL_0515:  bgt.s      IL_052a

    IL_0517:  ldarga.s   cmMatrix
    IL_0519:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_5
    IL_051e:  conv.r8
    IL_051f:  ldc.r8     -0.5
    IL_0528:  bge.un.s   IL_0534

    IL_052a:  ldarg.2
    IL_052b:  ldind.ref
    IL_052c:  ldc.i4.s   15
    IL_052e:  ldc.i4.1
    IL_052f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0534:  ldarga.s   cmMatrix
    IL_0536:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_6
    IL_053b:  conv.r8
    IL_053c:  ldc.r8     0.5
    IL_0545:  bgt.s      IL_055a

    IL_0547:  ldarga.s   cmMatrix
    IL_0549:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_6
    IL_054e:  conv.r8
    IL_054f:  ldc.r8     -0.5
    IL_0558:  bge.un.s   IL_0564

    IL_055a:  ldarg.2
    IL_055b:  ldind.ref
    IL_055c:  ldc.i4.s   16
    IL_055e:  ldc.i4.1
    IL_055f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0564:  ldarga.s   cmMatrix
    IL_0566:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_7
    IL_056b:  conv.r8
    IL_056c:  ldc.r8     0.5
    IL_0575:  bgt.s      IL_058a

    IL_0577:  ldarga.s   cmMatrix
    IL_0579:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_7
    IL_057e:  conv.r8
    IL_057f:  ldc.r8     -0.5
    IL_0588:  bge.un.s   IL_0594

    IL_058a:  ldarg.2
    IL_058b:  ldind.ref
    IL_058c:  ldc.i4.s   17
    IL_058e:  ldc.i4.1
    IL_058f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0594:  ldarga.s   cmMatrix
    IL_0596:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_8
    IL_059b:  conv.r8
    IL_059c:  ldc.r8     0.5
    IL_05a5:  bgt.s      IL_05ba

    IL_05a7:  ldarga.s   cmMatrix
    IL_05a9:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_8
    IL_05ae:  conv.r8
    IL_05af:  ldc.r8     -0.5
    IL_05b8:  bge.un.s   IL_05c4

    IL_05ba:  ldarg.2
    IL_05bb:  ldind.ref
    IL_05bc:  ldc.i4.s   18
    IL_05be:  ldc.i4.1
    IL_05bf:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_05c4:  ldarga.s   cmMatrix
    IL_05c6:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_9
    IL_05cb:  conv.r8
    IL_05cc:  ldc.r8     1000
    IL_05d5:  bgt.s      IL_05ea

    IL_05d7:  ldarga.s   cmMatrix
    IL_05d9:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_9
    IL_05de:  conv.r8
    IL_05df:  ldc.r8     -1000
    IL_05e8:  bge.un.s   IL_05f4

    IL_05ea:  ldarg.2
    IL_05eb:  ldind.ref
    IL_05ec:  ldc.i4.s   19
    IL_05ee:  ldc.i4.1
    IL_05ef:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_05f4:  ldarga.s   cmMatrix
    IL_05f6:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_0
    IL_05fb:  conv.r8
    IL_05fc:  ldc.r8     0.5
    IL_0605:  bgt.s      IL_061a

    IL_0607:  ldarga.s   cmMatrix
    IL_0609:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_0
    IL_060e:  conv.r8
    IL_060f:  ldc.r8     -0.5
    IL_0618:  bge.un.s   IL_0624

    IL_061a:  ldarg.2
    IL_061b:  ldind.ref
    IL_061c:  ldc.i4.s   20
    IL_061e:  ldc.i4.1
    IL_061f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0624:  ldarga.s   cmMatrix
    IL_0626:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_1
    IL_062b:  conv.r8
    IL_062c:  ldc.r8     0.5
    IL_0635:  bgt.s      IL_064a

    IL_0637:  ldarga.s   cmMatrix
    IL_0639:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_1
    IL_063e:  conv.r8
    IL_063f:  ldc.r8     -0.5
    IL_0648:  bge.un.s   IL_0654

    IL_064a:  ldarg.2
    IL_064b:  ldind.ref
    IL_064c:  ldc.i4.s   21
    IL_064e:  ldc.i4.1
    IL_064f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0654:  ldarga.s   cmMatrix
    IL_0656:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_2
    IL_065b:  conv.r8
    IL_065c:  ldc.r8     0.65
    IL_0665:  bgt.s      IL_067a

    IL_0667:  ldarga.s   cmMatrix
    IL_0669:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_2
    IL_066e:  conv.r8
    IL_066f:  ldc.r8     0.05
    IL_0678:  bge.un.s   IL_0684

    IL_067a:  ldarg.2
    IL_067b:  ldind.ref
    IL_067c:  ldc.i4.s   22
    IL_067e:  ldc.i4.1
    IL_067f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0684:  ldarga.s   cmMatrix
    IL_0686:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_3
    IL_068b:  conv.r8
    IL_068c:  ldc.r8     0.5
    IL_0695:  bgt.s      IL_06aa

    IL_0697:  ldarga.s   cmMatrix
    IL_0699:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_3
    IL_069e:  conv.r8
    IL_069f:  ldc.r8     -0.5
    IL_06a8:  bge.un.s   IL_06b4

    IL_06aa:  ldarg.2
    IL_06ab:  ldind.ref
    IL_06ac:  ldc.i4.s   23
    IL_06ae:  ldc.i4.1
    IL_06af:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_06b4:  ldarga.s   cmMatrix
    IL_06b6:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_4
    IL_06bb:  conv.r8
    IL_06bc:  ldc.r8     0.5
    IL_06c5:  bgt.s      IL_06da

    IL_06c7:  ldarga.s   cmMatrix
    IL_06c9:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_4
    IL_06ce:  conv.r8
    IL_06cf:  ldc.r8     -0.5
    IL_06d8:  bge.un.s   IL_06e4

    IL_06da:  ldarg.2
    IL_06db:  ldind.ref
    IL_06dc:  ldc.i4.s   24
    IL_06de:  ldc.i4.1
    IL_06df:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_06e4:  ldarga.s   cmMatrix
    IL_06e6:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_5
    IL_06eb:  conv.r8
    IL_06ec:  ldc.r8     0.5
    IL_06f5:  bgt.s      IL_070a

    IL_06f7:  ldarga.s   cmMatrix
    IL_06f9:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_5
    IL_06fe:  conv.r8
    IL_06ff:  ldc.r8     -0.5
    IL_0708:  bge.un.s   IL_0714

    IL_070a:  ldarg.2
    IL_070b:  ldind.ref
    IL_070c:  ldc.i4.s   25
    IL_070e:  ldc.i4.1
    IL_070f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0714:  ldarga.s   cmMatrix
    IL_0716:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_6
    IL_071b:  conv.r8
    IL_071c:  ldc.r8     0.5
    IL_0725:  bgt.s      IL_073a

    IL_0727:  ldarga.s   cmMatrix
    IL_0729:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_6
    IL_072e:  conv.r8
    IL_072f:  ldc.r8     -0.5
    IL_0738:  bge.un.s   IL_0744

    IL_073a:  ldarg.2
    IL_073b:  ldind.ref
    IL_073c:  ldc.i4.s   26
    IL_073e:  ldc.i4.1
    IL_073f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0744:  ldarga.s   cmMatrix
    IL_0746:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_7
    IL_074b:  conv.r8
    IL_074c:  ldc.r8     0.5
    IL_0755:  bgt.s      IL_076a

    IL_0757:  ldarga.s   cmMatrix
    IL_0759:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_7
    IL_075e:  conv.r8
    IL_075f:  ldc.r8     -0.5
    IL_0768:  bge.un.s   IL_0774

    IL_076a:  ldarg.2
    IL_076b:  ldind.ref
    IL_076c:  ldc.i4.s   27
    IL_076e:  ldc.i4.1
    IL_076f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0774:  ldarga.s   cmMatrix
    IL_0776:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_8
    IL_077b:  conv.r8
    IL_077c:  ldc.r8     0.5
    IL_0785:  bgt.s      IL_079a

    IL_0787:  ldarga.s   cmMatrix
    IL_0789:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_8
    IL_078e:  conv.r8
    IL_078f:  ldc.r8     -0.5
    IL_0798:  bge.un.s   IL_07a4

    IL_079a:  ldarg.2
    IL_079b:  ldind.ref
    IL_079c:  ldc.i4.s   28
    IL_079e:  ldc.i4.1
    IL_079f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_07a4:  ldarga.s   cmMatrix
    IL_07a6:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_9
    IL_07ab:  conv.r8
    IL_07ac:  ldc.r8     1000
    IL_07b5:  bgt.s      IL_07ca

    IL_07b7:  ldarga.s   cmMatrix
    IL_07b9:  ldfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_9
    IL_07be:  conv.r8
    IL_07bf:  ldc.r8     -1000
    IL_07c8:  bge.un.s   IL_07d4

    IL_07ca:  ldarg.2
    IL_07cb:  ldind.ref
    IL_07cc:  ldc.i4.s   29
    IL_07ce:  ldc.i4.1
    IL_07cf:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_07d4:  ret
  } // end of method ScannerSettings::ValidateColorMatrix

  .method public hidebysig instance valuetype Calibration.EEPromState 
          ValidateEEProm([Pakon]Pakon.ScannerInitializeWarnings iwWarnings) cil managed
  {
    // Code size       151 (0x97)
    .maxstack  3
    IL_0000:  ldarg.0
    IL_0001:  newobj     instance void [Pakon]Pakon.IntBits::.ctor()
    IL_0006:  stfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibEEPromInvalid
    IL_000b:  ldarg.1
    IL_000c:  ldc.i4.m1
    IL_000d:  bne.un.s   IL_0011

    IL_000f:  ldc.i4.0
    IL_0010:  ret

    IL_0011:  ldarg.0
    IL_0012:  ldarg.0
    IL_0013:  ldfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibEEPromInvalid
    IL_0018:  call       instance void Calibration.ScannerSettings::ValidateMotorSpeeds([Pakon]Pakon.IntBits)
    IL_001d:  ldarg.0
    IL_001e:  ldc.i4.6
    IL_001f:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_0024:  brtrue.s   IL_0032

    IL_0026:  ldarg.0
    IL_0027:  ldarg.0
    IL_0028:  ldfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibEEPromInvalid
    IL_002d:  call       instance void Calibration.ScannerSettings::ValidateSteppers([Pakon]Pakon.IntBits)
    IL_0032:  ldarg.0
    IL_0033:  ldarg.0
    IL_0034:  ldfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibEEPromInvalid
    IL_0039:  call       instance void Calibration.ScannerSettings::ValidateOffsets([Pakon]Pakon.IntBits)
    IL_003e:  ldarg.0
    IL_003f:  ldarg.0
    IL_0040:  ldfld      valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmNegative
    IL_0045:  ldarg.0
    IL_0046:  ldflda     [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibColorNegInvalid
    IL_004b:  call       instance void Calibration.ScannerSettings::ValidateColorMatrix(valuetype Calibration.ColorMatrixConfig,
                                                                                        [Pakon]Pakon.IntBits&)
    IL_0050:  ldarg.0
    IL_0051:  ldc.i4.s   23
    IL_0053:  call       instance bool [Pakon]Pakon.ScannerSettings::get_Item([Pakon]Pakon.ScannerCapabilities)
    IL_0058:  brfalse.s  IL_006c

    IL_005a:  ldarg.0
    IL_005b:  ldarg.0
    IL_005c:  ldfld      valuetype Calibration.ColorMatrixConfig Calibration.ScannerSettings::m_cmPositive
    IL_0061:  ldarg.0
    IL_0062:  ldflda     [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibColorPosInvalid
    IL_0067:  call       instance void Calibration.ScannerSettings::ValidateColorMatrix(valuetype Calibration.ColorMatrixConfig,
                                                                                        [Pakon]Pakon.IntBits&)
    IL_006c:  ldarg.0
    IL_006d:  ldfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibEEPromInvalid
    IL_0072:  callvirt   instance bool [Pakon]Pakon.IntBits::IsEmpty()
    IL_0077:  brfalse.s  IL_0093

    IL_0079:  ldarg.0
    IL_007a:  ldfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibColorNegInvalid
    IL_007f:  callvirt   instance bool [Pakon]Pakon.IntBits::IsEmpty()
    IL_0084:  brfalse.s  IL_0093

    IL_0086:  ldarg.0
    IL_0087:  ldfld      [Pakon]Pakon.IntBits Calibration.ScannerSettings::m_ibColorPosInvalid
    IL_008c:  callvirt   instance bool [Pakon]Pakon.IntBits::IsEmpty()
    IL_0091:  brtrue.s   IL_0095

    IL_0093:  ldc.i4.2
    IL_0094:  ret

    IL_0095:  ldc.i4.1
    IL_0096:  ret
  } // end of method ScannerSettings::ValidateEEProm

  .property instance class Calibration.ScannerSettingsFirmware
          Firmware()
  {
    .get instance class Calibration.ScannerSettingsFirmware Calibration.ScannerSettings::get_Firmware()
  } // end of property ScannerSettings::Firmware
  .property instance [Pakon]Pakon.IntBits
          ColorNegativeInvalid()
  {
    .get instance [Pakon]Pakon.IntBits Calibration.ScannerSettings::get_ColorNegativeInvalid()
  } // end of property ScannerSettings::ColorNegativeInvalid
  .property instance [Pakon]Pakon.IntBits
          ColorPositiveInvalid()
  {
    .get instance [Pakon]Pakon.IntBits Calibration.ScannerSettings::get_ColorPositiveInvalid()
  } // end of property ScannerSettings::ColorPositiveInvalid
  .property instance bool Item(valuetype Calibration.EEPromValue)
  {
    .get instance bool Calibration.ScannerSettings::get_Item(valuetype Calibration.EEPromValue)
  } // end of property ScannerSettings::Item
} // end of class Calibration.ScannerSettings

.class public auto ansi beforefieldinit Calibration.ScannerSettingsFirmware
       extends [mscorlib]System.Object
{
  .field private [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 m_smModel
  .field private valuetype Calibration.USB135 m_usb135
  .field private valuetype Calibration.USB235 m_usb235
  .field private valuetype Calibration.USB335 m_usb335
  .field private int32 m_iHwUSB
  .field private int32 m_iSwUSB
  .field private int32 m_iHwLamp
  .field private int32 m_iSwLamp
  .field private int32 m_iHwCCD
  .field private int32 m_iSwCCD
  .field private int32 m_iHwDX
  .field private int32 m_iSwDX
  .field private int32 m_iHwMotor
  .field private int32 m_iSwMotor
  .field private int32 m_iHwAps
  .field private int32 m_iSwAps
  .field private string[] m_aryMotorFirmwareNames
  .field private string[] m_aryMotorFirmwareFiles
  .field private string[] m_aryDXFirmwareNames
  .field private string[] m_aryDXFirmwareFiles
  .field private string[] m_aryLampFirmwareNames
  .field private string[] m_aryLampFirmwareFiles
  .field private string[] m_aryCCDFirmwareNames
  .field private string[] m_aryCCDFirmwareFiles
  .field private string[] m_aryAPSFirmwareNames
  .field private string[] m_aryAPSFirmwareFiles
  .method public hidebysig specialname instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 
          get_Model() cil managed
  {
    // Code size       53 (0x35)
    .maxstack  1
    .locals ([Interop.LLCLib]LLCLib.SCANNER_MODEL_000 V_0)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_0006:  stloc.0
    IL_0007:  ldloc.0
    IL_0008:  switch     ( 
                          IL_002b,
                          IL_0025,
                          IL_002d,
                          IL_001f)
    IL_001d:  br.s       IL_0033

    IL_001f:  ldc.i4     0x546
    IL_0024:  ret

    IL_0025:  ldc.i4     0x547
    IL_002a:  ret

    IL_002b:  ldc.i4.7
    IL_002c:  ret

    IL_002d:  ldc.i4     0xd16
    IL_0032:  ret

    IL_0033:  ldc.i4.0
    IL_0034:  ret
  } // end of method ScannerSettingsFirmware::get_Model

  .method public hidebysig specialname instance valuetype Calibration.USB135 
          get_USB135() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Calibration.USB135 Calibration.ScannerSettingsFirmware::m_usb135
    IL_0006:  ret
  } // end of method ScannerSettingsFirmware::get_USB135

  .method public hidebysig specialname instance valuetype Calibration.USB235 
          get_USB235() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Calibration.USB235 Calibration.ScannerSettingsFirmware::m_usb235
    IL_0006:  ret
  } // end of method ScannerSettingsFirmware::get_USB235

  .method public hidebysig specialname instance valuetype Calibration.USB335 
          get_USB335() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Calibration.USB335 Calibration.ScannerSettingsFirmware::m_usb335
    IL_0006:  ret
  } // end of method ScannerSettingsFirmware::get_USB335

  .method public hidebysig specialname instance string 
          get_Motor() cil managed
  {
    // Code size       178 (0xb2)
    .maxstack  3
    .locals (string V_0,
             string V_1)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwMotor
    IL_0006:  ldc.i4     0x1000
    IL_000b:  bne.un.s   IL_001e

    IL_000d:  ldstr      ""
    IL_0012:  ldc.i4.0
    IL_0013:  newarr     [mscorlib]System.Object
    IL_0018:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_001d:  ret

    IL_001e:  ldarg.0
    IL_001f:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwMotor
    IL_0024:  ldc.i4     0x1001
    IL_0029:  beq.s      IL_0038

    IL_002b:  ldarg.0
    IL_002c:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwMotor
    IL_0031:  ldc.i4     0x1002
    IL_0036:  bne.un.s   IL_0049

    IL_0038:  ldstr      "Boot"
    IL_003d:  ldc.i4.0
    IL_003e:  newarr     [mscorlib]System.Object
    IL_0043:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_0048:  ret

    IL_0049:  ldstr      "{0:X}"
    IL_004e:  ldarg.0
    IL_004f:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwMotor
    IL_0054:  box        [mscorlib]System.Int32
    IL_0059:  call       string [mscorlib]System.String::Format(string,
                                                                object)
    IL_005e:  stloc.0
    IL_005f:  ldstr      "{0:X}"
    IL_0064:  ldarg.0
    IL_0065:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwMotor
    IL_006a:  box        [mscorlib]System.Int32
    IL_006f:  call       string [mscorlib]System.String::Format(string,
                                                                object)
    IL_0074:  stloc.1
    IL_0075:  ldloc.0
    IL_0076:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_007b:  ldc.i4.2
    IL_007c:  beq.s      IL_008b

    IL_007e:  ldstr      "0"
    IL_0083:  ldloc.0
    IL_0084:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0089:  br.s       IL_008c

    IL_008b:  ldloc.0
    IL_008c:  stloc.0
    IL_008d:  ldloc.1
    IL_008e:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_0093:  ldc.i4.2
    IL_0094:  beq.s      IL_00a3

    IL_0096:  ldstr      "0"
    IL_009b:  ldloc.1
    IL_009c:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_00a1:  br.s       IL_00a4

    IL_00a3:  ldloc.1
    IL_00a4:  stloc.1
    IL_00a5:  ldstr      "0x{0}, 0x{1}"
    IL_00aa:  ldloc.0
    IL_00ab:  ldloc.1
    IL_00ac:  call       string [mscorlib]System.String::Format(string,
                                                                object,
                                                                object)
    IL_00b1:  ret
  } // end of method ScannerSettingsFirmware::get_Motor

  .method public hidebysig specialname instance string 
          get_DX() cil managed
  {
    // Code size       178 (0xb2)
    .maxstack  3
    .locals (string V_0,
             string V_1)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwDX
    IL_0006:  ldc.i4     0x1000
    IL_000b:  bne.un.s   IL_001e

    IL_000d:  ldstr      ""
    IL_0012:  ldc.i4.0
    IL_0013:  newarr     [mscorlib]System.Object
    IL_0018:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_001d:  ret

    IL_001e:  ldarg.0
    IL_001f:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwDX
    IL_0024:  ldc.i4     0x1001
    IL_0029:  beq.s      IL_0038

    IL_002b:  ldarg.0
    IL_002c:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwDX
    IL_0031:  ldc.i4     0x1002
    IL_0036:  bne.un.s   IL_0049

    IL_0038:  ldstr      "Boot"
    IL_003d:  ldc.i4.0
    IL_003e:  newarr     [mscorlib]System.Object
    IL_0043:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_0048:  ret

    IL_0049:  ldstr      "{0:X}"
    IL_004e:  ldarg.0
    IL_004f:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwDX
    IL_0054:  box        [mscorlib]System.Int32
    IL_0059:  call       string [mscorlib]System.String::Format(string,
                                                                object)
    IL_005e:  stloc.0
    IL_005f:  ldstr      "{0:X}"
    IL_0064:  ldarg.0
    IL_0065:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwDX
    IL_006a:  box        [mscorlib]System.Int32
    IL_006f:  call       string [mscorlib]System.String::Format(string,
                                                                object)
    IL_0074:  stloc.1
    IL_0075:  ldloc.0
    IL_0076:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_007b:  ldc.i4.2
    IL_007c:  beq.s      IL_008b

    IL_007e:  ldstr      "0"
    IL_0083:  ldloc.0
    IL_0084:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0089:  br.s       IL_008c

    IL_008b:  ldloc.0
    IL_008c:  stloc.0
    IL_008d:  ldloc.1
    IL_008e:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_0093:  ldc.i4.2
    IL_0094:  beq.s      IL_00a3

    IL_0096:  ldstr      "0"
    IL_009b:  ldloc.1
    IL_009c:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_00a1:  br.s       IL_00a4

    IL_00a3:  ldloc.1
    IL_00a4:  stloc.1
    IL_00a5:  ldstr      "0x{0}, 0x{1}"
    IL_00aa:  ldloc.0
    IL_00ab:  ldloc.1
    IL_00ac:  call       string [mscorlib]System.String::Format(string,
                                                                object,
                                                                object)
    IL_00b1:  ret
  } // end of method ScannerSettingsFirmware::get_DX

  .method public hidebysig specialname instance string 
          get_Lamp() cil managed
  {
    // Code size       178 (0xb2)
    .maxstack  3
    .locals (string V_0,
             string V_1)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwLamp
    IL_0006:  ldc.i4     0x1000
    IL_000b:  bne.un.s   IL_001e

    IL_000d:  ldstr      ""
    IL_0012:  ldc.i4.0
    IL_0013:  newarr     [mscorlib]System.Object
    IL_0018:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_001d:  ret

    IL_001e:  ldarg.0
    IL_001f:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwLamp
    IL_0024:  ldc.i4     0x1001
    IL_0029:  beq.s      IL_0038

    IL_002b:  ldarg.0
    IL_002c:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwLamp
    IL_0031:  ldc.i4     0x1002
    IL_0036:  bne.un.s   IL_0049

    IL_0038:  ldstr      "Boot"
    IL_003d:  ldc.i4.0
    IL_003e:  newarr     [mscorlib]System.Object
    IL_0043:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_0048:  ret

    IL_0049:  ldstr      "{0:X}"
    IL_004e:  ldarg.0
    IL_004f:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwLamp
    IL_0054:  box        [mscorlib]System.Int32
    IL_0059:  call       string [mscorlib]System.String::Format(string,
                                                                object)
    IL_005e:  stloc.0
    IL_005f:  ldstr      "{0:X}"
    IL_0064:  ldarg.0
    IL_0065:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwLamp
    IL_006a:  box        [mscorlib]System.Int32
    IL_006f:  call       string [mscorlib]System.String::Format(string,
                                                                object)
    IL_0074:  stloc.1
    IL_0075:  ldloc.0
    IL_0076:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_007b:  ldc.i4.2
    IL_007c:  beq.s      IL_008b

    IL_007e:  ldstr      "0"
    IL_0083:  ldloc.0
    IL_0084:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0089:  br.s       IL_008c

    IL_008b:  ldloc.0
    IL_008c:  stloc.0
    IL_008d:  ldloc.1
    IL_008e:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_0093:  ldc.i4.2
    IL_0094:  beq.s      IL_00a3

    IL_0096:  ldstr      "0"
    IL_009b:  ldloc.1
    IL_009c:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_00a1:  br.s       IL_00a4

    IL_00a3:  ldloc.1
    IL_00a4:  stloc.1
    IL_00a5:  ldstr      "0x{0}, 0x{1}"
    IL_00aa:  ldloc.0
    IL_00ab:  ldloc.1
    IL_00ac:  call       string [mscorlib]System.String::Format(string,
                                                                object,
                                                                object)
    IL_00b1:  ret
  } // end of method ScannerSettingsFirmware::get_Lamp

  .method public hidebysig specialname instance string 
          get_CCD() cil managed
  {
    // Code size       178 (0xb2)
    .maxstack  3
    .locals (string V_0,
             string V_1)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwCCD
    IL_0006:  ldc.i4     0x1000
    IL_000b:  bne.un.s   IL_001e

    IL_000d:  ldstr      ""
    IL_0012:  ldc.i4.0
    IL_0013:  newarr     [mscorlib]System.Object
    IL_0018:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_001d:  ret

    IL_001e:  ldarg.0
    IL_001f:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwCCD
    IL_0024:  ldc.i4     0x1001
    IL_0029:  beq.s      IL_0038

    IL_002b:  ldarg.0
    IL_002c:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwCCD
    IL_0031:  ldc.i4     0x1002
    IL_0036:  bne.un.s   IL_0049

    IL_0038:  ldstr      "Boot"
    IL_003d:  ldc.i4.0
    IL_003e:  newarr     [mscorlib]System.Object
    IL_0043:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_0048:  ret

    IL_0049:  ldstr      "{0:X}"
    IL_004e:  ldarg.0
    IL_004f:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwCCD
    IL_0054:  box        [mscorlib]System.Int32
    IL_0059:  call       string [mscorlib]System.String::Format(string,
                                                                object)
    IL_005e:  stloc.0
    IL_005f:  ldstr      "{0:X}"
    IL_0064:  ldarg.0
    IL_0065:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwCCD
    IL_006a:  box        [mscorlib]System.Int32
    IL_006f:  call       string [mscorlib]System.String::Format(string,
                                                                object)
    IL_0074:  stloc.1
    IL_0075:  ldloc.0
    IL_0076:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_007b:  ldc.i4.2
    IL_007c:  beq.s      IL_008b

    IL_007e:  ldstr      "0"
    IL_0083:  ldloc.0
    IL_0084:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0089:  br.s       IL_008c

    IL_008b:  ldloc.0
    IL_008c:  stloc.0
    IL_008d:  ldloc.1
    IL_008e:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_0093:  ldc.i4.2
    IL_0094:  beq.s      IL_00a3

    IL_0096:  ldstr      "0"
    IL_009b:  ldloc.1
    IL_009c:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_00a1:  br.s       IL_00a4

    IL_00a3:  ldloc.1
    IL_00a4:  stloc.1
    IL_00a5:  ldstr      "0x{0}, 0x{1}"
    IL_00aa:  ldloc.0
    IL_00ab:  ldloc.1
    IL_00ac:  call       string [mscorlib]System.String::Format(string,
                                                                object,
                                                                object)
    IL_00b1:  ret
  } // end of method ScannerSettingsFirmware::get_CCD

  .method public hidebysig specialname instance string 
          get_APS() cil managed
  {
    // Code size       178 (0xb2)
    .maxstack  3
    .locals (string V_0,
             string V_1)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwAps
    IL_0006:  ldc.i4     0x1000
    IL_000b:  bne.un.s   IL_001e

    IL_000d:  ldstr      ""
    IL_0012:  ldc.i4.0
    IL_0013:  newarr     [mscorlib]System.Object
    IL_0018:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_001d:  ret

    IL_001e:  ldarg.0
    IL_001f:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwAps
    IL_0024:  ldc.i4     0x1001
    IL_0029:  beq.s      IL_0038

    IL_002b:  ldarg.0
    IL_002c:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwAps
    IL_0031:  ldc.i4     0x1002
    IL_0036:  bne.un.s   IL_0049

    IL_0038:  ldstr      "Boot"
    IL_003d:  ldc.i4.0
    IL_003e:  newarr     [mscorlib]System.Object
    IL_0043:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_0048:  ret

    IL_0049:  ldstr      "{0:X}"
    IL_004e:  ldarg.0
    IL_004f:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwAps
    IL_0054:  box        [mscorlib]System.Int32
    IL_0059:  call       string [mscorlib]System.String::Format(string,
                                                                object)
    IL_005e:  stloc.0
    IL_005f:  ldstr      "{0:X}"
    IL_0064:  ldarg.0
    IL_0065:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwAps
    IL_006a:  box        [mscorlib]System.Int32
    IL_006f:  call       string [mscorlib]System.String::Format(string,
                                                                object)
    IL_0074:  stloc.1
    IL_0075:  ldloc.0
    IL_0076:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_007b:  ldc.i4.2
    IL_007c:  beq.s      IL_008b

    IL_007e:  ldstr      "0"
    IL_0083:  ldloc.0
    IL_0084:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0089:  br.s       IL_008c

    IL_008b:  ldloc.0
    IL_008c:  stloc.0
    IL_008d:  ldloc.1
    IL_008e:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_0093:  ldc.i4.2
    IL_0094:  beq.s      IL_00a3

    IL_0096:  ldstr      "0"
    IL_009b:  ldloc.1
    IL_009c:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_00a1:  br.s       IL_00a4

    IL_00a3:  ldloc.1
    IL_00a4:  stloc.1
    IL_00a5:  ldstr      "0x{0}, 0x{1}"
    IL_00aa:  ldloc.0
    IL_00ab:  ldloc.1
    IL_00ac:  call       string [mscorlib]System.String::Format(string,
                                                                object,
                                                                object)
    IL_00b1:  ret
  } // end of method ScannerSettingsFirmware::get_APS

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       119 (0x77)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.4
    IL_0002:  stfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_0007:  ldarg.0
    IL_0008:  ldc.i4.0
    IL_0009:  stfld      valuetype Calibration.USB135 Calibration.ScannerSettingsFirmware::m_usb135
    IL_000e:  ldarg.0
    IL_000f:  ldc.i4.0
    IL_0010:  stfld      valuetype Calibration.USB235 Calibration.ScannerSettingsFirmware::m_usb235
    IL_0015:  ldarg.0
    IL_0016:  ldc.i4.0
    IL_0017:  stfld      valuetype Calibration.USB335 Calibration.ScannerSettingsFirmware::m_usb335
    IL_001c:  ldarg.0
    IL_001d:  ldc.i4.0
    IL_001e:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iHwUSB
    IL_0023:  ldarg.0
    IL_0024:  ldc.i4.0
    IL_0025:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iSwUSB
    IL_002a:  ldarg.0
    IL_002b:  ldc.i4.0
    IL_002c:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iHwLamp
    IL_0031:  ldarg.0
    IL_0032:  ldc.i4.0
    IL_0033:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iSwLamp
    IL_0038:  ldarg.0
    IL_0039:  ldc.i4.0
    IL_003a:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iHwCCD
    IL_003f:  ldarg.0
    IL_0040:  ldc.i4.0
    IL_0041:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iSwCCD
    IL_0046:  ldarg.0
    IL_0047:  ldc.i4.0
    IL_0048:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iHwDX
    IL_004d:  ldarg.0
    IL_004e:  ldc.i4.0
    IL_004f:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iSwDX
    IL_0054:  ldarg.0
    IL_0055:  ldc.i4.0
    IL_0056:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iHwMotor
    IL_005b:  ldarg.0
    IL_005c:  ldc.i4.0
    IL_005d:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iSwMotor
    IL_0062:  ldarg.0
    IL_0063:  ldc.i4.0
    IL_0064:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iHwAps
    IL_0069:  ldarg.0
    IL_006a:  ldc.i4.0
    IL_006b:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iSwAps
    IL_0070:  ldarg.0
    IL_0071:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0076:  ret
  } // end of method ScannerSettingsFirmware::.ctor

  .method public hidebysig instance void 
          Reset() cil managed
  {
    // Code size       183 (0xb7)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.4
    IL_0002:  stfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_0007:  ldarg.0
    IL_0008:  ldc.i4.0
    IL_0009:  stfld      valuetype Calibration.USB135 Calibration.ScannerSettingsFirmware::m_usb135
    IL_000e:  ldarg.0
    IL_000f:  ldc.i4.0
    IL_0010:  stfld      valuetype Calibration.USB235 Calibration.ScannerSettingsFirmware::m_usb235
    IL_0015:  ldarg.0
    IL_0016:  ldc.i4.0
    IL_0017:  stfld      valuetype Calibration.USB335 Calibration.ScannerSettingsFirmware::m_usb335
    IL_001c:  ldarg.0
    IL_001d:  ldc.i4.0
    IL_001e:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iHwUSB
    IL_0023:  ldarg.0
    IL_0024:  ldc.i4.0
    IL_0025:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iSwUSB
    IL_002a:  ldarg.0
    IL_002b:  ldc.i4.0
    IL_002c:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iHwLamp
    IL_0031:  ldarg.0
    IL_0032:  ldc.i4.0
    IL_0033:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iSwLamp
    IL_0038:  ldarg.0
    IL_0039:  ldc.i4.0
    IL_003a:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iHwCCD
    IL_003f:  ldarg.0
    IL_0040:  ldc.i4.0
    IL_0041:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iSwCCD
    IL_0046:  ldarg.0
    IL_0047:  ldc.i4.0
    IL_0048:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iHwDX
    IL_004d:  ldarg.0
    IL_004e:  ldc.i4.0
    IL_004f:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iSwDX
    IL_0054:  ldarg.0
    IL_0055:  ldc.i4.0
    IL_0056:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iHwMotor
    IL_005b:  ldarg.0
    IL_005c:  ldc.i4.0
    IL_005d:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iSwMotor
    IL_0062:  ldarg.0
    IL_0063:  ldc.i4.0
    IL_0064:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iHwAps
    IL_0069:  ldarg.0
    IL_006a:  ldc.i4.0
    IL_006b:  stfld      int32 Calibration.ScannerSettingsFirmware::m_iSwAps
    IL_0070:  ldarg.0
    IL_0071:  ldnull
    IL_0072:  stfld      string[] Calibration.ScannerSettingsFirmware::m_aryMotorFirmwareNames
    IL_0077:  ldarg.0
    IL_0078:  ldnull
    IL_0079:  stfld      string[] Calibration.ScannerSettingsFirmware::m_aryMotorFirmwareFiles
    IL_007e:  ldarg.0
    IL_007f:  ldnull
    IL_0080:  stfld      string[] Calibration.ScannerSettingsFirmware::m_aryDXFirmwareNames
    IL_0085:  ldarg.0
    IL_0086:  ldnull
    IL_0087:  stfld      string[] Calibration.ScannerSettingsFirmware::m_aryDXFirmwareFiles
    IL_008c:  ldarg.0
    IL_008d:  ldnull
    IL_008e:  stfld      string[] Calibration.ScannerSettingsFirmware::m_aryLampFirmwareNames
    IL_0093:  ldarg.0
    IL_0094:  ldnull
    IL_0095:  stfld      string[] Calibration.ScannerSettingsFirmware::m_aryLampFirmwareFiles
    IL_009a:  ldarg.0
    IL_009b:  ldnull
    IL_009c:  stfld      string[] Calibration.ScannerSettingsFirmware::m_aryCCDFirmwareNames
    IL_00a1:  ldarg.0
    IL_00a2:  ldnull
    IL_00a3:  stfld      string[] Calibration.ScannerSettingsFirmware::m_aryCCDFirmwareFiles
    IL_00a8:  ldarg.0
    IL_00a9:  ldnull
    IL_00aa:  stfld      string[] Calibration.ScannerSettingsFirmware::m_aryAPSFirmwareNames
    IL_00af:  ldarg.0
    IL_00b0:  ldnull
    IL_00b1:  stfld      string[] Calibration.ScannerSettingsFirmware::m_aryAPSFirmwareFiles
    IL_00b6:  ret
  } // end of method ScannerSettingsFirmware::Reset

  .method private hidebysig instance void 
          FindFirmwareFile(string[] aryNames,
                           string[] aryFiles,
                           string strName,
                           [out] string& strFile) cil managed
  {
    // Code size       30 (0x1e)
    .maxstack  3
    .locals (int32 V_0)
    IL_0000:  ldarg.1
    IL_0001:  ldarg.3
    IL_0002:  call       int32 [mscorlib]System.Array::IndexOf([mscorlib]System.Array,
                                                               object)
    IL_0007:  stloc.0
    IL_0008:  ldloc.0
    IL_0009:  ldc.i4.m1
    IL_000a:  bne.un.s   IL_0017

    IL_000c:  ldstr      "Firmware name not found"
    IL_0011:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0016:  throw

    IL_0017:  ldarg.s    strFile
    IL_0019:  ldarg.2
    IL_001a:  ldloc.0
    IL_001b:  ldelem.ref
    IL_001c:  stind.ref
    IL_001d:  ret
  } // end of method ScannerSettingsFirmware::FindFirmwareFile

  .method public hidebysig instance void 
          SetPersonality(class Calibration.Scanner csScanner,
                         string strName) cil managed
  {
    // Code size       341 (0x155)
    .maxstack  3
    .locals (string[] V_0,
             int32[] V_1,
             int32 V_2,
             string[] V_3,
             int32[] V_4,
             int32 V_5,
             string[] V_6,
             int32[] V_7,
             int32 V_8,
             [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 V_9)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_0006:  stloc.s    V_9
    IL_0008:  ldloc.s    V_9
    IL_000a:  switch     ( 
                          IL_0082,
                          IL_0024,
                          IL_00e5,
                          IL_0024)
    IL_001f:  br         IL_014a

    IL_0024:  ldarg.0
    IL_0025:  ldfld      valuetype Calibration.USB135 Calibration.ScannerSettingsFirmware::m_usb135
    IL_002a:  box        Calibration.USB135
    IL_002f:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_0034:  call       string[] [mscorlib]System.Enum::GetNames([mscorlib]System.Type)
    IL_0039:  stloc.0
    IL_003a:  ldarg.0
    IL_003b:  ldfld      valuetype Calibration.USB135 Calibration.ScannerSettingsFirmware::m_usb135
    IL_0040:  box        Calibration.USB135
    IL_0045:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_004a:  call       [mscorlib]System.Array [mscorlib]System.Enum::GetValues([mscorlib]System.Type)
    IL_004f:  castclass  int32[]
    IL_0054:  stloc.1
    IL_0055:  ldloc.0
    IL_0056:  ldarg.2
    IL_0057:  call       int32 [mscorlib]System.Array::IndexOf([mscorlib]System.Array,
                                                               object)
    IL_005c:  stloc.2
    IL_005d:  ldloc.2
    IL_005e:  ldc.i4.m1
    IL_005f:  beq.s      IL_0077

    IL_0061:  ldarg.0
    IL_0062:  ldloc.1
    IL_0063:  ldloc.2
    IL_0064:  ldelem.i4
    IL_0065:  stfld      valuetype Calibration.USB135 Calibration.ScannerSettingsFirmware::m_usb135
    IL_006a:  ldarg.1
    IL_006b:  ldarg.0
    IL_006c:  ldfld      valuetype Calibration.USB135 Calibration.ScannerSettingsFirmware::m_usb135
    IL_0071:  callvirt   instance void Calibration.Scanner::SetPersonality(valuetype Calibration.USB135)
    IL_0076:  ret

    IL_0077:  ldstr      "USB135 Invalid"
    IL_007c:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0081:  throw

    IL_0082:  ldarg.0
    IL_0083:  ldfld      valuetype Calibration.USB235 Calibration.ScannerSettingsFirmware::m_usb235
    IL_0088:  box        Calibration.USB235
    IL_008d:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_0092:  call       string[] [mscorlib]System.Enum::GetNames([mscorlib]System.Type)
    IL_0097:  stloc.3
    IL_0098:  ldarg.0
    IL_0099:  ldfld      valuetype Calibration.USB235 Calibration.ScannerSettingsFirmware::m_usb235
    IL_009e:  box        Calibration.USB235
    IL_00a3:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_00a8:  call       [mscorlib]System.Array [mscorlib]System.Enum::GetValues([mscorlib]System.Type)
    IL_00ad:  castclass  int32[]
    IL_00b2:  stloc.s    V_4
    IL_00b4:  ldloc.3
    IL_00b5:  ldarg.2
    IL_00b6:  call       int32 [mscorlib]System.Array::IndexOf([mscorlib]System.Array,
                                                               object)
    IL_00bb:  stloc.s    V_5
    IL_00bd:  ldloc.s    V_5
    IL_00bf:  ldc.i4.m1
    IL_00c0:  beq.s      IL_00da

    IL_00c2:  ldarg.0
    IL_00c3:  ldloc.s    V_4
    IL_00c5:  ldloc.s    V_5
    IL_00c7:  ldelem.i4
    IL_00c8:  stfld      valuetype Calibration.USB235 Calibration.ScannerSettingsFirmware::m_usb235
    IL_00cd:  ldarg.1
    IL_00ce:  ldarg.0
    IL_00cf:  ldfld      valuetype Calibration.USB235 Calibration.ScannerSettingsFirmware::m_usb235
    IL_00d4:  callvirt   instance void Calibration.Scanner::SetPersonality(valuetype Calibration.USB235)
    IL_00d9:  ret

    IL_00da:  ldstr      "USB135 Invalid"
    IL_00df:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_00e4:  throw

    IL_00e5:  ldarg.0
    IL_00e6:  ldfld      valuetype Calibration.USB335 Calibration.ScannerSettingsFirmware::m_usb335
    IL_00eb:  box        Calibration.USB335
    IL_00f0:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_00f5:  call       string[] [mscorlib]System.Enum::GetNames([mscorlib]System.Type)
    IL_00fa:  stloc.s    V_6
    IL_00fc:  ldarg.0
    IL_00fd:  ldfld      valuetype Calibration.USB335 Calibration.ScannerSettingsFirmware::m_usb335
    IL_0102:  box        Calibration.USB335
    IL_0107:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_010c:  call       [mscorlib]System.Array [mscorlib]System.Enum::GetValues([mscorlib]System.Type)
    IL_0111:  castclass  int32[]
    IL_0116:  stloc.s    V_7
    IL_0118:  ldloc.s    V_6
    IL_011a:  ldarg.2
    IL_011b:  call       int32 [mscorlib]System.Array::IndexOf([mscorlib]System.Array,
                                                               object)
    IL_0120:  stloc.s    V_8
    IL_0122:  ldloc.s    V_8
    IL_0124:  ldc.i4.m1
    IL_0125:  beq.s      IL_013f

    IL_0127:  ldarg.0
    IL_0128:  ldloc.s    V_7
    IL_012a:  ldloc.s    V_8
    IL_012c:  ldelem.i4
    IL_012d:  stfld      valuetype Calibration.USB335 Calibration.ScannerSettingsFirmware::m_usb335
    IL_0132:  ldarg.1
    IL_0133:  ldarg.0
    IL_0134:  ldfld      valuetype Calibration.USB335 Calibration.ScannerSettingsFirmware::m_usb335
    IL_0139:  callvirt   instance void Calibration.Scanner::SetPersonality(valuetype Calibration.USB335)
    IL_013e:  ret

    IL_013f:  ldstr      "USB135 Invalid"
    IL_0144:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0149:  throw

    IL_014a:  ldstr      "Scanner Model Invalid"
    IL_014f:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0154:  throw
  } // end of method ScannerSettingsFirmware::SetPersonality

  .method public hidebysig instance void 
          GetFirmwareFile(valuetype Calibration.ScannerFirmware sfModule,
                          string strName,
                          [out] [Interop.LLCLib]LLCLib.PIC_000& pic,
                          [out] string& strFile) cil managed
  {
    // Code size       168 (0xa8)
    .maxstack  5
    .locals (valuetype Calibration.ScannerFirmware V_0)
    IL_0000:  ldarg.1
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  ldc.i4.1
    IL_0004:  sub
    IL_0005:  switch     ( 
                          IL_0084,
                          IL_0052,
                          IL_006b,
                          IL_0039,
                          IL_0020)
    IL_001e:  br.s       IL_009d

    IL_0020:  ldarg.3
    IL_0021:  ldc.i4.4
    IL_0022:  stind.i4
    IL_0023:  ldarg.0
    IL_0024:  ldarg.0
    IL_0025:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryAPSFirmwareNames
    IL_002a:  ldarg.0
    IL_002b:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryAPSFirmwareFiles
    IL_0030:  ldarg.2
    IL_0031:  ldarg.s    strFile
    IL_0033:  call       instance void Calibration.ScannerSettingsFirmware::FindFirmwareFile(string[],
                                                                                             string[],
                                                                                             string,
                                                                                             string&)
    IL_0038:  ret

    IL_0039:  ldarg.3
    IL_003a:  ldc.i4.2
    IL_003b:  stind.i4
    IL_003c:  ldarg.0
    IL_003d:  ldarg.0
    IL_003e:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryCCDFirmwareNames
    IL_0043:  ldarg.0
    IL_0044:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryCCDFirmwareFiles
    IL_0049:  ldarg.2
    IL_004a:  ldarg.s    strFile
    IL_004c:  call       instance void Calibration.ScannerSettingsFirmware::FindFirmwareFile(string[],
                                                                                             string[],
                                                                                             string,
                                                                                             string&)
    IL_0051:  ret

    IL_0052:  ldarg.3
    IL_0053:  ldc.i4.3
    IL_0054:  stind.i4
    IL_0055:  ldarg.0
    IL_0056:  ldarg.0
    IL_0057:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryDXFirmwareNames
    IL_005c:  ldarg.0
    IL_005d:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryDXFirmwareFiles
    IL_0062:  ldarg.2
    IL_0063:  ldarg.s    strFile
    IL_0065:  call       instance void Calibration.ScannerSettingsFirmware::FindFirmwareFile(string[],
                                                                                             string[],
                                                                                             string,
                                                                                             string&)
    IL_006a:  ret

    IL_006b:  ldarg.3
    IL_006c:  ldc.i4.1
    IL_006d:  stind.i4
    IL_006e:  ldarg.0
    IL_006f:  ldarg.0
    IL_0070:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryLampFirmwareNames
    IL_0075:  ldarg.0
    IL_0076:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryLampFirmwareFiles
    IL_007b:  ldarg.2
    IL_007c:  ldarg.s    strFile
    IL_007e:  call       instance void Calibration.ScannerSettingsFirmware::FindFirmwareFile(string[],
                                                                                             string[],
                                                                                             string,
                                                                                             string&)
    IL_0083:  ret

    IL_0084:  ldarg.3
    IL_0085:  ldc.i4.0
    IL_0086:  stind.i4
    IL_0087:  ldarg.0
    IL_0088:  ldarg.0
    IL_0089:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryMotorFirmwareNames
    IL_008e:  ldarg.0
    IL_008f:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryMotorFirmwareFiles
    IL_0094:  ldarg.2
    IL_0095:  ldarg.s    strFile
    IL_0097:  call       instance void Calibration.ScannerSettingsFirmware::FindFirmwareFile(string[],
                                                                                             string[],
                                                                                             string,
                                                                                             string&)
    IL_009c:  ret

    IL_009d:  ldstr      "Firmware module not supported"
    IL_00a2:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_00a7:  throw
  } // end of method ScannerSettingsFirmware::GetFirmwareFile

  .method public hidebysig instance bool 
          GetInformation(class Calibration.Scanner csScanner,
                         [Interop.TLXLib]TLXLib.SCANNER_TYPE_000& stType,
                         int32& iSerialNumber,
                         [Pakon]Pakon.ScannerHW135& sh135,
                         [Pakon]Pakon.ScannerHW235& sh235,
                         [Pakon]Pakon.ScannerHW335& sh335) cil managed
  {
    // Code size       442 (0x1ba)
    .maxstack  20
    .locals (bool V_0,
             int32 V_1,
             int32 V_2,
             bool V_3)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldc.i4.0
    IL_0003:  stloc.1
    IL_0004:  ldc.i4.0
    IL_0005:  stloc.2
    IL_0006:  ldarg.1
    IL_0007:  ldarg.0
    IL_0008:  ldflda     [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_000d:  ldarg.0
    IL_000e:  ldflda     valuetype Calibration.USB135 Calibration.ScannerSettingsFirmware::m_usb135
    IL_0013:  ldarg.0
    IL_0014:  ldflda     valuetype Calibration.USB235 Calibration.ScannerSettingsFirmware::m_usb235
    IL_0019:  ldarg.0
    IL_001a:  ldflda     valuetype Calibration.USB335 Calibration.ScannerSettingsFirmware::m_usb335
    IL_001f:  ldloca.s   V_0
    IL_0021:  callvirt   instance void Calibration.Scanner::FindPersonality([Interop.LLCLib]LLCLib.SCANNER_MODEL_000&,
                                                                            valuetype Calibration.USB135&,
                                                                            valuetype Calibration.USB235&,
                                                                            valuetype Calibration.USB335&,
                                                                            bool&)
    IL_0026:  ldarg.1
    IL_0027:  ldloca.s   V_1
    IL_0029:  ldloca.s   V_2
    IL_002b:  ldarg.2
    IL_002c:  ldarg.s    sh135
    IL_002e:  ldarg.s    sh235
    IL_0030:  ldarg.s    sh335
    IL_0032:  ldarg.3
    IL_0033:  ldarg.0
    IL_0034:  ldflda     int32 Calibration.ScannerSettingsFirmware::m_iHwUSB
    IL_0039:  ldarg.0
    IL_003a:  ldflda     int32 Calibration.ScannerSettingsFirmware::m_iHwLamp
    IL_003f:  ldarg.0
    IL_0040:  ldflda     int32 Calibration.ScannerSettingsFirmware::m_iHwCCD
    IL_0045:  ldarg.0
    IL_0046:  ldflda     int32 Calibration.ScannerSettingsFirmware::m_iHwDX
    IL_004b:  ldarg.0
    IL_004c:  ldflda     int32 Calibration.ScannerSettingsFirmware::m_iHwMotor
    IL_0051:  ldarg.0
    IL_0052:  ldflda     int32 Calibration.ScannerSettingsFirmware::m_iHwAps
    IL_0057:  ldarg.0
    IL_0058:  ldflda     int32 Calibration.ScannerSettingsFirmware::m_iSwUSB
    IL_005d:  ldarg.0
    IL_005e:  ldflda     int32 Calibration.ScannerSettingsFirmware::m_iSwLamp
    IL_0063:  ldarg.0
    IL_0064:  ldflda     int32 Calibration.ScannerSettingsFirmware::m_iSwCCD
    IL_0069:  ldarg.0
    IL_006a:  ldflda     int32 Calibration.ScannerSettingsFirmware::m_iSwDX
    IL_006f:  ldarg.0
    IL_0070:  ldflda     int32 Calibration.ScannerSettingsFirmware::m_iSwMotor
    IL_0075:  ldarg.0
    IL_0076:  ldflda     int32 Calibration.ScannerSettingsFirmware::m_iSwAps
    IL_007b:  callvirt   instance void Calibration.Scanner::FirmwareAssess(int32&,
                                                                           int32&,
                                                                           [Interop.TLXLib]TLXLib.SCANNER_TYPE_000&,
                                                                           [Pakon]Pakon.ScannerHW135&,
                                                                           [Pakon]Pakon.ScannerHW235&,
                                                                           [Pakon]Pakon.ScannerHW335&,
                                                                           int32&,
                                                                           int32&,
                                                                           int32&,
                                                                           int32&,
                                                                           int32&,
                                                                           int32&,
                                                                           int32&,
                                                                           int32&,
                                                                           int32&,
                                                                           int32&,
                                                                           int32&,
                                                                           int32&,
                                                                           int32&)
    IL_0080:  ldc.i4.1
    IL_0081:  stloc.3
    IL_0082:  ldarg.2
    IL_0083:  ldind.i4
    IL_0084:  brtrue.s   IL_0088

    IL_0086:  ldc.i4.0
    IL_0087:  stloc.3
    IL_0088:  ldarg.0
    IL_0089:  ldfld      valuetype Calibration.USB135 Calibration.ScannerSettingsFirmware::m_usb135
    IL_008e:  brtrue.s   IL_00a2

    IL_0090:  ldarg.0
    IL_0091:  ldfld      valuetype Calibration.USB235 Calibration.ScannerSettingsFirmware::m_usb235
    IL_0096:  brtrue.s   IL_00a2

    IL_0098:  ldarg.0
    IL_0099:  ldfld      valuetype Calibration.USB335 Calibration.ScannerSettingsFirmware::m_usb335
    IL_009e:  brtrue.s   IL_00a2

    IL_00a0:  ldc.i4.0
    IL_00a1:  stloc.3
    IL_00a2:  ldarg.s    sh135
    IL_00a4:  ldind.i4
    IL_00a5:  brtrue.s   IL_00b3

    IL_00a7:  ldarg.s    sh235
    IL_00a9:  ldind.i4
    IL_00aa:  brtrue.s   IL_00b3

    IL_00ac:  ldarg.s    sh335
    IL_00ae:  ldind.i4
    IL_00af:  brtrue.s   IL_00b3

    IL_00b1:  ldc.i4.0
    IL_00b2:  stloc.3
    IL_00b3:  ldarg.0
    IL_00b4:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwLamp
    IL_00b9:  ldc.i4     0x100
    IL_00be:  bge.s      IL_00df

    IL_00c0:  ldarg.0
    IL_00c1:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwLamp
    IL_00c6:  ldc.i4     0x100
    IL_00cb:  bge.s      IL_00df

    IL_00cd:  ldarg.0
    IL_00ce:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwLamp
    IL_00d3:  ldc.i4.0
    IL_00d4:  blt.s      IL_00df

    IL_00d6:  ldarg.0
    IL_00d7:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwLamp
    IL_00dc:  ldc.i4.0
    IL_00dd:  bgt.s      IL_00e1

    IL_00df:  ldc.i4.0
    IL_00e0:  stloc.3
    IL_00e1:  ldarg.0
    IL_00e2:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwMotor
    IL_00e7:  ldc.i4     0x100
    IL_00ec:  bge.s      IL_010d

    IL_00ee:  ldarg.0
    IL_00ef:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwMotor
    IL_00f4:  ldc.i4     0x100
    IL_00f9:  bge.s      IL_010d

    IL_00fb:  ldarg.0
    IL_00fc:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwMotor
    IL_0101:  ldc.i4.0
    IL_0102:  blt.s      IL_010d

    IL_0104:  ldarg.0
    IL_0105:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwMotor
    IL_010a:  ldc.i4.0
    IL_010b:  bgt.s      IL_010f

    IL_010d:  ldc.i4.0
    IL_010e:  stloc.3
    IL_010f:  ldarg.2
    IL_0110:  ldind.i4
    IL_0111:  ldc.i4     0x546
    IL_0116:  beq.s      IL_017d

    IL_0118:  ldarg.2
    IL_0119:  ldind.i4
    IL_011a:  ldc.i4     0x547
    IL_011f:  beq.s      IL_017d

    IL_0121:  ldarg.0
    IL_0122:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwCCD
    IL_0127:  ldc.i4     0x100
    IL_012c:  bge.s      IL_014d

    IL_012e:  ldarg.0
    IL_012f:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwCCD
    IL_0134:  ldc.i4     0x100
    IL_0139:  bge.s      IL_014d

    IL_013b:  ldarg.0
    IL_013c:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwCCD
    IL_0141:  ldc.i4.0
    IL_0142:  blt.s      IL_014d

    IL_0144:  ldarg.0
    IL_0145:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwCCD
    IL_014a:  ldc.i4.0
    IL_014b:  bgt.s      IL_014f

    IL_014d:  ldc.i4.0
    IL_014e:  stloc.3
    IL_014f:  ldarg.0
    IL_0150:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwDX
    IL_0155:  ldc.i4     0x100
    IL_015a:  bge.s      IL_017b

    IL_015c:  ldarg.0
    IL_015d:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwDX
    IL_0162:  ldc.i4     0x100
    IL_0167:  bge.s      IL_017b

    IL_0169:  ldarg.0
    IL_016a:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwDX
    IL_016f:  ldc.i4.0
    IL_0170:  blt.s      IL_017b

    IL_0172:  ldarg.0
    IL_0173:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwDX
    IL_0178:  ldc.i4.0
    IL_0179:  bgt.s      IL_017d

    IL_017b:  ldc.i4.0
    IL_017c:  stloc.3
    IL_017d:  ldarg.0
    IL_017e:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwAps
    IL_0183:  ldc.i4     0x1000
    IL_0188:  beq.s      IL_01b8

    IL_018a:  ldarg.0
    IL_018b:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwAps
    IL_0190:  ldc.i4     0x100
    IL_0195:  bge.s      IL_01b6

    IL_0197:  ldarg.0
    IL_0198:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwAps
    IL_019d:  ldc.i4     0x100
    IL_01a2:  bge.s      IL_01b6

    IL_01a4:  ldarg.0
    IL_01a5:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwAps
    IL_01aa:  ldc.i4.0
    IL_01ab:  blt.s      IL_01b6

    IL_01ad:  ldarg.0
    IL_01ae:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iSwAps
    IL_01b3:  ldc.i4.0
    IL_01b4:  bgt.s      IL_01b8

    IL_01b6:  ldc.i4.0
    IL_01b7:  stloc.3
    IL_01b8:  ldloc.3
    IL_01b9:  ret
  } // end of method ScannerSettingsFirmware::GetInformation

  .method public hidebysig instance void 
          GetFileInformation(class Calibration.Scanner csScanner,
                             valuetype Calibration.ScannerFirmware sfModule,
                             [System.Windows.Forms]System.Windows.Forms.TextBox tbFirmware,
                             [System.Windows.Forms]System.Windows.Forms.ComboBox cbFirmwareChange) cil managed
  {
    // Code size       580 (0x244)
    .maxstack  6
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2,
             int32 V_3,
             int32 V_4,
             valuetype Calibration.ScannerFirmware V_5,
             [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 V_6)
    IL_0000:  ldarg.2
    IL_0001:  stloc.s    V_5
    IL_0003:  ldloc.s    V_5
    IL_0005:  ldc.i4.1
    IL_0006:  sub
    IL_0007:  switch     ( 
                          IL_01cd,
                          IL_00f7,
                          IL_0160,
                          IL_008e,
                          IL_0025)
    IL_0020:  br         IL_0238

    IL_0025:  ldarg.0
    IL_0026:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_002b:  stloc.s    V_6
    IL_002d:  ldloc.s    V_6
    IL_002f:  switch     ( 
                          IL_0041,
                          IL_0243,
                          IL_0041)
    IL_0040:  ret

    IL_0041:  ldarg.0
    IL_0042:  call       instance string Calibration.ScannerSettingsFirmware::get_APS()
    IL_0047:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_004c:  brfalse    IL_0243

    IL_0051:  ldarg.3
    IL_0052:  ldarg.0
    IL_0053:  call       instance string Calibration.ScannerSettingsFirmware::get_APS()
    IL_0058:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_005d:  ldarg.0
    IL_005e:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_0063:  ldarg.2
    IL_0064:  ldarg.0
    IL_0065:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwAps
    IL_006a:  ldarg.0
    IL_006b:  ldflda     string[] Calibration.ScannerSettingsFirmware::m_aryAPSFirmwareNames
    IL_0070:  ldarg.0
    IL_0071:  ldflda     string[] Calibration.ScannerSettingsFirmware::m_aryAPSFirmwareFiles
    IL_0076:  ldloca.s   V_0
    IL_0078:  call       void Calibration.TLXRegistry::LoadFirmwareFileInformation([Interop.LLCLib]LLCLib.SCANNER_MODEL_000,
                                                                                   valuetype Calibration.ScannerFirmware,
                                                                                   int32,
                                                                                   string[]&,
                                                                                   string[]&,
                                                                                   int32&)
    IL_007d:  ldarg.0
    IL_007e:  ldarg.0
    IL_007f:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryAPSFirmwareNames
    IL_0084:  ldarg.3
    IL_0085:  ldarg.s    cbFirmwareChange
    IL_0087:  ldloc.0
    IL_0088:  call       instance void Calibration.ScannerSettingsFirmware::DisplayFileInformation(string[],
                                                                                                   [System.Windows.Forms]System.Windows.Forms.TextBox,
                                                                                                   [System.Windows.Forms]System.Windows.Forms.ComboBox,
                                                                                                   int32)
    IL_008d:  ret

    IL_008e:  ldarg.0
    IL_008f:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_0094:  stloc.s    V_6
    IL_0096:  ldloc.s    V_6
    IL_0098:  switch     ( 
                          IL_00aa,
                          IL_0243,
                          IL_00aa)
    IL_00a9:  ret

    IL_00aa:  ldarg.0
    IL_00ab:  call       instance string Calibration.ScannerSettingsFirmware::get_CCD()
    IL_00b0:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_00b5:  brfalse    IL_0243

    IL_00ba:  ldarg.3
    IL_00bb:  ldarg.0
    IL_00bc:  call       instance string Calibration.ScannerSettingsFirmware::get_CCD()
    IL_00c1:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_00c6:  ldarg.0
    IL_00c7:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_00cc:  ldarg.2
    IL_00cd:  ldarg.0
    IL_00ce:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwCCD
    IL_00d3:  ldarg.0
    IL_00d4:  ldflda     string[] Calibration.ScannerSettingsFirmware::m_aryCCDFirmwareNames
    IL_00d9:  ldarg.0
    IL_00da:  ldflda     string[] Calibration.ScannerSettingsFirmware::m_aryCCDFirmwareFiles
    IL_00df:  ldloca.s   V_1
    IL_00e1:  call       void Calibration.TLXRegistry::LoadFirmwareFileInformation([Interop.LLCLib]LLCLib.SCANNER_MODEL_000,
                                                                                   valuetype Calibration.ScannerFirmware,
                                                                                   int32,
                                                                                   string[]&,
                                                                                   string[]&,
                                                                                   int32&)
    IL_00e6:  ldarg.0
    IL_00e7:  ldarg.0
    IL_00e8:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryCCDFirmwareNames
    IL_00ed:  ldarg.3
    IL_00ee:  ldarg.s    cbFirmwareChange
    IL_00f0:  ldloc.1
    IL_00f1:  call       instance void Calibration.ScannerSettingsFirmware::DisplayFileInformation(string[],
                                                                                                   [System.Windows.Forms]System.Windows.Forms.TextBox,
                                                                                                   [System.Windows.Forms]System.Windows.Forms.ComboBox,
                                                                                                   int32)
    IL_00f6:  ret

    IL_00f7:  ldarg.0
    IL_00f8:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_00fd:  stloc.s    V_6
    IL_00ff:  ldloc.s    V_6
    IL_0101:  switch     ( 
                          IL_0113,
                          IL_0243,
                          IL_0113)
    IL_0112:  ret

    IL_0113:  ldarg.0
    IL_0114:  call       instance string Calibration.ScannerSettingsFirmware::get_DX()
    IL_0119:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_011e:  brfalse    IL_0243

    IL_0123:  ldarg.3
    IL_0124:  ldarg.0
    IL_0125:  call       instance string Calibration.ScannerSettingsFirmware::get_DX()
    IL_012a:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_012f:  ldarg.0
    IL_0130:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_0135:  ldarg.2
    IL_0136:  ldarg.0
    IL_0137:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwDX
    IL_013c:  ldarg.0
    IL_013d:  ldflda     string[] Calibration.ScannerSettingsFirmware::m_aryDXFirmwareNames
    IL_0142:  ldarg.0
    IL_0143:  ldflda     string[] Calibration.ScannerSettingsFirmware::m_aryDXFirmwareFiles
    IL_0148:  ldloca.s   V_2
    IL_014a:  call       void Calibration.TLXRegistry::LoadFirmwareFileInformation([Interop.LLCLib]LLCLib.SCANNER_MODEL_000,
                                                                                   valuetype Calibration.ScannerFirmware,
                                                                                   int32,
                                                                                   string[]&,
                                                                                   string[]&,
                                                                                   int32&)
    IL_014f:  ldarg.0
    IL_0150:  ldarg.0
    IL_0151:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryDXFirmwareNames
    IL_0156:  ldarg.3
    IL_0157:  ldarg.s    cbFirmwareChange
    IL_0159:  ldloc.2
    IL_015a:  call       instance void Calibration.ScannerSettingsFirmware::DisplayFileInformation(string[],
                                                                                                   [System.Windows.Forms]System.Windows.Forms.TextBox,
                                                                                                   [System.Windows.Forms]System.Windows.Forms.ComboBox,
                                                                                                   int32)
    IL_015f:  ret

    IL_0160:  ldarg.0
    IL_0161:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_0166:  stloc.s    V_6
    IL_0168:  ldloc.s    V_6
    IL_016a:  switch     ( 
                          IL_0180,
                          IL_0180,
                          IL_0180,
                          IL_0180)
    IL_017f:  ret

    IL_0180:  ldarg.0
    IL_0181:  call       instance string Calibration.ScannerSettingsFirmware::get_Lamp()
    IL_0186:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_018b:  brfalse    IL_0243

    IL_0190:  ldarg.3
    IL_0191:  ldarg.0
    IL_0192:  call       instance string Calibration.ScannerSettingsFirmware::get_Lamp()
    IL_0197:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_019c:  ldarg.0
    IL_019d:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_01a2:  ldarg.2
    IL_01a3:  ldarg.0
    IL_01a4:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwLamp
    IL_01a9:  ldarg.0
    IL_01aa:  ldflda     string[] Calibration.ScannerSettingsFirmware::m_aryLampFirmwareNames
    IL_01af:  ldarg.0
    IL_01b0:  ldflda     string[] Calibration.ScannerSettingsFirmware::m_aryLampFirmwareFiles
    IL_01b5:  ldloca.s   V_3
    IL_01b7:  call       void Calibration.TLXRegistry::LoadFirmwareFileInformation([Interop.LLCLib]LLCLib.SCANNER_MODEL_000,
                                                                                   valuetype Calibration.ScannerFirmware,
                                                                                   int32,
                                                                                   string[]&,
                                                                                   string[]&,
                                                                                   int32&)
    IL_01bc:  ldarg.0
    IL_01bd:  ldarg.0
    IL_01be:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryLampFirmwareNames
    IL_01c3:  ldarg.3
    IL_01c4:  ldarg.s    cbFirmwareChange
    IL_01c6:  ldloc.3
    IL_01c7:  call       instance void Calibration.ScannerSettingsFirmware::DisplayFileInformation(string[],
                                                                                                   [System.Windows.Forms]System.Windows.Forms.TextBox,
                                                                                                   [System.Windows.Forms]System.Windows.Forms.ComboBox,
                                                                                                   int32)
    IL_01cc:  ret

    IL_01cd:  ldarg.0
    IL_01ce:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_01d3:  stloc.s    V_6
    IL_01d5:  ldloc.s    V_6
    IL_01d7:  switch     ( 
                          IL_01ed,
                          IL_01ed,
                          IL_01ed,
                          IL_01ed)
    IL_01ec:  ret

    IL_01ed:  ldarg.0
    IL_01ee:  call       instance string Calibration.ScannerSettingsFirmware::get_Motor()
    IL_01f3:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_01f8:  brfalse.s  IL_0243

    IL_01fa:  ldarg.3
    IL_01fb:  ldarg.0
    IL_01fc:  call       instance string Calibration.ScannerSettingsFirmware::get_Motor()
    IL_0201:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Text(string)
    IL_0206:  ldarg.0
    IL_0207:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.ScannerSettingsFirmware::m_smModel
    IL_020c:  ldarg.2
    IL_020d:  ldarg.0
    IL_020e:  ldfld      int32 Calibration.ScannerSettingsFirmware::m_iHwMotor
    IL_0213:  ldarg.0
    IL_0214:  ldflda     string[] Calibration.ScannerSettingsFirmware::m_aryMotorFirmwareNames
    IL_0219:  ldarg.0
    IL_021a:  ldflda     string[] Calibration.ScannerSettingsFirmware::m_aryMotorFirmwareFiles
    IL_021f:  ldloca.s   V_4
    IL_0221:  call       void Calibration.TLXRegistry::LoadFirmwareFileInformation([Interop.LLCLib]LLCLib.SCANNER_MODEL_000,
                                                                                   valuetype Calibration.ScannerFirmware,
                                                                                   int32,
                                                                                   string[]&,
                                                                                   string[]&,
                                                                                   int32&)
    IL_0226:  ldarg.0
    IL_0227:  ldarg.0
    IL_0228:  ldfld      string[] Calibration.ScannerSettingsFirmware::m_aryMotorFirmwareNames
    IL_022d:  ldarg.3
    IL_022e:  ldarg.s    cbFirmwareChange
    IL_0230:  ldloc.s    V_4
    IL_0232:  call       instance void Calibration.ScannerSettingsFirmware::DisplayFileInformation(string[],
                                                                                                   [System.Windows.Forms]System.Windows.Forms.TextBox,
                                                                                                   [System.Windows.Forms]System.Windows.Forms.ComboBox,
                                                                                                   int32)
    IL_0237:  ret

    IL_0238:  ldstr      "Invalid ScannerFirmware"
    IL_023d:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0242:  throw

    IL_0243:  ret
  } // end of method ScannerSettingsFirmware::GetFileInformation

  .method private hidebysig instance void 
          DisplayFileInformation(string[] aryNames,
                                 [System.Windows.Forms]System.Windows.Forms.TextBox tbBoard,
                                 [System.Windows.Forms]System.Windows.Forms.ComboBox cbBoardChange,
                                 int32 iSelect) cil managed
  {
    // Code size       135 (0x87)
    .maxstack  3
    .locals (string V_0,
             int32 V_1,
             string[] V_2,
             int32 V_3)
    IL_0000:  ldarg.3
    IL_0001:  callvirt   instance [System.Windows.Forms]System.Windows.Forms.ComboBox/ObjectCollection [System.Windows.Forms]System.Windows.Forms.ComboBox::get_Items()
    IL_0006:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.ComboBox/ObjectCollection::Clear()
    IL_000b:  ldarg.1
    IL_000c:  brfalse.s  IL_002f

    IL_000e:  ldarg.1
    IL_000f:  stloc.2
    IL_0010:  ldc.i4.0
    IL_0011:  stloc.3
    IL_0012:  br.s       IL_0029

    IL_0014:  ldloc.2
    IL_0015:  ldloc.3
    IL_0016:  ldelem.ref
    IL_0017:  stloc.0
    IL_0018:  ldarg.3
    IL_0019:  callvirt   instance [System.Windows.Forms]System.Windows.Forms.ComboBox/ObjectCollection [System.Windows.Forms]System.Windows.Forms.ComboBox::get_Items()
    IL_001e:  ldloc.0
    IL_001f:  callvirt   instance int32 [System.Windows.Forms]System.Windows.Forms.ComboBox/ObjectCollection::Add(object)
    IL_0024:  pop
    IL_0025:  ldloc.3
    IL_0026:  ldc.i4.1
    IL_0027:  add
    IL_0028:  stloc.3
    IL_0029:  ldloc.3
    IL_002a:  ldloc.2
    IL_002b:  ldlen
    IL_002c:  conv.i4
    IL_002d:  blt.s      IL_0014

    IL_002f:  ldarg.3
    IL_0030:  callvirt   instance [System.Windows.Forms]System.Windows.Forms.ComboBox/ObjectCollection [System.Windows.Forms]System.Windows.Forms.ComboBox::get_Items()
    IL_0035:  callvirt   instance int32 [System.Windows.Forms]System.Windows.Forms.ComboBox/ObjectCollection::get_Count()
    IL_003a:  ldc.i4.0
    IL_003b:  ble.s      IL_0086

    IL_003d:  ldarg.3
    IL_003e:  ldarg.2
    IL_003f:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0044:  callvirt   instance int32 [System.Windows.Forms]System.Windows.Forms.ComboBox::FindString(string)
    IL_0049:  ldc.i4.m1
    IL_004a:  bne.un.s   IL_006d

    IL_004c:  ldarg.3
    IL_004d:  callvirt   instance [System.Windows.Forms]System.Windows.Forms.ComboBox/ObjectCollection [System.Windows.Forms]System.Windows.Forms.ComboBox::get_Items()
    IL_0052:  ldarg.2
    IL_0053:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0058:  callvirt   instance int32 [System.Windows.Forms]System.Windows.Forms.ComboBox/ObjectCollection::Add(object)
    IL_005d:  pop
    IL_005e:  ldarg.3
    IL_005f:  ldarg.2
    IL_0060:  callvirt   instance string [System.Windows.Forms]System.Windows.Forms.Control::get_Text()
    IL_0065:  callvirt   instance int32 [System.Windows.Forms]System.Windows.Forms.ComboBox::FindString(string)
    IL_006a:  stloc.1
    IL_006b:  br.s       IL_0078

    IL_006d:  ldarg.3
    IL_006e:  ldarg.1
    IL_006f:  ldarg.s    iSelect
    IL_0071:  ldelem.ref
    IL_0072:  callvirt   instance int32 [System.Windows.Forms]System.Windows.Forms.ComboBox::FindString(string)
    IL_0077:  stloc.1
    IL_0078:  ldarg.3
    IL_0079:  ldloc.1
    IL_007a:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.ListControl::set_SelectedIndex(int32)
    IL_007f:  ldarg.3
    IL_0080:  ldc.i4.1
    IL_0081:  callvirt   instance void [System.Windows.Forms]System.Windows.Forms.Control::set_Enabled(bool)
    IL_0086:  ret
  } // end of method ScannerSettingsFirmware::DisplayFileInformation

  .property instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000
          Model()
  {
    .get instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Calibration.ScannerSettingsFirmware::get_Model()
  } // end of property ScannerSettingsFirmware::Model
  .property instance valuetype Calibration.USB135
          USB135()
  {
    .get instance valuetype Calibration.USB135 Calibration.ScannerSettingsFirmware::get_USB135()
  } // end of property ScannerSettingsFirmware::USB135
  .property instance valuetype Calibration.USB235
          USB235()
  {
    .get instance valuetype Calibration.USB235 Calibration.ScannerSettingsFirmware::get_USB235()
  } // end of property ScannerSettingsFirmware::USB235
  .property instance valuetype Calibration.USB335
          USB335()
  {
    .get instance valuetype Calibration.USB335 Calibration.ScannerSettingsFirmware::get_USB335()
  } // end of property ScannerSettingsFirmware::USB335
  .property instance string Motor()
  {
    .get instance string Calibration.ScannerSettingsFirmware::get_Motor()
  } // end of property ScannerSettingsFirmware::Motor
  .property instance string DX()
  {
    .get instance string Calibration.ScannerSettingsFirmware::get_DX()
  } // end of property ScannerSettingsFirmware::DX
  .property instance string Lamp()
  {
    .get instance string Calibration.ScannerSettingsFirmware::get_Lamp()
  } // end of property ScannerSettingsFirmware::Lamp
  .property instance string CCD()
  {
    .get instance string Calibration.ScannerSettingsFirmware::get_CCD()
  } // end of property ScannerSettingsFirmware::CCD
  .property instance string APS()
  {
    .get instance string Calibration.ScannerSettingsFirmware::get_APS()
  } // end of property ScannerSettingsFirmware::APS
} // end of class Calibration.ScannerSettingsFirmware

.class public auto ansi beforefieldinit Calibration.ScannerUnsafe
       extends [mscorlib]System.Object
{
  .field private native int m_ipAcquire
  .field private uint16* m_pusAcquire
  .field private int32 m_nPixels
  .field private uint16[] m_aryRed
  .field private uint16[] m_aryGreen
  .field private uint16[] m_aryBlue
  .field private uint16[] m_aryIR
  .field private bool m_bBinning
  .field private bool m_bThreeQuarters
  .method public hidebysig specialname instance void 
          set_ThreeQuarters(bool 'value') cil managed
  {
    // Code size       8 (0x8)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      bool Calibration.ScannerUnsafe::m_bThreeQuarters
    IL_0007:  ret
  } // end of method ScannerUnsafe::set_ThreeQuarters

  .method public hidebysig specialname instance void 
          set_Binning(bool 'value') cil managed
  {
    // Code size       8 (0x8)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      bool Calibration.ScannerUnsafe::m_bBinning
    IL_0007:  ret
  } // end of method ScannerUnsafe::set_Binning

  .method public hidebysig specialname instance int32 
          get_Pixels() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32 Calibration.ScannerUnsafe::m_nPixels
    IL_0006:  ret
  } // end of method ScannerUnsafe::get_Pixels

  .method public hidebysig specialname instance uint16[] 
          get_RedChannel() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      uint16[] Calibration.ScannerUnsafe::m_aryRed
    IL_0006:  ret
  } // end of method ScannerUnsafe::get_RedChannel

  .method public hidebysig specialname instance uint16[] 
          get_GreenChannel() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      uint16[] Calibration.ScannerUnsafe::m_aryGreen
    IL_0006:  ret
  } // end of method ScannerUnsafe::get_GreenChannel

  .method public hidebysig specialname instance uint16[] 
          get_BlueChannel() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      uint16[] Calibration.ScannerUnsafe::m_aryBlue
    IL_0006:  ret
  } // end of method ScannerUnsafe::get_BlueChannel

  .method public hidebysig specialname instance uint16[] 
          get_IRChannel() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      uint16[] Calibration.ScannerUnsafe::m_aryIR
    IL_0006:  ret
  } // end of method ScannerUnsafe::get_IRChannel

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       100 (0x64)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.0
    IL_0002:  conv.u
    IL_0003:  stfld      uint16* Calibration.ScannerUnsafe::m_pusAcquire
    IL_0008:  ldarg.0
    IL_0009:  ldc.i4.0
    IL_000a:  stfld      int32 Calibration.ScannerUnsafe::m_nPixels
    IL_000f:  ldarg.0
    IL_0010:  ldc.i4     0x841
    IL_0015:  newarr     [mscorlib]System.UInt16
    IL_001a:  stfld      uint16[] Calibration.ScannerUnsafe::m_aryRed
    IL_001f:  ldarg.0
    IL_0020:  ldc.i4     0x841
    IL_0025:  newarr     [mscorlib]System.UInt16
    IL_002a:  stfld      uint16[] Calibration.ScannerUnsafe::m_aryGreen
    IL_002f:  ldarg.0
    IL_0030:  ldc.i4     0x841
    IL_0035:  newarr     [mscorlib]System.UInt16
    IL_003a:  stfld      uint16[] Calibration.ScannerUnsafe::m_aryBlue
    IL_003f:  ldarg.0
    IL_0040:  ldc.i4     0x841
    IL_0045:  newarr     [mscorlib]System.UInt16
    IL_004a:  stfld      uint16[] Calibration.ScannerUnsafe::m_aryIR
    IL_004f:  ldarg.0
    IL_0050:  ldc.i4.0
    IL_0051:  stfld      bool Calibration.ScannerUnsafe::m_bBinning
    IL_0056:  ldarg.0
    IL_0057:  ldc.i4.0
    IL_0058:  stfld      bool Calibration.ScannerUnsafe::m_bThreeQuarters
    IL_005d:  ldarg.0
    IL_005e:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0063:  ret
  } // end of method ScannerUnsafe::.ctor

  .method public hidebysig instance void 
          Acquire(bool bIRChannel) cil managed
  {
    // Code size       238 (0xee)
    .maxstack  3
    .locals (int32 V_0,
             uint16* V_1,
             int32 V_2,
             int32 V_3,
             int32 V_4,
             int32 V_5,
             int32 V_6)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      bool Calibration.ScannerUnsafe::m_bThreeQuarters
    IL_0006:  brfalse.s  IL_0010

    IL_0008:  ldc.i4     0x630
    IL_000d:  stloc.0
    IL_000e:  br.s       IL_0026

    IL_0010:  ldarg.0
    IL_0011:  ldfld      bool Calibration.ScannerUnsafe::m_bBinning
    IL_0016:  brfalse.s  IL_0020

    IL_0018:  ldc.i4     0x420
    IL_001d:  stloc.0
    IL_001e:  br.s       IL_0026

    IL_0020:  ldc.i4     0x841
    IL_0025:  stloc.0
    IL_0026:  ldarg.0
    IL_0027:  ldloc.0
    IL_0028:  newarr     [mscorlib]System.UInt16
    IL_002d:  stfld      uint16[] Calibration.ScannerUnsafe::m_aryRed
    IL_0032:  ldarg.0
    IL_0033:  ldloc.0
    IL_0034:  newarr     [mscorlib]System.UInt16
    IL_0039:  stfld      uint16[] Calibration.ScannerUnsafe::m_aryGreen
    IL_003e:  ldarg.0
    IL_003f:  ldloc.0
    IL_0040:  newarr     [mscorlib]System.UInt16
    IL_0045:  stfld      uint16[] Calibration.ScannerUnsafe::m_aryBlue
    IL_004a:  ldarg.0
    IL_004b:  ldloc.0
    IL_004c:  newarr     [mscorlib]System.UInt16
    IL_0051:  stfld      uint16[] Calibration.ScannerUnsafe::m_aryIR
    IL_0056:  ldarg.0
    IL_0057:  ldfld      uint16* Calibration.ScannerUnsafe::m_pusAcquire
    IL_005c:  stloc.1
    IL_005d:  ldc.i4.0
    IL_005e:  stloc.2
    IL_005f:  br.s       IL_0073

    IL_0061:  ldarg.0
    IL_0062:  ldfld      uint16[] Calibration.ScannerUnsafe::m_aryRed
    IL_0067:  ldloc.2
    IL_0068:  ldloc.1
    IL_0069:  ldind.u2
    IL_006a:  stelem.i2
    IL_006b:  ldloc.2
    IL_006c:  ldc.i4.1
    IL_006d:  add
    IL_006e:  stloc.2
    IL_006f:  ldloc.1
    IL_0070:  ldc.i4.2
    IL_0071:  add
    IL_0072:  stloc.1
    IL_0073:  ldloc.2
    IL_0074:  ldloc.0
    IL_0075:  blt.s      IL_0061

    IL_0077:  ldc.i4.0
    IL_0078:  stloc.3
    IL_0079:  br.s       IL_008d

    IL_007b:  ldarg.0
    IL_007c:  ldfld      uint16[] Calibration.ScannerUnsafe::m_aryGreen
    IL_0081:  ldloc.3
    IL_0082:  ldloc.1
    IL_0083:  ldind.u2
    IL_0084:  stelem.i2
    IL_0085:  ldloc.3
    IL_0086:  ldc.i4.1
    IL_0087:  add
    IL_0088:  stloc.3
    IL_0089:  ldloc.1
    IL_008a:  ldc.i4.2
    IL_008b:  add
    IL_008c:  stloc.1
    IL_008d:  ldloc.3
    IL_008e:  ldloc.0
    IL_008f:  blt.s      IL_007b

    IL_0091:  ldc.i4.0
    IL_0092:  stloc.s    V_4
    IL_0094:  br.s       IL_00ab

    IL_0096:  ldarg.0
    IL_0097:  ldfld      uint16[] Calibration.ScannerUnsafe::m_aryBlue
    IL_009c:  ldloc.s    V_4
    IL_009e:  ldloc.1
    IL_009f:  ldind.u2
    IL_00a0:  stelem.i2
    IL_00a1:  ldloc.s    V_4
    IL_00a3:  ldc.i4.1
    IL_00a4:  add
    IL_00a5:  stloc.s    V_4
    IL_00a7:  ldloc.1
    IL_00a8:  ldc.i4.2
    IL_00a9:  add
    IL_00aa:  stloc.1
    IL_00ab:  ldloc.s    V_4
    IL_00ad:  ldloc.0
    IL_00ae:  blt.s      IL_0096

    IL_00b0:  ldarg.1
    IL_00b1:  brfalse.s  IL_00d3

    IL_00b3:  ldc.i4.0
    IL_00b4:  stloc.s    V_5
    IL_00b6:  br.s       IL_00cd

    IL_00b8:  ldarg.0
    IL_00b9:  ldfld      uint16[] Calibration.ScannerUnsafe::m_aryIR
    IL_00be:  ldloc.s    V_5
    IL_00c0:  ldloc.1
    IL_00c1:  ldind.u2
    IL_00c2:  stelem.i2
    IL_00c3:  ldloc.s    V_5
    IL_00c5:  ldc.i4.1
    IL_00c6:  add
    IL_00c7:  stloc.s    V_5
    IL_00c9:  ldloc.1
    IL_00ca:  ldc.i4.2
    IL_00cb:  add
    IL_00cc:  stloc.1
    IL_00cd:  ldloc.s    V_5
    IL_00cf:  ldloc.0
    IL_00d0:  blt.s      IL_00b8

    IL_00d2:  ret

    IL_00d3:  ldc.i4.0
    IL_00d4:  stloc.s    V_6
    IL_00d6:  br.s       IL_00e8

    IL_00d8:  ldarg.0
    IL_00d9:  ldfld      uint16[] Calibration.ScannerUnsafe::m_aryIR
    IL_00de:  ldloc.s    V_6
    IL_00e0:  ldc.i4.0
    IL_00e1:  stelem.i2
    IL_00e2:  ldloc.s    V_6
    IL_00e4:  ldc.i4.1
    IL_00e5:  add
    IL_00e6:  stloc.s    V_6
    IL_00e8:  ldloc.s    V_6
    IL_00ea:  ldloc.0
    IL_00eb:  blt.s      IL_00d8

    IL_00ed:  ret
  } // end of method ScannerUnsafe::Acquire

  .method public hidebysig instance void 
          Allocate() cil managed
  {
    // Code size       51 (0x33)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4     0x4330
    IL_0006:  call       native int [mscorlib]System.Runtime.InteropServices.Marshal::AllocHGlobal(int32)
    IL_000b:  stfld      native int Calibration.ScannerUnsafe::m_ipAcquire
    IL_0010:  ldarg.0
    IL_0011:  ldarg.0
    IL_0012:  ldfld      native int Calibration.ScannerUnsafe::m_ipAcquire
    IL_0017:  call       void* [mscorlib]System.IntPtr::op_Explicit(native int)
    IL_001c:  stfld      uint16* Calibration.ScannerUnsafe::m_pusAcquire
    IL_0021:  ldarg.0
    IL_0022:  ldarg.0
    IL_0023:  ldflda     native int Calibration.ScannerUnsafe::m_ipAcquire
    IL_0028:  call       instance int32 [mscorlib]System.IntPtr::ToInt32()
    IL_002d:  stfld      int32 Calibration.ScannerUnsafe::m_nPixels
    IL_0032:  ret
  } // end of method ScannerUnsafe::Allocate

  .method public hidebysig instance void 
          Deallocate() cil managed
  {
    // Code size       12 (0xc)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      native int Calibration.ScannerUnsafe::m_ipAcquire
    IL_0006:  call       void [mscorlib]System.Runtime.InteropServices.Marshal::FreeHGlobal(native int)
    IL_000b:  ret
  } // end of method ScannerUnsafe::Deallocate

  .property instance bool ThreeQuarters()
  {
    .set instance void Calibration.ScannerUnsafe::set_ThreeQuarters(bool)
  } // end of property ScannerUnsafe::ThreeQuarters
  .property instance bool Binning()
  {
    .set instance void Calibration.ScannerUnsafe::set_Binning(bool)
  } // end of property ScannerUnsafe::Binning
  .property instance int32 Pixels()
  {
    .get instance int32 Calibration.ScannerUnsafe::get_Pixels()
  } // end of property ScannerUnsafe::Pixels
  .property instance uint16[] RedChannel()
  {
    .get instance uint16[] Calibration.ScannerUnsafe::get_RedChannel()
  } // end of property ScannerUnsafe::RedChannel
  .property instance uint16[] GreenChannel()
  {
    .get instance uint16[] Calibration.ScannerUnsafe::get_GreenChannel()
  } // end of property ScannerUnsafe::GreenChannel
  .property instance uint16[] BlueChannel()
  {
    .get instance uint16[] Calibration.ScannerUnsafe::get_BlueChannel()
  } // end of property ScannerUnsafe::BlueChannel
  .property instance uint16[] IRChannel()
  {
    .get instance uint16[] Calibration.ScannerUnsafe::get_IRChannel()
  } // end of property ScannerUnsafe::IRChannel
} // end of class Calibration.ScannerUnsafe

.class public auto ansi beforefieldinit Calibration.TLXRegistry
       extends [mscorlib]System.Object
{
  .method private hidebysig static string 
          GetLightKey([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 stType,
                      [Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor,
                      bool bIR) cil managed
  {
    // Code size       142 (0x8e)
    .maxstack  2
    .locals ([Interop.TLXLib]TLXLib.FILM_COLOR_000 V_0,
             [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_1)
    IL_0000:  ldarg.1
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  ldc.i4.1
    IL_0004:  bne.un.s   IL_0083

    IL_0006:  ldarg.0
    IL_0007:  stloc.1
    IL_0008:  ldloc.1
    IL_0009:  ldc.i4.7
    IL_000a:  sub
    IL_000b:  switch     ( 
                          IL_0042,
                          IL_0042)
    IL_0018:  ldloc.1
    IL_0019:  ldc.i4     0x546
    IL_001e:  sub
    IL_001f:  switch     ( 
                          IL_0053,
                          IL_0053)
    IL_002c:  ldloc.1
    IL_002d:  ldc.i4     0xd16
    IL_0032:  sub
    IL_0033:  switch     ( 
                          IL_0053,
                          IL_0053)
    IL_0040:  br.s       IL_0078

    IL_0042:  ldstr      "ColNeg"
    IL_0047:  ldc.i4.0
    IL_0048:  newarr     [mscorlib]System.Object
    IL_004d:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_0052:  ret

    IL_0053:  ldarg.2
    IL_0054:  brfalse.s  IL_0067

    IL_0056:  ldstr      "ColNegIr"
    IL_005b:  ldc.i4.0
    IL_005c:  newarr     [mscorlib]System.Object
    IL_0061:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_0066:  ret

    IL_0067:  ldstr      "ColNeg"
    IL_006c:  ldc.i4.0
    IL_006d:  newarr     [mscorlib]System.Object
    IL_0072:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_0077:  ret

    IL_0078:  ldstr      "Film Type not supported"
    IL_007d:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0082:  throw

    IL_0083:  ldstr      "Film Color not supported"
    IL_0088:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_008d:  throw
  } // end of method TLXRegistry::GetLightKey

  .method private hidebysig static string 
          GetDpiKey([Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                    [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat) cil managed
  {
    // Code size       200 (0xc8)
    .maxstack  2
    .locals ([Interop.TLXLib]TLXLib.FILM_FORMAT_000 V_0,
             [Interop.TLXLib]TLXLib.RESOLUTION_000 V_1)
    IL_0000:  ldarg.1
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  switch     ( 
                          IL_0015,
                          IL_0069)
    IL_0010:  br         IL_00bd

    IL_0015:  ldarg.0
    IL_0016:  stloc.1
    IL_0017:  ldloc.1
    IL_0018:  switch     ( 
                          IL_002b,
                          IL_003c,
                          IL_004d)
    IL_0029:  br.s       IL_005e

    IL_002b:  ldstr      "DpiBase4_24"
    IL_0030:  ldc.i4.0
    IL_0031:  newarr     [mscorlib]System.Object
    IL_0036:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_003b:  ret

    IL_003c:  ldstr      "DpiBase8_24"
    IL_0041:  ldc.i4.0
    IL_0042:  newarr     [mscorlib]System.Object
    IL_0047:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_004c:  ret

    IL_004d:  ldstr      "DpiBase16_24"
    IL_0052:  ldc.i4.0
    IL_0053:  newarr     [mscorlib]System.Object
    IL_0058:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_005d:  ret

    IL_005e:  ldstr      "Resolution not supported"
    IL_0063:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0068:  throw

    IL_0069:  ldarg.0
    IL_006a:  stloc.1
    IL_006b:  ldloc.1
    IL_006c:  switch     ( 
                          IL_007f,
                          IL_0090,
                          IL_00a1)
    IL_007d:  br.s       IL_00b2

    IL_007f:  ldstr      "DpiBase4_35"
    IL_0084:  ldc.i4.0
    IL_0085:  newarr     [mscorlib]System.Object
    IL_008a:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_008f:  ret

    IL_0090:  ldstr      "DpiBase8_35"
    IL_0095:  ldc.i4.0
    IL_0096:  newarr     [mscorlib]System.Object
    IL_009b:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_00a0:  ret

    IL_00a1:  ldstr      "DpiBase16_35"
    IL_00a6:  ldc.i4.0
    IL_00a7:  newarr     [mscorlib]System.Object
    IL_00ac:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_00b1:  ret

    IL_00b2:  ldstr      "Resolution not supported"
    IL_00b7:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_00bc:  throw

    IL_00bd:  ldstr      "Film format not supported"
    IL_00c2:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_00c7:  throw
  } // end of method TLXRegistry::GetDpiKey

  .method private hidebysig static string 
          GetScanKey([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 stType) cil managed
  {
    // Code size       122 (0x7a)
    .maxstack  2
    .locals ([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_0)
    IL_0000:  ldarg.0
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  ldc.i4.7
    IL_0004:  sub
    IL_0005:  switch     ( 
                          IL_004d,
                          IL_004d)
    IL_0012:  ldloc.0
    IL_0013:  ldc.i4     0x546
    IL_0018:  sub
    IL_0019:  switch     ( 
                          IL_003c,
                          IL_003c)
    IL_0026:  ldloc.0
    IL_0027:  ldc.i4     0xd16
    IL_002c:  sub
    IL_002d:  switch     ( 
                          IL_005e,
                          IL_005e)
    IL_003a:  br.s       IL_006f

    IL_003c:  ldstr      "SOFTWARE\\Pakon\\TLB\\Scan"
    IL_0041:  ldc.i4.0
    IL_0042:  newarr     [mscorlib]System.Object
    IL_0047:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_004c:  ret

    IL_004d:  ldstr      "SOFTWARE\\Pakon\\TLA\\Scan"
    IL_0052:  ldc.i4.0
    IL_0053:  newarr     [mscorlib]System.Object
    IL_0058:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_005d:  ret

    IL_005e:  ldstr      "SOFTWARE\\Pakon\\TLC\\Scan"
    IL_0063:  ldc.i4.0
    IL_0064:  newarr     [mscorlib]System.Object
    IL_0069:  call       string [mscorlib]System.String::Format(string,
                                                                object[])
    IL_006e:  ret

    IL_006f:  ldstr      "Invalid Scanner Type"
    IL_0074:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0079:  throw
  } // end of method TLXRegistry::GetScanKey

  .method private hidebysig static string 
          GetProgramPath([Interop.LLCLib]LLCLib.SCANNER_MODEL_000 smModel) cil managed
  {
    // Code size       118 (0x76)
    .maxstack  2
    .locals (string V_0,
             [mscorlib]Microsoft.Win32.RegistryKey V_1,
             [mscorlib]Microsoft.Win32.RegistryKey V_2,
             [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 V_3)
    IL_0000:  ldstr      ""
    IL_0005:  stloc.0
    IL_0006:  ldsfld     [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.Registry::LocalMachine
    IL_000b:  stloc.1
    IL_000c:  ldnull
    IL_000d:  stloc.2
    IL_000e:  ldarg.0
    IL_000f:  stloc.3
    IL_0010:  ldloc.3
    IL_0011:  switch     ( 
                          IL_0036,
                          IL_0028,
                          IL_0044,
                          IL_0028)
    IL_0026:  br.s       IL_0052

    IL_0028:  ldloc.1
    IL_0029:  ldstr      "SOFTWARE\\Pakon\\TLB"
    IL_002e:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string)
    IL_0033:  stloc.2
    IL_0034:  br.s       IL_005d

    IL_0036:  ldloc.1
    IL_0037:  ldstr      "SOFTWARE\\Pakon\\TLA"
    IL_003c:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string)
    IL_0041:  stloc.2
    IL_0042:  br.s       IL_005d

    IL_0044:  ldloc.1
    IL_0045:  ldstr      "SOFTWARE\\Pakon\\TLC"
    IL_004a:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string)
    IL_004f:  stloc.2
    IL_0050:  br.s       IL_005d

    IL_0052:  ldstr      "Invalid Scanner Model"
    IL_0057:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_005c:  throw

    IL_005d:  ldloc.2
    IL_005e:  ldstr      "ProgramPath"
    IL_0063:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0068:  castclass  [mscorlib]System.String
    IL_006d:  stloc.0
    IL_006e:  ldloc.2
    IL_006f:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::Close()
    IL_0074:  ldloc.0
    IL_0075:  ret
  } // end of method TLXRegistry::GetProgramPath

  .method private hidebysig static void  LoadFileInformation(string strPath,
                                                             string strPrefix,
                                                             int32 iHw,
                                                             string strHwMax,
                                                             string[]& aryNames,
                                                             string[]& aryFiles,
                                                             [out] int32& iSelect) cil managed
  {
    // Code size       460 (0x1cc)
    .maxstack  6
    .locals (string V_0,
             [mscorlib]System.IO.DirectoryInfo V_1,
             string V_2,
             [mscorlib]System.IO.FileInfo[] V_3,
             int32 V_4,
             [mscorlib]System.IO.FileInfo V_5,
             string V_6,
             string V_7,
             int32 V_8,
             [mscorlib]System.IO.FileInfo V_9,
             string V_10,
             string V_11,
             [mscorlib]System.IO.FileInfo[] V_12,
             int32 V_13)
    IL_0000:  ldarg.s    iSelect
    IL_0002:  ldc.i4.0
    IL_0003:  stind.i4
    IL_0004:  ldstr      "00"
    IL_0009:  stloc.0
    IL_000a:  ldarg.0
    IL_000b:  newobj     instance void [mscorlib]System.IO.DirectoryInfo::.ctor(string)
    IL_0010:  stloc.1
    IL_0011:  ldarg.1
    IL_0012:  ldstr      "\?\?\?\?.hex"
    IL_0017:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_001c:  stloc.2
    IL_001d:  ldloc.1
    IL_001e:  ldloc.2
    IL_001f:  callvirt   instance [mscorlib]System.IO.FileInfo[] [mscorlib]System.IO.DirectoryInfo::GetFiles(string)
    IL_0024:  stloc.3
    IL_0025:  ldloc.3
    IL_0026:  ldlen
    IL_0027:  conv.i4
    IL_0028:  stloc.s    V_4
    IL_002a:  ldloc.3
    IL_002b:  stloc.s    V_12
    IL_002d:  ldc.i4.0
    IL_002e:  stloc.s    V_13
    IL_0030:  br.s       IL_0080

    IL_0032:  ldloc.s    V_12
    IL_0034:  ldloc.s    V_13
    IL_0036:  ldelem.ref
    IL_0037:  stloc.s    V_5
    IL_0039:  ldstr      ""
    IL_003e:  ldloc.s    V_5
    IL_0040:  callvirt   instance string [mscorlib]System.IO.FileSystemInfo::get_Name()
    IL_0045:  ldc.i4.2
    IL_0046:  callvirt   instance char [mscorlib]System.String::get_Chars(int32)
    IL_004b:  box        [mscorlib]System.Char
    IL_0050:  ldloc.s    V_5
    IL_0052:  callvirt   instance string [mscorlib]System.IO.FileSystemInfo::get_Name()
    IL_0057:  ldc.i4.3
    IL_0058:  callvirt   instance char [mscorlib]System.String::get_Chars(int32)
    IL_005d:  box        [mscorlib]System.Char
    IL_0062:  call       string [mscorlib]System.String::Concat(object,
                                                                object,
                                                                object)
    IL_0067:  stloc.s    V_6
    IL_0069:  ldloc.s    V_6
    IL_006b:  ldarg.3
    IL_006c:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_0071:  ldc.i4.0
    IL_0072:  ble.s      IL_007a

    IL_0074:  ldloc.s    V_4
    IL_0076:  ldc.i4.1
    IL_0077:  sub
    IL_0078:  stloc.s    V_4
    IL_007a:  ldloc.s    V_13
    IL_007c:  ldc.i4.1
    IL_007d:  add
    IL_007e:  stloc.s    V_13
    IL_0080:  ldloc.s    V_13
    IL_0082:  ldloc.s    V_12
    IL_0084:  ldlen
    IL_0085:  conv.i4
    IL_0086:  blt.s      IL_0032

    IL_0088:  ldloc.s    V_4
    IL_008a:  ldc.i4.0
    IL_008b:  ble        IL_01cb

    IL_0090:  ldarg.s    aryNames
    IL_0092:  ldloc.s    V_4
    IL_0094:  newarr     [mscorlib]System.String
    IL_0099:  stind.ref
    IL_009a:  ldarg.s    aryFiles
    IL_009c:  ldloc.s    V_4
    IL_009e:  newarr     [mscorlib]System.String
    IL_00a3:  stind.ref
    IL_00a4:  ldstr      "{0:X}"
    IL_00a9:  ldarg.2
    IL_00aa:  box        [mscorlib]System.Int32
    IL_00af:  call       string [mscorlib]System.String::Format(string,
                                                                object)
    IL_00b4:  stloc.s    V_7
    IL_00b6:  ldloc.s    V_7
    IL_00b8:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_00bd:  ldc.i4.2
    IL_00be:  beq.s      IL_00ce

    IL_00c0:  ldstr      "0"
    IL_00c5:  ldloc.s    V_7
    IL_00c7:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_00cc:  br.s       IL_00d0

    IL_00ce:  ldloc.s    V_7
    IL_00d0:  stloc.s    V_7
    IL_00d2:  ldc.i4.0
    IL_00d3:  stloc.s    V_8
    IL_00d5:  ldloc.3
    IL_00d6:  stloc.s    V_12
    IL_00d8:  ldc.i4.0
    IL_00d9:  stloc.s    V_13
    IL_00db:  br         IL_01c0

    IL_00e0:  ldloc.s    V_12
    IL_00e2:  ldloc.s    V_13
    IL_00e4:  ldelem.ref
    IL_00e5:  stloc.s    V_9
    IL_00e7:  ldstr      ""
    IL_00ec:  ldloc.s    V_9
    IL_00ee:  callvirt   instance string [mscorlib]System.IO.FileSystemInfo::get_Name()
    IL_00f3:  ldc.i4.2
    IL_00f4:  callvirt   instance char [mscorlib]System.String::get_Chars(int32)
    IL_00f9:  box        [mscorlib]System.Char
    IL_00fe:  ldloc.s    V_9
    IL_0100:  callvirt   instance string [mscorlib]System.IO.FileSystemInfo::get_Name()
    IL_0105:  ldc.i4.3
    IL_0106:  callvirt   instance char [mscorlib]System.String::get_Chars(int32)
    IL_010b:  box        [mscorlib]System.Char
    IL_0110:  call       string [mscorlib]System.String::Concat(object,
                                                                object,
                                                                object)
    IL_0115:  stloc.s    V_10
    IL_0117:  ldstr      ""
    IL_011c:  ldloc.s    V_9
    IL_011e:  callvirt   instance string [mscorlib]System.IO.FileSystemInfo::get_Name()
    IL_0123:  ldc.i4.4
    IL_0124:  callvirt   instance char [mscorlib]System.String::get_Chars(int32)
    IL_0129:  box        [mscorlib]System.Char
    IL_012e:  ldloc.s    V_9
    IL_0130:  callvirt   instance string [mscorlib]System.IO.FileSystemInfo::get_Name()
    IL_0135:  ldc.i4.5
    IL_0136:  callvirt   instance char [mscorlib]System.String::get_Chars(int32)
    IL_013b:  box        [mscorlib]System.Char
    IL_0140:  call       string [mscorlib]System.String::Concat(object,
                                                                object,
                                                                object)
    IL_0145:  stloc.s    V_11
    IL_0147:  ldloc.s    V_10
    IL_0149:  callvirt   instance string [mscorlib]System.String::ToUpper()
    IL_014e:  stloc.s    V_10
    IL_0150:  ldloc.s    V_11
    IL_0152:  callvirt   instance string [mscorlib]System.String::ToUpper()
    IL_0157:  stloc.s    V_11
    IL_0159:  ldloc.s    V_10
    IL_015b:  ldarg.3
    IL_015c:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_0161:  ldc.i4.0
    IL_0162:  bgt.s      IL_01ba

    IL_0164:  ldloc.s    V_10
    IL_0166:  ldloc.s    V_7
    IL_0168:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_016d:  brfalse.s  IL_017b

    IL_016f:  ldarg.2
    IL_0170:  ldc.i4.0
    IL_0171:  ble.s      IL_017b

    IL_0173:  ldarg.2
    IL_0174:  ldc.i4     0x100
    IL_0179:  blt.s      IL_018e

    IL_017b:  ldloc.s    V_11
    IL_017d:  ldloc.0
    IL_017e:  callvirt   instance int32 [mscorlib]System.String::CompareTo(string)
    IL_0183:  ldc.i4.0
    IL_0184:  blt.s      IL_018e

    IL_0186:  ldarg.s    iSelect
    IL_0188:  ldloc.s    V_8
    IL_018a:  stind.i4
    IL_018b:  ldloc.s    V_11
    IL_018d:  stloc.0
    IL_018e:  ldarg.s    aryNames
    IL_0190:  ldind.ref
    IL_0191:  ldloc.s    V_8
    IL_0193:  ldstr      "0x"
    IL_0198:  ldloc.s    V_10
    IL_019a:  ldstr      ", 0x"
    IL_019f:  ldloc.s    V_11
    IL_01a1:  call       string [mscorlib]System.String::Concat(string,
                                                                string,
                                                                string,
                                                                string)
    IL_01a6:  stelem.ref
    IL_01a7:  ldarg.s    aryFiles
    IL_01a9:  ldind.ref
    IL_01aa:  ldloc.s    V_8
    IL_01ac:  ldloc.s    V_9
    IL_01ae:  callvirt   instance string [mscorlib]System.IO.FileSystemInfo::get_FullName()
    IL_01b3:  stelem.ref
    IL_01b4:  ldloc.s    V_8
    IL_01b6:  ldc.i4.1
    IL_01b7:  add
    IL_01b8:  stloc.s    V_8
    IL_01ba:  ldloc.s    V_13
    IL_01bc:  ldc.i4.1
    IL_01bd:  add
    IL_01be:  stloc.s    V_13
    IL_01c0:  ldloc.s    V_13
    IL_01c2:  ldloc.s    V_12
    IL_01c4:  ldlen
    IL_01c5:  conv.i4
    IL_01c6:  blt        IL_00e0

    IL_01cb:  ret
  } // end of method TLXRegistry::LoadFileInformation

  .method public hidebysig static void  LoadFirmwareFileInformation([Interop.LLCLib]LLCLib.SCANNER_MODEL_000 smModel,
                                                                    valuetype Calibration.ScannerFirmware sfModule,
                                                                    int32 iHw,
                                                                    string[]& aryNames,
                                                                    string[]& aryFiles,
                                                                    [out] int32& iSelect) cil managed
  {
    // Code size       421 (0x1a5)
    .maxstack  7
    .locals (string V_0,
             string V_1,
             string V_2,
             valuetype Calibration.ScannerFirmware V_3,
             [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 V_4)
    IL_0000:  ldarg.0
    IL_0001:  call       string Calibration.TLXRegistry::GetProgramPath([Interop.LLCLib]LLCLib.SCANNER_MODEL_000)
    IL_0006:  ldstr      "\\Config\\Firmware"
    IL_000b:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0010:  stloc.0
    IL_0011:  ldstr      "xx"
    IL_0016:  stloc.1
    IL_0017:  ldstr      "ff"
    IL_001c:  stloc.2
    IL_001d:  ldarg.1
    IL_001e:  stloc.3
    IL_001f:  ldloc.3
    IL_0020:  ldc.i4.1
    IL_0021:  sub
    IL_0022:  switch     ( 
                          IL_013e,
                          IL_00ba,
                          IL_00f7,
                          IL_007d,
                          IL_0040)
    IL_003b:  br         IL_018b

    IL_0040:  ldarg.0
    IL_0041:  stloc.s    V_4
    IL_0043:  ldloc.s    V_4
    IL_0045:  switch     ( 
                          IL_005c,
                          IL_0072,
                          IL_0067,
                          IL_0072)
    IL_005a:  br.s       IL_0072

    IL_005c:  ldstr      "ap"
    IL_0061:  stloc.1
    IL_0062:  br         IL_0196

    IL_0067:  ldstr      "ap"
    IL_006c:  stloc.1
    IL_006d:  br         IL_0196

    IL_0072:  ldstr      "Invalid Scanner Model"
    IL_0077:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_007c:  throw

    IL_007d:  ldarg.0
    IL_007e:  stloc.s    V_4
    IL_0080:  ldloc.s    V_4
    IL_0082:  switch     ( 
                          IL_0099,
                          IL_00af,
                          IL_00a4,
                          IL_00af)
    IL_0097:  br.s       IL_00af

    IL_0099:  ldstr      "cd"
    IL_009e:  stloc.1
    IL_009f:  br         IL_0196

    IL_00a4:  ldstr      "ce"
    IL_00a9:  stloc.1
    IL_00aa:  br         IL_0196

    IL_00af:  ldstr      "Invalid Scanner Model"
    IL_00b4:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_00b9:  throw

    IL_00ba:  ldarg.0
    IL_00bb:  stloc.s    V_4
    IL_00bd:  ldloc.s    V_4
    IL_00bf:  switch     ( 
                          IL_00d6,
                          IL_00ec,
                          IL_00e1,
                          IL_00ec)
    IL_00d4:  br.s       IL_00ec

    IL_00d6:  ldstr      "dx"
    IL_00db:  stloc.1
    IL_00dc:  br         IL_0196

    IL_00e1:  ldstr      "dy"
    IL_00e6:  stloc.1
    IL_00e7:  br         IL_0196

    IL_00ec:  ldstr      "Invalid Scanner Model"
    IL_00f1:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_00f6:  throw

    IL_00f7:  ldarg.0
    IL_00f8:  stloc.s    V_4
    IL_00fa:  ldloc.s    V_4
    IL_00fc:  switch     ( 
                          IL_0123,
                          IL_011b,
                          IL_012b,
                          IL_0113)
    IL_0111:  br.s       IL_0133

    IL_0113:  ldstr      "pl"
    IL_0118:  stloc.1
    IL_0119:  br.s       IL_0196

    IL_011b:  ldstr      "nl"
    IL_0120:  stloc.1
    IL_0121:  br.s       IL_0196

    IL_0123:  ldstr      "lp"
    IL_0128:  stloc.1
    IL_0129:  br.s       IL_0196

    IL_012b:  ldstr      "lq"
    IL_0130:  stloc.1
    IL_0131:  br.s       IL_0196

    IL_0133:  ldstr      "Invalid Scanner Model"
    IL_0138:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_013d:  throw

    IL_013e:  ldarg.0
    IL_013f:  stloc.s    V_4
    IL_0141:  ldloc.s    V_4
    IL_0143:  switch     ( 
                          IL_016a,
                          IL_0162,
                          IL_0178,
                          IL_015a)
    IL_0158:  br.s       IL_0180

    IL_015a:  ldstr      "pm"
    IL_015f:  stloc.1
    IL_0160:  br.s       IL_0196

    IL_0162:  ldstr      "nm"
    IL_0167:  stloc.1
    IL_0168:  br.s       IL_0196

    IL_016a:  ldstr      "mc"
    IL_016f:  stloc.1
    IL_0170:  ldstr      "08"
    IL_0175:  stloc.2
    IL_0176:  br.s       IL_0196

    IL_0178:  ldstr      "md"
    IL_017d:  stloc.1
    IL_017e:  br.s       IL_0196

    IL_0180:  ldstr      "Invalid Scanner Model"
    IL_0185:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_018a:  throw

    IL_018b:  ldstr      "Invalid ScannerFirmware"
    IL_0190:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0195:  throw

    IL_0196:  ldloc.0
    IL_0197:  ldloc.1
    IL_0198:  ldarg.2
    IL_0199:  ldloc.2
    IL_019a:  ldarg.3
    IL_019b:  ldarg.s    aryFiles
    IL_019d:  ldarg.s    iSelect
    IL_019f:  call       void Calibration.TLXRegistry::LoadFileInformation(string,
                                                                           string,
                                                                           int32,
                                                                           string,
                                                                           string[]&,
                                                                           string[]&,
                                                                           int32&)
    IL_01a4:  ret
  } // end of method TLXRegistry::LoadFirmwareFileInformation

  .method public hidebysig static void  GetGain([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iType,
                                                [Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                                [Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor,
                                                [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                                bool bIR,
                                                [out] int32& iGain_R,
                                                [out] int32& iGain_G,
                                                [out] int32& iGain_B) cil managed
  {
    // Code size       142 (0x8e)
    .maxstack  5
    .locals ([mscorlib]Microsoft.Win32.RegistryKey V_0,
             string V_1,
             [mscorlib]Microsoft.Win32.RegistryKey V_2,
             string[] V_3)
    IL_0000:  ldsfld     [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.Registry::LocalMachine
    IL_0005:  stloc.0
    IL_0006:  ldc.i4.5
    IL_0007:  newarr     [mscorlib]System.String
    IL_000c:  stloc.3
    IL_000d:  ldloc.3
    IL_000e:  ldc.i4.0
    IL_000f:  ldarg.0
    IL_0010:  call       string Calibration.TLXRegistry::GetScanKey([Interop.TLXLib]TLXLib.SCANNER_TYPE_000)
    IL_0015:  stelem.ref
    IL_0016:  ldloc.3
    IL_0017:  ldc.i4.1
    IL_0018:  ldstr      "\\"
    IL_001d:  stelem.ref
    IL_001e:  ldloc.3
    IL_001f:  ldc.i4.2
    IL_0020:  ldarg.1
    IL_0021:  ldarg.3
    IL_0022:  call       string Calibration.TLXRegistry::GetDpiKey([Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                   [Interop.TLXLib]TLXLib.FILM_FORMAT_000)
    IL_0027:  stelem.ref
    IL_0028:  ldloc.3
    IL_0029:  ldc.i4.3
    IL_002a:  ldstr      "\\"
    IL_002f:  stelem.ref
    IL_0030:  ldloc.3
    IL_0031:  ldc.i4.4
    IL_0032:  ldarg.0
    IL_0033:  ldarg.2
    IL_0034:  ldarg.s    bIR
    IL_0036:  call       string Calibration.TLXRegistry::GetLightKey([Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                     [Interop.TLXLib]TLXLib.FILM_COLOR_000,
                                                                     bool)
    IL_003b:  stelem.ref
    IL_003c:  ldloc.3
    IL_003d:  call       string [mscorlib]System.String::Concat(string[])
    IL_0042:  stloc.1
    IL_0043:  ldloc.0
    IL_0044:  ldloc.1
    IL_0045:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string)
    IL_004a:  stloc.2
    IL_004b:  ldarg.s    iGain_R
    IL_004d:  ldloc.2
    IL_004e:  ldstr      "Gain_R"
    IL_0053:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0058:  unbox      [mscorlib]System.Int32
    IL_005d:  ldind.i4
    IL_005e:  stind.i4
    IL_005f:  ldarg.s    iGain_G
    IL_0061:  ldloc.2
    IL_0062:  ldstr      "Gain_G"
    IL_0067:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_006c:  unbox      [mscorlib]System.Int32
    IL_0071:  ldind.i4
    IL_0072:  stind.i4
    IL_0073:  ldarg.s    iGain_B
    IL_0075:  ldloc.2
    IL_0076:  ldstr      "Gain_B"
    IL_007b:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0080:  unbox      [mscorlib]System.Int32
    IL_0085:  ldind.i4
    IL_0086:  stind.i4
    IL_0087:  ldloc.2
    IL_0088:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::Close()
    IL_008d:  ret
  } // end of method TLXRegistry::GetGain

  .method public hidebysig static void  GetOpenGateIncandescent([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iType,
                                                                [Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                                                [Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor,
                                                                [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                                                bool bIR,
                                                                [out] int32& iGain_R,
                                                                [out] int32& iGain_G,
                                                                [out] int32& iGain_B,
                                                                [out] int32& iOffset_R,
                                                                [out] int32& iOffset_G,
                                                                [out] int32& iOffset_B,
                                                                [out] int32& iExposure_R,
                                                                [out] int32& iExposure_G,
                                                                [out] int32& iExposure_B,
                                                                [out] int32& iCurrent_IR,
                                                                [out] int32& iIrLEDStartTime) cil managed
  {
    // Code size       302 (0x12e)
    .maxstack  5
    .locals ([mscorlib]Microsoft.Win32.RegistryKey V_0,
             string V_1,
             [mscorlib]Microsoft.Win32.RegistryKey V_2,
             string[] V_3)
    IL_0000:  ldsfld     [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.Registry::LocalMachine
    IL_0005:  stloc.0
    IL_0006:  ldc.i4.5
    IL_0007:  newarr     [mscorlib]System.String
    IL_000c:  stloc.3
    IL_000d:  ldloc.3
    IL_000e:  ldc.i4.0
    IL_000f:  ldarg.0
    IL_0010:  call       string Calibration.TLXRegistry::GetScanKey([Interop.TLXLib]TLXLib.SCANNER_TYPE_000)
    IL_0015:  stelem.ref
    IL_0016:  ldloc.3
    IL_0017:  ldc.i4.1
    IL_0018:  ldstr      "\\"
    IL_001d:  stelem.ref
    IL_001e:  ldloc.3
    IL_001f:  ldc.i4.2
    IL_0020:  ldarg.1
    IL_0021:  ldarg.3
    IL_0022:  call       string Calibration.TLXRegistry::GetDpiKey([Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                   [Interop.TLXLib]TLXLib.FILM_FORMAT_000)
    IL_0027:  stelem.ref
    IL_0028:  ldloc.3
    IL_0029:  ldc.i4.3
    IL_002a:  ldstr      "\\"
    IL_002f:  stelem.ref
    IL_0030:  ldloc.3
    IL_0031:  ldc.i4.4
    IL_0032:  ldarg.0
    IL_0033:  ldarg.2
    IL_0034:  ldarg.s    bIR
    IL_0036:  call       string Calibration.TLXRegistry::GetLightKey([Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                     [Interop.TLXLib]TLXLib.FILM_COLOR_000,
                                                                     bool)
    IL_003b:  stelem.ref
    IL_003c:  ldloc.3
    IL_003d:  call       string [mscorlib]System.String::Concat(string[])
    IL_0042:  stloc.1
    IL_0043:  ldloc.0
    IL_0044:  ldloc.1
    IL_0045:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string)
    IL_004a:  stloc.2
    IL_004b:  ldarg.s    iGain_R
    IL_004d:  ldloc.2
    IL_004e:  ldstr      "Gain_R"
    IL_0053:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0058:  unbox      [mscorlib]System.Int32
    IL_005d:  ldind.i4
    IL_005e:  stind.i4
    IL_005f:  ldarg.s    iGain_G
    IL_0061:  ldloc.2
    IL_0062:  ldstr      "Gain_G"
    IL_0067:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_006c:  unbox      [mscorlib]System.Int32
    IL_0071:  ldind.i4
    IL_0072:  stind.i4
    IL_0073:  ldarg.s    iGain_B
    IL_0075:  ldloc.2
    IL_0076:  ldstr      "Gain_B"
    IL_007b:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0080:  unbox      [mscorlib]System.Int32
    IL_0085:  ldind.i4
    IL_0086:  stind.i4
    IL_0087:  ldarg.s    iOffset_R
    IL_0089:  ldloc.2
    IL_008a:  ldstr      "Offset_R"
    IL_008f:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0094:  unbox      [mscorlib]System.Int32
    IL_0099:  ldind.i4
    IL_009a:  stind.i4
    IL_009b:  ldarg.s    iOffset_G
    IL_009d:  ldloc.2
    IL_009e:  ldstr      "Offset_G"
    IL_00a3:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_00a8:  unbox      [mscorlib]System.Int32
    IL_00ad:  ldind.i4
    IL_00ae:  stind.i4
    IL_00af:  ldarg.s    iOffset_B
    IL_00b1:  ldloc.2
    IL_00b2:  ldstr      "Offset_B"
    IL_00b7:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_00bc:  unbox      [mscorlib]System.Int32
    IL_00c1:  ldind.i4
    IL_00c2:  stind.i4
    IL_00c3:  ldarg.s    iExposure_R
    IL_00c5:  ldloc.2
    IL_00c6:  ldstr      "CcdExposureOpenGate_R"
    IL_00cb:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_00d0:  unbox      [mscorlib]System.Int32
    IL_00d5:  ldind.i4
    IL_00d6:  stind.i4
    IL_00d7:  ldarg.s    iExposure_G
    IL_00d9:  ldloc.2
    IL_00da:  ldstr      "CcdExposureOpenGate_G"
    IL_00df:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_00e4:  unbox      [mscorlib]System.Int32
    IL_00e9:  ldind.i4
    IL_00ea:  stind.i4
    IL_00eb:  ldarg.s    iExposure_B
    IL_00ed:  ldloc.2
    IL_00ee:  ldstr      "CcdExposureOpenGate_B"
    IL_00f3:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_00f8:  unbox      [mscorlib]System.Int32
    IL_00fd:  ldind.i4
    IL_00fe:  stind.i4
    IL_00ff:  ldarg.s    iCurrent_IR
    IL_0101:  ldloc.2
    IL_0102:  ldstr      "CurrentOpenGate_Ir"
    IL_0107:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_010c:  unbox      [mscorlib]System.Int32
    IL_0111:  ldind.i4
    IL_0112:  stind.i4
    IL_0113:  ldarg.s    iIrLEDStartTime
    IL_0115:  ldloc.2
    IL_0116:  ldstr      "IrLEDStartTime"
    IL_011b:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0120:  unbox      [mscorlib]System.Int32
    IL_0125:  ldind.i4
    IL_0126:  stind.i4
    IL_0127:  ldloc.2
    IL_0128:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::Close()
    IL_012d:  ret
  } // end of method TLXRegistry::GetOpenGateIncandescent

  .method public hidebysig static void  GetOpenGateLED([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iType,
                                                       [Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                                       [Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor,
                                                       [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                                       bool bIR,
                                                       [out] int32& nGain_R,
                                                       [out] int32& nGain_G,
                                                       [out] int32& nGain_B,
                                                       [out] int32& nOffset_R,
                                                       [out] int32& nOffset_G,
                                                       [out] int32& nOffset_B,
                                                       [out] int32& nCurrent_R,
                                                       [out] int32& nCurrent_G,
                                                       [out] int32& nCurrent_B,
                                                       [out] int32& nCurrent_Ir,
                                                       [out] float64& dDutyCycle_R,
                                                       [out] float64& dDutyCycle_G,
                                                       [out] float64& dDutyCycle_B,
                                                       [out] float64& dDutyCycle_IR,
                                                       [out] float64& dDutyCycleOpenGate_R,
                                                       [out] float64& dDutyCycleOpenGate_G,
                                                       [out] float64& dDutyCycleOpenGate_B,
                                                       [out] float64& dDutyCycleOpenGate_IR) cil managed
  {
    // Code size       474 (0x1da)
    .maxstack  5
    .locals ([mscorlib]Microsoft.Win32.RegistryKey V_0,
             string V_1,
             [mscorlib]Microsoft.Win32.RegistryKey V_2,
             string[] V_3)
    IL_0000:  ldsfld     [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.Registry::LocalMachine
    IL_0005:  stloc.0
    IL_0006:  ldc.i4.5
    IL_0007:  newarr     [mscorlib]System.String
    IL_000c:  stloc.3
    IL_000d:  ldloc.3
    IL_000e:  ldc.i4.0
    IL_000f:  ldarg.0
    IL_0010:  call       string Calibration.TLXRegistry::GetScanKey([Interop.TLXLib]TLXLib.SCANNER_TYPE_000)
    IL_0015:  stelem.ref
    IL_0016:  ldloc.3
    IL_0017:  ldc.i4.1
    IL_0018:  ldstr      "\\"
    IL_001d:  stelem.ref
    IL_001e:  ldloc.3
    IL_001f:  ldc.i4.2
    IL_0020:  ldarg.1
    IL_0021:  ldarg.3
    IL_0022:  call       string Calibration.TLXRegistry::GetDpiKey([Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                   [Interop.TLXLib]TLXLib.FILM_FORMAT_000)
    IL_0027:  stelem.ref
    IL_0028:  ldloc.3
    IL_0029:  ldc.i4.3
    IL_002a:  ldstr      "\\"
    IL_002f:  stelem.ref
    IL_0030:  ldloc.3
    IL_0031:  ldc.i4.4
    IL_0032:  ldarg.0
    IL_0033:  ldarg.2
    IL_0034:  ldarg.s    bIR
    IL_0036:  call       string Calibration.TLXRegistry::GetLightKey([Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                     [Interop.TLXLib]TLXLib.FILM_COLOR_000,
                                                                     bool)
    IL_003b:  stelem.ref
    IL_003c:  ldloc.3
    IL_003d:  call       string [mscorlib]System.String::Concat(string[])
    IL_0042:  stloc.1
    IL_0043:  ldloc.0
    IL_0044:  ldloc.1
    IL_0045:  callvirt   instance [mscorlib]Microsoft.Win32.RegistryKey [mscorlib]Microsoft.Win32.RegistryKey::OpenSubKey(string)
    IL_004a:  stloc.2
    IL_004b:  ldarg.s    nGain_R
    IL_004d:  ldloc.2
    IL_004e:  ldstr      "Gain_R"
    IL_0053:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0058:  unbox      [mscorlib]System.Int32
    IL_005d:  ldind.i4
    IL_005e:  stind.i4
    IL_005f:  ldarg.s    nGain_G
    IL_0061:  ldloc.2
    IL_0062:  ldstr      "Gain_G"
    IL_0067:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_006c:  unbox      [mscorlib]System.Int32
    IL_0071:  ldind.i4
    IL_0072:  stind.i4
    IL_0073:  ldarg.s    nGain_B
    IL_0075:  ldloc.2
    IL_0076:  ldstr      "Gain_B"
    IL_007b:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0080:  unbox      [mscorlib]System.Int32
    IL_0085:  ldind.i4
    IL_0086:  stind.i4
    IL_0087:  ldarg.s    nOffset_R
    IL_0089:  ldloc.2
    IL_008a:  ldstr      "Offset_R"
    IL_008f:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0094:  unbox      [mscorlib]System.Int32
    IL_0099:  ldind.i4
    IL_009a:  stind.i4
    IL_009b:  ldarg.s    nOffset_G
    IL_009d:  ldloc.2
    IL_009e:  ldstr      "Offset_G"
    IL_00a3:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_00a8:  unbox      [mscorlib]System.Int32
    IL_00ad:  ldind.i4
    IL_00ae:  stind.i4
    IL_00af:  ldarg.s    nOffset_B
    IL_00b1:  ldloc.2
    IL_00b2:  ldstr      "Offset_B"
    IL_00b7:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_00bc:  unbox      [mscorlib]System.Int32
    IL_00c1:  ldind.i4
    IL_00c2:  stind.i4
    IL_00c3:  ldarg.s    nCurrent_R
    IL_00c5:  ldloc.2
    IL_00c6:  ldstr      "Current_R"
    IL_00cb:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_00d0:  unbox      [mscorlib]System.Int32
    IL_00d5:  ldind.i4
    IL_00d6:  stind.i4
    IL_00d7:  ldarg.s    nCurrent_G
    IL_00d9:  ldloc.2
    IL_00da:  ldstr      "Current_G"
    IL_00df:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_00e4:  unbox      [mscorlib]System.Int32
    IL_00e9:  ldind.i4
    IL_00ea:  stind.i4
    IL_00eb:  ldarg.s    nCurrent_B
    IL_00ed:  ldloc.2
    IL_00ee:  ldstr      "Current_B"
    IL_00f3:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_00f8:  unbox      [mscorlib]System.Int32
    IL_00fd:  ldind.i4
    IL_00fe:  stind.i4
    IL_00ff:  ldarg.s    nCurrent_Ir
    IL_0101:  ldloc.2
    IL_0102:  ldstr      "Current_Ir"
    IL_0107:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_010c:  unbox      [mscorlib]System.Int32
    IL_0111:  ldind.i4
    IL_0112:  stind.i4
    IL_0113:  ldarg.s    dDutyCycle_R
    IL_0115:  ldloc.2
    IL_0116:  ldstr      "DutyCycle_R"
    IL_011b:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0120:  castclass  [mscorlib]System.String
    IL_0125:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_012a:  stind.r8
    IL_012b:  ldarg.s    dDutyCycle_G
    IL_012d:  ldloc.2
    IL_012e:  ldstr      "DutyCycle_G"
    IL_0133:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0138:  castclass  [mscorlib]System.String
    IL_013d:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_0142:  stind.r8
    IL_0143:  ldarg.s    dDutyCycle_B
    IL_0145:  ldloc.2
    IL_0146:  ldstr      "DutyCycle_B"
    IL_014b:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0150:  castclass  [mscorlib]System.String
    IL_0155:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_015a:  stind.r8
    IL_015b:  ldarg.s    dDutyCycle_IR
    IL_015d:  ldloc.2
    IL_015e:  ldstr      "DutyCycle_Ir"
    IL_0163:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0168:  castclass  [mscorlib]System.String
    IL_016d:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_0172:  stind.r8
    IL_0173:  ldarg.s    dDutyCycleOpenGate_R
    IL_0175:  ldloc.2
    IL_0176:  ldstr      "DutyCycleOpenGate_R"
    IL_017b:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0180:  castclass  [mscorlib]System.String
    IL_0185:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_018a:  stind.r8
    IL_018b:  ldarg.s    dDutyCycleOpenGate_G
    IL_018d:  ldloc.2
    IL_018e:  ldstr      "DutyCycleOpenGate_G"
    IL_0193:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_0198:  castclass  [mscorlib]System.String
    IL_019d:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_01a2:  stind.r8
    IL_01a3:  ldarg.s    dDutyCycleOpenGate_B
    IL_01a5:  ldloc.2
    IL_01a6:  ldstr      "DutyCycleOpenGate_B"
    IL_01ab:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_01b0:  castclass  [mscorlib]System.String
    IL_01b5:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_01ba:  stind.r8
    IL_01bb:  ldarg.s    dDutyCycleOpenGate_IR
    IL_01bd:  ldloc.2
    IL_01be:  ldstr      "DutyCycleOpenGate_Ir"
    IL_01c3:  callvirt   instance object [mscorlib]Microsoft.Win32.RegistryKey::GetValue(string)
    IL_01c8:  castclass  [mscorlib]System.String
    IL_01cd:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_01d2:  stind.r8
    IL_01d3:  ldloc.2
    IL_01d4:  callvirt   instance void [mscorlib]Microsoft.Win32.RegistryKey::Close()
    IL_01d9:  ret
  } // end of method TLXRegistry::GetOpenGateLED

  .method public hidebysig static string 
          GetTrackTestLog([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iType) cil managed
  {
    // Code size       27 (0x1b)
    .maxstack  8
    IL_0000:  ldstr      "{0}{1}"
    IL_0005:  ldarg.0
    IL_0006:  call       [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.Global::Convert([Interop.TLXLib]TLXLib.SCANNER_TYPE_000)
    IL_000b:  call       string Calibration.TLXRegistry::GetProgramPath([Interop.LLCLib]LLCLib.SCANNER_MODEL_000)
    IL_0010:  ldstr      "\\Logs\\PakonFilmTrackTestLog.txt"
    IL_0015:  call       string [mscorlib]System.String::Format(string,
                                                                object,
                                                                object)
    IL_001a:  ret
  } // end of method TLXRegistry::GetTrackTestLog

  .method public hidebysig static string 
          GetDXCodeLog([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 iType) cil managed
  {
    // Code size       27 (0x1b)
    .maxstack  8
    IL_0000:  ldstr      "{0}{1}"
    IL_0005:  ldarg.0
    IL_0006:  call       [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.Global::Convert([Interop.TLXLib]TLXLib.SCANNER_TYPE_000)
    IL_000b:  call       string Calibration.TLXRegistry::GetProgramPath([Interop.LLCLib]LLCLib.SCANNER_MODEL_000)
    IL_0010:  ldstr      "\\Logs\\DXCode.txt"
    IL_0015:  call       string [mscorlib]System.String::Format(string,
                                                                object,
                                                                object)
    IL_001a:  ret
  } // end of method TLXRegistry::GetDXCodeLog

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0006:  ret
  } // end of method TLXRegistry::.ctor

} // end of class Calibration.TLXRegistry

.class public auto ansi beforefieldinit Calibration.TLXRegistryFile
       extends [mscorlib]System.Object
{
  .field public static literal string m_strSection135 = "Pakon\\TLB]"
  .field public static literal string m_strSection235 = "Pakon\\TLA]"
  .field public static literal string m_strSection335 = "Pakon\\TLC]"
  .field public static literal string m_strSectionColor = "ColorKodak]"
  .field public static literal string m_strSectionScanner = "Scan]"
  .field public static literal string m_strSectionDpi16_24 = "DpiBase16_24]"
  .field public static literal string m_strSectionDpi16_35 = "DpiBase16_35]"
  .field public static literal string m_strSectionDpi4_24 = "DpiBase4_24]"
  .field public static literal string m_strSectionDpi4_35 = "DpiBase4_35]"
  .field public static literal string m_strSectionDpi8_24 = "DpiBase8_24]"
  .field public static literal string m_strSectionDpi8_35 = "DpiBase8_35]"
  .field public static literal string m_strKeyColorNeg = "\"NegMatrix"
  .field public static literal string m_strKeyColorPos = "\"PosMatrix"
  .field public static literal string m_strKeyScannerType = "\"ScannerType\""
  .field public static literal string m_strKeyScannerVersionHW = "\"ScannerVersionHw\""
  .field public static literal string m_strKeyScannerSerialNumber = "\"ScannerSerialNumber\""
  .field public static literal string m_strKeyDpiOffset = "\"Offset\""
  .field public static literal string m_strKeyDpiMotorAdjust = "\"MotorAdjust\""
  .field public static literal string m_strKeyDpiMotorAdjustIr = "\"MotorAdjust_Ir\""
  .field public static literal string m_strKeyDpiMotorSpeed = "\"MotorSpeed\""
  .field public static literal string m_strKeyDpiMotorSpeedIr = "\"MotorSpeed_Ir\""
  .field public static literal string m_strKeyDpiMotorSpeedPlus = "\"MotorSpeedPlus\""
  .field public static literal string m_strKeyDpiMotorSpeedPlusIr = "\"MotorSpeedPlus_Ir\""
  .field public static literal string m_strKeyStepperLens = "\"StepperLens\""
  .field public static literal string m_strKeyStepperCCD = "\"StepperCCD\""
  .field public static literal string m_strKeyStepperCCDAdjust = "\"StepperCCDAdjust\""
  .field private [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 m_smFileType
  .field private [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 m_stType
  .field private int32 m_nSerialNumber
  .field private [Pakon]Pakon.ScannerHW135 m_sh135
  .field private [Pakon]Pakon.ScannerHW235 m_sh235
  .field private [Pakon]Pakon.ScannerHW335 m_sh335
  .field private valuetype Calibration.DPIConfig m_dpi35mm16Base
  .field private valuetype Calibration.DPIConfig m_dpi35mm8Base
  .field private valuetype Calibration.DPIConfig m_dpi35mm4Base
  .field private valuetype Calibration.DPIConfig m_dpi24mm16Base
  .field private valuetype Calibration.DPIConfig m_dpi24mm8Base
  .field private valuetype Calibration.DPIConfig m_dpi24mm4Base
  .field private valuetype Calibration.ColorMatrixConfig m_cmNegative
  .field private valuetype Calibration.ColorMatrixConfig m_cmPositive
  .field private [Pakon]Pakon.IntBits m_ibEEPromNotFound
  .field private [Pakon]Pakon.IntBits m_ibColorNegNotFound
  .field private [Pakon]Pakon.IntBits m_ibColorPosNotFound
  .field private string m_strFile
  .method public hidebysig specialname instance string 
          get_Name() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      string Calibration.TLXRegistryFile::m_strFile
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_Name

  .method public hidebysig specialname instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 
          get_ScannerType() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Calibration.TLXRegistryFile::m_stType
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_ScannerType

  .method public hidebysig specialname instance int32 
          get_ScannerSerialNumber() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32 Calibration.TLXRegistryFile::m_nSerialNumber
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_ScannerSerialNumber

  .method public hidebysig specialname instance [Pakon]Pakon.ScannerHW135 
          get_ScannerHW135() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Pakon]Pakon.ScannerHW135 Calibration.TLXRegistryFile::m_sh135
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_ScannerHW135

  .method public hidebysig specialname instance [Pakon]Pakon.ScannerHW235 
          get_ScannerHW235() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Pakon]Pakon.ScannerHW235 Calibration.TLXRegistryFile::m_sh235
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_ScannerHW235

  .method public hidebysig specialname instance [Pakon]Pakon.ScannerHW335 
          get_ScannerHW335() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Pakon]Pakon.ScannerHW335 Calibration.TLXRegistryFile::m_sh335
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_ScannerHW335

  .method public hidebysig specialname instance valuetype Calibration.DPIConfig 
          get_Base16_35mm() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm16Base
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_Base16_35mm

  .method public hidebysig specialname instance valuetype Calibration.DPIConfig 
          get_Base8_35mm() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm8Base
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_Base8_35mm

  .method public hidebysig specialname instance valuetype Calibration.DPIConfig 
          get_Base4_35mm() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm4Base
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_Base4_35mm

  .method public hidebysig specialname instance valuetype Calibration.DPIConfig 
          get_Base16_24mm() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm16Base
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_Base16_24mm

  .method public hidebysig specialname instance valuetype Calibration.DPIConfig 
          get_Base8_24mm() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm8Base
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_Base8_24mm

  .method public hidebysig specialname instance valuetype Calibration.DPIConfig 
          get_Base4_24mm() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm4Base
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_Base4_24mm

  .method public hidebysig specialname instance valuetype Calibration.ColorMatrixConfig 
          get_MatrixNeg() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_MatrixNeg

  .method public hidebysig specialname instance valuetype Calibration.ColorMatrixConfig 
          get_MatrixPos() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_MatrixPos

  .method public hidebysig specialname instance [Pakon]Pakon.IntBits 
          get_EEProm() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_EEProm

  .method public hidebysig specialname instance [Pakon]Pakon.IntBits 
          get_ColorNeg() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibColorNegNotFound
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_ColorNeg

  .method public hidebysig specialname instance [Pakon]Pakon.IntBits 
          get_ColorPos() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibColorPosNotFound
    IL_0006:  ret
  } // end of method TLXRegistryFile::get_ColorPos

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       178 (0xb2)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.4
    IL_0002:  stfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_0007:  ldarg.0
    IL_0008:  ldc.i4.0
    IL_0009:  stfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Calibration.TLXRegistryFile::m_stType
    IL_000e:  ldarg.0
    IL_000f:  ldc.i4.0
    IL_0010:  stfld      int32 Calibration.TLXRegistryFile::m_nSerialNumber
    IL_0015:  ldarg.0
    IL_0016:  ldc.i4.0
    IL_0017:  stfld      [Pakon]Pakon.ScannerHW135 Calibration.TLXRegistryFile::m_sh135
    IL_001c:  ldarg.0
    IL_001d:  ldc.i4.0
    IL_001e:  stfld      [Pakon]Pakon.ScannerHW235 Calibration.TLXRegistryFile::m_sh235
    IL_0023:  ldarg.0
    IL_0024:  ldc.i4.0
    IL_0025:  stfld      [Pakon]Pakon.ScannerHW335 Calibration.TLXRegistryFile::m_sh335
    IL_002a:  ldarg.0
    IL_002b:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm16Base
    IL_0030:  initobj    Calibration.DPIConfig
    IL_0036:  ldarg.0
    IL_0037:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm8Base
    IL_003c:  initobj    Calibration.DPIConfig
    IL_0042:  ldarg.0
    IL_0043:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm4Base
    IL_0048:  initobj    Calibration.DPIConfig
    IL_004e:  ldarg.0
    IL_004f:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm16Base
    IL_0054:  initobj    Calibration.DPIConfig
    IL_005a:  ldarg.0
    IL_005b:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm8Base
    IL_0060:  initobj    Calibration.DPIConfig
    IL_0066:  ldarg.0
    IL_0067:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm4Base
    IL_006c:  initobj    Calibration.DPIConfig
    IL_0072:  ldarg.0
    IL_0073:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_0078:  initobj    Calibration.ColorMatrixConfig
    IL_007e:  ldarg.0
    IL_007f:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0084:  initobj    Calibration.ColorMatrixConfig
    IL_008a:  ldarg.0
    IL_008b:  newobj     instance void [Pakon]Pakon.IntBits::.ctor()
    IL_0090:  stfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0095:  ldarg.0
    IL_0096:  newobj     instance void [Pakon]Pakon.IntBits::.ctor()
    IL_009b:  stfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibColorNegNotFound
    IL_00a0:  ldarg.0
    IL_00a1:  newobj     instance void [Pakon]Pakon.IntBits::.ctor()
    IL_00a6:  stfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibColorPosNotFound
    IL_00ab:  ldarg.0
    IL_00ac:  call       instance void [mscorlib]System.Object::.ctor()
    IL_00b1:  ret
  } // end of method TLXRegistryFile::.ctor

  .method private hidebysig instance int32 
          ReadDWord(string strLine,
                    int32 nDefault) cil managed
  {
    // Code size       46 (0x2e)
    .maxstack  5
    .locals (int32 V_0,
             int32 V_1,
             string V_2)
    IL_0000:  ldarg.2
    IL_0001:  stloc.0
    IL_0002:  ldarg.1
    IL_0003:  ldc.i4.s   61
    IL_0005:  callvirt   instance int32 [mscorlib]System.String::IndexOf(char)
    IL_000a:  stloc.1
    IL_000b:  ldloc.1
    IL_000c:  ldc.i4.m1
    IL_000d:  beq.s      IL_002c

    IL_000f:  ldarg.1
    IL_0010:  ldloc.1
    IL_0011:  ldc.i4.7
    IL_0012:  add
    IL_0013:  ldarg.1
    IL_0014:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_0019:  ldloc.1
    IL_001a:  ldc.i4.7
    IL_001b:  add
    IL_001c:  sub
    IL_001d:  callvirt   instance string [mscorlib]System.String::Substring(int32,
                                                                            int32)
    IL_0022:  stloc.2
    IL_0023:  ldloc.2
    IL_0024:  ldc.i4.s   16
    IL_0026:  call       int32 [mscorlib]System.Convert::ToInt32(string,
                                                                 int32)
    IL_002b:  stloc.0
    IL_002c:  ldloc.0
    IL_002d:  ret
  } // end of method TLXRegistryFile::ReadDWord

  .method private hidebysig instance void 
          InitializeNotFoundIntBits() cil managed
  {
    // Code size       174 (0xae)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_0006:  brtrue.s   IL_0042

    IL_0008:  ldarg.0
    IL_0009:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_000e:  ldc.i4.1
    IL_000f:  stfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_0014:  ldarg.0
    IL_0015:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibColorNegNotFound
    IL_001a:  ldc.i4     0xfff
    IL_001f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Bits(int32)
    IL_0024:  ldarg.0
    IL_0025:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_002a:  ldc.i4.1
    IL_002b:  stfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_0030:  ldarg.0
    IL_0031:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibColorPosNotFound
    IL_0036:  ldc.i4     0xfff
    IL_003b:  callvirt   instance void [Pakon]Pakon.IntBits::set_Bits(int32)
    IL_0040:  br.s       IL_0083

    IL_0042:  ldarg.0
    IL_0043:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_0048:  ldc.i4.2
    IL_0049:  stfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_004e:  ldarg.0
    IL_004f:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibColorNegNotFound
    IL_0054:  ldc.i4     0x3fffffff
    IL_0059:  callvirt   instance void [Pakon]Pakon.IntBits::set_Bits(int32)
    IL_005e:  ldarg.0
    IL_005f:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_0064:  ldc.i4.2
    IL_0065:  bne.un.s   IL_0083

    IL_0067:  ldarg.0
    IL_0068:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_006d:  ldc.i4.2
    IL_006e:  stfld      valuetype Calibration.ColorMatrixType Calibration.ColorMatrixConfig::m_cmType
    IL_0073:  ldarg.0
    IL_0074:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibColorPosNotFound
    IL_0079:  ldc.i4     0x3fffffff
    IL_007e:  callvirt   instance void [Pakon]Pakon.IntBits::set_Bits(int32)
    IL_0083:  ldarg.0
    IL_0084:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_0089:  ldc.i4.3
    IL_008a:  bne.un.s   IL_009d

    IL_008c:  ldarg.0
    IL_008d:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0092:  ldc.i4     0x3f000038
    IL_0097:  callvirt   instance void [Pakon]Pakon.IntBits::set_Bits(int32)
    IL_009c:  ret

    IL_009d:  ldarg.0
    IL_009e:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_00a3:  ldc.i4     0x3fffffff
    IL_00a8:  callvirt   instance void [Pakon]Pakon.IntBits::set_Bits(int32)
    IL_00ad:  ret
  } // end of method TLXRegistryFile::InitializeNotFoundIntBits

  .method public hidebysig instance void 
          LoadFile([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 eType,
                   int32 nSerialNumber) cil managed
  {
    // Code size       387 (0x183)
    .maxstack  5
    .locals ([mscorlib]System.IO.StreamReader V_0,
             string V_1)
    IL_0000:  ldarg.0
    IL_0001:  ldstr      ""
    IL_0006:  stfld      string Calibration.TLXRegistryFile::m_strFile
    IL_000b:  ldarg.1
    IL_000c:  ldarg.2
    IL_000d:  ldarg.0
    IL_000e:  ldflda     string Calibration.TLXRegistryFile::m_strFile
    IL_0013:  call       void Calibration.Global::GetRegistryFile([Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                  int32,
                                                                  string&)
    IL_0018:  ldarg.0
    IL_0019:  ldfld      string Calibration.TLXRegistryFile::m_strFile
    IL_001e:  newobj     instance void [mscorlib]System.IO.StreamReader::.ctor(string)
    IL_0023:  stloc.0
    .try
    {
      IL_0024:  ldloc.0
      IL_0025:  callvirt   instance string [mscorlib]System.IO.TextReader::ReadLine()
      IL_002a:  stloc.1
      IL_002b:  br         IL_0170

      IL_0030:  ldarg.0
      IL_0031:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
      IL_0036:  ldc.i4.4
      IL_0037:  bne.un.s   IL_0094

      IL_0039:  ldloc.1
      IL_003a:  ldstr      "Pakon\\TLB]"
      IL_003f:  callvirt   instance bool [mscorlib]System.String::EndsWith(string)
      IL_0044:  brfalse.s  IL_004f

      IL_0046:  ldarg.0
      IL_0047:  ldc.i4.3
      IL_0048:  stfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
      IL_004d:  br.s       IL_0079

      IL_004f:  ldloc.1
      IL_0050:  ldstr      "Pakon\\TLA]"
      IL_0055:  callvirt   instance bool [mscorlib]System.String::EndsWith(string)
      IL_005a:  brfalse.s  IL_0065

      IL_005c:  ldarg.0
      IL_005d:  ldc.i4.0
      IL_005e:  stfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
      IL_0063:  br.s       IL_0079

      IL_0065:  ldloc.1
      IL_0066:  ldstr      "Pakon\\TLC]"
      IL_006b:  callvirt   instance bool [mscorlib]System.String::EndsWith(string)
      IL_0070:  brfalse.s  IL_0079

      IL_0072:  ldarg.0
      IL_0073:  ldc.i4.2
      IL_0074:  stfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
      IL_0079:  ldarg.0
      IL_007a:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
      IL_007f:  ldc.i4.4
      IL_0080:  beq.s      IL_0088

      IL_0082:  ldarg.0
      IL_0083:  call       instance void Calibration.TLXRegistryFile::InitializeNotFoundIntBits()
      IL_0088:  ldloc.0
      IL_0089:  callvirt   instance string [mscorlib]System.IO.TextReader::ReadLine()
      IL_008e:  stloc.1
      IL_008f:  br         IL_0170

      IL_0094:  ldloc.1
      IL_0095:  ldstr      "ColorKodak]"
      IL_009a:  callvirt   instance bool [mscorlib]System.String::EndsWith(string)
      IL_009f:  brfalse.s  IL_00af

      IL_00a1:  ldarg.0
      IL_00a2:  ldloc.0
      IL_00a3:  ldloca.s   V_1
      IL_00a5:  call       instance void Calibration.TLXRegistryFile::LoadColorMatrices([mscorlib]System.IO.StreamReader,
                                                                                        string&)
      IL_00aa:  br         IL_0170

      IL_00af:  ldloc.1
      IL_00b0:  ldstr      "Scan]"
      IL_00b5:  callvirt   instance bool [mscorlib]System.String::EndsWith(string)
      IL_00ba:  brfalse.s  IL_00ca

      IL_00bc:  ldarg.0
      IL_00bd:  ldloc.0
      IL_00be:  ldloca.s   V_1
      IL_00c0:  call       instance void Calibration.TLXRegistryFile::LoadScannerIdentification([mscorlib]System.IO.StreamReader,
                                                                                                string&)
      IL_00c5:  br         IL_0170

      IL_00ca:  ldloc.1
      IL_00cb:  ldstr      "DpiBase16_24]"
      IL_00d0:  callvirt   instance bool [mscorlib]System.String::EndsWith(string)
      IL_00d5:  brfalse.s  IL_00e7

      IL_00d7:  ldarg.0
      IL_00d8:  ldloc.0
      IL_00d9:  ldloca.s   V_1
      IL_00db:  ldc.i4.2
      IL_00dc:  ldc.i4.0
      IL_00dd:  call       instance void Calibration.TLXRegistryFile::LoadDpiConfig([mscorlib]System.IO.StreamReader,
                                                                                    string&,
                                                                                    [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                    [Interop.TLXLib]TLXLib.FILM_FORMAT_000)
      IL_00e2:  br         IL_0170

      IL_00e7:  ldloc.1
      IL_00e8:  ldstr      "DpiBase16_35]"
      IL_00ed:  callvirt   instance bool [mscorlib]System.String::EndsWith(string)
      IL_00f2:  brfalse.s  IL_0101

      IL_00f4:  ldarg.0
      IL_00f5:  ldloc.0
      IL_00f6:  ldloca.s   V_1
      IL_00f8:  ldc.i4.2
      IL_00f9:  ldc.i4.1
      IL_00fa:  call       instance void Calibration.TLXRegistryFile::LoadDpiConfig([mscorlib]System.IO.StreamReader,
                                                                                    string&,
                                                                                    [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                    [Interop.TLXLib]TLXLib.FILM_FORMAT_000)
      IL_00ff:  br.s       IL_0170

      IL_0101:  ldloc.1
      IL_0102:  ldstr      "DpiBase4_24]"
      IL_0107:  callvirt   instance bool [mscorlib]System.String::EndsWith(string)
      IL_010c:  brfalse.s  IL_011b

      IL_010e:  ldarg.0
      IL_010f:  ldloc.0
      IL_0110:  ldloca.s   V_1
      IL_0112:  ldc.i4.0
      IL_0113:  ldc.i4.0
      IL_0114:  call       instance void Calibration.TLXRegistryFile::LoadDpiConfig([mscorlib]System.IO.StreamReader,
                                                                                    string&,
                                                                                    [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                    [Interop.TLXLib]TLXLib.FILM_FORMAT_000)
      IL_0119:  br.s       IL_0170

      IL_011b:  ldloc.1
      IL_011c:  ldstr      "DpiBase4_35]"
      IL_0121:  callvirt   instance bool [mscorlib]System.String::EndsWith(string)
      IL_0126:  brfalse.s  IL_0135

      IL_0128:  ldarg.0
      IL_0129:  ldloc.0
      IL_012a:  ldloca.s   V_1
      IL_012c:  ldc.i4.0
      IL_012d:  ldc.i4.1
      IL_012e:  call       instance void Calibration.TLXRegistryFile::LoadDpiConfig([mscorlib]System.IO.StreamReader,
                                                                                    string&,
                                                                                    [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                    [Interop.TLXLib]TLXLib.FILM_FORMAT_000)
      IL_0133:  br.s       IL_0170

      IL_0135:  ldloc.1
      IL_0136:  ldstr      "DpiBase8_24]"
      IL_013b:  callvirt   instance bool [mscorlib]System.String::EndsWith(string)
      IL_0140:  brfalse.s  IL_014f

      IL_0142:  ldarg.0
      IL_0143:  ldloc.0
      IL_0144:  ldloca.s   V_1
      IL_0146:  ldc.i4.1
      IL_0147:  ldc.i4.0
      IL_0148:  call       instance void Calibration.TLXRegistryFile::LoadDpiConfig([mscorlib]System.IO.StreamReader,
                                                                                    string&,
                                                                                    [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                    [Interop.TLXLib]TLXLib.FILM_FORMAT_000)
      IL_014d:  br.s       IL_0170

      IL_014f:  ldloc.1
      IL_0150:  ldstr      "DpiBase8_35]"
      IL_0155:  callvirt   instance bool [mscorlib]System.String::EndsWith(string)
      IL_015a:  brfalse.s  IL_0169

      IL_015c:  ldarg.0
      IL_015d:  ldloc.0
      IL_015e:  ldloca.s   V_1
      IL_0160:  ldc.i4.1
      IL_0161:  ldc.i4.1
      IL_0162:  call       instance void Calibration.TLXRegistryFile::LoadDpiConfig([mscorlib]System.IO.StreamReader,
                                                                                    string&,
                                                                                    [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                                    [Interop.TLXLib]TLXLib.FILM_FORMAT_000)
      IL_0167:  br.s       IL_0170

      IL_0169:  ldloc.0
      IL_016a:  callvirt   instance string [mscorlib]System.IO.TextReader::ReadLine()
      IL_016f:  stloc.1
      IL_0170:  ldloc.1
      IL_0171:  brtrue     IL_0030

      IL_0176:  leave.s    IL_0182

    }  // end .try
    finally
    {
      IL_0178:  ldloc.0
      IL_0179:  brfalse.s  IL_0181

      IL_017b:  ldloc.0
      IL_017c:  callvirt   instance void [mscorlib]System.IDisposable::Dispose()
      IL_0181:  endfinally
    }  // end handler
    IL_0182:  ret
  } // end of method TLXRegistryFile::LoadFile

  .method private hidebysig instance void 
          LoadColorMatrices([mscorlib]System.IO.StreamReader sr,
                            string& strTemp) cil managed
  {
    // Code size       2487 (0x9b7)
    .maxstack  5
    .locals ([Interop.TLXLib]TLXLib.FILM_COLOR_000 V_0,
             int32 V_1,
             string V_2,
             string V_3,
             int32 V_4,
             int32 V_5)
    IL_0000:  ldarg.2
    IL_0001:  ldarg.1
    IL_0002:  callvirt   instance string [mscorlib]System.IO.TextReader::ReadLine()
    IL_0007:  stind.ref
    IL_0008:  br         IL_09a1

    IL_000d:  ldc.i4     0x1000
    IL_0012:  stloc.0
    IL_0013:  ldarg.2
    IL_0014:  ldind.ref
    IL_0015:  ldstr      "\"NegMatrix"
    IL_001a:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_001f:  brfalse.s  IL_0025

    IL_0021:  ldc.i4.1
    IL_0022:  stloc.0
    IL_0023:  br.s       IL_0035

    IL_0025:  ldarg.2
    IL_0026:  ldind.ref
    IL_0027:  ldstr      "\"PosMatrix"
    IL_002c:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_0031:  brfalse.s  IL_0035

    IL_0033:  ldc.i4.2
    IL_0034:  stloc.0
    IL_0035:  ldloc.0
    IL_0036:  ldc.i4     0x1000
    IL_003b:  beq        IL_0999

    IL_0040:  ldarg.2
    IL_0041:  ldind.ref
    IL_0042:  ldc.i4.s   61
    IL_0044:  callvirt   instance int32 [mscorlib]System.String::IndexOf(char)
    IL_0049:  stloc.1
    IL_004a:  ldloc.1
    IL_004b:  ldc.i4.m1
    IL_004c:  beq        IL_0999

    IL_0051:  ldarg.2
    IL_0052:  ldind.ref
    IL_0053:  ldstr      "\"NegMatrix"
    IL_0058:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_005d:  ldc.i4.2
    IL_005e:  callvirt   instance string [mscorlib]System.String::Substring(int32,
                                                                            int32)
    IL_0063:  stloc.2
    IL_0064:  ldarg.2
    IL_0065:  ldind.ref
    IL_0066:  ldloc.1
    IL_0067:  ldc.i4.2
    IL_0068:  add
    IL_0069:  ldarg.2
    IL_006a:  ldind.ref
    IL_006b:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_0070:  ldloc.1
    IL_0071:  ldc.i4.3
    IL_0072:  add
    IL_0073:  sub
    IL_0074:  callvirt   instance string [mscorlib]System.String::Substring(int32,
                                                                            int32)
    IL_0079:  stloc.3
    IL_007a:  ldloc.2
    IL_007b:  ldc.i4.1
    IL_007c:  callvirt   instance char [mscorlib]System.String::get_Chars(int32)
    IL_0081:  ldc.i4.s   34
    IL_0083:  bne.un.s   IL_008e

    IL_0085:  ldloc.2
    IL_0086:  ldc.i4.0
    IL_0087:  ldc.i4.1
    IL_0088:  callvirt   instance string [mscorlib]System.String::Substring(int32,
                                                                            int32)
    IL_008d:  stloc.2
    IL_008e:  ldloc.2
    IL_008f:  call       int32 [mscorlib]System.Convert::ToInt32(string)
    IL_0094:  stloc.s    V_4
    IL_0096:  ldloc.0
    IL_0097:  ldc.i4.1
    IL_0098:  bne.un.s   IL_00aa

    IL_009a:  ldarg.0
    IL_009b:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibColorNegNotFound
    IL_00a0:  ldloc.s    V_4
    IL_00a2:  ldc.i4.0
    IL_00a3:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_00a8:  br.s       IL_00b8

    IL_00aa:  ldarg.0
    IL_00ab:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibColorPosNotFound
    IL_00b0:  ldloc.s    V_4
    IL_00b2:  ldc.i4.0
    IL_00b3:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_00b8:  ldloc.s    V_4
    IL_00ba:  stloc.s    V_5
    IL_00bc:  ldloc.s    V_5
    IL_00be:  switch     ( 
                          IL_0140,
                          IL_01ac,
                          IL_0218,
                          IL_0284,
                          IL_02f0,
                          IL_035c,
                          IL_03c8,
                          IL_0434,
                          IL_04a0,
                          IL_050c,
                          IL_0578,
                          IL_05e4,
                          IL_0650,
                          IL_0680,
                          IL_06b0,
                          IL_06e0,
                          IL_0710,
                          IL_0740,
                          IL_0770,
                          IL_07a0,
                          IL_07d0,
                          IL_0800,
                          IL_0830,
                          IL_0860,
                          IL_0890,
                          IL_08c0,
                          IL_08f0,
                          IL_091d,
                          IL_0947,
                          IL_0971)
    IL_013b:  br         IL_0999

    IL_0140:  ldloc.0
    IL_0141:  ldc.i4.1
    IL_0142:  bne.un.s   IL_0178

    IL_0144:  ldarg.0
    IL_0145:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_014a:  brtrue.s   IL_0162

    IL_014c:  ldarg.0
    IL_014d:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_0152:  ldloc.3
    IL_0153:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_0158:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_0
    IL_015d:  br         IL_0999

    IL_0162:  ldarg.0
    IL_0163:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_0168:  ldloc.3
    IL_0169:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_016e:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_0
    IL_0173:  br         IL_0999

    IL_0178:  ldarg.0
    IL_0179:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_017e:  brtrue.s   IL_0196

    IL_0180:  ldarg.0
    IL_0181:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0186:  ldloc.3
    IL_0187:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_018c:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_0
    IL_0191:  br         IL_0999

    IL_0196:  ldarg.0
    IL_0197:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_019c:  ldloc.3
    IL_019d:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_01a2:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_0
    IL_01a7:  br         IL_0999

    IL_01ac:  ldloc.0
    IL_01ad:  ldc.i4.1
    IL_01ae:  bne.un.s   IL_01e4

    IL_01b0:  ldarg.0
    IL_01b1:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_01b6:  brtrue.s   IL_01ce

    IL_01b8:  ldarg.0
    IL_01b9:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_01be:  ldloc.3
    IL_01bf:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_01c4:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_1
    IL_01c9:  br         IL_0999

    IL_01ce:  ldarg.0
    IL_01cf:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_01d4:  ldloc.3
    IL_01d5:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_01da:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_1
    IL_01df:  br         IL_0999

    IL_01e4:  ldarg.0
    IL_01e5:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_01ea:  brtrue.s   IL_0202

    IL_01ec:  ldarg.0
    IL_01ed:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_01f2:  ldloc.3
    IL_01f3:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_01f8:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_1
    IL_01fd:  br         IL_0999

    IL_0202:  ldarg.0
    IL_0203:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0208:  ldloc.3
    IL_0209:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_020e:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_1
    IL_0213:  br         IL_0999

    IL_0218:  ldloc.0
    IL_0219:  ldc.i4.1
    IL_021a:  bne.un.s   IL_0250

    IL_021c:  ldarg.0
    IL_021d:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_0222:  brtrue.s   IL_023a

    IL_0224:  ldarg.0
    IL_0225:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_022a:  ldloc.3
    IL_022b:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_0230:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_2
    IL_0235:  br         IL_0999

    IL_023a:  ldarg.0
    IL_023b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_0240:  ldloc.3
    IL_0241:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0246:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_2
    IL_024b:  br         IL_0999

    IL_0250:  ldarg.0
    IL_0251:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_0256:  brtrue.s   IL_026e

    IL_0258:  ldarg.0
    IL_0259:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_025e:  ldloc.3
    IL_025f:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_0264:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_2
    IL_0269:  br         IL_0999

    IL_026e:  ldarg.0
    IL_026f:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0274:  ldloc.3
    IL_0275:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_027a:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_2
    IL_027f:  br         IL_0999

    IL_0284:  ldloc.0
    IL_0285:  ldc.i4.1
    IL_0286:  bne.un.s   IL_02bc

    IL_0288:  ldarg.0
    IL_0289:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_028e:  brtrue.s   IL_02a6

    IL_0290:  ldarg.0
    IL_0291:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_0296:  ldloc.3
    IL_0297:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_029c:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_3
    IL_02a1:  br         IL_0999

    IL_02a6:  ldarg.0
    IL_02a7:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_02ac:  ldloc.3
    IL_02ad:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_02b2:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_3
    IL_02b7:  br         IL_0999

    IL_02bc:  ldarg.0
    IL_02bd:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_02c2:  brtrue.s   IL_02da

    IL_02c4:  ldarg.0
    IL_02c5:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_02ca:  ldloc.3
    IL_02cb:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_02d0:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue0_3
    IL_02d5:  br         IL_0999

    IL_02da:  ldarg.0
    IL_02db:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_02e0:  ldloc.3
    IL_02e1:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_02e6:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_3
    IL_02eb:  br         IL_0999

    IL_02f0:  ldloc.0
    IL_02f1:  ldc.i4.1
    IL_02f2:  bne.un.s   IL_0328

    IL_02f4:  ldarg.0
    IL_02f5:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_02fa:  brtrue.s   IL_0312

    IL_02fc:  ldarg.0
    IL_02fd:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_0302:  ldloc.3
    IL_0303:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_0308:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_0
    IL_030d:  br         IL_0999

    IL_0312:  ldarg.0
    IL_0313:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_0318:  ldloc.3
    IL_0319:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_031e:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_4
    IL_0323:  br         IL_0999

    IL_0328:  ldarg.0
    IL_0329:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_032e:  brtrue.s   IL_0346

    IL_0330:  ldarg.0
    IL_0331:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0336:  ldloc.3
    IL_0337:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_033c:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_0
    IL_0341:  br         IL_0999

    IL_0346:  ldarg.0
    IL_0347:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_034c:  ldloc.3
    IL_034d:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0352:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_4
    IL_0357:  br         IL_0999

    IL_035c:  ldloc.0
    IL_035d:  ldc.i4.1
    IL_035e:  bne.un.s   IL_0394

    IL_0360:  ldarg.0
    IL_0361:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_0366:  brtrue.s   IL_037e

    IL_0368:  ldarg.0
    IL_0369:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_036e:  ldloc.3
    IL_036f:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_0374:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_1
    IL_0379:  br         IL_0999

    IL_037e:  ldarg.0
    IL_037f:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_0384:  ldloc.3
    IL_0385:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_038a:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_5
    IL_038f:  br         IL_0999

    IL_0394:  ldarg.0
    IL_0395:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_039a:  brtrue.s   IL_03b2

    IL_039c:  ldarg.0
    IL_039d:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_03a2:  ldloc.3
    IL_03a3:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_03a8:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_1
    IL_03ad:  br         IL_0999

    IL_03b2:  ldarg.0
    IL_03b3:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_03b8:  ldloc.3
    IL_03b9:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_03be:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_5
    IL_03c3:  br         IL_0999

    IL_03c8:  ldloc.0
    IL_03c9:  ldc.i4.1
    IL_03ca:  bne.un.s   IL_0400

    IL_03cc:  ldarg.0
    IL_03cd:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_03d2:  brtrue.s   IL_03ea

    IL_03d4:  ldarg.0
    IL_03d5:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_03da:  ldloc.3
    IL_03db:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_03e0:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_2
    IL_03e5:  br         IL_0999

    IL_03ea:  ldarg.0
    IL_03eb:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_03f0:  ldloc.3
    IL_03f1:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_03f6:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_6
    IL_03fb:  br         IL_0999

    IL_0400:  ldarg.0
    IL_0401:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_0406:  brtrue.s   IL_041e

    IL_0408:  ldarg.0
    IL_0409:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_040e:  ldloc.3
    IL_040f:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_0414:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_2
    IL_0419:  br         IL_0999

    IL_041e:  ldarg.0
    IL_041f:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0424:  ldloc.3
    IL_0425:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_042a:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_6
    IL_042f:  br         IL_0999

    IL_0434:  ldloc.0
    IL_0435:  ldc.i4.1
    IL_0436:  bne.un.s   IL_046c

    IL_0438:  ldarg.0
    IL_0439:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_043e:  brtrue.s   IL_0456

    IL_0440:  ldarg.0
    IL_0441:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_0446:  ldloc.3
    IL_0447:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_044c:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_3
    IL_0451:  br         IL_0999

    IL_0456:  ldarg.0
    IL_0457:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_045c:  ldloc.3
    IL_045d:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0462:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_7
    IL_0467:  br         IL_0999

    IL_046c:  ldarg.0
    IL_046d:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_0472:  brtrue.s   IL_048a

    IL_0474:  ldarg.0
    IL_0475:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_047a:  ldloc.3
    IL_047b:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_0480:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue1_3
    IL_0485:  br         IL_0999

    IL_048a:  ldarg.0
    IL_048b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0490:  ldloc.3
    IL_0491:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0496:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_7
    IL_049b:  br         IL_0999

    IL_04a0:  ldloc.0
    IL_04a1:  ldc.i4.1
    IL_04a2:  bne.un.s   IL_04d8

    IL_04a4:  ldarg.0
    IL_04a5:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_04aa:  brtrue.s   IL_04c2

    IL_04ac:  ldarg.0
    IL_04ad:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_04b2:  ldloc.3
    IL_04b3:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_04b8:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_0
    IL_04bd:  br         IL_0999

    IL_04c2:  ldarg.0
    IL_04c3:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_04c8:  ldloc.3
    IL_04c9:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_04ce:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_8
    IL_04d3:  br         IL_0999

    IL_04d8:  ldarg.0
    IL_04d9:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_04de:  brtrue.s   IL_04f6

    IL_04e0:  ldarg.0
    IL_04e1:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_04e6:  ldloc.3
    IL_04e7:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_04ec:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_0
    IL_04f1:  br         IL_0999

    IL_04f6:  ldarg.0
    IL_04f7:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_04fc:  ldloc.3
    IL_04fd:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0502:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_8
    IL_0507:  br         IL_0999

    IL_050c:  ldloc.0
    IL_050d:  ldc.i4.1
    IL_050e:  bne.un.s   IL_0544

    IL_0510:  ldarg.0
    IL_0511:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_0516:  brtrue.s   IL_052e

    IL_0518:  ldarg.0
    IL_0519:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_051e:  ldloc.3
    IL_051f:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_0524:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_1
    IL_0529:  br         IL_0999

    IL_052e:  ldarg.0
    IL_052f:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_0534:  ldloc.3
    IL_0535:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_053a:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_9
    IL_053f:  br         IL_0999

    IL_0544:  ldarg.0
    IL_0545:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_054a:  brtrue.s   IL_0562

    IL_054c:  ldarg.0
    IL_054d:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0552:  ldloc.3
    IL_0553:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_0558:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_1
    IL_055d:  br         IL_0999

    IL_0562:  ldarg.0
    IL_0563:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0568:  ldloc.3
    IL_0569:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_056e:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue0_9
    IL_0573:  br         IL_0999

    IL_0578:  ldloc.0
    IL_0579:  ldc.i4.1
    IL_057a:  bne.un.s   IL_05b0

    IL_057c:  ldarg.0
    IL_057d:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_0582:  brtrue.s   IL_059a

    IL_0584:  ldarg.0
    IL_0585:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_058a:  ldloc.3
    IL_058b:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_0590:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_2
    IL_0595:  br         IL_0999

    IL_059a:  ldarg.0
    IL_059b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_05a0:  ldloc.3
    IL_05a1:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_05a6:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_0
    IL_05ab:  br         IL_0999

    IL_05b0:  ldarg.0
    IL_05b1:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_05b6:  brtrue.s   IL_05ce

    IL_05b8:  ldarg.0
    IL_05b9:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_05be:  ldloc.3
    IL_05bf:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_05c4:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_2
    IL_05c9:  br         IL_0999

    IL_05ce:  ldarg.0
    IL_05cf:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_05d4:  ldloc.3
    IL_05d5:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_05da:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_0
    IL_05df:  br         IL_0999

    IL_05e4:  ldloc.0
    IL_05e5:  ldc.i4.1
    IL_05e6:  bne.un.s   IL_061c

    IL_05e8:  ldarg.0
    IL_05e9:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_05ee:  brtrue.s   IL_0606

    IL_05f0:  ldarg.0
    IL_05f1:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_05f6:  ldloc.3
    IL_05f7:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_05fc:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_3
    IL_0601:  br         IL_0999

    IL_0606:  ldarg.0
    IL_0607:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_060c:  ldloc.3
    IL_060d:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0612:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_1
    IL_0617:  br         IL_0999

    IL_061c:  ldarg.0
    IL_061d:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_0622:  brtrue.s   IL_063a

    IL_0624:  ldarg.0
    IL_0625:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_062a:  ldloc.3
    IL_062b:  call       float64 [mscorlib]System.Convert::ToDouble(string)
    IL_0630:  stfld      float64 Calibration.ColorMatrixConfig::m_dfMatrixValue2_3
    IL_0635:  br         IL_0999

    IL_063a:  ldarg.0
    IL_063b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0640:  ldloc.3
    IL_0641:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0646:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_1
    IL_064b:  br         IL_0999

    IL_0650:  ldloc.0
    IL_0651:  ldc.i4.1
    IL_0652:  bne.un.s   IL_066a

    IL_0654:  ldarg.0
    IL_0655:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_065a:  ldloc.3
    IL_065b:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0660:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_2
    IL_0665:  br         IL_0999

    IL_066a:  ldarg.0
    IL_066b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0670:  ldloc.3
    IL_0671:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0676:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_2
    IL_067b:  br         IL_0999

    IL_0680:  ldloc.0
    IL_0681:  ldc.i4.1
    IL_0682:  bne.un.s   IL_069a

    IL_0684:  ldarg.0
    IL_0685:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_068a:  ldloc.3
    IL_068b:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0690:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_3
    IL_0695:  br         IL_0999

    IL_069a:  ldarg.0
    IL_069b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_06a0:  ldloc.3
    IL_06a1:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_06a6:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_3
    IL_06ab:  br         IL_0999

    IL_06b0:  ldloc.0
    IL_06b1:  ldc.i4.1
    IL_06b2:  bne.un.s   IL_06ca

    IL_06b4:  ldarg.0
    IL_06b5:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_06ba:  ldloc.3
    IL_06bb:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_06c0:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_4
    IL_06c5:  br         IL_0999

    IL_06ca:  ldarg.0
    IL_06cb:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_06d0:  ldloc.3
    IL_06d1:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_06d6:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_4
    IL_06db:  br         IL_0999

    IL_06e0:  ldloc.0
    IL_06e1:  ldc.i4.1
    IL_06e2:  bne.un.s   IL_06fa

    IL_06e4:  ldarg.0
    IL_06e5:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_06ea:  ldloc.3
    IL_06eb:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_06f0:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_5
    IL_06f5:  br         IL_0999

    IL_06fa:  ldarg.0
    IL_06fb:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0700:  ldloc.3
    IL_0701:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0706:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_5
    IL_070b:  br         IL_0999

    IL_0710:  ldloc.0
    IL_0711:  ldc.i4.1
    IL_0712:  bne.un.s   IL_072a

    IL_0714:  ldarg.0
    IL_0715:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_071a:  ldloc.3
    IL_071b:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0720:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_6
    IL_0725:  br         IL_0999

    IL_072a:  ldarg.0
    IL_072b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0730:  ldloc.3
    IL_0731:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0736:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_6
    IL_073b:  br         IL_0999

    IL_0740:  ldloc.0
    IL_0741:  ldc.i4.1
    IL_0742:  bne.un.s   IL_075a

    IL_0744:  ldarg.0
    IL_0745:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_074a:  ldloc.3
    IL_074b:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0750:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_7
    IL_0755:  br         IL_0999

    IL_075a:  ldarg.0
    IL_075b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0760:  ldloc.3
    IL_0761:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0766:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_7
    IL_076b:  br         IL_0999

    IL_0770:  ldloc.0
    IL_0771:  ldc.i4.1
    IL_0772:  bne.un.s   IL_078a

    IL_0774:  ldarg.0
    IL_0775:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_077a:  ldloc.3
    IL_077b:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0780:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_8
    IL_0785:  br         IL_0999

    IL_078a:  ldarg.0
    IL_078b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0790:  ldloc.3
    IL_0791:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0796:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_8
    IL_079b:  br         IL_0999

    IL_07a0:  ldloc.0
    IL_07a1:  ldc.i4.1
    IL_07a2:  bne.un.s   IL_07ba

    IL_07a4:  ldarg.0
    IL_07a5:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_07aa:  ldloc.3
    IL_07ab:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_07b0:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_9
    IL_07b5:  br         IL_0999

    IL_07ba:  ldarg.0
    IL_07bb:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_07c0:  ldloc.3
    IL_07c1:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_07c6:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue1_9
    IL_07cb:  br         IL_0999

    IL_07d0:  ldloc.0
    IL_07d1:  ldc.i4.1
    IL_07d2:  bne.un.s   IL_07ea

    IL_07d4:  ldarg.0
    IL_07d5:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_07da:  ldloc.3
    IL_07db:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_07e0:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_0
    IL_07e5:  br         IL_0999

    IL_07ea:  ldarg.0
    IL_07eb:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_07f0:  ldloc.3
    IL_07f1:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_07f6:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_0
    IL_07fb:  br         IL_0999

    IL_0800:  ldloc.0
    IL_0801:  ldc.i4.1
    IL_0802:  bne.un.s   IL_081a

    IL_0804:  ldarg.0
    IL_0805:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_080a:  ldloc.3
    IL_080b:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0810:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_1
    IL_0815:  br         IL_0999

    IL_081a:  ldarg.0
    IL_081b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0820:  ldloc.3
    IL_0821:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0826:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_1
    IL_082b:  br         IL_0999

    IL_0830:  ldloc.0
    IL_0831:  ldc.i4.1
    IL_0832:  bne.un.s   IL_084a

    IL_0834:  ldarg.0
    IL_0835:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_083a:  ldloc.3
    IL_083b:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0840:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_2
    IL_0845:  br         IL_0999

    IL_084a:  ldarg.0
    IL_084b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0850:  ldloc.3
    IL_0851:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0856:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_2
    IL_085b:  br         IL_0999

    IL_0860:  ldloc.0
    IL_0861:  ldc.i4.1
    IL_0862:  bne.un.s   IL_087a

    IL_0864:  ldarg.0
    IL_0865:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_086a:  ldloc.3
    IL_086b:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0870:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_3
    IL_0875:  br         IL_0999

    IL_087a:  ldarg.0
    IL_087b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0880:  ldloc.3
    IL_0881:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0886:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_3
    IL_088b:  br         IL_0999

    IL_0890:  ldloc.0
    IL_0891:  ldc.i4.1
    IL_0892:  bne.un.s   IL_08aa

    IL_0894:  ldarg.0
    IL_0895:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_089a:  ldloc.3
    IL_089b:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_08a0:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_4
    IL_08a5:  br         IL_0999

    IL_08aa:  ldarg.0
    IL_08ab:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_08b0:  ldloc.3
    IL_08b1:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_08b6:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_4
    IL_08bb:  br         IL_0999

    IL_08c0:  ldloc.0
    IL_08c1:  ldc.i4.1
    IL_08c2:  bne.un.s   IL_08da

    IL_08c4:  ldarg.0
    IL_08c5:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_08ca:  ldloc.3
    IL_08cb:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_08d0:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_5
    IL_08d5:  br         IL_0999

    IL_08da:  ldarg.0
    IL_08db:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_08e0:  ldloc.3
    IL_08e1:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_08e6:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_5
    IL_08eb:  br         IL_0999

    IL_08f0:  ldloc.0
    IL_08f1:  ldc.i4.1
    IL_08f2:  bne.un.s   IL_090a

    IL_08f4:  ldarg.0
    IL_08f5:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_08fa:  ldloc.3
    IL_08fb:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0900:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_6
    IL_0905:  br         IL_0999

    IL_090a:  ldarg.0
    IL_090b:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0910:  ldloc.3
    IL_0911:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0916:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_6
    IL_091b:  br.s       IL_0999

    IL_091d:  ldloc.0
    IL_091e:  ldc.i4.1
    IL_091f:  bne.un.s   IL_0934

    IL_0921:  ldarg.0
    IL_0922:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_0927:  ldloc.3
    IL_0928:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_092d:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_7
    IL_0932:  br.s       IL_0999

    IL_0934:  ldarg.0
    IL_0935:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_093a:  ldloc.3
    IL_093b:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0940:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_7
    IL_0945:  br.s       IL_0999

    IL_0947:  ldloc.0
    IL_0948:  ldc.i4.1
    IL_0949:  bne.un.s   IL_095e

    IL_094b:  ldarg.0
    IL_094c:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_0951:  ldloc.3
    IL_0952:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0957:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_8
    IL_095c:  br.s       IL_0999

    IL_095e:  ldarg.0
    IL_095f:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_0964:  ldloc.3
    IL_0965:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_096a:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_8
    IL_096f:  br.s       IL_0999

    IL_0971:  ldloc.0
    IL_0972:  ldc.i4.1
    IL_0973:  bne.un.s   IL_0988

    IL_0975:  ldarg.0
    IL_0976:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmNegative
    IL_097b:  ldloc.3
    IL_097c:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0981:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_9
    IL_0986:  br.s       IL_0999

    IL_0988:  ldarg.0
    IL_0989:  ldflda     valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::m_cmPositive
    IL_098e:  ldloc.3
    IL_098f:  call       float32 [mscorlib]System.Convert::ToSingle(string)
    IL_0994:  stfld      float32 Calibration.ColorMatrixConfig::m_fMatrixValue2_9
    IL_0999:  ldarg.2
    IL_099a:  ldarg.1
    IL_099b:  callvirt   instance string [mscorlib]System.IO.TextReader::ReadLine()
    IL_09a0:  stind.ref
    IL_09a1:  ldarg.2
    IL_09a2:  ldind.ref
    IL_09a3:  ldstr      "]"
    IL_09a8:  callvirt   instance bool [mscorlib]System.String::EndsWith(string)
    IL_09ad:  brtrue.s   IL_09b6

    IL_09af:  ldarg.2
    IL_09b0:  ldind.ref
    IL_09b1:  brtrue     IL_000d

    IL_09b6:  ret
  } // end of method TLXRegistryFile::LoadColorMatrices

  .method private hidebysig instance void 
          LoadScannerIdentification([mscorlib]System.IO.StreamReader sr,
                                    string& strTemp) cil managed
  {
    // Code size       199 (0xc7)
    .maxstack  4
    .locals ([Interop.LLCLib]LLCLib.SCANNER_MODEL_000 V_0)
    IL_0000:  ldarg.2
    IL_0001:  ldarg.1
    IL_0002:  callvirt   instance string [mscorlib]System.IO.TextReader::ReadLine()
    IL_0007:  stind.ref
    IL_0008:  br         IL_00b1

    IL_000d:  ldarg.2
    IL_000e:  ldind.ref
    IL_000f:  ldstr      "\"ScannerType\""
    IL_0014:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_0019:  brfalse.s  IL_002c

    IL_001b:  ldarg.0
    IL_001c:  ldarg.0
    IL_001d:  ldarg.2
    IL_001e:  ldind.ref
    IL_001f:  ldc.i4.0
    IL_0020:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0025:  stfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Calibration.TLXRegistryFile::m_stType
    IL_002a:  br.s       IL_00a9

    IL_002c:  ldarg.2
    IL_002d:  ldind.ref
    IL_002e:  ldstr      "\"ScannerVersionHw\""
    IL_0033:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_0038:  brfalse.s  IL_008c

    IL_003a:  ldarg.0
    IL_003b:  ldfld      [Interop.LLCLib]LLCLib.SCANNER_MODEL_000 Calibration.TLXRegistryFile::m_smFileType
    IL_0040:  stloc.0
    IL_0041:  ldloc.0
    IL_0042:  switch     ( 
                          IL_006a,
                          IL_00a9,
                          IL_007b,
                          IL_0059)
    IL_0057:  br.s       IL_00a9

    IL_0059:  ldarg.0
    IL_005a:  ldarg.0
    IL_005b:  ldarg.2
    IL_005c:  ldind.ref
    IL_005d:  ldc.i4.0
    IL_005e:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0063:  stfld      [Pakon]Pakon.ScannerHW135 Calibration.TLXRegistryFile::m_sh135
    IL_0068:  br.s       IL_00a9

    IL_006a:  ldarg.0
    IL_006b:  ldarg.0
    IL_006c:  ldarg.2
    IL_006d:  ldind.ref
    IL_006e:  ldc.i4.0
    IL_006f:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0074:  stfld      [Pakon]Pakon.ScannerHW235 Calibration.TLXRegistryFile::m_sh235
    IL_0079:  br.s       IL_00a9

    IL_007b:  ldarg.0
    IL_007c:  ldarg.0
    IL_007d:  ldarg.2
    IL_007e:  ldind.ref
    IL_007f:  ldc.i4.0
    IL_0080:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0085:  stfld      [Pakon]Pakon.ScannerHW335 Calibration.TLXRegistryFile::m_sh335
    IL_008a:  br.s       IL_00a9

    IL_008c:  ldarg.2
    IL_008d:  ldind.ref
    IL_008e:  ldstr      "\"ScannerSerialNumber\""
    IL_0093:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_0098:  brfalse.s  IL_00a9

    IL_009a:  ldarg.0
    IL_009b:  ldarg.0
    IL_009c:  ldarg.2
    IL_009d:  ldind.ref
    IL_009e:  ldc.i4.0
    IL_009f:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_00a4:  stfld      int32 Calibration.TLXRegistryFile::m_nSerialNumber
    IL_00a9:  ldarg.2
    IL_00aa:  ldarg.1
    IL_00ab:  callvirt   instance string [mscorlib]System.IO.TextReader::ReadLine()
    IL_00b0:  stind.ref
    IL_00b1:  ldarg.2
    IL_00b2:  ldind.ref
    IL_00b3:  ldstr      "]"
    IL_00b8:  callvirt   instance bool [mscorlib]System.String::EndsWith(string)
    IL_00bd:  brtrue.s   IL_00c6

    IL_00bf:  ldarg.2
    IL_00c0:  ldind.ref
    IL_00c1:  brtrue     IL_000d

    IL_00c6:  ret
  } // end of method TLXRegistryFile::LoadScannerIdentification

  .method private hidebysig instance void 
          LoadDpiConfig([mscorlib]System.IO.StreamReader sr,
                        string& strTemp,
                        [Interop.TLXLib]TLXLib.RESOLUTION_000 prResolution,
                        [Interop.TLXLib]TLXLib.FILM_FORMAT_000 ffFormat) cil managed
  {
    // Code size       2808 (0xaf8)
    .maxstack  4
    .locals ([Interop.TLXLib]TLXLib.FILM_FORMAT_000 V_0,
             [Interop.TLXLib]TLXLib.RESOLUTION_000 V_1)
    IL_0000:  ldarg.2
    IL_0001:  ldarg.1
    IL_0002:  callvirt   instance string [mscorlib]System.IO.TextReader::ReadLine()
    IL_0007:  stind.ref
    IL_0008:  br         IL_0ae2

    IL_000d:  ldarg.2
    IL_000e:  ldind.ref
    IL_000f:  ldstr      "\"Offset\""
    IL_0014:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_0019:  brfalse    IL_0150

    IL_001e:  ldarg.s    ffFormat
    IL_0020:  stloc.0
    IL_0021:  ldloc.0
    IL_0022:  switch     ( 
                          IL_00c2,
                          IL_0034)
    IL_002f:  br         IL_0ada

    IL_0034:  ldarg.3
    IL_0035:  stloc.1
    IL_0036:  ldloc.1
    IL_0037:  switch     ( 
                          IL_009b,
                          IL_0074,
                          IL_004d)
    IL_0048:  br         IL_0ada

    IL_004d:  ldarg.0
    IL_004e:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm16Base
    IL_0053:  ldarg.0
    IL_0054:  ldarg.2
    IL_0055:  ldind.ref
    IL_0056:  ldc.i4.0
    IL_0057:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_005c:  conv.u2
    IL_005d:  stfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0062:  ldarg.0
    IL_0063:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0068:  ldc.i4.5
    IL_0069:  ldc.i4.0
    IL_006a:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_006f:  br         IL_0ada

    IL_0074:  ldarg.0
    IL_0075:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm8Base
    IL_007a:  ldarg.0
    IL_007b:  ldarg.2
    IL_007c:  ldind.ref
    IL_007d:  ldc.i4.0
    IL_007e:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0083:  conv.u2
    IL_0084:  stfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0089:  ldarg.0
    IL_008a:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_008f:  ldc.i4.4
    IL_0090:  ldc.i4.0
    IL_0091:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0096:  br         IL_0ada

    IL_009b:  ldarg.0
    IL_009c:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm4Base
    IL_00a1:  ldarg.0
    IL_00a2:  ldarg.2
    IL_00a3:  ldind.ref
    IL_00a4:  ldc.i4.0
    IL_00a5:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_00aa:  conv.u2
    IL_00ab:  stfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_00b0:  ldarg.0
    IL_00b1:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_00b6:  ldc.i4.3
    IL_00b7:  ldc.i4.0
    IL_00b8:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_00bd:  br         IL_0ada

    IL_00c2:  ldarg.3
    IL_00c3:  stloc.1
    IL_00c4:  ldloc.1
    IL_00c5:  switch     ( 
                          IL_0129,
                          IL_0102,
                          IL_00db)
    IL_00d6:  br         IL_0ada

    IL_00db:  ldarg.0
    IL_00dc:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm16Base
    IL_00e1:  ldarg.0
    IL_00e2:  ldarg.2
    IL_00e3:  ldind.ref
    IL_00e4:  ldc.i4.0
    IL_00e5:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_00ea:  conv.u2
    IL_00eb:  stfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_00f0:  ldarg.0
    IL_00f1:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_00f6:  ldc.i4.2
    IL_00f7:  ldc.i4.0
    IL_00f8:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_00fd:  br         IL_0ada

    IL_0102:  ldarg.0
    IL_0103:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm8Base
    IL_0108:  ldarg.0
    IL_0109:  ldarg.2
    IL_010a:  ldind.ref
    IL_010b:  ldc.i4.0
    IL_010c:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0111:  conv.u2
    IL_0112:  stfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_0117:  ldarg.0
    IL_0118:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_011d:  ldc.i4.1
    IL_011e:  ldc.i4.0
    IL_011f:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0124:  br         IL_0ada

    IL_0129:  ldarg.0
    IL_012a:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm4Base
    IL_012f:  ldarg.0
    IL_0130:  ldarg.2
    IL_0131:  ldind.ref
    IL_0132:  ldc.i4.0
    IL_0133:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0138:  conv.u2
    IL_0139:  stfld      uint16 Calibration.DPIConfig::m_usOffset
    IL_013e:  ldarg.0
    IL_013f:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0144:  ldc.i4.0
    IL_0145:  ldc.i4.0
    IL_0146:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_014b:  br         IL_0ada

    IL_0150:  ldarg.2
    IL_0151:  ldind.ref
    IL_0152:  ldstr      "\"MotorSpeedPlus_Ir\""
    IL_0157:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_015c:  brfalse    IL_020c

    IL_0161:  ldarg.0
    IL_0162:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Calibration.TLXRegistryFile::m_stType
    IL_0167:  ldc.i4     0x547
    IL_016c:  bne.un     IL_0ada

    IL_0171:  ldarg.s    ffFormat
    IL_0173:  stloc.0
    IL_0174:  ldloc.0
    IL_0175:  ldc.i4.1
    IL_0176:  bne.un     IL_0ada

    IL_017b:  ldarg.3
    IL_017c:  stloc.1
    IL_017d:  ldloc.1
    IL_017e:  switch     ( 
                          IL_01e4,
                          IL_01bc,
                          IL_0194)
    IL_018f:  br         IL_0ada

    IL_0194:  ldarg.0
    IL_0195:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm16Base
    IL_019a:  ldarg.0
    IL_019b:  ldarg.2
    IL_019c:  ldind.ref
    IL_019d:  ldc.i4.0
    IL_019e:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_01a3:  conv.u2
    IL_01a4:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_01a9:  ldarg.0
    IL_01aa:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_01af:  ldc.i4.s   29
    IL_01b1:  ldc.i4.0
    IL_01b2:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_01b7:  br         IL_0ada

    IL_01bc:  ldarg.0
    IL_01bd:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm8Base
    IL_01c2:  ldarg.0
    IL_01c3:  ldarg.2
    IL_01c4:  ldind.ref
    IL_01c5:  ldc.i4.0
    IL_01c6:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_01cb:  conv.u2
    IL_01cc:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_01d1:  ldarg.0
    IL_01d2:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_01d7:  ldc.i4.s   27
    IL_01d9:  ldc.i4.0
    IL_01da:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_01df:  br         IL_0ada

    IL_01e4:  ldarg.0
    IL_01e5:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm4Base
    IL_01ea:  ldarg.0
    IL_01eb:  ldarg.2
    IL_01ec:  ldind.ref
    IL_01ed:  ldc.i4.0
    IL_01ee:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_01f3:  conv.u2
    IL_01f4:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_01f9:  ldarg.0
    IL_01fa:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_01ff:  ldc.i4.s   25
    IL_0201:  ldc.i4.0
    IL_0202:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0207:  br         IL_0ada

    IL_020c:  ldarg.2
    IL_020d:  ldind.ref
    IL_020e:  ldstr      "\"MotorSpeed_Ir\""
    IL_0213:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_0218:  brfalse    IL_0365

    IL_021d:  ldarg.0
    IL_021e:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Calibration.TLXRegistryFile::m_stType
    IL_0223:  ldc.i4     0x547
    IL_0228:  beq        IL_0ada

    IL_022d:  ldarg.s    ffFormat
    IL_022f:  stloc.0
    IL_0230:  ldloc.0
    IL_0231:  switch     ( 
                          IL_02d4,
                          IL_0243)
    IL_023e:  br         IL_0ada

    IL_0243:  ldarg.3
    IL_0244:  stloc.1
    IL_0245:  ldloc.1
    IL_0246:  switch     ( 
                          IL_02ac,
                          IL_0284,
                          IL_025c)
    IL_0257:  br         IL_0ada

    IL_025c:  ldarg.0
    IL_025d:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm16Base
    IL_0262:  ldarg.0
    IL_0263:  ldarg.2
    IL_0264:  ldind.ref
    IL_0265:  ldc.i4.0
    IL_0266:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_026b:  conv.u2
    IL_026c:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_0271:  ldarg.0
    IL_0272:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0277:  ldc.i4.s   29
    IL_0279:  ldc.i4.0
    IL_027a:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_027f:  br         IL_0ada

    IL_0284:  ldarg.0
    IL_0285:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm8Base
    IL_028a:  ldarg.0
    IL_028b:  ldarg.2
    IL_028c:  ldind.ref
    IL_028d:  ldc.i4.0
    IL_028e:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0293:  conv.u2
    IL_0294:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_0299:  ldarg.0
    IL_029a:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_029f:  ldc.i4.s   27
    IL_02a1:  ldc.i4.0
    IL_02a2:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_02a7:  br         IL_0ada

    IL_02ac:  ldarg.0
    IL_02ad:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm4Base
    IL_02b2:  ldarg.0
    IL_02b3:  ldarg.2
    IL_02b4:  ldind.ref
    IL_02b5:  ldc.i4.0
    IL_02b6:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_02bb:  conv.u2
    IL_02bc:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_02c1:  ldarg.0
    IL_02c2:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_02c7:  ldc.i4.s   25
    IL_02c9:  ldc.i4.0
    IL_02ca:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_02cf:  br         IL_0ada

    IL_02d4:  ldarg.3
    IL_02d5:  stloc.1
    IL_02d6:  ldloc.1
    IL_02d7:  switch     ( 
                          IL_033d,
                          IL_0315,
                          IL_02ed)
    IL_02e8:  br         IL_0ada

    IL_02ed:  ldarg.0
    IL_02ee:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm16Base
    IL_02f3:  ldarg.0
    IL_02f4:  ldarg.2
    IL_02f5:  ldind.ref
    IL_02f6:  ldc.i4.0
    IL_02f7:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_02fc:  conv.u2
    IL_02fd:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_0302:  ldarg.0
    IL_0303:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0308:  ldc.i4.s   23
    IL_030a:  ldc.i4.0
    IL_030b:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0310:  br         IL_0ada

    IL_0315:  ldarg.0
    IL_0316:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm8Base
    IL_031b:  ldarg.0
    IL_031c:  ldarg.2
    IL_031d:  ldind.ref
    IL_031e:  ldc.i4.0
    IL_031f:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0324:  conv.u2
    IL_0325:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_032a:  ldarg.0
    IL_032b:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0330:  ldc.i4.s   21
    IL_0332:  ldc.i4.0
    IL_0333:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0338:  br         IL_0ada

    IL_033d:  ldarg.0
    IL_033e:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm4Base
    IL_0343:  ldarg.0
    IL_0344:  ldarg.2
    IL_0345:  ldind.ref
    IL_0346:  ldc.i4.0
    IL_0347:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_034c:  conv.u2
    IL_034d:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed_Ir
    IL_0352:  ldarg.0
    IL_0353:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0358:  ldc.i4.s   19
    IL_035a:  ldc.i4.0
    IL_035b:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0360:  br         IL_0ada

    IL_0365:  ldarg.2
    IL_0366:  ldind.ref
    IL_0367:  ldstr      "\"MotorAdjust\""
    IL_036c:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_0371:  brfalse    IL_045a

    IL_0376:  ldarg.s    ffFormat
    IL_0378:  stloc.0
    IL_0379:  ldloc.0
    IL_037a:  switch     ( 
                          IL_03f3,
                          IL_038c)
    IL_0387:  br         IL_0ada

    IL_038c:  ldarg.3
    IL_038d:  stloc.1
    IL_038e:  ldloc.1
    IL_038f:  switch     ( 
                          IL_03d9,
                          IL_03bf,
                          IL_03a5)
    IL_03a0:  br         IL_0ada

    IL_03a5:  ldarg.0
    IL_03a6:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm16Base
    IL_03ab:  ldarg.0
    IL_03ac:  ldarg.2
    IL_03ad:  ldind.ref
    IL_03ae:  ldc.i4.0
    IL_03af:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_03b4:  conv.u2
    IL_03b5:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust
    IL_03ba:  br         IL_0ada

    IL_03bf:  ldarg.0
    IL_03c0:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm8Base
    IL_03c5:  ldarg.0
    IL_03c6:  ldarg.2
    IL_03c7:  ldind.ref
    IL_03c8:  ldc.i4.0
    IL_03c9:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_03ce:  conv.u2
    IL_03cf:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust
    IL_03d4:  br         IL_0ada

    IL_03d9:  ldarg.0
    IL_03da:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm4Base
    IL_03df:  ldarg.0
    IL_03e0:  ldarg.2
    IL_03e1:  ldind.ref
    IL_03e2:  ldc.i4.0
    IL_03e3:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_03e8:  conv.u2
    IL_03e9:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust
    IL_03ee:  br         IL_0ada

    IL_03f3:  ldarg.3
    IL_03f4:  stloc.1
    IL_03f5:  ldloc.1
    IL_03f6:  switch     ( 
                          IL_0440,
                          IL_0426,
                          IL_040c)
    IL_0407:  br         IL_0ada

    IL_040c:  ldarg.0
    IL_040d:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm16Base
    IL_0412:  ldarg.0
    IL_0413:  ldarg.2
    IL_0414:  ldind.ref
    IL_0415:  ldc.i4.0
    IL_0416:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_041b:  conv.u2
    IL_041c:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust
    IL_0421:  br         IL_0ada

    IL_0426:  ldarg.0
    IL_0427:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm8Base
    IL_042c:  ldarg.0
    IL_042d:  ldarg.2
    IL_042e:  ldind.ref
    IL_042f:  ldc.i4.0
    IL_0430:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0435:  conv.u2
    IL_0436:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust
    IL_043b:  br         IL_0ada

    IL_0440:  ldarg.0
    IL_0441:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm4Base
    IL_0446:  ldarg.0
    IL_0447:  ldarg.2
    IL_0448:  ldind.ref
    IL_0449:  ldc.i4.0
    IL_044a:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_044f:  conv.u2
    IL_0450:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust
    IL_0455:  br         IL_0ada

    IL_045a:  ldarg.2
    IL_045b:  ldind.ref
    IL_045c:  ldstr      "\"MotorAdjust_Ir\""
    IL_0461:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_0466:  brfalse    IL_054f

    IL_046b:  ldarg.s    ffFormat
    IL_046d:  stloc.0
    IL_046e:  ldloc.0
    IL_046f:  switch     ( 
                          IL_04e8,
                          IL_0481)
    IL_047c:  br         IL_0ada

    IL_0481:  ldarg.3
    IL_0482:  stloc.1
    IL_0483:  ldloc.1
    IL_0484:  switch     ( 
                          IL_04ce,
                          IL_04b4,
                          IL_049a)
    IL_0495:  br         IL_0ada

    IL_049a:  ldarg.0
    IL_049b:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm16Base
    IL_04a0:  ldarg.0
    IL_04a1:  ldarg.2
    IL_04a2:  ldind.ref
    IL_04a3:  ldc.i4.0
    IL_04a4:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_04a9:  conv.u2
    IL_04aa:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust_Ir
    IL_04af:  br         IL_0ada

    IL_04b4:  ldarg.0
    IL_04b5:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm8Base
    IL_04ba:  ldarg.0
    IL_04bb:  ldarg.2
    IL_04bc:  ldind.ref
    IL_04bd:  ldc.i4.0
    IL_04be:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_04c3:  conv.u2
    IL_04c4:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust_Ir
    IL_04c9:  br         IL_0ada

    IL_04ce:  ldarg.0
    IL_04cf:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm4Base
    IL_04d4:  ldarg.0
    IL_04d5:  ldarg.2
    IL_04d6:  ldind.ref
    IL_04d7:  ldc.i4.0
    IL_04d8:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_04dd:  conv.u2
    IL_04de:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust_Ir
    IL_04e3:  br         IL_0ada

    IL_04e8:  ldarg.3
    IL_04e9:  stloc.1
    IL_04ea:  ldloc.1
    IL_04eb:  switch     ( 
                          IL_0535,
                          IL_051b,
                          IL_0501)
    IL_04fc:  br         IL_0ada

    IL_0501:  ldarg.0
    IL_0502:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm16Base
    IL_0507:  ldarg.0
    IL_0508:  ldarg.2
    IL_0509:  ldind.ref
    IL_050a:  ldc.i4.0
    IL_050b:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0510:  conv.u2
    IL_0511:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust_Ir
    IL_0516:  br         IL_0ada

    IL_051b:  ldarg.0
    IL_051c:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm8Base
    IL_0521:  ldarg.0
    IL_0522:  ldarg.2
    IL_0523:  ldind.ref
    IL_0524:  ldc.i4.0
    IL_0525:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_052a:  conv.u2
    IL_052b:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust_Ir
    IL_0530:  br         IL_0ada

    IL_0535:  ldarg.0
    IL_0536:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm4Base
    IL_053b:  ldarg.0
    IL_053c:  ldarg.2
    IL_053d:  ldind.ref
    IL_053e:  ldc.i4.0
    IL_053f:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0544:  conv.u2
    IL_0545:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeedAdjust_Ir
    IL_054a:  br         IL_0ada

    IL_054f:  ldarg.2
    IL_0550:  ldind.ref
    IL_0551:  ldstr      "\"MotorSpeedPlus\""
    IL_0556:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_055b:  brfalse    IL_060b

    IL_0560:  ldarg.0
    IL_0561:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Calibration.TLXRegistryFile::m_stType
    IL_0566:  ldc.i4     0x547
    IL_056b:  bne.un     IL_0ada

    IL_0570:  ldarg.s    ffFormat
    IL_0572:  stloc.0
    IL_0573:  ldloc.0
    IL_0574:  ldc.i4.1
    IL_0575:  bne.un     IL_0ada

    IL_057a:  ldarg.3
    IL_057b:  stloc.1
    IL_057c:  ldloc.1
    IL_057d:  switch     ( 
                          IL_05e3,
                          IL_05bb,
                          IL_0593)
    IL_058e:  br         IL_0ada

    IL_0593:  ldarg.0
    IL_0594:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm16Base
    IL_0599:  ldarg.0
    IL_059a:  ldarg.2
    IL_059b:  ldind.ref
    IL_059c:  ldc.i4.0
    IL_059d:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_05a2:  conv.u2
    IL_05a3:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_05a8:  ldarg.0
    IL_05a9:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_05ae:  ldc.i4.s   28
    IL_05b0:  ldc.i4.0
    IL_05b1:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_05b6:  br         IL_0ada

    IL_05bb:  ldarg.0
    IL_05bc:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm8Base
    IL_05c1:  ldarg.0
    IL_05c2:  ldarg.2
    IL_05c3:  ldind.ref
    IL_05c4:  ldc.i4.0
    IL_05c5:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_05ca:  conv.u2
    IL_05cb:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_05d0:  ldarg.0
    IL_05d1:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_05d6:  ldc.i4.s   26
    IL_05d8:  ldc.i4.0
    IL_05d9:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_05de:  br         IL_0ada

    IL_05e3:  ldarg.0
    IL_05e4:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm4Base
    IL_05e9:  ldarg.0
    IL_05ea:  ldarg.2
    IL_05eb:  ldind.ref
    IL_05ec:  ldc.i4.0
    IL_05ed:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_05f2:  conv.u2
    IL_05f3:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_05f8:  ldarg.0
    IL_05f9:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_05fe:  ldc.i4.s   24
    IL_0600:  ldc.i4.0
    IL_0601:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0606:  br         IL_0ada

    IL_060b:  ldarg.2
    IL_060c:  ldind.ref
    IL_060d:  ldstr      "\"MotorSpeed\""
    IL_0612:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_0617:  brfalse    IL_0764

    IL_061c:  ldarg.0
    IL_061d:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Calibration.TLXRegistryFile::m_stType
    IL_0622:  ldc.i4     0x547
    IL_0627:  beq        IL_0ada

    IL_062c:  ldarg.s    ffFormat
    IL_062e:  stloc.0
    IL_062f:  ldloc.0
    IL_0630:  switch     ( 
                          IL_06d3,
                          IL_0642)
    IL_063d:  br         IL_0ada

    IL_0642:  ldarg.3
    IL_0643:  stloc.1
    IL_0644:  ldloc.1
    IL_0645:  switch     ( 
                          IL_06ab,
                          IL_0683,
                          IL_065b)
    IL_0656:  br         IL_0ada

    IL_065b:  ldarg.0
    IL_065c:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm16Base
    IL_0661:  ldarg.0
    IL_0662:  ldarg.2
    IL_0663:  ldind.ref
    IL_0664:  ldc.i4.0
    IL_0665:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_066a:  conv.u2
    IL_066b:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_0670:  ldarg.0
    IL_0671:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0676:  ldc.i4.s   28
    IL_0678:  ldc.i4.0
    IL_0679:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_067e:  br         IL_0ada

    IL_0683:  ldarg.0
    IL_0684:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm8Base
    IL_0689:  ldarg.0
    IL_068a:  ldarg.2
    IL_068b:  ldind.ref
    IL_068c:  ldc.i4.0
    IL_068d:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0692:  conv.u2
    IL_0693:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_0698:  ldarg.0
    IL_0699:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_069e:  ldc.i4.s   26
    IL_06a0:  ldc.i4.0
    IL_06a1:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_06a6:  br         IL_0ada

    IL_06ab:  ldarg.0
    IL_06ac:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm4Base
    IL_06b1:  ldarg.0
    IL_06b2:  ldarg.2
    IL_06b3:  ldind.ref
    IL_06b4:  ldc.i4.0
    IL_06b5:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_06ba:  conv.u2
    IL_06bb:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_06c0:  ldarg.0
    IL_06c1:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_06c6:  ldc.i4.s   24
    IL_06c8:  ldc.i4.0
    IL_06c9:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_06ce:  br         IL_0ada

    IL_06d3:  ldarg.3
    IL_06d4:  stloc.1
    IL_06d5:  ldloc.1
    IL_06d6:  switch     ( 
                          IL_073c,
                          IL_0714,
                          IL_06ec)
    IL_06e7:  br         IL_0ada

    IL_06ec:  ldarg.0
    IL_06ed:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm16Base
    IL_06f2:  ldarg.0
    IL_06f3:  ldarg.2
    IL_06f4:  ldind.ref
    IL_06f5:  ldc.i4.0
    IL_06f6:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_06fb:  conv.u2
    IL_06fc:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_0701:  ldarg.0
    IL_0702:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0707:  ldc.i4.s   22
    IL_0709:  ldc.i4.0
    IL_070a:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_070f:  br         IL_0ada

    IL_0714:  ldarg.0
    IL_0715:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm8Base
    IL_071a:  ldarg.0
    IL_071b:  ldarg.2
    IL_071c:  ldind.ref
    IL_071d:  ldc.i4.0
    IL_071e:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0723:  conv.u2
    IL_0724:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_0729:  ldarg.0
    IL_072a:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_072f:  ldc.i4.s   20
    IL_0731:  ldc.i4.0
    IL_0732:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0737:  br         IL_0ada

    IL_073c:  ldarg.0
    IL_073d:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm4Base
    IL_0742:  ldarg.0
    IL_0743:  ldarg.2
    IL_0744:  ldind.ref
    IL_0745:  ldc.i4.0
    IL_0746:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_074b:  conv.u2
    IL_074c:  stfld      uint16 Calibration.DPIConfig::m_usMotorSpeed
    IL_0751:  ldarg.0
    IL_0752:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0757:  ldc.i4.s   18
    IL_0759:  ldc.i4.0
    IL_075a:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_075f:  br         IL_0ada

    IL_0764:  ldarg.2
    IL_0765:  ldind.ref
    IL_0766:  ldstr      "\"StepperLens\""
    IL_076b:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_0770:  brfalse    IL_08ab

    IL_0775:  ldarg.s    ffFormat
    IL_0777:  stloc.0
    IL_0778:  ldloc.0
    IL_0779:  switch     ( 
                          IL_081c,
                          IL_078b)
    IL_0786:  br         IL_0ada

    IL_078b:  ldarg.3
    IL_078c:  stloc.1
    IL_078d:  ldloc.1
    IL_078e:  switch     ( 
                          IL_07f4,
                          IL_07cc,
                          IL_07a4)
    IL_079f:  br         IL_0ada

    IL_07a4:  ldarg.0
    IL_07a5:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm16Base
    IL_07aa:  ldarg.0
    IL_07ab:  ldarg.2
    IL_07ac:  ldind.ref
    IL_07ad:  ldc.i4.0
    IL_07ae:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_07b3:  conv.u2
    IL_07b4:  stfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_07b9:  ldarg.0
    IL_07ba:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_07bf:  ldc.i4.s   16
    IL_07c1:  ldc.i4.0
    IL_07c2:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_07c7:  br         IL_0ada

    IL_07cc:  ldarg.0
    IL_07cd:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm8Base
    IL_07d2:  ldarg.0
    IL_07d3:  ldarg.2
    IL_07d4:  ldind.ref
    IL_07d5:  ldc.i4.0
    IL_07d6:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_07db:  conv.u2
    IL_07dc:  stfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_07e1:  ldarg.0
    IL_07e2:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_07e7:  ldc.i4.s   14
    IL_07e9:  ldc.i4.0
    IL_07ea:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_07ef:  br         IL_0ada

    IL_07f4:  ldarg.0
    IL_07f5:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm4Base
    IL_07fa:  ldarg.0
    IL_07fb:  ldarg.2
    IL_07fc:  ldind.ref
    IL_07fd:  ldc.i4.0
    IL_07fe:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0803:  conv.u2
    IL_0804:  stfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_0809:  ldarg.0
    IL_080a:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_080f:  ldc.i4.s   12
    IL_0811:  ldc.i4.0
    IL_0812:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0817:  br         IL_0ada

    IL_081c:  ldarg.3
    IL_081d:  stloc.1
    IL_081e:  ldloc.1
    IL_081f:  switch     ( 
                          IL_0884,
                          IL_085d,
                          IL_0835)
    IL_0830:  br         IL_0ada

    IL_0835:  ldarg.0
    IL_0836:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm16Base
    IL_083b:  ldarg.0
    IL_083c:  ldarg.2
    IL_083d:  ldind.ref
    IL_083e:  ldc.i4.0
    IL_083f:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0844:  conv.u2
    IL_0845:  stfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_084a:  ldarg.0
    IL_084b:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0850:  ldc.i4.s   10
    IL_0852:  ldc.i4.0
    IL_0853:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0858:  br         IL_0ada

    IL_085d:  ldarg.0
    IL_085e:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm8Base
    IL_0863:  ldarg.0
    IL_0864:  ldarg.2
    IL_0865:  ldind.ref
    IL_0866:  ldc.i4.0
    IL_0867:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_086c:  conv.u2
    IL_086d:  stfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_0872:  ldarg.0
    IL_0873:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0878:  ldc.i4.8
    IL_0879:  ldc.i4.0
    IL_087a:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_087f:  br         IL_0ada

    IL_0884:  ldarg.0
    IL_0885:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm4Base
    IL_088a:  ldarg.0
    IL_088b:  ldarg.2
    IL_088c:  ldind.ref
    IL_088d:  ldc.i4.0
    IL_088e:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0893:  conv.u2
    IL_0894:  stfld      uint16 Calibration.DPIConfig::m_usLensStepper
    IL_0899:  ldarg.0
    IL_089a:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_089f:  ldc.i4.6
    IL_08a0:  ldc.i4.0
    IL_08a1:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_08a6:  br         IL_0ada

    IL_08ab:  ldarg.2
    IL_08ac:  ldind.ref
    IL_08ad:  ldstr      "\"StepperCCDAdjust\""
    IL_08b2:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_08b7:  brfalse    IL_09a0

    IL_08bc:  ldarg.s    ffFormat
    IL_08be:  stloc.0
    IL_08bf:  ldloc.0
    IL_08c0:  switch     ( 
                          IL_0939,
                          IL_08d2)
    IL_08cd:  br         IL_0ada

    IL_08d2:  ldarg.3
    IL_08d3:  stloc.1
    IL_08d4:  ldloc.1
    IL_08d5:  switch     ( 
                          IL_091f,
                          IL_0905,
                          IL_08eb)
    IL_08e6:  br         IL_0ada

    IL_08eb:  ldarg.0
    IL_08ec:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm16Base
    IL_08f1:  ldarg.0
    IL_08f2:  ldarg.2
    IL_08f3:  ldind.ref
    IL_08f4:  ldc.i4.0
    IL_08f5:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_08fa:  conv.i2
    IL_08fb:  stfld      int16 Calibration.DPIConfig::m_sCCDStepperAdjust
    IL_0900:  br         IL_0ada

    IL_0905:  ldarg.0
    IL_0906:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm8Base
    IL_090b:  ldarg.0
    IL_090c:  ldarg.2
    IL_090d:  ldind.ref
    IL_090e:  ldc.i4.0
    IL_090f:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0914:  conv.i2
    IL_0915:  stfld      int16 Calibration.DPIConfig::m_sCCDStepperAdjust
    IL_091a:  br         IL_0ada

    IL_091f:  ldarg.0
    IL_0920:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm4Base
    IL_0925:  ldarg.0
    IL_0926:  ldarg.2
    IL_0927:  ldind.ref
    IL_0928:  ldc.i4.0
    IL_0929:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_092e:  conv.i2
    IL_092f:  stfld      int16 Calibration.DPIConfig::m_sCCDStepperAdjust
    IL_0934:  br         IL_0ada

    IL_0939:  ldarg.3
    IL_093a:  stloc.1
    IL_093b:  ldloc.1
    IL_093c:  switch     ( 
                          IL_0986,
                          IL_096c,
                          IL_0952)
    IL_094d:  br         IL_0ada

    IL_0952:  ldarg.0
    IL_0953:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm16Base
    IL_0958:  ldarg.0
    IL_0959:  ldarg.2
    IL_095a:  ldind.ref
    IL_095b:  ldc.i4.0
    IL_095c:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0961:  conv.i2
    IL_0962:  stfld      int16 Calibration.DPIConfig::m_sCCDStepperAdjust
    IL_0967:  br         IL_0ada

    IL_096c:  ldarg.0
    IL_096d:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm8Base
    IL_0972:  ldarg.0
    IL_0973:  ldarg.2
    IL_0974:  ldind.ref
    IL_0975:  ldc.i4.0
    IL_0976:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_097b:  conv.i2
    IL_097c:  stfld      int16 Calibration.DPIConfig::m_sCCDStepperAdjust
    IL_0981:  br         IL_0ada

    IL_0986:  ldarg.0
    IL_0987:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm4Base
    IL_098c:  ldarg.0
    IL_098d:  ldarg.2
    IL_098e:  ldind.ref
    IL_098f:  ldc.i4.0
    IL_0990:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0995:  conv.i2
    IL_0996:  stfld      int16 Calibration.DPIConfig::m_sCCDStepperAdjust
    IL_099b:  br         IL_0ada

    IL_09a0:  ldarg.2
    IL_09a1:  ldind.ref
    IL_09a2:  ldstr      "\"StepperCCD\""
    IL_09a7:  callvirt   instance bool [mscorlib]System.String::StartsWith(string)
    IL_09ac:  brfalse    IL_0ada

    IL_09b1:  ldarg.s    ffFormat
    IL_09b3:  stloc.0
    IL_09b4:  ldloc.0
    IL_09b5:  switch     ( 
                          IL_0a58,
                          IL_09c7)
    IL_09c2:  br         IL_0ada

    IL_09c7:  ldarg.3
    IL_09c8:  stloc.1
    IL_09c9:  ldloc.1
    IL_09ca:  switch     ( 
                          IL_0a30,
                          IL_0a08,
                          IL_09e0)
    IL_09db:  br         IL_0ada

    IL_09e0:  ldarg.0
    IL_09e1:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm16Base
    IL_09e6:  ldarg.0
    IL_09e7:  ldarg.2
    IL_09e8:  ldind.ref
    IL_09e9:  ldc.i4.0
    IL_09ea:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_09ef:  conv.u2
    IL_09f0:  stfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_09f5:  ldarg.0
    IL_09f6:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_09fb:  ldc.i4.s   17
    IL_09fd:  ldc.i4.0
    IL_09fe:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0a03:  br         IL_0ada

    IL_0a08:  ldarg.0
    IL_0a09:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm8Base
    IL_0a0e:  ldarg.0
    IL_0a0f:  ldarg.2
    IL_0a10:  ldind.ref
    IL_0a11:  ldc.i4.0
    IL_0a12:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0a17:  conv.u2
    IL_0a18:  stfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0a1d:  ldarg.0
    IL_0a1e:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0a23:  ldc.i4.s   15
    IL_0a25:  ldc.i4.0
    IL_0a26:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0a2b:  br         IL_0ada

    IL_0a30:  ldarg.0
    IL_0a31:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi35mm4Base
    IL_0a36:  ldarg.0
    IL_0a37:  ldarg.2
    IL_0a38:  ldind.ref
    IL_0a39:  ldc.i4.0
    IL_0a3a:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0a3f:  conv.u2
    IL_0a40:  stfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0a45:  ldarg.0
    IL_0a46:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0a4b:  ldc.i4.s   13
    IL_0a4d:  ldc.i4.0
    IL_0a4e:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0a53:  br         IL_0ada

    IL_0a58:  ldarg.3
    IL_0a59:  stloc.1
    IL_0a5a:  ldloc.1
    IL_0a5b:  switch     ( 
                          IL_0ab8,
                          IL_0a93,
                          IL_0a6e)
    IL_0a6c:  br.s       IL_0ada

    IL_0a6e:  ldarg.0
    IL_0a6f:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm16Base
    IL_0a74:  ldarg.0
    IL_0a75:  ldarg.2
    IL_0a76:  ldind.ref
    IL_0a77:  ldc.i4.0
    IL_0a78:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0a7d:  conv.u2
    IL_0a7e:  stfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0a83:  ldarg.0
    IL_0a84:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0a89:  ldc.i4.s   11
    IL_0a8b:  ldc.i4.0
    IL_0a8c:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0a91:  br.s       IL_0ada

    IL_0a93:  ldarg.0
    IL_0a94:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm8Base
    IL_0a99:  ldarg.0
    IL_0a9a:  ldarg.2
    IL_0a9b:  ldind.ref
    IL_0a9c:  ldc.i4.0
    IL_0a9d:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0aa2:  conv.u2
    IL_0aa3:  stfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0aa8:  ldarg.0
    IL_0aa9:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0aae:  ldc.i4.s   9
    IL_0ab0:  ldc.i4.0
    IL_0ab1:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0ab6:  br.s       IL_0ada

    IL_0ab8:  ldarg.0
    IL_0ab9:  ldflda     valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::m_dpi24mm4Base
    IL_0abe:  ldarg.0
    IL_0abf:  ldarg.2
    IL_0ac0:  ldind.ref
    IL_0ac1:  ldc.i4.0
    IL_0ac2:  call       instance int32 Calibration.TLXRegistryFile::ReadDWord(string,
                                                                               int32)
    IL_0ac7:  conv.u2
    IL_0ac8:  stfld      uint16 Calibration.DPIConfig::m_usCCDStepper
    IL_0acd:  ldarg.0
    IL_0ace:  ldfld      [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::m_ibEEPromNotFound
    IL_0ad3:  ldc.i4.7
    IL_0ad4:  ldc.i4.0
    IL_0ad5:  callvirt   instance void [Pakon]Pakon.IntBits::set_Item(int32,
                                                                      bool)
    IL_0ada:  ldarg.2
    IL_0adb:  ldarg.1
    IL_0adc:  callvirt   instance string [mscorlib]System.IO.TextReader::ReadLine()
    IL_0ae1:  stind.ref
    IL_0ae2:  ldarg.2
    IL_0ae3:  ldind.ref
    IL_0ae4:  ldstr      "]"
    IL_0ae9:  callvirt   instance bool [mscorlib]System.String::EndsWith(string)
    IL_0aee:  brtrue.s   IL_0af7

    IL_0af0:  ldarg.2
    IL_0af1:  ldind.ref
    IL_0af2:  brtrue     IL_000d

    IL_0af7:  ret
  } // end of method TLXRegistryFile::LoadDpiConfig

  .property instance string Name()
  {
    .get instance string Calibration.TLXRegistryFile::get_Name()
  } // end of property TLXRegistryFile::Name
  .property instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000
          ScannerType()
  {
    .get instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Calibration.TLXRegistryFile::get_ScannerType()
  } // end of property TLXRegistryFile::ScannerType
  .property instance int32 ScannerSerialNumber()
  {
    .get instance int32 Calibration.TLXRegistryFile::get_ScannerSerialNumber()
  } // end of property TLXRegistryFile::ScannerSerialNumber
  .property instance [Pakon]Pakon.ScannerHW135
          ScannerHW135()
  {
    .get instance [Pakon]Pakon.ScannerHW135 Calibration.TLXRegistryFile::get_ScannerHW135()
  } // end of property TLXRegistryFile::ScannerHW135
  .property instance [Pakon]Pakon.ScannerHW235
          ScannerHW235()
  {
    .get instance [Pakon]Pakon.ScannerHW235 Calibration.TLXRegistryFile::get_ScannerHW235()
  } // end of property TLXRegistryFile::ScannerHW235
  .property instance [Pakon]Pakon.ScannerHW335
          ScannerHW335()
  {
    .get instance [Pakon]Pakon.ScannerHW335 Calibration.TLXRegistryFile::get_ScannerHW335()
  } // end of property TLXRegistryFile::ScannerHW335
  .property instance valuetype Calibration.DPIConfig
          Base16_35mm()
  {
    .get instance valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::get_Base16_35mm()
  } // end of property TLXRegistryFile::Base16_35mm
  .property instance valuetype Calibration.DPIConfig
          Base8_35mm()
  {
    .get instance valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::get_Base8_35mm()
  } // end of property TLXRegistryFile::Base8_35mm
  .property instance valuetype Calibration.DPIConfig
          Base4_35mm()
  {
    .get instance valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::get_Base4_35mm()
  } // end of property TLXRegistryFile::Base4_35mm
  .property instance valuetype Calibration.DPIConfig
          Base16_24mm()
  {
    .get instance valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::get_Base16_24mm()
  } // end of property TLXRegistryFile::Base16_24mm
  .property instance valuetype Calibration.DPIConfig
          Base8_24mm()
  {
    .get instance valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::get_Base8_24mm()
  } // end of property TLXRegistryFile::Base8_24mm
  .property instance valuetype Calibration.DPIConfig
          Base4_24mm()
  {
    .get instance valuetype Calibration.DPIConfig Calibration.TLXRegistryFile::get_Base4_24mm()
  } // end of property TLXRegistryFile::Base4_24mm
  .property instance valuetype Calibration.ColorMatrixConfig
          MatrixNeg()
  {
    .get instance valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::get_MatrixNeg()
  } // end of property TLXRegistryFile::MatrixNeg
  .property instance valuetype Calibration.ColorMatrixConfig
          MatrixPos()
  {
    .get instance valuetype Calibration.ColorMatrixConfig Calibration.TLXRegistryFile::get_MatrixPos()
  } // end of property TLXRegistryFile::MatrixPos
  .property instance [Pakon]Pakon.IntBits
          EEProm()
  {
    .get instance [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::get_EEProm()
  } // end of property TLXRegistryFile::EEProm
  .property instance [Pakon]Pakon.IntBits
          ColorNeg()
  {
    .get instance [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::get_ColorNeg()
  } // end of property TLXRegistryFile::ColorNeg
  .property instance [Pakon]Pakon.IntBits
          ColorPos()
  {
    .get instance [Pakon]Pakon.IntBits Calibration.TLXRegistryFile::get_ColorPos()
  } // end of property TLXRegistryFile::ColorPos
} // end of class Calibration.TLXRegistryFile

.class private auto ansi '<PrivateImplementationDetails>'
       extends [mscorlib]System.Object
{
  .class explicit ansi sealed nested private '$$struct0x6000020-1'
         extends [mscorlib]System.ValueType
  {
    .pack 1
    .size 10
  } // end of class '$$struct0x6000020-1'

  .class explicit ansi sealed nested private '$$struct0x6000022-1'
         extends [mscorlib]System.ValueType
  {
    .pack 1
    .size 10
  } // end of class '$$struct0x6000022-1'

  .field static assembly valuetype '<PrivateImplementationDetails>'/'$$struct0x6000020-1' '$$method0x6000020-1' at I_00002E30
  .field static assembly valuetype '<PrivateImplementationDetails>'/'$$struct0x6000022-1' '$$method0x6000022-1' at I_00002ED0
} // end of class '<PrivateImplementationDetails>'


// =============================================================

.data cil I_00002E30 = bytearray (
                 2C 00 2F 00 7C 00 20 00 0A 00)                   // ,./.|. ...
.data cil I_00002E3A = int8[6]
.data cil I_00002ED0 = bytearray (
                 2C 00 2F 00 7C 00 20 00 0A 00)                   // ,./.|. ...
// *********** DISASSEMBLY COMPLETE ***********************
