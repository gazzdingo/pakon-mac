
// Metadata version: v1.1.4322
.assembly extern mscorlib
{
  .publickeytoken = (B7 7A 5C 56 19 34 E0 89 )                         // .z\V.4..
  .ver 1:0:5000:0
}
.assembly extern Interop.TLXLib
{
  .ver 1:1:0:0
}
.assembly extern System.Windows.Forms
{
  .publickeytoken = (B7 7A 5C 56 19 34 E0 89 )                         // .z\V.4..
  .ver 1:0:5000:0
}
.assembly Pakon
{
  .custom instance void [mscorlib]System.Reflection.AssemblyTrademarkAttribute::.ctor(string) = ( 01 00 00 00 00 ) 
  .custom instance void [mscorlib]System.Reflection.AssemblyCopyrightAttribute::.ctor(string) = ( 01 00 12 43 6F 70 79 72 69 67 68 74 20 28 43 29   // ...Copyright (C)
                                                                                                  20 32 30 30 35 00 00 )                            //  2005..
  .custom instance void [mscorlib]System.Reflection.AssemblyTitleAttribute::.ctor(string) = ( 01 00 15 43 6F 6D 6D 6F 6E 20 53 63 61 6E 6E 65   // ...Common Scanne
                                                                                              72 20 41 63 63 65 73 73 00 00 )                   // r Access..
  .custom instance void [mscorlib]System.Reflection.AssemblyKeyFileAttribute::.ctor(string) = ( 01 00 00 00 00 ) 
  .custom instance void [mscorlib]System.Reflection.AssemblyDelaySignAttribute::.ctor(bool) = ( 01 00 00 00 00 ) 
  .custom instance void [mscorlib]System.Reflection.AssemblyProductAttribute::.ctor(string) = ( 01 00 09 50 61 6B 6F 6E 20 44 4C 4C 00 00 )       // ...Pakon DLL..
  .custom instance void [mscorlib]System.Reflection.AssemblyKeyNameAttribute::.ctor(string) = ( 01 00 00 00 00 ) 
  .custom instance void [mscorlib]System.Reflection.AssemblyCompanyAttribute::.ctor(string) = ( 01 00 05 50 61 6B 6F 6E 00 00 )                   // ...Pakon..
  .custom instance void [mscorlib]System.Reflection.AssemblyConfigurationAttribute::.ctor(string) = ( 01 00 00 00 00 ) 
  .custom instance void [mscorlib]System.Reflection.AssemblyDescriptionAttribute::.ctor(string) = ( 01 00 15 43 6F 6D 6D 6F 6E 20 53 63 61 6E 6E 65   // ...Common Scanne
                                                                                                    72 20 41 63 63 65 73 73 00 00 )                   // r Access..
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
.module Pakon.dll
// MVID: {AA92D321-DA23-4216-8AD2-18AE36F17F20}
.custom instance void [mscorlib]System.Security.UnverifiableCodeAttribute::.ctor() = ( 01 00 00 00 ) 
.imagebase 0x11000000
.file alignment 0x00001000
.stackreserve 0x00100000
.subsystem 0x0003       // WINDOWS_CUI
.corflags 0x00000001    //  ILONLY


// =============== CLASS MEMBERS DECLARATION ===================

.class public auto ansi sealed Pakon.ScannerInitializeWarnings
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Pakon.ScannerInitializeWarnings Unknown = int32(0xFFFFFFFF)
  .field public static literal valuetype Pakon.ScannerInitializeWarnings None = int32(0x00000000)
  .field public static literal valuetype Pakon.ScannerInitializeWarnings Blank = int32(0x00000001)
  .field public static literal valuetype Pakon.ScannerInitializeWarnings ChecksumBad = int32(0x00000002)
} // end of class Pakon.ScannerInitializeWarnings

.class public auto ansi sealed Pakon.ScannerHW135
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Pakon.ScannerHW135 Unknown = int32(0x00000000)
  .field public static literal valuetype Pakon.ScannerHW135 Alpha = int32(0x0000000A)
  .field public static literal valuetype Pakon.ScannerHW135 Beta = int32(0x00000064)
  .field public static literal valuetype Pakon.ScannerHW135 Charlie = int32(0x000000C8)
  .field public static literal valuetype Pakon.ScannerHW135 Preproduction = int32(0x0000012C)
  .field public static literal valuetype Pakon.ScannerHW135 Production = int32(0x00000190)
} // end of class Pakon.ScannerHW135

.class public auto ansi sealed Pakon.ScannerHW235
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Pakon.ScannerHW235 Unknown = int32(0x00000000)
  .field public static literal valuetype Pakon.ScannerHW235 Rev_A = int32(0x00000003)
  .field public static literal valuetype Pakon.ScannerHW235 Bridge = int32(0x00000032)
  .field public static literal valuetype Pakon.ScannerHW235 Rev_D = int32(0x000003E8)
  .field public static literal valuetype Pakon.ScannerHW235 RFTSplice = int32(0x0000044C)
} // end of class Pakon.ScannerHW235

.class public auto ansi sealed Pakon.ScannerHW335
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Pakon.ScannerHW335 Unknown = int32(0x00000000)
  .field public static literal valuetype Pakon.ScannerHW335 Alpha = int32(0x0000000A)
  .field public static literal valuetype Pakon.ScannerHW335 Beta = int32(0x00000064)
  .field public static literal valuetype Pakon.ScannerHW335 Charlie = int32(0x000000C8)
  .field public static literal valuetype Pakon.ScannerHW335 Preproduction = int32(0x0000012C)
  .field public static literal valuetype Pakon.ScannerHW335 Production = int32(0x00000190)
  .field public static literal valuetype Pakon.ScannerHW335 RFTSplice = int32(0x000007D0)
} // end of class Pakon.ScannerHW335

.class public auto ansi sealed Pakon.ScannerCapabilities
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Pakon.ScannerCapabilities LampManualControl = int32(0x00000000)
  .field public static literal valuetype Pakon.ScannerCapabilities SAV_UseColorCorrectionLUT = int32(0x00000001)
  .field public static literal valuetype Pakon.ScannerCapabilities FocusCorrection = int32(0x00000002)
  .field public static literal valuetype Pakon.ScannerCapabilities MultipleFilmTrack = int32(0x00000003)
  .field public static literal valuetype Pakon.ScannerCapabilities PressureRollers = int32(0x00000004)
  .field public static literal valuetype Pakon.ScannerCapabilities AIDToolkit = int32(0x00000005)
  .field public static literal valuetype Pakon.ScannerCapabilities FixedFocalLength = int32(0x00000006)
  .field public static literal valuetype Pakon.ScannerCapabilities FilterWheel = int32(0x00000007)
  .field public static literal valuetype Pakon.ScannerCapabilities Unused09 = int32(0x00000008)
  .field public static literal valuetype Pakon.ScannerCapabilities Unused10 = int32(0x00000009)
  .field public static literal valuetype Pakon.ScannerCapabilities Unused11 = int32(0x0000000A)
  .field public static literal valuetype Pakon.ScannerCapabilities Unused12 = int32(0x0000000B)
  .field public static literal valuetype Pakon.ScannerCapabilities Unused13 = int32(0x0000000C)
  .field public static literal valuetype Pakon.ScannerCapabilities Unused14 = int32(0x0000000D)
  .field public static literal valuetype Pakon.ScannerCapabilities Unused15 = int32(0x0000000E)
  .field public static literal valuetype Pakon.ScannerCapabilities Unused16 = int32(0x0000000F)
  .field public static literal valuetype Pakon.ScannerCapabilities Unused17 = int32(0x00000010)
  .field public static literal valuetype Pakon.ScannerCapabilities Unused18 = int32(0x00000011)
  .field public static literal valuetype Pakon.ScannerCapabilities Unused19 = int32(0x00000012)
  .field public static literal valuetype Pakon.ScannerCapabilities Unused20 = int32(0x00000013)
  .field public static literal valuetype Pakon.ScannerCapabilities Unused21 = int32(0x00000014)
  .field public static literal valuetype Pakon.ScannerCapabilities Unused22 = int32(0x00000015)
  .field public static literal valuetype Pakon.ScannerCapabilities FilmC41 = int32(0x00000016)
  .field public static literal valuetype Pakon.ScannerCapabilities FilmPositive = int32(0x00000017)
  .field public static literal valuetype Pakon.ScannerCapabilities Film24MM = int32(0x00000018)
  .field public static literal valuetype Pakon.ScannerCapabilities Film24MMCartridge = int32(0x00000019)
  .field public static literal valuetype Pakon.ScannerCapabilities Film24MM16Base = int32(0x0000001A)
  .field public static literal valuetype Pakon.ScannerCapabilities Film24MM8Base = int32(0x0000001B)
  .field public static literal valuetype Pakon.ScannerCapabilities Film24MM4Base = int32(0x0000001C)
  .field public static literal valuetype Pakon.ScannerCapabilities Film35MM16Base = int32(0x0000001D)
  .field public static literal valuetype Pakon.ScannerCapabilities Film35MM8Base = int32(0x0000001E)
  .field public static literal valuetype Pakon.ScannerCapabilities Film35MM4Base = int32(0x0000001F)
} // end of class Pakon.ScannerCapabilities

.class public auto ansi sealed Pakon.PictureInfo
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Pakon.PictureInfo FrameNumber = int32(0x00000000)
  .field public static literal valuetype Pakon.PictureInfo FileName = int32(0x00000001)
  .field public static literal valuetype Pakon.PictureInfo Directory = int32(0x00000002)
  .field public static literal valuetype Pakon.PictureInfo Rotation = int32(0x00000003)
  .field public static literal valuetype Pakon.PictureInfo SelectedHidden = int32(0x00000004)
} // end of class Pakon.PictureInfo

.class public sequential ansi sealed beforefieldinit Pakon.SiPlanarFileHeader
       extends [mscorlib]System.ValueType
{
  .field public uint32 m_uiSize
  .field public uint32 m_uiWidth
  .field public uint32 m_uiHeight
  .field public uint32 m_uiBitCount
} // end of class Pakon.SiPlanarFileHeader

.class public auto ansi beforefieldinit Pakon.IntBits
       extends [mscorlib]System.Object
{
  .custom instance void [mscorlib]System.Reflection.DefaultMemberAttribute::.ctor(string) = ( 01 00 04 49 74 65 6D 00 00 )                      // ...Item..
  .field private int32 m_nBits
  .method public hidebysig specialname instance void 
          set_Bits(int32 'value') cil managed
  {
    // Code size       8 (0x8)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      int32 Pakon.IntBits::m_nBits
    IL_0007:  ret
  } // end of method IntBits::set_Bits

  .method public hidebysig instance void 
          Empty() cil managed
  {
    // Code size       8 (0x8)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.0
    IL_0002:  stfld      int32 Pakon.IntBits::m_nBits
    IL_0007:  ret
  } // end of method IntBits::Empty

  .method public hidebysig instance bool 
          IsEmpty() cil managed
  {
    // Code size       10 (0xa)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32 Pakon.IntBits::m_nBits
    IL_0006:  ldc.i4.0
    IL_0007:  ceq
    IL_0009:  ret
  } // end of method IntBits::IsEmpty

  .method public hidebysig instance void 
          Equals(class Pakon.IntBits ib) cil managed
  {
    // Code size       13 (0xd)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  ldfld      int32 Pakon.IntBits::m_nBits
    IL_0007:  stfld      int32 Pakon.IntBits::m_nBits
    IL_000c:  ret
  } // end of method IntBits::Equals

  .method public hidebysig instance class Pakon.IntBits 
          Clone() cil managed
  {
    // Code size       20 (0x14)
    .maxstack  2
    .locals (class Pakon.IntBits V_0)
    IL_0000:  newobj     instance void Pakon.IntBits::.ctor()
    IL_0005:  stloc.0
    IL_0006:  ldloc.0
    IL_0007:  ldarg.0
    IL_0008:  ldfld      int32 Pakon.IntBits::m_nBits
    IL_000d:  stfld      int32 Pakon.IntBits::m_nBits
    IL_0012:  ldloc.0
    IL_0013:  ret
  } // end of method IntBits::Clone

  .method public hidebysig specialname instance bool 
          get_Item(int32 nIndex) cil managed
  {
    // Code size       20 (0x14)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32 Pakon.IntBits::m_nBits
    IL_0006:  ldc.i4.1
    IL_0007:  ldarg.1
    IL_0008:  ldc.i4.s   31
    IL_000a:  and
    IL_000b:  shl
    IL_000c:  and
    IL_000d:  ldc.i4.0
    IL_000e:  ceq
    IL_0010:  ldc.i4.0
    IL_0011:  ceq
    IL_0013:  ret
  } // end of method IntBits::get_Item

  .method public hidebysig specialname instance void 
          set_Item(int32 nIndex,
                   bool 'value') cil managed
  {
    // Code size       44 (0x2c)
    .maxstack  8
    IL_0000:  ldarg.2
    IL_0001:  brfalse.s  IL_0017

    IL_0003:  ldarg.0
    IL_0004:  dup
    IL_0005:  ldfld      int32 Pakon.IntBits::m_nBits
    IL_000a:  ldc.i4.1
    IL_000b:  ldarg.1
    IL_000c:  ldc.i4.s   31
    IL_000e:  and
    IL_000f:  shl
    IL_0010:  or
    IL_0011:  stfld      int32 Pakon.IntBits::m_nBits
    IL_0016:  ret

    IL_0017:  ldarg.0
    IL_0018:  dup
    IL_0019:  ldfld      int32 Pakon.IntBits::m_nBits
    IL_001e:  ldc.i4.1
    IL_001f:  ldarg.1
    IL_0020:  ldc.i4.s   31
    IL_0022:  and
    IL_0023:  shl
    IL_0024:  not
    IL_0025:  and
    IL_0026:  stfld      int32 Pakon.IntBits::m_nBits
    IL_002b:  ret
  } // end of method IntBits::set_Item

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       14 (0xe)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.0
    IL_0002:  stfld      int32 Pakon.IntBits::m_nBits
    IL_0007:  ldarg.0
    IL_0008:  call       instance void [mscorlib]System.Object::.ctor()
    IL_000d:  ret
  } // end of method IntBits::.ctor

  .property instance int32 Bits()
  {
    .set instance void Pakon.IntBits::set_Bits(int32)
  } // end of property IntBits::Bits
  .property instance bool Item(int32)
  {
    .set instance void Pakon.IntBits::set_Item(int32,
                                               bool)
    .get instance bool Pakon.IntBits::get_Item(int32)
  } // end of property IntBits::Item
} // end of class Pakon.IntBits

.class public auto ansi beforefieldinit Pakon.Global
       extends [mscorlib]System.Object
{
  .field public static [Interop.TLXLib]TLXLib.SAVE_CONTROL_000 MEMORY_PLANAR_16
  .method public hidebysig static void  ErrorGeneral([System.Windows.Forms]System.Windows.Forms.Form formOwner,
                                                     [mscorlib]System.Exception caught,
                                                     string strCaption) cil managed
  {
    // Code size       14 (0xe)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  callvirt   instance string [mscorlib]System.Exception::get_Message()
    IL_0007:  ldarg.2
    IL_0008:  call       void Pakon.TLXErrorMessageBox::Show([System.Windows.Forms]System.Windows.Forms.Form,
                                                             string,
                                                             string)
    IL_000d:  ret
  } // end of method Global::ErrorGeneral

  .method public hidebysig static void  MessageHardware([System.Windows.Forms]System.Windows.Forms.Form formOwner,
                                                        class Pakon.Scanner csScanner,
                                                        [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                                                        int32 lStatus,
                                                        string strCaption) cil managed
  {
    // Code size       610 (0x262)
    .maxstack  3
    .locals (string V_0)
    IL_0000:  ldarg.3
    IL_0001:  brfalse    IL_0261

    IL_0006:  ldstr      ""
    IL_000b:  stloc.0
    IL_000c:  ldarg.3
    IL_000d:  ldc.i4.1
    IL_000e:  and
    IL_000f:  ldc.i4.1
    IL_0010:  bne.un.s   IL_001e

    IL_0012:  ldloc.0
    IL_0013:  ldstr      "   -  Host Board Fault\n"
    IL_0018:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_001d:  stloc.0
    IL_001e:  ldarg.3
    IL_001f:  ldc.i4.2
    IL_0020:  and
    IL_0021:  ldc.i4.2
    IL_0022:  bne.un.s   IL_0030

    IL_0024:  ldloc.0
    IL_0025:  ldstr      "   -  DX Board Fault\n"
    IL_002a:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_002f:  stloc.0
    IL_0030:  ldarg.3
    IL_0031:  ldc.i4.4
    IL_0032:  and
    IL_0033:  ldc.i4.4
    IL_0034:  bne.un.s   IL_0042

    IL_0036:  ldloc.0
    IL_0037:  ldstr      "   -  Lamp Board Fault\n"
    IL_003c:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0041:  stloc.0
    IL_0042:  ldarg.3
    IL_0043:  ldc.i4.8
    IL_0044:  and
    IL_0045:  ldc.i4.8
    IL_0046:  bne.un.s   IL_0054

    IL_0048:  ldloc.0
    IL_0049:  ldstr      "   -  CCD Board Fault\n"
    IL_004e:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0053:  stloc.0
    IL_0054:  ldarg.3
    IL_0055:  ldc.i4.s   16
    IL_0057:  and
    IL_0058:  ldc.i4.s   16
    IL_005a:  bne.un.s   IL_0068

    IL_005c:  ldloc.0
    IL_005d:  ldstr      "   -  Motor Board Fault\n"
    IL_0062:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0067:  stloc.0
    IL_0068:  ldarg.3
    IL_0069:  ldc.i4.s   64
    IL_006b:  and
    IL_006c:  ldc.i4.s   64
    IL_006e:  bne.un.s   IL_007c

    IL_0070:  ldloc.0
    IL_0071:  ldstr      "   -  Hardware Error\n"
    IL_0076:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_007b:  stloc.0
    IL_007c:  ldarg.3
    IL_007d:  ldc.i4     0x100
    IL_0082:  and
    IL_0083:  ldc.i4     0x100
    IL_0088:  bne.un.s   IL_0096

    IL_008a:  ldloc.0
    IL_008b:  ldstr      "   -  Lamp Warning\n"
    IL_0090:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0095:  stloc.0
    IL_0096:  ldarg.3
    IL_0097:  ldc.i4     0x200
    IL_009c:  and
    IL_009d:  ldc.i4     0x200
    IL_00a2:  bne.un.s   IL_00b0

    IL_00a4:  ldloc.0
    IL_00a5:  ldstr      "   -  Lamp Error\n"
    IL_00aa:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_00af:  stloc.0
    IL_00b0:  ldarg.3
    IL_00b1:  ldc.i4     0x400
    IL_00b6:  and
    IL_00b7:  ldc.i4     0x400
    IL_00bc:  bne.un.s   IL_00ca

    IL_00be:  ldloc.0
    IL_00bf:  ldstr      "   -  Temperature Warning\n"
    IL_00c4:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_00c9:  stloc.0
    IL_00ca:  ldarg.3
    IL_00cb:  ldc.i4     0x800
    IL_00d0:  and
    IL_00d1:  ldc.i4     0x800
    IL_00d6:  bne.un.s   IL_00e4

    IL_00d8:  ldloc.0
    IL_00d9:  ldstr      "   -  Temperature Error\n"
    IL_00de:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_00e3:  stloc.0
    IL_00e4:  ldarg.3
    IL_00e5:  ldc.i4     0x1000
    IL_00ea:  and
    IL_00eb:  ldc.i4     0x1000
    IL_00f0:  bne.un.s   IL_00fe

    IL_00f2:  ldloc.0
    IL_00f3:  ldstr      "   -  Lamp Burn Out Error\n"
    IL_00f8:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_00fd:  stloc.0
    IL_00fe:  ldarg.3
    IL_00ff:  ldc.i4     0x2000
    IL_0104:  and
    IL_0105:  ldc.i4     0x2000
    IL_010a:  bne.un.s   IL_0118

    IL_010c:  ldloc.0
    IL_010d:  ldstr      "   -  Lamp Fan Warning\n"
    IL_0112:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0117:  stloc.0
    IL_0118:  ldarg.3
    IL_0119:  ldc.i4     0x4000
    IL_011e:  and
    IL_011f:  ldc.i4     0x4000
    IL_0124:  bne.un.s   IL_0132

    IL_0126:  ldloc.0
    IL_0127:  ldstr      "   -  Lamp Fan Error\n"
    IL_012c:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0131:  stloc.0
    IL_0132:  ldarg.3
    IL_0133:  ldc.i4     0x40000
    IL_0138:  and
    IL_0139:  ldc.i4     0x40000
    IL_013e:  bne.un.s   IL_014c

    IL_0140:  ldloc.0
    IL_0141:  ldstr      "   -  Power Warning\n"
    IL_0146:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_014b:  stloc.0
    IL_014c:  ldarg.3
    IL_014d:  ldc.i4     0x80000
    IL_0152:  and
    IL_0153:  ldc.i4     0x80000
    IL_0158:  bne.un.s   IL_0166

    IL_015a:  ldloc.0
    IL_015b:  ldstr      "   -  Power Error\n"
    IL_0160:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0165:  stloc.0
    IL_0166:  ldarg.3
    IL_0167:  ldc.i4     0x200000
    IL_016c:  and
    IL_016d:  ldc.i4     0x200000
    IL_0172:  bne.un.s   IL_0180

    IL_0174:  ldloc.0
    IL_0175:  ldstr      "   -  Stepper CCD Error\n"
    IL_017a:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_017f:  stloc.0
    IL_0180:  ldarg.3
    IL_0181:  ldc.i4     0x400000
    IL_0186:  and
    IL_0187:  ldc.i4     0x400000
    IL_018c:  bne.un.s   IL_019a

    IL_018e:  ldloc.0
    IL_018f:  ldstr      "   -  Stepper Lens Error\n"
    IL_0194:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0199:  stloc.0
    IL_019a:  ldarg.3
    IL_019b:  ldc.i4     0x800000
    IL_01a0:  and
    IL_01a1:  ldc.i4     0x800000
    IL_01a6:  bne.un.s   IL_01b4

    IL_01a8:  ldloc.0
    IL_01a9:  ldstr      "   -  Filter Wheel Error\n"
    IL_01ae:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_01b3:  stloc.0
    IL_01b4:  ldarg.3
    IL_01b5:  ldc.i4     0x1000000
    IL_01ba:  and
    IL_01bb:  ldc.i4     0x1000000
    IL_01c0:  bne.un.s   IL_01ce

    IL_01c2:  ldloc.0
    IL_01c3:  ldstr      "   -  Film Guide Error\n"
    IL_01c8:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_01cd:  stloc.0
    IL_01ce:  ldarg.3
    IL_01cf:  ldc.i4     0x2000000
    IL_01d4:  and
    IL_01d5:  ldc.i4     0x2000000
    IL_01da:  bne.un.s   IL_01e8

    IL_01dc:  ldloc.0
    IL_01dd:  ldstr      "   -  Film In Guides Error\n"
    IL_01e2:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_01e7:  stloc.0
    IL_01e8:  ldarg.3
    IL_01e9:  ldc.i4     0x4000000
    IL_01ee:  and
    IL_01ef:  ldc.i4     0x4000000
    IL_01f4:  bne.un.s   IL_0202

    IL_01f6:  ldloc.0
    IL_01f7:  ldstr      "   -  Blower Warning\n"
    IL_01fc:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0201:  stloc.0
    IL_0202:  ldarg.3
    IL_0203:  ldc.i4     0x8000000
    IL_0208:  and
    IL_0209:  ldc.i4     0x8000000
    IL_020e:  bne.un.s   IL_021c

    IL_0210:  ldloc.0
    IL_0211:  ldstr      "   -  Cleaning Required\n"
    IL_0216:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_021b:  stloc.0
    IL_021c:  ldarg.3
    IL_021d:  ldc.i4     0x10000000
    IL_0222:  and
    IL_0223:  ldc.i4     0x10000000
    IL_0228:  bne.un.s   IL_0236

    IL_022a:  ldloc.0
    IL_022b:  ldstr      "   -  Film Emulsion Down\n"
    IL_0230:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_0235:  stloc.0
    IL_0236:  ldarg.3
    IL_0237:  ldc.i4     0x20000000
    IL_023c:  and
    IL_023d:  ldc.i4     0x20000000
    IL_0242:  bne.un.s   IL_0250

    IL_0244:  ldloc.0
    IL_0245:  ldstr      "   -  Film Tail First\n"
    IL_024a:  call       string [mscorlib]System.String::Concat(string,
                                                                string)
    IL_024f:  stloc.0
    IL_0250:  ldloc.0
    IL_0251:  callvirt   instance int32 [mscorlib]System.String::get_Length()
    IL_0256:  brfalse.s  IL_0261

    IL_0258:  ldarg.0
    IL_0259:  ldloc.0
    IL_025a:  ldarg.s    strCaption
    IL_025c:  call       void Pakon.TLXErrorMessageBox::Show([System.Windows.Forms]System.Windows.Forms.Form,
                                                             string,
                                                             string)
    IL_0261:  ret
  } // end of method Global::MessageHardware

  .method public hidebysig static void  ErrorCOM([System.Windows.Forms]System.Windows.Forms.Form formOwner,
                                                 class Pakon.Scanner csScanner,
                                                 [mscorlib]System.Runtime.InteropServices.COMException caught,
                                                 string strCaption) cil managed
  {
    // Code size       193 (0xc1)
    .maxstack  5
    .locals ([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000[] V_0,
             int32 V_1,
             string V_2,
             string V_3,
             [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 V_4,
             [Interop.TLXLib]TLXLib.ERROR_CODES_000 V_5,
             [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000[] V_6,
             int32 V_7)
    IL_0000:  ldc.i4.4
    IL_0001:  newarr     [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000
    IL_0006:  stloc.s    V_6
    IL_0008:  ldloc.s    V_6
    IL_000a:  ldc.i4.0
    IL_000b:  ldc.i4.s   41
    IL_000d:  stelem.i4
    IL_000e:  ldloc.s    V_6
    IL_0010:  ldc.i4.1
    IL_0011:  ldc.i4.1
    IL_0012:  stelem.i4
    IL_0013:  ldloc.s    V_6
    IL_0015:  ldc.i4.2
    IL_0016:  ldc.i4.s   35
    IL_0018:  stelem.i4
    IL_0019:  ldloc.s    V_6
    IL_001b:  ldc.i4.3
    IL_001c:  ldc.i4.s   39
    IL_001e:  stelem.i4
    IL_001f:  ldloc.s    V_6
    IL_0021:  stloc.0
    IL_0022:  ldc.i4.0
    IL_0023:  stloc.1
    IL_0024:  ldstr      ""
    IL_0029:  stloc.2
    IL_002a:  ldstr      ""
    IL_002f:  stloc.3
    IL_0030:  ldloc.0
    IL_0031:  stloc.s    V_6
    IL_0033:  ldc.i4.0
    IL_0034:  stloc.s    V_7
    IL_0036:  br.s       IL_005e

    IL_0038:  ldloc.s    V_6
    IL_003a:  ldloc.s    V_7
    IL_003c:  ldelem.i4
    IL_003d:  stloc.s    V_4
    IL_003f:  ldarg.1
    IL_0040:  ldloc.s    V_4
    IL_0042:  ldloca.s   V_2
    IL_0044:  ldloca.s   V_3
    IL_0046:  ldloca.s   V_1
    IL_0048:  callvirt   instance void Pakon.Scanner::GetAndClearLastErrorTLX([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000,
                                                                              string&,
                                                                              string&,
                                                                              int32&)
    IL_004d:  ldloc.1
    IL_004e:  brfalse.s  IL_0058

    IL_0050:  ldloc.1
    IL_0051:  ldc.i4     0x87
    IL_0056:  bne.un.s   IL_0066

    IL_0058:  ldloc.s    V_7
    IL_005a:  ldc.i4.1
    IL_005b:  add
    IL_005c:  stloc.s    V_7
    IL_005e:  ldloc.s    V_7
    IL_0060:  ldloc.s    V_6
    IL_0062:  ldlen
    IL_0063:  conv.i4
    IL_0064:  blt.s      IL_0038

    IL_0066:  ldloc.1
    IL_0067:  brtrue.s   IL_00b8

    IL_0069:  ldarg.2
    IL_006a:  callvirt   instance int32 [mscorlib]System.Runtime.InteropServices.ExternalException::get_ErrorCode()
    IL_006f:  ldc.i4     0x80004005
    IL_0074:  bne.un.s   IL_009c

    IL_0076:  ldarg.2
    IL_0077:  callvirt   instance string [mscorlib]System.Exception::get_Message()
    IL_007c:  call       int32 [mscorlib]System.Convert::ToInt32(string)
    IL_0081:  stloc.s    V_5
    IL_0083:  ldstr      "{0}"
    IL_0088:  ldloc.s    V_5
    IL_008a:  box        [Interop.TLXLib]TLXLib.ERROR_CODES_000
    IL_008f:  call       instance string [mscorlib]System.Enum::ToString()
    IL_0094:  call       string [mscorlib]System.String::Format(string,
                                                                object)
    IL_0099:  stloc.2
    IL_009a:  br.s       IL_00b8

    IL_009c:  ldstr      "Error Code is : {0:X}. Error message is : {1}."
    IL_00a1:  ldarg.2
    IL_00a2:  callvirt   instance int32 [mscorlib]System.Runtime.InteropServices.ExternalException::get_ErrorCode()
    IL_00a7:  box        [mscorlib]System.Int32
    IL_00ac:  ldarg.2
    IL_00ad:  callvirt   instance string [mscorlib]System.Exception::get_Message()
    IL_00b2:  call       string [mscorlib]System.String::Format(string,
                                                                object,
                                                                object)
    IL_00b7:  stloc.2
    IL_00b8:  ldarg.0
    IL_00b9:  ldloc.2
    IL_00ba:  ldarg.3
    IL_00bb:  call       void Pakon.TLXErrorMessageBox::Show([System.Windows.Forms]System.Windows.Forms.Form,
                                                             string,
                                                             string)
    IL_00c0:  ret
  } // end of method Global::ErrorCOM

  .method public hidebysig static bool  IsScanTypeAvailable(class Pakon.Scanner csScanner,
                                                            class Pakon.ScannerSettings csScannerSettings,
                                                            [Interop.TLXLib]TLXLib.FILM_FORMAT_000 ffScanType,
                                                            [Interop.TLXLib]TLXLib.RESOLUTION_000 prScanType) cil managed
  {
    // Code size       134 (0x86)
    .maxstack  3
    .locals ([Interop.TLXLib]TLXLib.FILM_FORMAT_000 V_0,
             [Interop.TLXLib]TLXLib.RESOLUTION_000 V_1)
    IL_0000:  ldarg.2
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  switch     ( 
                          IL_0045,
                          IL_0012)
    IL_0010:  br.s       IL_0084

    IL_0012:  ldarg.3
    IL_0013:  stloc.1
    IL_0014:  ldloc.1
    IL_0015:  switch     ( 
                          IL_003a,
                          IL_0031,
                          IL_0028)
    IL_0026:  br.s       IL_0043

    IL_0028:  ldarg.1
    IL_0029:  ldc.i4.s   29
    IL_002b:  callvirt   instance bool Pakon.ScannerSettings::get_Item(valuetype Pakon.ScannerCapabilities)
    IL_0030:  ret

    IL_0031:  ldarg.1
    IL_0032:  ldc.i4.s   30
    IL_0034:  callvirt   instance bool Pakon.ScannerSettings::get_Item(valuetype Pakon.ScannerCapabilities)
    IL_0039:  ret

    IL_003a:  ldarg.1
    IL_003b:  ldc.i4.s   31
    IL_003d:  callvirt   instance bool Pakon.ScannerSettings::get_Item(valuetype Pakon.ScannerCapabilities)
    IL_0042:  ret

    IL_0043:  ldc.i4.0
    IL_0044:  ret

    IL_0045:  ldarg.1
    IL_0046:  ldc.i4.s   24
    IL_0048:  callvirt   instance bool Pakon.ScannerSettings::get_Item(valuetype Pakon.ScannerCapabilities)
    IL_004d:  brfalse.s  IL_0082

    IL_004f:  ldarg.3
    IL_0050:  stloc.1
    IL_0051:  ldloc.1
    IL_0052:  switch     ( 
                          IL_0077,
                          IL_006e,
                          IL_0065)
    IL_0063:  br.s       IL_0080

    IL_0065:  ldarg.1
    IL_0066:  ldc.i4.s   26
    IL_0068:  callvirt   instance bool Pakon.ScannerSettings::get_Item(valuetype Pakon.ScannerCapabilities)
    IL_006d:  ret

    IL_006e:  ldarg.1
    IL_006f:  ldc.i4.s   27
    IL_0071:  callvirt   instance bool Pakon.ScannerSettings::get_Item(valuetype Pakon.ScannerCapabilities)
    IL_0076:  ret

    IL_0077:  ldarg.1
    IL_0078:  ldc.i4.s   28
    IL_007a:  callvirt   instance bool Pakon.ScannerSettings::get_Item(valuetype Pakon.ScannerCapabilities)
    IL_007f:  ret

    IL_0080:  ldc.i4.0
    IL_0081:  ret

    IL_0082:  ldc.i4.0
    IL_0083:  ret

    IL_0084:  ldc.i4.0
    IL_0085:  ret
  } // end of method Global::IsScanTypeAvailable

  .method public hidebysig static int32  GetResolutionHeight([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 stType,
                                                             [Interop.TLXLib]TLXLib.RESOLUTION_000 srResolution,
                                                             [Interop.TLXLib]TLXLib.FILM_FORMAT_000 ffFormat) cil managed
  {
    // Code size       161 (0xa1)
    .maxstack  2
    .locals ([Interop.TLXLib]TLXLib.FRAME_SIZES_000 V_0,
             [Interop.TLXLib]TLXLib.FILM_FORMAT_000 V_1,
             [Interop.TLXLib]TLXLib.RESOLUTION_000 V_2,
             [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_3)
    IL_0000:  ldc.i4     0x7d0
    IL_0005:  stloc.0
    IL_0006:  ldarg.2
    IL_0007:  stloc.1
    IL_0008:  ldloc.1
    IL_0009:  switch     ( 
                          IL_0018,
                          IL_0046)
    IL_0016:  br.s       IL_0094

    IL_0018:  ldarg.1
    IL_0019:  stloc.2
    IL_001a:  ldloc.2
    IL_001b:  switch     ( 
                          IL_002e,
                          IL_0036,
                          IL_003e)
    IL_002c:  br.s       IL_009f

    IL_002e:  ldc.i4     0x359
    IL_0033:  stloc.0
    IL_0034:  br.s       IL_009f

    IL_0036:  ldc.i4     0x4b0
    IL_003b:  stloc.0
    IL_003c:  br.s       IL_009f

    IL_003e:  ldc.i4     0x6b2
    IL_0043:  stloc.0
    IL_0044:  br.s       IL_009f

    IL_0046:  ldarg.1
    IL_0047:  stloc.2
    IL_0048:  ldloc.2
    IL_0049:  switch     ( 
                          IL_005c,
                          IL_0064,
                          IL_008c)
    IL_005a:  br.s       IL_009f

    IL_005c:  ldc.i4     0x3e8
    IL_0061:  stloc.0
    IL_0062:  br.s       IL_009f

    IL_0064:  ldarg.0
    IL_0065:  stloc.3
    IL_0066:  ldloc.3
    IL_0067:  ldc.i4     0x546
    IL_006c:  sub
    IL_006d:  switch     ( 
                          IL_007c,
                          IL_007c)
    IL_007a:  br.s       IL_0084

    IL_007c:  ldc.i4     0x5dc
    IL_0081:  stloc.0
    IL_0082:  br.s       IL_009f

    IL_0084:  ldc.i4     0x578
    IL_0089:  stloc.0
    IL_008a:  br.s       IL_009f

    IL_008c:  ldc.i4     0x7d0
    IL_0091:  stloc.0
    IL_0092:  br.s       IL_009f

    IL_0094:  ldstr      "GetResolutionHeight Film Format not supported"
    IL_0099:  newobj     instance void [mscorlib]System.FormatException::.ctor(string)
    IL_009e:  throw

    IL_009f:  ldloc.0
    IL_00a0:  ret
  } // end of method Global::GetResolutionHeight

  .method public hidebysig static int32  BufferSize(int32 nWidth,
                                                    int32 nHeight,
                                                    [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 eMemoryFormat,
                                                    bool bFourChannel) cil managed
  {
    // Code size       101 (0x65)
    .maxstack  2
    .locals ([Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 V_0)
    IL_0000:  ldarg.2
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  switch     ( 
                          IL_0030,
                          IL_0045,
                          IL_0016)
    IL_0014:  br.s       IL_005a

    IL_0016:  ldarg.0
    IL_0017:  ldarg.1
    IL_0018:  ble.s      IL_0025

    IL_001a:  ldarg.1
    IL_001b:  ldc.i4.3
    IL_001c:  add
    IL_001d:  ldarg.0
    IL_001e:  mul
    IL_001f:  ldc.i4.3
    IL_0020:  mul
    IL_0021:  ldc.i4.s   62
    IL_0023:  add
    IL_0024:  ret

    IL_0025:  ldarg.0
    IL_0026:  ldc.i4.3
    IL_0027:  add
    IL_0028:  ldarg.0
    IL_0029:  mul
    IL_002a:  ldc.i4.3
    IL_002b:  mul
    IL_002c:  ldc.i4.s   62
    IL_002e:  add
    IL_002f:  ret

    IL_0030:  ldarg.3
    IL_0031:  brfalse.s  IL_003c

    IL_0033:  ldc.i4.8
    IL_0034:  ldarg.0
    IL_0035:  mul
    IL_0036:  ldarg.1
    IL_0037:  mul
    IL_0038:  ldc.i4.s   16
    IL_003a:  add
    IL_003b:  ret

    IL_003c:  ldc.i4.6
    IL_003d:  ldarg.0
    IL_003e:  mul
    IL_003f:  ldarg.1
    IL_0040:  mul
    IL_0041:  ldc.i4.s   16
    IL_0043:  add
    IL_0044:  ret

    IL_0045:  ldarg.3
    IL_0046:  brfalse.s  IL_0051

    IL_0048:  ldc.i4.4
    IL_0049:  ldarg.0
    IL_004a:  mul
    IL_004b:  ldarg.1
    IL_004c:  mul
    IL_004d:  ldc.i4.s   60
    IL_004f:  mul
    IL_0050:  ret

    IL_0051:  ldc.i4.3
    IL_0052:  ldarg.0
    IL_0053:  mul
    IL_0054:  ldarg.1
    IL_0055:  mul
    IL_0056:  ldc.i4.s   60
    IL_0058:  mul
    IL_0059:  ret

    IL_005a:  ldstr      "File format not supported"
    IL_005f:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0064:  throw
  } // end of method Global::BufferSize

  .method public hidebysig static void  Convert(int32 iScannerType,
                                                int32 iScannerVersionHw,
                                                [out] [Interop.TLXLib]TLXLib.SCANNER_TYPE_000& nScannerType,
                                                [out] valuetype Pakon.ScannerHW135& sh135,
                                                [out] valuetype Pakon.ScannerHW235& sh235,
                                                [out] valuetype Pakon.ScannerHW335& sh335) cil managed
  {
    // Code size       395 (0x18b)
    .maxstack  2
    .locals ([Interop.TLXLib]TLXLib.SCANNER_VERSION_HW_000 V_0,
             [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_1,
             [Interop.TLXLib]TLXLib.SCANNER_VERSION_HW_000 V_2)
    IL_0000:  ldarg.2
    IL_0001:  ldc.i4.0
    IL_0002:  stind.i4
    IL_0003:  ldarg.3
    IL_0004:  ldc.i4.0
    IL_0005:  stind.i4
    IL_0006:  ldarg.s    sh235
    IL_0008:  ldc.i4.0
    IL_0009:  stind.i4
    IL_000a:  ldarg.s    sh335
    IL_000c:  ldc.i4.0
    IL_000d:  stind.i4
    IL_000e:  ldarg.2
    IL_000f:  ldind.i4
    IL_0010:  box        [Interop.TLXLib]TLXLib.SCANNER_TYPE_000
    IL_0015:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_001a:  ldarg.0
    IL_001b:  box        [mscorlib]System.Int32
    IL_0020:  call       bool [mscorlib]System.Enum::IsDefined([mscorlib]System.Type,
                                                               object)
    IL_0025:  brfalse    IL_018a

    IL_002a:  ldarg.2
    IL_002b:  ldarg.0
    IL_002c:  stind.i4
    IL_002d:  ldc.i4.0
    IL_002e:  stloc.0
    IL_002f:  ldloc.0
    IL_0030:  box        [Interop.TLXLib]TLXLib.SCANNER_VERSION_HW_000
    IL_0035:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_003a:  ldarg.1
    IL_003b:  box        [mscorlib]System.Int32
    IL_0040:  call       bool [mscorlib]System.Enum::IsDefined([mscorlib]System.Type,
                                                               object)
    IL_0045:  brfalse    IL_018a

    IL_004a:  ldarg.1
    IL_004b:  stloc.0
    IL_004c:  ldarg.2
    IL_004d:  ldind.i4
    IL_004e:  stloc.1
    IL_004f:  ldloc.1
    IL_0050:  ldc.i4.7
    IL_0051:  sub
    IL_0052:  switch     ( 
                          IL_00db,
                          IL_00db)
    IL_005f:  ldloc.1
    IL_0060:  ldc.i4     0x546
    IL_0065:  sub
    IL_0066:  switch     ( 
                          IL_0088,
                          IL_0088)
    IL_0073:  ldloc.1
    IL_0074:  ldc.i4     0xd16
    IL_0079:  sub
    IL_007a:  switch     ( 
                          IL_011a,
                          IL_011a)
    IL_0087:  ret

    IL_0088:  ldloc.0
    IL_0089:  stloc.2
    IL_008a:  ldloc.2
    IL_008b:  ldc.i4     0xc8
    IL_0090:  bgt.s      IL_00a5

    IL_0092:  ldloc.2
    IL_0093:  ldc.i4.s   10
    IL_0095:  beq.s      IL_00be

    IL_0097:  ldloc.2
    IL_0098:  ldc.i4.s   100
    IL_009a:  beq.s      IL_00d3

    IL_009c:  ldloc.2
    IL_009d:  ldc.i4     0xc8
    IL_00a2:  beq.s      IL_00c3

    IL_00a4:  ret

    IL_00a5:  ldloc.2
    IL_00a6:  ldc.i4     0x12c
    IL_00ab:  beq.s      IL_00cb

    IL_00ad:  ldloc.2
    IL_00ae:  ldc.i4     0x190
    IL_00b3:  beq.s      IL_00d3

    IL_00b5:  ldloc.2
    IL_00b6:  ldc.i4     0x3e8
    IL_00bb:  beq.s      IL_00d3

    IL_00bd:  ret

    IL_00be:  ldarg.3
    IL_00bf:  ldc.i4.s   10
    IL_00c1:  stind.i4
    IL_00c2:  ret

    IL_00c3:  ldarg.3
    IL_00c4:  ldc.i4     0xc8
    IL_00c9:  stind.i4
    IL_00ca:  ret

    IL_00cb:  ldarg.3
    IL_00cc:  ldc.i4     0x12c
    IL_00d1:  stind.i4
    IL_00d2:  ret

    IL_00d3:  ldarg.3
    IL_00d4:  ldc.i4     0x190
    IL_00d9:  stind.i4
    IL_00da:  ret

    IL_00db:  ldloc.0
    IL_00dc:  stloc.2
    IL_00dd:  ldloc.2
    IL_00de:  ldc.i4.s   50
    IL_00e0:  bgt.s      IL_00ec

    IL_00e2:  ldloc.2
    IL_00e3:  ldc.i4.3
    IL_00e4:  beq.s      IL_00fd

    IL_00e6:  ldloc.2
    IL_00e7:  ldc.i4.s   50
    IL_00e9:  beq.s      IL_0102

    IL_00eb:  ret

    IL_00ec:  ldloc.2
    IL_00ed:  ldc.i4     0x3e8
    IL_00f2:  beq.s      IL_0108

    IL_00f4:  ldloc.2
    IL_00f5:  ldc.i4     0x44c
    IL_00fa:  beq.s      IL_0111

    IL_00fc:  ret

    IL_00fd:  ldarg.s    sh235
    IL_00ff:  ldc.i4.3
    IL_0100:  stind.i4
    IL_0101:  ret

    IL_0102:  ldarg.s    sh235
    IL_0104:  ldc.i4.s   50
    IL_0106:  stind.i4
    IL_0107:  ret

    IL_0108:  ldarg.s    sh235
    IL_010a:  ldc.i4     0x3e8
    IL_010f:  stind.i4
    IL_0110:  ret

    IL_0111:  ldarg.s    sh235
    IL_0113:  ldc.i4     0x44c
    IL_0118:  stind.i4
    IL_0119:  ret

    IL_011a:  ldloc.0
    IL_011b:  stloc.2
    IL_011c:  ldloc.2
    IL_011d:  ldc.i4     0xc8
    IL_0122:  bgt.s      IL_0137

    IL_0124:  ldloc.2
    IL_0125:  ldc.i4.s   10
    IL_0127:  beq.s      IL_0161

    IL_0129:  ldloc.2
    IL_012a:  ldc.i4.s   100
    IL_012c:  beq.s      IL_0179

    IL_012e:  ldloc.2
    IL_012f:  ldc.i4     0xc8
    IL_0134:  beq.s      IL_0167

    IL_0136:  ret

    IL_0137:  ldloc.2
    IL_0138:  ldc.i4     0x190
    IL_013d:  bgt.s      IL_0150

    IL_013f:  ldloc.2
    IL_0140:  ldc.i4     0x12c
    IL_0145:  beq.s      IL_0170

    IL_0147:  ldloc.2
    IL_0148:  ldc.i4     0x190
    IL_014d:  beq.s      IL_0179

    IL_014f:  ret

    IL_0150:  ldloc.2
    IL_0151:  ldc.i4     0x3e8
    IL_0156:  beq.s      IL_0179

    IL_0158:  ldloc.2
    IL_0159:  ldc.i4     0x7d0
    IL_015e:  beq.s      IL_0182

    IL_0160:  ret

    IL_0161:  ldarg.s    sh335
    IL_0163:  ldc.i4.s   10
    IL_0165:  stind.i4
    IL_0166:  ret

    IL_0167:  ldarg.s    sh335
    IL_0169:  ldc.i4     0xc8
    IL_016e:  stind.i4
    IL_016f:  ret

    IL_0170:  ldarg.s    sh335
    IL_0172:  ldc.i4     0x12c
    IL_0177:  stind.i4
    IL_0178:  ret

    IL_0179:  ldarg.s    sh335
    IL_017b:  ldc.i4     0x190
    IL_0180:  stind.i4
    IL_0181:  ret

    IL_0182:  ldarg.s    sh335
    IL_0184:  ldc.i4     0x7d0
    IL_0189:  stind.i4
    IL_018a:  ret
  } // end of method Global::Convert

  .method private hidebysig specialname rtspecialname static 
          void  .cctor() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldc.i4.0
    IL_0001:  stsfld     [Interop.TLXLib]TLXLib.SAVE_CONTROL_000 Pakon.Global::MEMORY_PLANAR_16
    IL_0006:  ret
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

} // end of class Pakon.Global

.class public auto ansi sealed Pakon.TLXError
       extends [mscorlib]System.MulticastDelegate
{
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(object 'object',
                               native int 'method') runtime managed
  {
  } // end of method TLXError::.ctor

  .method public hidebysig virtual instance void 
          Invoke([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                 int32 lStatus) runtime managed
  {
  } // end of method TLXError::Invoke

  .method public hidebysig newslot virtual 
          instance [mscorlib]System.IAsyncResult 
          BeginInvoke([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                      int32 lStatus,
                      [mscorlib]System.AsyncCallback callback,
                      object 'object') runtime managed
  {
  } // end of method TLXError::BeginInvoke

  .method public hidebysig newslot virtual 
          instance void  EndInvoke([mscorlib]System.IAsyncResult result) runtime managed
  {
  } // end of method TLXError::EndInvoke

} // end of class Pakon.TLXError

.class public auto ansi sealed Pakon.TLXHardware
       extends [mscorlib]System.MulticastDelegate
{
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(object 'object',
                               native int 'method') runtime managed
  {
  } // end of method TLXHardware::.ctor

  .method public hidebysig virtual instance void 
          Invoke([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                 int32 lStatus) runtime managed
  {
  } // end of method TLXHardware::Invoke

  .method public hidebysig newslot virtual 
          instance [mscorlib]System.IAsyncResult 
          BeginInvoke([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                      int32 lStatus,
                      [mscorlib]System.AsyncCallback callback,
                      object 'object') runtime managed
  {
  } // end of method TLXHardware::BeginInvoke

  .method public hidebysig newslot virtual 
          instance void  EndInvoke([mscorlib]System.IAsyncResult result) runtime managed
  {
  } // end of method TLXHardware::EndInvoke

} // end of class Pakon.TLXHardware

.class public auto ansi sealed Pakon.TLXScanProgress
       extends [mscorlib]System.MulticastDelegate
{
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(object 'object',
                               native int 'method') runtime managed
  {
  } // end of method TLXScanProgress::.ctor

  .method public hidebysig virtual instance void 
          Invoke([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                 int32 lStatus) runtime managed
  {
  } // end of method TLXScanProgress::Invoke

  .method public hidebysig newslot virtual 
          instance [mscorlib]System.IAsyncResult 
          BeginInvoke([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                      int32 lStatus,
                      [mscorlib]System.AsyncCallback callback,
                      object 'object') runtime managed
  {
  } // end of method TLXScanProgress::BeginInvoke

  .method public hidebysig newslot virtual 
          instance void  EndInvoke([mscorlib]System.IAsyncResult result) runtime managed
  {
  } // end of method TLXScanProgress::EndInvoke

} // end of class Pakon.TLXScanProgress

.class public auto ansi sealed Pakon.TLXSaveProgress
       extends [mscorlib]System.MulticastDelegate
{
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(object 'object',
                               native int 'method') runtime managed
  {
  } // end of method TLXSaveProgress::.ctor

  .method public hidebysig virtual instance void 
          Invoke([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                 int32 lStatus) runtime managed
  {
  } // end of method TLXSaveProgress::Invoke

  .method public hidebysig newslot virtual 
          instance [mscorlib]System.IAsyncResult 
          BeginInvoke([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                      int32 lStatus,
                      [mscorlib]System.AsyncCallback callback,
                      object 'object') runtime managed
  {
  } // end of method TLXSaveProgress::BeginInvoke

  .method public hidebysig newslot virtual 
          instance void  EndInvoke([mscorlib]System.IAsyncResult result) runtime managed
  {
  } // end of method TLXSaveProgress::EndInvoke

} // end of class Pakon.TLXSaveProgress

.class public auto ansi beforefieldinit Pakon.CallBackClient
       extends [mscorlib]System.Object
       implements [Interop.TLXLib]TLXLib.ICallBackClient
{
  .field private class Pakon.Scanner m_csScanner
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(class Pakon.Scanner csScanner) cil managed
  {
    // Code size       14 (0xe)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0006:  ldarg.0
    IL_0007:  ldarg.1
    IL_0008:  stfld      class Pakon.Scanner Pakon.CallBackClient::m_csScanner
    IL_000d:  ret
  } // end of method CallBackClient::.ctor

  .method public hidebysig newslot virtual final 
          instance void  Awake(int32 lOperation,
                               int32 lStatus) cil managed
  {
    // Code size       32 (0x20)
    .maxstack  8
    IL_0000:  ldarg.2
    IL_0001:  ldc.i4     0xbb8
    IL_0006:  bne.un.s   IL_0012

    IL_0008:  ldc.i4     0x12c
    IL_000d:  call       void [mscorlib]System.Threading.Thread::Sleep(int32)
    IL_0012:  ldarg.0
    IL_0013:  ldfld      class Pakon.Scanner Pakon.CallBackClient::m_csScanner
    IL_0018:  ldarg.1
    IL_0019:  ldarg.2
    IL_001a:  callvirt   instance void Pakon.Scanner::TLXAwake(int32,
                                                               int32)
    IL_001f:  ret
  } // end of method CallBackClient::Awake

} // end of class Pakon.CallBackClient

.class public auto ansi beforefieldinit Pakon.Scanner
       extends [mscorlib]System.Object
{
  .field private class Pakon.TLXError m_evTLXError
  .field private class Pakon.TLXHardware m_evTLXHardware
  .field private class Pakon.TLXScanProgress m_evTLXScanProgress
  .field private class Pakon.TLXSaveProgress m_evTLXSaveProgress
  .field private class Pakon.ScannerScan m_csScannerScan
  .field private class Pakon.ScannerSave m_csScannerSave
  .field private class Pakon.ScannerUnsafe m_csUnsafe
  .field family [Interop.TLXLib]TLXLib.TLXMainClass m_csTLX
  .field private int32 m_iTLXCookie
  .method public hidebysig specialname instance void 
          add_m_evTLXError(class Pakon.TLXError 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Pakon.TLXError Pakon.Scanner::m_evTLXError
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  Pakon.TLXError
    IL_0012:  stfld      class Pakon.TLXError Pakon.Scanner::m_evTLXError
    IL_0017:  ret
  } // end of method Scanner::add_m_evTLXError

  .method public hidebysig specialname instance void 
          remove_m_evTLXError(class Pakon.TLXError 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Pakon.TLXError Pakon.Scanner::m_evTLXError
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  Pakon.TLXError
    IL_0012:  stfld      class Pakon.TLXError Pakon.Scanner::m_evTLXError
    IL_0017:  ret
  } // end of method Scanner::remove_m_evTLXError

  .method public hidebysig specialname instance void 
          add_m_evTLXHardware(class Pakon.TLXHardware 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Pakon.TLXHardware Pakon.Scanner::m_evTLXHardware
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  Pakon.TLXHardware
    IL_0012:  stfld      class Pakon.TLXHardware Pakon.Scanner::m_evTLXHardware
    IL_0017:  ret
  } // end of method Scanner::add_m_evTLXHardware

  .method public hidebysig specialname instance void 
          remove_m_evTLXHardware(class Pakon.TLXHardware 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Pakon.TLXHardware Pakon.Scanner::m_evTLXHardware
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  Pakon.TLXHardware
    IL_0012:  stfld      class Pakon.TLXHardware Pakon.Scanner::m_evTLXHardware
    IL_0017:  ret
  } // end of method Scanner::remove_m_evTLXHardware

  .method public hidebysig specialname instance void 
          add_m_evTLXScanProgress(class Pakon.TLXScanProgress 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Pakon.TLXScanProgress Pakon.Scanner::m_evTLXScanProgress
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  Pakon.TLXScanProgress
    IL_0012:  stfld      class Pakon.TLXScanProgress Pakon.Scanner::m_evTLXScanProgress
    IL_0017:  ret
  } // end of method Scanner::add_m_evTLXScanProgress

  .method public hidebysig specialname instance void 
          remove_m_evTLXScanProgress(class Pakon.TLXScanProgress 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Pakon.TLXScanProgress Pakon.Scanner::m_evTLXScanProgress
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  Pakon.TLXScanProgress
    IL_0012:  stfld      class Pakon.TLXScanProgress Pakon.Scanner::m_evTLXScanProgress
    IL_0017:  ret
  } // end of method Scanner::remove_m_evTLXScanProgress

  .method public hidebysig specialname instance void 
          add_m_evTLXSaveProgress(class Pakon.TLXSaveProgress 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Pakon.TLXSaveProgress Pakon.Scanner::m_evTLXSaveProgress
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  Pakon.TLXSaveProgress
    IL_0012:  stfld      class Pakon.TLXSaveProgress Pakon.Scanner::m_evTLXSaveProgress
    IL_0017:  ret
  } // end of method Scanner::add_m_evTLXSaveProgress

  .method public hidebysig specialname instance void 
          remove_m_evTLXSaveProgress(class Pakon.TLXSaveProgress 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Pakon.TLXSaveProgress Pakon.Scanner::m_evTLXSaveProgress
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  Pakon.TLXSaveProgress
    IL_0012:  stfld      class Pakon.TLXSaveProgress Pakon.Scanner::m_evTLXSaveProgress
    IL_0017:  ret
  } // end of method Scanner::remove_m_evTLXSaveProgress

  .method public hidebysig specialname instance class Pakon.ScannerUnsafe 
          get_Unsafe() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      class Pakon.ScannerUnsafe Pakon.Scanner::m_csUnsafe
    IL_0006:  ret
  } // end of method Scanner::get_Unsafe

  .method public hidebysig specialname instance class Pakon.IScanPictures 
          get_IScan() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      class Pakon.ScannerScan Pakon.Scanner::m_csScannerScan
    IL_0006:  ret
  } // end of method Scanner::get_IScan

  .method public hidebysig specialname instance class Pakon.ISavePictures 
          get_ISave() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      class Pakon.ScannerSave Pakon.Scanner::m_csScannerSave
    IL_0006:  ret
  } // end of method Scanner::get_ISave

  .method public hidebysig specialname instance class Pakon.ISavePictures3 
          get_ISave3() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      class Pakon.ScannerSave Pakon.Scanner::m_csScannerSave
    IL_0006:  ret
  } // end of method Scanner::get_ISave3

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       90 (0x5a)
    .maxstack  4
    IL_0000:  ldarg.0
    IL_0001:  ldnull
    IL_0002:  stfld      class Pakon.ScannerScan Pakon.Scanner::m_csScannerScan
    IL_0007:  ldarg.0
    IL_0008:  ldnull
    IL_0009:  stfld      class Pakon.ScannerSave Pakon.Scanner::m_csScannerSave
    IL_000e:  ldarg.0
    IL_000f:  newobj     instance void Pakon.ScannerUnsafe::.ctor()
    IL_0014:  stfld      class Pakon.ScannerUnsafe Pakon.Scanner::m_csUnsafe
    IL_0019:  ldarg.0
    IL_001a:  newobj     instance void [Interop.TLXLib]TLXLib.TLXMainClass::.ctor()
    IL_001f:  stfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.Scanner::m_csTLX
    IL_0024:  ldarg.0
    IL_0025:  ldc.i4.0
    IL_0026:  stfld      int32 Pakon.Scanner::m_iTLXCookie
    IL_002b:  ldarg.0
    IL_002c:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0031:  ldarg.0
    IL_0032:  ldarg.0
    IL_0033:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.Scanner::m_csTLX
    IL_0038:  newobj     instance void Pakon.ScannerScan::.ctor([Interop.TLXLib]TLXLib.TLXMainClass)
    IL_003d:  stfld      class Pakon.ScannerScan Pakon.Scanner::m_csScannerScan
    IL_0042:  ldarg.0
    IL_0043:  ldarg.0
    IL_0044:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.Scanner::m_csTLX
    IL_0049:  ldarg.0
    IL_004a:  ldfld      class Pakon.ScannerUnsafe Pakon.Scanner::m_csUnsafe
    IL_004f:  newobj     instance void Pakon.ScannerSave::.ctor([Interop.TLXLib]TLXLib.TLXMainClass,
                                                                class Pakon.ScannerUnsafe)
    IL_0054:  stfld      class Pakon.ScannerSave Pakon.Scanner::m_csScannerSave
    IL_0059:  ret
  } // end of method Scanner::.ctor

  .method public hidebysig instance void 
          TLXAwake(int32 lOperation,
                   int32 lStatus) cil managed
  {
    // Code size       415 (0x19f)
    .maxstack  3
    .locals ([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 V_0,
             bool V_1,
             [Interop.TLXLib]TLXLib.WORKER_THREAD_PROGRESS_000 V_2,
             [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 V_3,
             [Interop.TLXLib]TLXLib.WORKER_THREAD_PROGRESS_000 V_4)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldloc.0
    IL_0003:  box        [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000
    IL_0008:  call       instance [mscorlib]System.Type [mscorlib]System.Object::GetType()
    IL_000d:  ldarg.1
    IL_000e:  box        [mscorlib]System.Int32
    IL_0013:  call       bool [mscorlib]System.Enum::IsDefined([mscorlib]System.Type,
                                                               object)
    IL_0018:  stloc.1
    IL_0019:  ldloc.1
    IL_001a:  brfalse    IL_0193

    IL_001f:  ldarg.1
    IL_0020:  stloc.0
    IL_0021:  ldloc.0
    IL_0022:  stloc.3
    IL_0023:  ldloc.3
    IL_0024:  switch     ( 
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_00eb,
                          IL_00eb,
                          IL_00eb,
                          IL_00eb,
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_0104,
                          IL_00d2,
                          IL_011d,
                          IL_00d2,
                          IL_0104,
                          IL_00d2)
    IL_00d1:  ret

    IL_00d2:  ldarg.0
    IL_00d3:  ldfld      class Pakon.TLXError Pakon.Scanner::m_evTLXError
    IL_00d8:  brfalse    IL_019e

    IL_00dd:  ldarg.0
    IL_00de:  ldfld      class Pakon.TLXError Pakon.Scanner::m_evTLXError
    IL_00e3:  ldloc.0
    IL_00e4:  ldarg.2
    IL_00e5:  callvirt   instance void Pakon.TLXError::Invoke([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000,
                                                              int32)
    IL_00ea:  ret

    IL_00eb:  ldarg.0
    IL_00ec:  ldfld      class Pakon.TLXHardware Pakon.Scanner::m_evTLXHardware
    IL_00f1:  brfalse    IL_019e

    IL_00f6:  ldarg.0
    IL_00f7:  ldfld      class Pakon.TLXHardware Pakon.Scanner::m_evTLXHardware
    IL_00fc:  ldloc.0
    IL_00fd:  ldarg.2
    IL_00fe:  callvirt   instance void Pakon.TLXHardware::Invoke([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000,
                                                                 int32)
    IL_0103:  ret

    IL_0104:  ldarg.0
    IL_0105:  ldfld      class Pakon.TLXScanProgress Pakon.Scanner::m_evTLXScanProgress
    IL_010a:  brfalse    IL_019e

    IL_010f:  ldarg.0
    IL_0110:  ldfld      class Pakon.TLXScanProgress Pakon.Scanner::m_evTLXScanProgress
    IL_0115:  ldloc.0
    IL_0116:  ldarg.2
    IL_0117:  callvirt   instance void Pakon.TLXScanProgress::Invoke([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000,
                                                                     int32)
    IL_011c:  ret

    IL_011d:  ldarg.2
    IL_011e:  stloc.2
    IL_011f:  ldloc.2
    IL_0120:  stloc.s    V_4
    IL_0122:  ldloc.s    V_4
    IL_0124:  ldc.i4     0x3e8
    IL_0129:  bgt.s      IL_013b

    IL_012b:  ldloc.s    V_4
    IL_012d:  ldc.i4.0
    IL_012e:  beq.s      IL_017d

    IL_0130:  ldloc.s    V_4
    IL_0132:  ldc.i4     0x3e8
    IL_0137:  beq.s      IL_017d

    IL_0139:  br.s       IL_0165

    IL_013b:  ldloc.s    V_4
    IL_013d:  ldc.i4     0x7d0
    IL_0142:  beq.s      IL_0165

    IL_0144:  ldloc.s    V_4
    IL_0146:  ldc.i4     0xbb8
    IL_014b:  bne.un.s   IL_0165

    IL_014d:  ldarg.0
    IL_014e:  call       instance class Pakon.ISavePictures Pakon.Scanner::get_ISave()
    IL_0153:  callvirt   instance void Pakon.ISavePictures::ClientMemoryBufferDismissAll()
    IL_0158:  ldarg.0
    IL_0159:  call       instance class Pakon.ScannerUnsafe Pakon.Scanner::get_Unsafe()
    IL_015e:  callvirt   instance void Pakon.ScannerUnsafe::Deallocate()
    IL_0163:  br.s       IL_017d

    IL_0165:  ldarg.0
    IL_0166:  call       instance class Pakon.ScannerUnsafe Pakon.Scanner::get_Unsafe()
    IL_016b:  ldarg.0
    IL_016c:  callvirt   instance void Pakon.ScannerUnsafe::ProcessBuffer(class Pakon.Scanner)
    IL_0171:  ldarg.0
    IL_0172:  call       instance class Pakon.ScannerUnsafe Pakon.Scanner::get_Unsafe()
    IL_0177:  ldarg.0
    IL_0178:  callvirt   instance void Pakon.ScannerUnsafe::NextBuffer(class Pakon.Scanner)
    IL_017d:  ldarg.0
    IL_017e:  ldfld      class Pakon.TLXSaveProgress Pakon.Scanner::m_evTLXSaveProgress
    IL_0183:  brfalse.s  IL_019e

    IL_0185:  ldarg.0
    IL_0186:  ldfld      class Pakon.TLXSaveProgress Pakon.Scanner::m_evTLXSaveProgress
    IL_018b:  ldloc.0
    IL_018c:  ldarg.2
    IL_018d:  callvirt   instance void Pakon.TLXSaveProgress::Invoke([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000,
                                                                     int32)
    IL_0192:  ret

    IL_0193:  ldstr      "Callback operation invalid"
    IL_0198:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_019d:  throw

    IL_019e:  ret
  } // end of method Scanner::TLXAwake

  .method public hidebysig newslot virtual 
          instance bool  IsClosed() cil managed
  {
    // Code size       10 (0xa)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32 Pakon.Scanner::m_iTLXCookie
    IL_0006:  ldc.i4.0
    IL_0007:  ceq
    IL_0009:  ret
  } // end of method Scanner::IsClosed

  .method public hidebysig newslot virtual 
          instance void  Closing() cil managed
  {
    // Code size       1 (0x1)
    .maxstack  8
    IL_0000:  ret
  } // end of method Scanner::Closing

  .method public hidebysig instance void 
          InitializeTLX([Interop.TLXLib]TLXLib.INITIALIZE_CONTROL_000 iInitializeControl) cil managed
  {
    // Code size       64 (0x40)
    .maxstack  4
    .locals (int32 V_0,
             int32 V_1)
    IL_0000:  ldc.i4     0x30d40
    IL_0005:  stloc.0
    IL_0006:  ldarg.1
    IL_0007:  stloc.1
    IL_0008:  ldarg.0
    IL_0009:  ldarg.0
    IL_000a:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.Scanner::m_csTLX
    IL_000f:  ldarg.0
    IL_0010:  newobj     instance void Pakon.CallBackClient::.ctor(class Pakon.Scanner)
    IL_0015:  callvirt   instance int32 [Interop.TLXLib]TLXLib.TLXMainClass::CBAdvise([Interop.TLXLib]TLXLib.ICallBackClient)
    IL_001a:  stfld      int32 Pakon.Scanner::m_iTLXCookie
    IL_001f:  ldarg.0
    IL_0020:  ldfld      int32 Pakon.Scanner::m_iTLXCookie
    IL_0025:  brtrue.s   IL_0032

    IL_0027:  ldstr      "No Scanner Detected"
    IL_002c:  newobj     instance void [mscorlib]System.ArgumentNullException::.ctor(string)
    IL_0031:  throw

    IL_0032:  ldarg.0
    IL_0033:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.Scanner::m_csTLX
    IL_0038:  ldloc.1
    IL_0039:  ldloc.0
    IL_003a:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::InitializeScanner(int32,
                                                                                              int32)
    IL_003f:  ret
  } // end of method Scanner::InitializeTLX

  .method public hidebysig instance void 
          GetAndClearLastErrorTLX([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                                  string& strError,
                                  string& strErrorNumbers,
                                  [out] int32& iReturn) cil managed
  {
    // Code size       207 (0xcf)
    .maxstack  5
    .locals ([Interop.TLXLib]TLXLib.INT_IID_000 V_0,
             [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 V_1)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldarg.1
    IL_0003:  stloc.1
    IL_0004:  ldloc.1
    IL_0005:  ldc.i4.1
    IL_0006:  sub
    IL_0007:  switch     ( 
                          IL_00af,
                          IL_00bd,
                          IL_00af,
                          IL_00bd,
                          IL_00af,
                          IL_00bd,
                          IL_00af,
                          IL_00bd,
                          IL_00af,
                          IL_00bd,
                          IL_00af,
                          IL_00bd,
                          IL_00af,
                          IL_00bd,
                          IL_00af,
                          IL_00bd,
                          IL_00b3)
    IL_0050:  ldloc.1
    IL_0051:  ldc.i4.s   21
    IL_0053:  sub
    IL_0054:  switch     ( 
                          IL_00b3,
                          IL_00bd,
                          IL_00b3,
                          IL_00bd,
                          IL_00b3,
                          IL_00bd,
                          IL_00b3,
                          IL_00bd,
                          IL_00b3,
                          IL_00bd,
                          IL_00b3,
                          IL_00bd,
                          IL_00b3,
                          IL_00bd,
                          IL_00b3,
                          IL_00bd,
                          IL_00b3,
                          IL_00bd,
                          IL_00b7,
                          IL_00bd,
                          IL_00bb)
    IL_00ad:  br.s       IL_00bd

    IL_00af:  ldc.i4.0
    IL_00b0:  stloc.0
    IL_00b1:  br.s       IL_00bd

    IL_00b3:  ldc.i4.1
    IL_00b4:  stloc.0
    IL_00b5:  br.s       IL_00bd

    IL_00b7:  ldc.i4.2
    IL_00b8:  stloc.0
    IL_00b9:  br.s       IL_00bd

    IL_00bb:  ldc.i4.4
    IL_00bc:  stloc.0
    IL_00bd:  ldarg.s    iReturn
    IL_00bf:  ldarg.0
    IL_00c0:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.Scanner::m_csTLX
    IL_00c5:  ldloc.0
    IL_00c6:  ldarg.2
    IL_00c7:  ldarg.3
    IL_00c8:  callvirt   instance int32 [Interop.TLXLib]TLXLib.TLXMainClass::GetAndClearLastError(int32,
                                                                                                  string&,
                                                                                                  string&)
    IL_00cd:  stind.i4
    IL_00ce:  ret
  } // end of method Scanner::GetAndClearLastErrorTLX

  .method public hidebysig instance void 
          GetInitializeWarnings(valuetype Pakon.ScannerInitializeWarnings& iwScanner) cil managed
  {
    // Code size       19 (0x13)
    .maxstack  2
    .locals (int32 V_0)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldarg.0
    IL_0003:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.Scanner::m_csTLX
    IL_0008:  ldloca.s   V_0
    IL_000a:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::GetInitializeWarnings(int32&)
    IL_000f:  ldarg.1
    IL_0010:  ldloc.0
    IL_0011:  stind.i4
    IL_0012:  ret
  } // end of method Scanner::GetInitializeWarnings

  .method public hidebysig instance void 
          CBUnadviseTLX() cil managed
  {
    // Code size       33 (0x21)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32 Pakon.Scanner::m_iTLXCookie
    IL_0006:  brfalse.s  IL_0020

    IL_0008:  ldarg.0
    IL_0009:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.Scanner::m_csTLX
    IL_000e:  ldarg.0
    IL_000f:  ldfld      int32 Pakon.Scanner::m_iTLXCookie
    IL_0014:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::CBUnadvise(int32)
    IL_0019:  ldarg.0
    IL_001a:  ldc.i4.0
    IL_001b:  stfld      int32 Pakon.Scanner::m_iTLXCookie
    IL_0020:  ret
  } // end of method Scanner::CBUnadviseTLX

  .event Pakon.TLXError m_evTLXError
  {
    .addon instance void Pakon.Scanner::add_m_evTLXError(class Pakon.TLXError)
    .removeon instance void Pakon.Scanner::remove_m_evTLXError(class Pakon.TLXError)
  } // end of event Scanner::m_evTLXError
  .event Pakon.TLXHardware m_evTLXHardware
  {
    .addon instance void Pakon.Scanner::add_m_evTLXHardware(class Pakon.TLXHardware)
    .removeon instance void Pakon.Scanner::remove_m_evTLXHardware(class Pakon.TLXHardware)
  } // end of event Scanner::m_evTLXHardware
  .event Pakon.TLXScanProgress m_evTLXScanProgress
  {
    .addon instance void Pakon.Scanner::add_m_evTLXScanProgress(class Pakon.TLXScanProgress)
    .removeon instance void Pakon.Scanner::remove_m_evTLXScanProgress(class Pakon.TLXScanProgress)
  } // end of event Scanner::m_evTLXScanProgress
  .event Pakon.TLXSaveProgress m_evTLXSaveProgress
  {
    .addon instance void Pakon.Scanner::add_m_evTLXSaveProgress(class Pakon.TLXSaveProgress)
    .removeon instance void Pakon.Scanner::remove_m_evTLXSaveProgress(class Pakon.TLXSaveProgress)
  } // end of event Scanner::m_evTLXSaveProgress
  .property instance class Pakon.ScannerUnsafe
          Unsafe()
  {
    .get instance class Pakon.ScannerUnsafe Pakon.Scanner::get_Unsafe()
  } // end of property Scanner::Unsafe
  .property instance class Pakon.IScanPictures
          IScan()
  {
    .get instance class Pakon.IScanPictures Pakon.Scanner::get_IScan()
  } // end of property Scanner::IScan
  .property instance class Pakon.ISavePictures
          ISave()
  {
    .get instance class Pakon.ISavePictures Pakon.Scanner::get_ISave()
  } // end of property Scanner::ISave
  .property instance class Pakon.ISavePictures3
          ISave3()
  {
    .get instance class Pakon.ISavePictures3 Pakon.Scanner::get_ISave3()
  } // end of property Scanner::ISave3
} // end of class Pakon.Scanner

.class interface public abstract auto ansi Pakon.ISavePictures3
{
  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureInfo3(int32 iIndex,
                                         [out] int32& iRollIndexFromStrip,
                                         [out] int32& iStripIndexFromStrip,
                                         [out] int32& iFilmProductFromStrip,
                                         [out] int32& iFilmSpecifierFromStrip,
                                         [out] string& strFrameName,
                                         [out] int32& iFrameNumber,
                                         [out] int32& iPrintAspectRatio,
                                         [out] string& strFileName,
                                         [out] string& strDirectory,
                                         [out] int32& iRotation,
                                         [out] [Interop.TLXLib]TLXLib.S_OR_H_000& eiSelectedHidden) cil managed
  {
  } // end of method ISavePictures3::GetPictureInfo3

} // end of class Pakon.ISavePictures3

.class interface public abstract auto ansi Pakon.ISavePictures
{
  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureCountScanGroup(int32 iRollIndex,
                                                  int32& iStripCount,
                                                  int32& iPictureCount,
                                                  int32& iScanWarnings) cil managed
  {
  } // end of method ISavePictures::GetPictureCountScanGroup

  .method public hidebysig newslot abstract virtual 
          instance void  MoveOldestRollToSaveGroup() cil managed
  {
  } // end of method ISavePictures::MoveOldestRollToSaveGroup

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureCountSaveGroup(int32& iRollCount,
                                                  int32& iStripCount,
                                                  int32& iPictureCount,
                                                  int32& iPictureSelectedCount,
                                                  int32& iPictureHiddenCount) cil managed
  {
  } // end of method ISavePictures::GetPictureCountSaveGroup

  .method public hidebysig newslot abstract virtual 
          instance void  SaveToDisk([Interop.TLXLib]TLXLib.INDEX_000 eIndex,
                                    [Interop.TLXLib]TLXLib.SAVE_CONTROL_000 eSaveControl,
                                    int32 iBoundingWidth,
                                    int32 iBoundingHeight,
                                    [Interop.TLXLib]TLXLib.SCALING_METHOD_000 eScalingMethod,
                                    [Interop.TLXLib]TLXLib.FILE_FORMAT_000 eFileFormat,
                                    int32 iCompression,
                                    int32 iDpi,
                                    int32 iColorBits) cil managed
  {
  } // end of method ISavePictures::SaveToDisk

  .method public hidebysig newslot abstract virtual 
          instance void  ClientMemoryBufferAdd(int32 iByteStartPointer,
                                               int32 iByteCount) cil managed
  {
  } // end of method ISavePictures::ClientMemoryBufferAdd

  .method public hidebysig newslot abstract virtual 
          instance void  ClientMemoryBufferDismissAll() cil managed
  {
  } // end of method ISavePictures::ClientMemoryBufferDismissAll

  .method public hidebysig newslot abstract virtual 
          instance void  SaveToClientMemory([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 stType,
                                            [Interop.TLXLib]TLXLib.INDEX_000 eIndex,
                                            [Interop.TLXLib]TLXLib.SAVE_CONTROL_000 eSaveControl,
                                            int32 iBoundingWidth,
                                            int32 iBoundingHeight,
                                            [Interop.TLXLib]TLXLib.SCALING_METHOD_000 eScalingMethod,
                                            [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 eFileFormat,
                                            bool bFourChannel) cil managed
  {
  } // end of method ISavePictures::SaveToClientMemory

  .method public hidebysig newslot abstract virtual 
          instance void  SaveCancel() cil managed
  {
  } // end of method ISavePictures::SaveCancel

  .method public hidebysig newslot abstract virtual 
          instance void  PutPictureInfo(int32 iIndex,
                                        int32 iFrameNumber,
                                        string strFileName,
                                        string strDirectory,
                                        int32 iRotation,
                                        [Interop.TLXLib]TLXLib.S_OR_H_000 eSelectedHidden) cil managed
  {
  } // end of method ISavePictures::PutPictureInfo

  .method public hidebysig newslot abstract virtual 
          instance void  PutPictureSelection([Interop.TLXLib]TLXLib.INDEX_000 eIndex,
                                             [Interop.TLXLib]TLXLib.S_OR_H_000 eSelectOrHidden,
                                             bool bSkipHidden) cil managed
  {
  } // end of method ISavePictures::PutPictureSelection

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureFramingUserInfo(int32 iIndex,
                                                   int32& iLeftHR,
                                                   int32& iTopHR,
                                                   int32& iRightHR,
                                                   int32& iBottomHR) cil managed
  {
  } // end of method ISavePictures::GetPictureFramingUserInfo

  .method public hidebysig newslot abstract virtual 
          instance void  GetPictureFramingUserInfoLowRes(int32 iIndex,
                                                         int32& iLeftLR,
                                                         int32& iTopLR,
                                                         int32& iRightLR,
                                                         int32& iBottomLR) cil managed
  {
  } // end of method ISavePictures::GetPictureFramingUserInfoLowRes

} // end of class Pakon.ISavePictures

.class public auto ansi beforefieldinit Pakon.ScannerSave
       extends [mscorlib]System.Object
       implements Pakon.ISavePictures,
                  Pakon.ISavePictures3
{
  .field private [Interop.TLXLib]TLXLib.TLXMainClass m_csTLX
  .field private class Pakon.ScannerUnsafe m_csUnsafe
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor([Interop.TLXLib]TLXLib.TLXMainClass csTLX,
                               class Pakon.ScannerUnsafe csUnsafe) cil managed
  {
    // Code size       35 (0x23)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldnull
    IL_0002:  stfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_0007:  ldarg.0
    IL_0008:  ldnull
    IL_0009:  stfld      class Pakon.ScannerUnsafe Pakon.ScannerSave::m_csUnsafe
    IL_000e:  ldarg.0
    IL_000f:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0014:  ldarg.0
    IL_0015:  ldarg.1
    IL_0016:  stfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_001b:  ldarg.0
    IL_001c:  ldarg.2
    IL_001d:  stfld      class Pakon.ScannerUnsafe Pakon.ScannerSave::m_csUnsafe
    IL_0022:  ret
  } // end of method ScannerSave::.ctor

  .method public hidebysig newslot virtual final 
          instance void  GetPictureCountScanGroup(int32 iRollIndex,
                                                  int32& iStripCount,
                                                  int32& iPictureCount,
                                                  int32& iScanWarnings) cil managed
  {
    // Code size       17 (0x11)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  ldarg.3
    IL_0009:  ldarg.s    iScanWarnings
    IL_000b:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::GetPictureCountScanGroup(int32,
                                                                                                     int32&,
                                                                                                     int32&,
                                                                                                     int32&)
    IL_0010:  ret
  } // end of method ScannerSave::GetPictureCountScanGroup

  .method public hidebysig newslot virtual final 
          instance void  MoveOldestRollToSaveGroup() cil managed
  {
    // Code size       12 (0xc)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_0006:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::MoveOldestRollToSaveGroup()
    IL_000b:  ret
  } // end of method ScannerSave::MoveOldestRollToSaveGroup

  .method public hidebysig newslot virtual final 
          instance void  GetPictureCountSaveGroup(int32& iRollCount,
                                                  int32& iStripCount,
                                                  int32& iPictureCount,
                                                  int32& iPictureSelectedCount,
                                                  int32& iPictureHiddenCount) cil managed
  {
    // Code size       19 (0x13)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  ldarg.3
    IL_0009:  ldarg.s    iPictureSelectedCount
    IL_000b:  ldarg.s    iPictureHiddenCount
    IL_000d:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::GetPictureCountSaveGroup(int32&,
                                                                                                     int32&,
                                                                                                     int32&,
                                                                                                     int32&,
                                                                                                     int32&)
    IL_0012:  ret
  } // end of method ScannerSave::GetPictureCountSaveGroup

  .method public hidebysig newslot virtual final 
          instance void  SaveToDisk([Interop.TLXLib]TLXLib.INDEX_000 eIndex,
                                    [Interop.TLXLib]TLXLib.SAVE_CONTROL_000 eSaveControl,
                                    int32 iBoundingWidth,
                                    int32 iBoundingHeight,
                                    [Interop.TLXLib]TLXLib.SCALING_METHOD_000 eScalingMethod,
                                    [Interop.TLXLib]TLXLib.FILE_FORMAT_000 eFileFormat,
                                    int32 iCompression,
                                    int32 iDpi,
                                    int32 iColorBits) cil managed
  {
    // Code size       38 (0x26)
    .maxstack  12
    IL_0000:  ldarg.2
    IL_0001:  ldc.i4     0x84
    IL_0006:  or
    IL_0007:  starg.s    eSaveControl
    IL_0009:  ldarg.0
    IL_000a:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_000f:  ldarg.1
    IL_0010:  ldnull
    IL_0011:  ldarg.2
    IL_0012:  ldarg.3
    IL_0013:  ldarg.s    iBoundingHeight
    IL_0015:  ldc.i4.0
    IL_0016:  ldarg.s    eScalingMethod
    IL_0018:  ldarg.s    eFileFormat
    IL_001a:  ldarg.s    iCompression
    IL_001c:  ldarg.s    iDpi
    IL_001e:  ldarg.s    iColorBits
    IL_0020:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::SaveToDisk(int32,
                                                                                       string,
                                                                                       int32,
                                                                                       int32,
                                                                                       int32,
                                                                                       int32,
                                                                                       int32,
                                                                                       int32,
                                                                                       int32,
                                                                                       int32,
                                                                                       int32)
    IL_0025:  ret
  } // end of method ScannerSave::SaveToDisk

  .method public hidebysig newslot virtual final 
          instance void  ClientMemoryBufferAdd(int32 iByteStartPointer,
                                               int32 iByteCount) cil managed
  {
    // Code size       14 (0xe)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::ClientMemoryBufferAdd(int32,
                                                                                                  int32)
    IL_000d:  ret
  } // end of method ScannerSave::ClientMemoryBufferAdd

  .method public hidebysig newslot virtual final 
          instance void  ClientMemoryBufferDismissAll() cil managed
  {
    // Code size       12 (0xc)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_0006:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::ClientMemoryBufferDismissAll()
    IL_000b:  ret
  } // end of method ScannerSave::ClientMemoryBufferDismissAll

  .method public hidebysig newslot virtual final 
          instance void  SaveToClientMemory([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 stType,
                                            [Interop.TLXLib]TLXLib.INDEX_000 eIndex,
                                            [Interop.TLXLib]TLXLib.SAVE_CONTROL_000 eSaveControl,
                                            int32 iBoundingWidth,
                                            int32 iBoundingHeight,
                                            [Interop.TLXLib]TLXLib.SCALING_METHOD_000 eScalingMethod,
                                            [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 eFileFormat,
                                            bool bFourChannel) cil managed
  {
    // Code size       76 (0x4c)
    .maxstack  9
    .locals ([Interop.TLXLib]TLXLib.ROTATE_000 V_0)
    IL_0000:  ldarg.s    bFourChannel
    IL_0002:  brfalse.s  IL_000f

    IL_0004:  ldarg.3
    IL_0005:  ldc.i4     0x480
    IL_000a:  or
    IL_000b:  starg.s    eSaveControl
    IL_000d:  br.s       IL_0018

    IL_000f:  ldarg.3
    IL_0010:  ldc.i4     0x484
    IL_0015:  or
    IL_0016:  starg.s    eSaveControl
    IL_0018:  ldarg.s    bFourChannel
    IL_001a:  brtrue.s   IL_001f

    IL_001c:  ldc.i4.0
    IL_001d:  br.s       IL_0033

    IL_001f:  ldarg.1
    IL_0020:  ldc.i4     0x546
    IL_0025:  beq.s      IL_0032

    IL_0027:  ldarg.1
    IL_0028:  ldc.i4     0x547
    IL_002d:  beq.s      IL_0032

    IL_002f:  ldc.i4.1
    IL_0030:  br.s       IL_0033

    IL_0032:  ldc.i4.3
    IL_0033:  stloc.0
    IL_0034:  ldarg.0
    IL_0035:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_003a:  ldarg.2
    IL_003b:  ldarg.3
    IL_003c:  ldarg.s    iBoundingWidth
    IL_003e:  ldarg.s    iBoundingHeight
    IL_0040:  ldloc.0
    IL_0041:  ldarg.s    eScalingMethod
    IL_0043:  ldarg.s    eFileFormat
    IL_0045:  ldc.i4.1
    IL_0046:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::SaveToClientMemory(int32,
                                                                                               int32,
                                                                                               int32,
                                                                                               int32,
                                                                                               int32,
                                                                                               int32,
                                                                                               int32,
                                                                                               int32)
    IL_004b:  ret
  } // end of method ScannerSave::SaveToClientMemory

  .method public hidebysig newslot virtual final 
          instance void  SaveCancel() cil managed
  {
    // Code size       12 (0xc)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_0006:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::SaveCancel()
    IL_000b:  ret
  } // end of method ScannerSave::SaveCancel

  .method public hidebysig newslot virtual final 
          instance void  GetPictureInfo3(int32 iIndex,
                                         [out] int32& iRollIndexFromStrip,
                                         [out] int32& iStripIndexFromStrip,
                                         [out] int32& iFilmProductFromStrip,
                                         [out] int32& iFilmSpecifierFromStrip,
                                         [out] string& strFrameName,
                                         [out] int32& iFrameNumber,
                                         [out] int32& iPrintAspectRatio,
                                         [out] string& strFileName,
                                         [out] string& strDirectory,
                                         [out] int32& iRotation,
                                         [out] [Interop.TLXLib]TLXLib.S_OR_H_000& eSelectedHidden) cil managed
  {
    // Code size       39 (0x27)
    .maxstack  13
    .locals (int32 V_0)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldarg.0
    IL_0003:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_0008:  ldarg.1
    IL_0009:  ldarg.2
    IL_000a:  ldarg.3
    IL_000b:  ldarg.s    iFilmProductFromStrip
    IL_000d:  ldarg.s    iFilmSpecifierFromStrip
    IL_000f:  ldarg.s    strFrameName
    IL_0011:  ldarg.s    iFrameNumber
    IL_0013:  ldarg.s    iPrintAspectRatio
    IL_0015:  ldarg.s    strFileName
    IL_0017:  ldarg.s    strDirectory
    IL_0019:  ldarg.s    iRotation
    IL_001b:  ldloca.s   V_0
    IL_001d:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::GetPictureInfo3(int32,
                                                                                            int32&,
                                                                                            int32&,
                                                                                            int32&,
                                                                                            int32&,
                                                                                            string&,
                                                                                            int32&,
                                                                                            int32&,
                                                                                            string&,
                                                                                            string&,
                                                                                            int32&,
                                                                                            int32&)
    IL_0022:  ldarg.s    eSelectedHidden
    IL_0024:  ldloc.0
    IL_0025:  stind.i4
    IL_0026:  ret
  } // end of method ScannerSave::GetPictureInfo3

  .method public hidebysig newslot virtual final 
          instance void  PutPictureInfo(int32 iIndex,
                                        int32 iFrameNumber,
                                        string strFileName,
                                        string strDirectory,
                                        int32 iRotation,
                                        [Interop.TLXLib]TLXLib.S_OR_H_000 eSelectedHidden) cil managed
  {
    // Code size       21 (0x15)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  ldarg.3
    IL_0009:  ldarg.s    strDirectory
    IL_000b:  ldarg.s    iRotation
    IL_000d:  ldarg.s    eSelectedHidden
    IL_000f:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::PutPictureInfo(int32,
                                                                                           int32,
                                                                                           string,
                                                                                           string,
                                                                                           int32,
                                                                                           int32)
    IL_0014:  ret
  } // end of method ScannerSave::PutPictureInfo

  .method public hidebysig newslot virtual final 
          instance void  PutPictureSelection([Interop.TLXLib]TLXLib.INDEX_000 eIndex,
                                             [Interop.TLXLib]TLXLib.S_OR_H_000 eSelectOrHidden,
                                             bool bSkipHidden) cil managed
  {
    // Code size       21 (0x15)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  ldarg.3
    IL_0009:  brtrue.s   IL_000e

    IL_000b:  ldc.i4.0
    IL_000c:  br.s       IL_000f

    IL_000e:  ldc.i4.1
    IL_000f:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::PutPictureSelection(int32,
                                                                                                int32,
                                                                                                int32)
    IL_0014:  ret
  } // end of method ScannerSave::PutPictureSelection

  .method public hidebysig newslot virtual final 
          instance void  GetPictureFramingUserInfo(int32 iIndex,
                                                   int32& iLeftHR,
                                                   int32& iTopHR,
                                                   int32& iRightHR,
                                                   int32& iBottomHR) cil managed
  {
    // Code size       33 (0x21)
    .maxstack  8
    IL_0000:  ldarg.2
    IL_0001:  ldc.i4.0
    IL_0002:  stind.i4
    IL_0003:  ldarg.3
    IL_0004:  ldc.i4.0
    IL_0005:  stind.i4
    IL_0006:  ldarg.s    iRightHR
    IL_0008:  ldc.i4.0
    IL_0009:  stind.i4
    IL_000a:  ldarg.s    iBottomHR
    IL_000c:  ldc.i4.0
    IL_000d:  stind.i4
    IL_000e:  ldarg.0
    IL_000f:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_0014:  ldarg.1
    IL_0015:  ldarg.2
    IL_0016:  ldarg.3
    IL_0017:  ldarg.s    iRightHR
    IL_0019:  ldarg.s    iBottomHR
    IL_001b:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::GetPictureFramingUserInfo(int32,
                                                                                                      int32&,
                                                                                                      int32&,
                                                                                                      int32&,
                                                                                                      int32&)
    IL_0020:  ret
  } // end of method ScannerSave::GetPictureFramingUserInfo

  .method public hidebysig newslot virtual final 
          instance void  GetPictureFramingUserInfoLowRes(int32 iIndex,
                                                         int32& iLeftLR,
                                                         int32& iTopLR,
                                                         int32& iRightLR,
                                                         int32& iBottomLR) cil managed
  {
    // Code size       33 (0x21)
    .maxstack  8
    IL_0000:  ldarg.2
    IL_0001:  ldc.i4.0
    IL_0002:  stind.i4
    IL_0003:  ldarg.3
    IL_0004:  ldc.i4.0
    IL_0005:  stind.i4
    IL_0006:  ldarg.s    iRightLR
    IL_0008:  ldc.i4.0
    IL_0009:  stind.i4
    IL_000a:  ldarg.s    iBottomLR
    IL_000c:  ldc.i4.0
    IL_000d:  stind.i4
    IL_000e:  ldarg.0
    IL_000f:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerSave::m_csTLX
    IL_0014:  ldarg.1
    IL_0015:  ldarg.2
    IL_0016:  ldarg.3
    IL_0017:  ldarg.s    iRightLR
    IL_0019:  ldarg.s    iBottomLR
    IL_001b:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::GetPictureFramingUserInfoLowRes(int32,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&,
                                                                                                            int32&)
    IL_0020:  ret
  } // end of method ScannerSave::GetPictureFramingUserInfoLowRes

} // end of class Pakon.ScannerSave

.class interface public abstract auto ansi Pakon.IScanPictures
{
  .method public hidebysig newslot abstract virtual 
          instance void  FocusCorrection([Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                         [Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor,
                                         [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                         bool bAdvanceFilm) cil managed
  {
  } // end of method IScanPictures::FocusCorrection

  .method public hidebysig newslot abstract virtual 
          instance void  LightCorrection([Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                         [Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor,
                                         [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                         bool bIR) cil managed
  {
  } // end of method IScanPictures::LightCorrection

  .method public hidebysig newslot abstract virtual 
          instance void  FilmTrackTest(bool bAdjustPots) cil managed
  {
  } // end of method IScanPictures::FilmTrackTest

  .method public hidebysig newslot abstract virtual 
          instance int32  FilmTrackTestResults() cil managed
  {
  } // end of method IScanPictures::FilmTrackTestResults

  .method public hidebysig newslot abstract virtual 
          instance void  ScanPictures([Interop.TLXLib]TLXLib.RESOLUTION_000 rResolution,
                                      [Interop.TLXLib]TLXLib.FILM_COLOR_000 fFilmColor,
                                      [Interop.TLXLib]TLXLib.FILM_FORMAT_000 fFilmFormat,
                                      [Interop.TLXLib]TLXLib.STRIP_MODE_000 smStripMode,
                                      [Interop.TLXLib]TLXLib.SCAN_CONTROL_000 scControl) cil managed
  {
  } // end of method IScanPictures::ScanPictures

  .method public hidebysig newslot abstract virtual 
          instance void  ScanCancel() cil managed
  {
  } // end of method IScanPictures::ScanCancel

  .method public hidebysig newslot abstract virtual 
          instance void  AdvanceFilm(int32 iAdvanceMilliseconds,
                                     int32 iAdvanceSpeed) cil managed
  {
  } // end of method IScanPictures::AdvanceFilm

  .method public hidebysig newslot abstract virtual 
          instance void  GetScannerInfo000([Interop.TLXLib]TLXLib.SCANNER_TYPE_000& iScannerType,
                                           int32& iScannerSerialNumber,
                                           valuetype Pakon.ScannerHW135& iHw135,
                                           valuetype Pakon.ScannerHW235& iHw235,
                                           valuetype Pakon.ScannerHW335& iHw335) cil managed
  {
  } // end of method IScanPictures::GetScannerInfo000

} // end of class Pakon.IScanPictures

.class public auto ansi beforefieldinit Pakon.ScannerScan
       extends [mscorlib]System.Object
       implements Pakon.IScanPictures
{
  .field private [Interop.TLXLib]TLXLib.TLXMainClass m_csTLX
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor([Interop.TLXLib]TLXLib.TLXMainClass csTLX) cil managed
  {
    // Code size       21 (0x15)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldnull
    IL_0002:  stfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerScan::m_csTLX
    IL_0007:  ldarg.0
    IL_0008:  call       instance void [mscorlib]System.Object::.ctor()
    IL_000d:  ldarg.0
    IL_000e:  ldarg.1
    IL_000f:  stfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerScan::m_csTLX
    IL_0014:  ret
  } // end of method ScannerScan::.ctor

  .method public hidebysig newslot virtual final 
          instance void  FocusCorrection([Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                         [Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor,
                                         [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                         bool bAdvanceFilm) cil managed
  {
    // Code size       25 (0x19)
    .maxstack  5
    .locals ([Interop.TLXLib]TLXLib.CALIBRATE_CONTROL_000 V_0)
    IL_0000:  ldarg.s    bAdvanceFilm
    IL_0002:  brtrue.s   IL_0007

    IL_0004:  ldc.i4.4
    IL_0005:  br.s       IL_0008

    IL_0007:  ldc.i4.8
    IL_0008:  stloc.0
    IL_0009:  ldarg.0
    IL_000a:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerScan::m_csTLX
    IL_000f:  ldarg.1
    IL_0010:  ldarg.2
    IL_0011:  ldarg.3
    IL_0012:  ldloc.0
    IL_0013:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::ForceCorrections(int32,
                                                                                             int32,
                                                                                             int32,
                                                                                             int32)
    IL_0018:  ret
  } // end of method ScannerScan::FocusCorrection

  .method public hidebysig newslot virtual final 
          instance void  LightCorrection([Interop.TLXLib]TLXLib.RESOLUTION_000 iResolution,
                                         [Interop.TLXLib]TLXLib.FILM_COLOR_000 iFilmColor,
                                         [Interop.TLXLib]TLXLib.FILM_FORMAT_000 iFilmFormat,
                                         bool bIR) cil managed
  {
    // Code size       30 (0x1e)
    .maxstack  5
    .locals ([Interop.TLXLib]TLXLib.CALIBRATE_CONTROL_000 V_0)
    IL_0000:  ldc.i4.1
    IL_0001:  stloc.0
    IL_0002:  ldarg.s    bIR
    IL_0004:  brfalse.s  IL_000e

    IL_0006:  ldloc.0
    IL_0007:  ldc.i4     0x80
    IL_000c:  or
    IL_000d:  stloc.0
    IL_000e:  ldarg.0
    IL_000f:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerScan::m_csTLX
    IL_0014:  ldarg.1
    IL_0015:  ldarg.2
    IL_0016:  ldarg.3
    IL_0017:  ldloc.0
    IL_0018:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::ForceCorrections(int32,
                                                                                             int32,
                                                                                             int32,
                                                                                             int32)
    IL_001d:  ret
  } // end of method ScannerScan::LightCorrection

  .method public hidebysig newslot virtual final 
          instance void  FilmTrackTest(bool bAdjustPots) cil managed
  {
    // Code size       22 (0x16)
    .maxstack  3
    .locals (int32 V_0)
    IL_0000:  ldarg.1
    IL_0001:  brtrue.s   IL_0006

    IL_0003:  ldc.i4.0
    IL_0004:  br.s       IL_0007

    IL_0006:  ldc.i4.1
    IL_0007:  stloc.0
    IL_0008:  ldarg.0
    IL_0009:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerScan::m_csTLX
    IL_000e:  ldloc.0
    IL_000f:  ldc.i4.1
    IL_0010:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::FilmTrackTest(int32,
                                                                                          int32)
    IL_0015:  ret
  } // end of method ScannerScan::FilmTrackTest

  .method public hidebysig newslot virtual final 
          instance int32  FilmTrackTestResults() cil managed
  {
    // Code size       12 (0xc)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerScan::m_csTLX
    IL_0006:  callvirt   instance int32 [Interop.TLXLib]TLXLib.TLXMainClass::FilmTrackTestResults()
    IL_000b:  ret
  } // end of method ScannerScan::FilmTrackTestResults

  .method public hidebysig newslot virtual final 
          instance void  ScanPictures([Interop.TLXLib]TLXLib.RESOLUTION_000 rResolution,
                                      [Interop.TLXLib]TLXLib.FILM_COLOR_000 fFilmColor,
                                      [Interop.TLXLib]TLXLib.FILM_FORMAT_000 fFilmFormat,
                                      [Interop.TLXLib]TLXLib.STRIP_MODE_000 smStripMode,
                                      [Interop.TLXLib]TLXLib.SCAN_CONTROL_000 scControl) cil managed
  {
    // Code size       40 (0x28)
    .maxstack  7
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2,
             int32 V_3,
             int32 V_4,
             string V_5)
    IL_0000:  ldarg.1
    IL_0001:  stloc.0
    IL_0002:  ldarg.2
    IL_0003:  stloc.1
    IL_0004:  ldarg.3
    IL_0005:  stloc.2
    IL_0006:  ldarg.s    smStripMode
    IL_0008:  stloc.3
    IL_0009:  ldarg.s    scControl
    IL_000b:  stloc.s    V_4
    IL_000d:  ldstr      "1000"
    IL_0012:  stloc.s    V_5
    IL_0014:  ldarg.0
    IL_0015:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerScan::m_csTLX
    IL_001a:  ldloc.0
    IL_001b:  ldloc.1
    IL_001c:  ldloc.2
    IL_001d:  ldloc.3
    IL_001e:  ldloc.s    V_4
    IL_0020:  ldloc.s    V_5
    IL_0022:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::ScanPictures(int32,
                                                                                         int32,
                                                                                         int32,
                                                                                         int32,
                                                                                         int32,
                                                                                         string)
    IL_0027:  ret
  } // end of method ScannerScan::ScanPictures

  .method public hidebysig newslot virtual final 
          instance void  ScanCancel() cil managed
  {
    // Code size       12 (0xc)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerScan::m_csTLX
    IL_0006:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::ScanCancel()
    IL_000b:  ret
  } // end of method ScannerScan::ScanCancel

  .method public hidebysig newslot virtual final 
          instance void  AdvanceFilm(int32 iAdvanceMilliseconds,
                                     int32 iAdvanceSpeed) cil managed
  {
    // Code size       14 (0xe)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerScan::m_csTLX
    IL_0006:  ldarg.1
    IL_0007:  ldarg.2
    IL_0008:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::AdvanceFilm(int32,
                                                                                        int32)
    IL_000d:  ret
  } // end of method ScannerScan::AdvanceFilm

  .method public hidebysig newslot virtual final 
          instance void  GetScannerInfo000([Interop.TLXLib]TLXLib.SCANNER_TYPE_000& iScannerType,
                                           int32& iScannerSerialNumber,
                                           valuetype Pakon.ScannerHW135& iHw135,
                                           valuetype Pakon.ScannerHW235& iHw235,
                                           valuetype Pakon.ScannerHW335& iHw335) cil managed
  {
    // Code size       93 (0x5d)
    .maxstack  13
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2,
             int32 V_3,
             int32 V_4,
             int32 V_5,
             int32 V_6,
             string V_7,
             string V_8,
             string V_9,
             string V_10)
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
    IL_0011:  ldstr      ""
    IL_0016:  stloc.s    V_7
    IL_0018:  ldstr      ""
    IL_001d:  stloc.s    V_8
    IL_001f:  ldstr      ""
    IL_0024:  stloc.s    V_9
    IL_0026:  ldstr      ""
    IL_002b:  stloc.s    V_10
    IL_002d:  ldarg.0
    IL_002e:  ldfld      [Interop.TLXLib]TLXLib.TLXMainClass Pakon.ScannerScan::m_csTLX
    IL_0033:  ldloca.s   V_0
    IL_0035:  ldloca.s   V_7
    IL_0037:  ldloca.s   V_8
    IL_0039:  ldarg.2
    IL_003a:  ldloca.s   V_1
    IL_003c:  ldloca.s   V_9
    IL_003e:  ldloca.s   V_2
    IL_0040:  ldloca.s   V_3
    IL_0042:  ldloca.s   V_4
    IL_0044:  ldloca.s   V_5
    IL_0046:  ldloca.s   V_6
    IL_0048:  ldloca.s   V_10
    IL_004a:  callvirt   instance void [Interop.TLXLib]TLXLib.TLXMainClass::GetScannerInfo000(int32&,
                                                                                              string&,
                                                                                              string&,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              string&,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              int32&,
                                                                                              string&)
    IL_004f:  ldloc.0
    IL_0050:  ldloc.1
    IL_0051:  ldarg.1
    IL_0052:  ldarg.3
    IL_0053:  ldarg.s    iHw235
    IL_0055:  ldarg.s    iHw335
    IL_0057:  call       void Pakon.Global::Convert(int32,
                                                    int32,
                                                    [Interop.TLXLib]TLXLib.SCANNER_TYPE_000&,
                                                    valuetype Pakon.ScannerHW135&,
                                                    valuetype Pakon.ScannerHW235&,
                                                    valuetype Pakon.ScannerHW335&)
    IL_005c:  ret
  } // end of method ScannerScan::GetScannerInfo000

} // end of class Pakon.ScannerScan

.class public auto ansi beforefieldinit Pakon.ScannerSettings
       extends [mscorlib]System.Object
{
  .custom instance void [mscorlib]System.Reflection.DefaultMemberAttribute::.ctor(string) = ( 01 00 04 49 74 65 6D 00 00 )                      // ...Item..
  .field private class Pakon.ScannerSettingsSave m_csScannerSettingsSave
  .field family valuetype Pakon.ScannerInitializeWarnings m_iwScanner
  .field family [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 m_stType
  .field family int32 m_nSerialNumber
  .field family valuetype Pakon.ScannerHW135 m_sh135
  .field family valuetype Pakon.ScannerHW235 m_sh235
  .field family valuetype Pakon.ScannerHW335 m_sh335
  .field private class Pakon.IntBits m_capabilities
  .method public hidebysig specialname instance valuetype Pakon.ScannerInitializeWarnings 
          get_InitializeWarnings() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Pakon.ScannerInitializeWarnings Pakon.ScannerSettings::m_iwScanner
    IL_0006:  ret
  } // end of method ScannerSettings::get_InitializeWarnings

  .method public hidebysig specialname instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 
          get_Type() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::m_stType
    IL_0006:  ret
  } // end of method ScannerSettings::get_Type

  .method public hidebysig specialname instance int32 
          get_SerialNumber() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      int32 Pakon.ScannerSettings::m_nSerialNumber
    IL_0006:  ret
  } // end of method ScannerSettings::get_SerialNumber

  .method public hidebysig specialname instance valuetype Pakon.ScannerHW135 
          get_Hardware135() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Pakon.ScannerHW135 Pakon.ScannerSettings::m_sh135
    IL_0006:  ret
  } // end of method ScannerSettings::get_Hardware135

  .method public hidebysig specialname instance valuetype Pakon.ScannerHW235 
          get_Hardware235() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Pakon.ScannerHW235 Pakon.ScannerSettings::m_sh235
    IL_0006:  ret
  } // end of method ScannerSettings::get_Hardware235

  .method public hidebysig specialname instance valuetype Pakon.ScannerHW335 
          get_Hardware335() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Pakon.ScannerHW335 Pakon.ScannerSettings::m_sh335
    IL_0006:  ret
  } // end of method ScannerSettings::get_Hardware335

  .method public hidebysig specialname instance bool 
          get_Item(valuetype Pakon.ScannerCapabilities iCapability) cil managed
  {
    // Code size       23 (0x17)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0006:  brtrue.s   IL_000a

    IL_0008:  ldc.i4.0
    IL_0009:  ret

    IL_000a:  ldarg.0
    IL_000b:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0010:  ldarg.1
    IL_0011:  callvirt   instance bool Pakon.IntBits::get_Item(int32)
    IL_0016:  ret
  } // end of method ScannerSettings::get_Item

  .method public hidebysig specialname instance class Pakon.ScannerSettingsSave 
          get_Save() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      class Pakon.ScannerSettingsSave Pakon.ScannerSettings::m_csScannerSettingsSave
    IL_0006:  ret
  } // end of method ScannerSettings::get_Save

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       74 (0x4a)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  ldnull
    IL_0002:  stfld      class Pakon.ScannerSettingsSave Pakon.ScannerSettings::m_csScannerSettingsSave
    IL_0007:  ldarg.0
    IL_0008:  ldc.i4.m1
    IL_0009:  stfld      valuetype Pakon.ScannerInitializeWarnings Pakon.ScannerSettings::m_iwScanner
    IL_000e:  ldarg.0
    IL_000f:  ldc.i4.0
    IL_0010:  stfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::m_stType
    IL_0015:  ldarg.0
    IL_0016:  ldc.i4.0
    IL_0017:  stfld      int32 Pakon.ScannerSettings::m_nSerialNumber
    IL_001c:  ldarg.0
    IL_001d:  ldc.i4.0
    IL_001e:  stfld      valuetype Pakon.ScannerHW135 Pakon.ScannerSettings::m_sh135
    IL_0023:  ldarg.0
    IL_0024:  ldc.i4.0
    IL_0025:  stfld      valuetype Pakon.ScannerHW235 Pakon.ScannerSettings::m_sh235
    IL_002a:  ldarg.0
    IL_002b:  ldc.i4.0
    IL_002c:  stfld      valuetype Pakon.ScannerHW335 Pakon.ScannerSettings::m_sh335
    IL_0031:  ldarg.0
    IL_0032:  ldnull
    IL_0033:  stfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0038:  ldarg.0
    IL_0039:  call       instance void [mscorlib]System.Object::.ctor()
    IL_003e:  ldarg.0
    IL_003f:  newobj     instance void Pakon.ScannerSettingsSave::.ctor()
    IL_0044:  stfld      class Pakon.ScannerSettingsSave Pakon.ScannerSettings::m_csScannerSettingsSave
    IL_0049:  ret
  } // end of method ScannerSettings::.ctor

  .method public hidebysig newslot virtual 
          instance void  Reset() cil managed
  {
    // Code size       50 (0x32)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.m1
    IL_0002:  stfld      valuetype Pakon.ScannerInitializeWarnings Pakon.ScannerSettings::m_iwScanner
    IL_0007:  ldarg.0
    IL_0008:  ldc.i4.0
    IL_0009:  stfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::m_stType
    IL_000e:  ldarg.0
    IL_000f:  ldc.i4.0
    IL_0010:  stfld      int32 Pakon.ScannerSettings::m_nSerialNumber
    IL_0015:  ldarg.0
    IL_0016:  ldc.i4.0
    IL_0017:  stfld      valuetype Pakon.ScannerHW135 Pakon.ScannerSettings::m_sh135
    IL_001c:  ldarg.0
    IL_001d:  ldc.i4.0
    IL_001e:  stfld      valuetype Pakon.ScannerHW235 Pakon.ScannerSettings::m_sh235
    IL_0023:  ldarg.0
    IL_0024:  ldc.i4.0
    IL_0025:  stfld      valuetype Pakon.ScannerHW335 Pakon.ScannerSettings::m_sh335
    IL_002a:  ldarg.0
    IL_002b:  ldnull
    IL_002c:  stfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0031:  ret
  } // end of method ScannerSettings::Reset

  .method family hidebysig instance void 
          SetCapabilities() cil managed
  {
    // Code size       944 (0x3b0)
    .maxstack  3
    .locals ([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_0)
    IL_0000:  ldarg.0
    IL_0001:  newobj     instance void Pakon.IntBits::.ctor()
    IL_0006:  stfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_000b:  ldarg.0
    IL_000c:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::get_Type()
    IL_0011:  stloc.0
    IL_0012:  ldloc.0
    IL_0013:  ldc.i4.7
    IL_0014:  sub
    IL_0015:  switch     ( 
                          IL_004b,
                          IL_010b)
    IL_0022:  ldloc.0
    IL_0023:  ldc.i4     0x546
    IL_0028:  sub
    IL_0029:  switch     ( 
                          IL_01e6,
                          IL_021e)
    IL_0036:  ldloc.0
    IL_0037:  ldc.i4     0xd16
    IL_003c:  sub
    IL_003d:  switch     ( 
                          IL_0256,
                          IL_02fc)
    IL_004a:  ret

    IL_004b:  ldarg.0
    IL_004c:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0051:  ldc.i4.s   26
    IL_0053:  ldc.i4.1
    IL_0054:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0059:  ldarg.0
    IL_005a:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_005f:  ldc.i4.s   27
    IL_0061:  ldc.i4.1
    IL_0062:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0067:  ldarg.0
    IL_0068:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_006d:  ldc.i4.s   28
    IL_006f:  ldc.i4.1
    IL_0070:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0075:  ldarg.0
    IL_0076:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_007b:  ldc.i4.s   22
    IL_007d:  ldc.i4.1
    IL_007e:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0083:  ldarg.0
    IL_0084:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0089:  ldc.i4.s   23
    IL_008b:  ldc.i4.1
    IL_008c:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0091:  ldarg.0
    IL_0092:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0097:  ldc.i4.s   24
    IL_0099:  ldc.i4.1
    IL_009a:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_009f:  ldarg.0
    IL_00a0:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_00a5:  ldc.i4.s   29
    IL_00a7:  ldc.i4.1
    IL_00a8:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_00ad:  ldarg.0
    IL_00ae:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_00b3:  ldc.i4.s   30
    IL_00b5:  ldc.i4.1
    IL_00b6:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_00bb:  ldarg.0
    IL_00bc:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_00c1:  ldc.i4.s   31
    IL_00c3:  ldc.i4.1
    IL_00c4:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_00c9:  ldarg.0
    IL_00ca:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_00cf:  ldc.i4.0
    IL_00d0:  ldc.i4.1
    IL_00d1:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_00d6:  ldarg.0
    IL_00d7:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_00dc:  ldc.i4.2
    IL_00dd:  ldc.i4.1
    IL_00de:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_00e3:  ldarg.0
    IL_00e4:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_00e9:  ldc.i4.4
    IL_00ea:  ldc.i4.1
    IL_00eb:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_00f0:  ldarg.0
    IL_00f1:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_00f6:  ldc.i4.3
    IL_00f7:  ldc.i4.1
    IL_00f8:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_00fd:  ldarg.0
    IL_00fe:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0103:  ldc.i4.7
    IL_0104:  ldc.i4.1
    IL_0105:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_010a:  ret

    IL_010b:  ldarg.0
    IL_010c:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0111:  ldc.i4.s   26
    IL_0113:  ldc.i4.1
    IL_0114:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0119:  ldarg.0
    IL_011a:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_011f:  ldc.i4.s   27
    IL_0121:  ldc.i4.1
    IL_0122:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0127:  ldarg.0
    IL_0128:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_012d:  ldc.i4.s   28
    IL_012f:  ldc.i4.1
    IL_0130:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0135:  ldarg.0
    IL_0136:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_013b:  ldc.i4.s   22
    IL_013d:  ldc.i4.1
    IL_013e:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0143:  ldarg.0
    IL_0144:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0149:  ldc.i4.s   23
    IL_014b:  ldc.i4.1
    IL_014c:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0151:  ldarg.0
    IL_0152:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0157:  ldc.i4.s   24
    IL_0159:  ldc.i4.1
    IL_015a:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_015f:  ldarg.0
    IL_0160:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0165:  ldc.i4.s   25
    IL_0167:  ldc.i4.1
    IL_0168:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_016d:  ldarg.0
    IL_016e:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0173:  ldc.i4.s   29
    IL_0175:  ldc.i4.1
    IL_0176:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_017b:  ldarg.0
    IL_017c:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0181:  ldc.i4.s   30
    IL_0183:  ldc.i4.1
    IL_0184:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0189:  ldarg.0
    IL_018a:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_018f:  ldc.i4.s   31
    IL_0191:  ldc.i4.1
    IL_0192:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0197:  ldarg.0
    IL_0198:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_019d:  ldc.i4.0
    IL_019e:  ldc.i4.1
    IL_019f:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_01a4:  ldarg.0
    IL_01a5:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_01aa:  ldc.i4.2
    IL_01ab:  ldc.i4.1
    IL_01ac:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_01b1:  ldarg.0
    IL_01b2:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_01b7:  ldc.i4.4
    IL_01b8:  ldc.i4.1
    IL_01b9:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_01be:  ldarg.0
    IL_01bf:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_01c4:  ldc.i4.3
    IL_01c5:  ldc.i4.1
    IL_01c6:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_01cb:  ldarg.0
    IL_01cc:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_01d1:  ldc.i4.5
    IL_01d2:  ldc.i4.1
    IL_01d3:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_01d8:  ldarg.0
    IL_01d9:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_01de:  ldc.i4.7
    IL_01df:  ldc.i4.1
    IL_01e0:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_01e5:  ret

    IL_01e6:  ldarg.0
    IL_01e7:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_01ec:  ldc.i4.s   29
    IL_01ee:  ldc.i4.1
    IL_01ef:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_01f4:  ldarg.0
    IL_01f5:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_01fa:  ldc.i4.s   30
    IL_01fc:  ldc.i4.1
    IL_01fd:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0202:  ldarg.0
    IL_0203:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0208:  ldc.i4.s   31
    IL_020a:  ldc.i4.1
    IL_020b:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0210:  ldarg.0
    IL_0211:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0216:  ldc.i4.6
    IL_0217:  ldc.i4.1
    IL_0218:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_021d:  ret

    IL_021e:  ldarg.0
    IL_021f:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0224:  ldc.i4.s   29
    IL_0226:  ldc.i4.1
    IL_0227:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_022c:  ldarg.0
    IL_022d:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0232:  ldc.i4.s   30
    IL_0234:  ldc.i4.1
    IL_0235:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_023a:  ldarg.0
    IL_023b:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0240:  ldc.i4.s   31
    IL_0242:  ldc.i4.1
    IL_0243:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0248:  ldarg.0
    IL_0249:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_024e:  ldc.i4.6
    IL_024f:  ldc.i4.1
    IL_0250:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0255:  ret

    IL_0256:  ldarg.0
    IL_0257:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_025c:  ldc.i4.s   26
    IL_025e:  ldc.i4.1
    IL_025f:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0264:  ldarg.0
    IL_0265:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_026a:  ldc.i4.s   27
    IL_026c:  ldc.i4.1
    IL_026d:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0272:  ldarg.0
    IL_0273:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0278:  ldc.i4.s   28
    IL_027a:  ldc.i4.1
    IL_027b:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0280:  ldarg.0
    IL_0281:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0286:  ldc.i4.s   22
    IL_0288:  ldc.i4.1
    IL_0289:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_028e:  ldarg.0
    IL_028f:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0294:  ldc.i4.s   23
    IL_0296:  ldc.i4.1
    IL_0297:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_029c:  ldarg.0
    IL_029d:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_02a2:  ldc.i4.s   24
    IL_02a4:  ldc.i4.1
    IL_02a5:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_02aa:  ldarg.0
    IL_02ab:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_02b0:  ldc.i4.s   29
    IL_02b2:  ldc.i4.1
    IL_02b3:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_02b8:  ldarg.0
    IL_02b9:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_02be:  ldc.i4.s   30
    IL_02c0:  ldc.i4.1
    IL_02c1:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_02c6:  ldarg.0
    IL_02c7:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_02cc:  ldc.i4.s   31
    IL_02ce:  ldc.i4.1
    IL_02cf:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_02d4:  ldarg.0
    IL_02d5:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_02da:  ldc.i4.2
    IL_02db:  ldc.i4.1
    IL_02dc:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_02e1:  ldarg.0
    IL_02e2:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_02e7:  ldc.i4.4
    IL_02e8:  ldc.i4.1
    IL_02e9:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_02ee:  ldarg.0
    IL_02ef:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_02f4:  ldc.i4.3
    IL_02f5:  ldc.i4.1
    IL_02f6:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_02fb:  ret

    IL_02fc:  ldarg.0
    IL_02fd:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0302:  ldc.i4.s   26
    IL_0304:  ldc.i4.1
    IL_0305:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_030a:  ldarg.0
    IL_030b:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0310:  ldc.i4.s   27
    IL_0312:  ldc.i4.1
    IL_0313:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0318:  ldarg.0
    IL_0319:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_031e:  ldc.i4.s   28
    IL_0320:  ldc.i4.1
    IL_0321:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0326:  ldarg.0
    IL_0327:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_032c:  ldc.i4.s   22
    IL_032e:  ldc.i4.1
    IL_032f:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0334:  ldarg.0
    IL_0335:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_033a:  ldc.i4.s   23
    IL_033c:  ldc.i4.1
    IL_033d:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0342:  ldarg.0
    IL_0343:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0348:  ldc.i4.s   24
    IL_034a:  ldc.i4.1
    IL_034b:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0350:  ldarg.0
    IL_0351:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0356:  ldc.i4.s   25
    IL_0358:  ldc.i4.1
    IL_0359:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_035e:  ldarg.0
    IL_035f:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0364:  ldc.i4.s   29
    IL_0366:  ldc.i4.1
    IL_0367:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_036c:  ldarg.0
    IL_036d:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0372:  ldc.i4.s   30
    IL_0374:  ldc.i4.1
    IL_0375:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_037a:  ldarg.0
    IL_037b:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_0380:  ldc.i4.s   31
    IL_0382:  ldc.i4.1
    IL_0383:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0388:  ldarg.0
    IL_0389:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_038e:  ldc.i4.2
    IL_038f:  ldc.i4.1
    IL_0390:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_0395:  ldarg.0
    IL_0396:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_039b:  ldc.i4.4
    IL_039c:  ldc.i4.1
    IL_039d:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_03a2:  ldarg.0
    IL_03a3:  ldfld      class Pakon.IntBits Pakon.ScannerSettings::m_capabilities
    IL_03a8:  ldc.i4.3
    IL_03a9:  ldc.i4.1
    IL_03aa:  callvirt   instance void Pakon.IntBits::set_Item(int32,
                                                               bool)
    IL_03af:  ret
  } // end of method ScannerSettings::SetCapabilities

  .method public hidebysig instance void 
          SetScannerType([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 stNewType) cil managed
  {
    // Code size       172 (0xac)
    .maxstack  2
    .locals ([Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_0)
    IL_0000:  ldarg.0
    IL_0001:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::get_Type()
    IL_0006:  stloc.0
    IL_0007:  ldloc.0
    IL_0008:  ldc.i4.8
    IL_0009:  bgt.s      IL_0024

    IL_000b:  ldloc.0
    IL_000c:  ldc.i4.0
    IL_000d:  beq.s      IL_004e

    IL_000f:  ldloc.0
    IL_0010:  ldc.i4.7
    IL_0011:  sub
    IL_0012:  switch     ( 
                          IL_0062,
                          IL_0062)
    IL_001f:  br         IL_00a4

    IL_0024:  ldloc.0
    IL_0025:  ldc.i4     0x546
    IL_002a:  sub
    IL_002b:  switch     ( 
                          IL_004e,
                          IL_004e)
    IL_0038:  ldloc.0
    IL_0039:  ldc.i4     0xd16
    IL_003e:  sub
    IL_003f:  switch     ( 
                          IL_007f,
                          IL_007f)
    IL_004c:  br.s       IL_00a4

    IL_004e:  ldarg.0
    IL_004f:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::m_stType
    IL_0054:  ldarg.1
    IL_0055:  beq.s      IL_00a4

    IL_0057:  ldstr      "Scanner type change not allowed"
    IL_005c:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0061:  throw

    IL_0062:  ldarg.0
    IL_0063:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::m_stType
    IL_0068:  ldc.i4.7
    IL_0069:  beq.s      IL_00a4

    IL_006b:  ldarg.0
    IL_006c:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::m_stType
    IL_0071:  ldc.i4.8
    IL_0072:  beq.s      IL_00a4

    IL_0074:  ldstr      "Scanner type change not allowed"
    IL_0079:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_007e:  throw

    IL_007f:  ldarg.0
    IL_0080:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::m_stType
    IL_0085:  ldc.i4     0xd16
    IL_008a:  beq.s      IL_00a4

    IL_008c:  ldarg.0
    IL_008d:  ldfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::m_stType
    IL_0092:  ldc.i4     0xd17
    IL_0097:  beq.s      IL_00a4

    IL_0099:  ldstr      "Scanner type change not allowed"
    IL_009e:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_00a3:  throw

    IL_00a4:  ldarg.0
    IL_00a5:  ldarg.1
    IL_00a6:  stfld      [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::m_stType
    IL_00ab:  ret
  } // end of method ScannerSettings::SetScannerType

  .method public hidebysig instance void 
          CompleteTLXInitialization(class Pakon.Scanner csScanner) cil managed
  {
    // Code size       60 (0x3c)
    .maxstack  8
    IL_0000:  ldarg.1
    IL_0001:  ldarg.0
    IL_0002:  ldflda     valuetype Pakon.ScannerInitializeWarnings Pakon.ScannerSettings::m_iwScanner
    IL_0007:  callvirt   instance void Pakon.Scanner::GetInitializeWarnings(valuetype Pakon.ScannerInitializeWarnings&)
    IL_000c:  ldarg.1
    IL_000d:  callvirt   instance class Pakon.IScanPictures Pakon.Scanner::get_IScan()
    IL_0012:  ldarg.0
    IL_0013:  ldflda     [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::m_stType
    IL_0018:  ldarg.0
    IL_0019:  ldflda     int32 Pakon.ScannerSettings::m_nSerialNumber
    IL_001e:  ldarg.0
    IL_001f:  ldflda     valuetype Pakon.ScannerHW135 Pakon.ScannerSettings::m_sh135
    IL_0024:  ldarg.0
    IL_0025:  ldflda     valuetype Pakon.ScannerHW235 Pakon.ScannerSettings::m_sh235
    IL_002a:  ldarg.0
    IL_002b:  ldflda     valuetype Pakon.ScannerHW335 Pakon.ScannerSettings::m_sh335
    IL_0030:  callvirt   instance void Pakon.IScanPictures::GetScannerInfo000([Interop.TLXLib]TLXLib.SCANNER_TYPE_000&,
                                                                              int32&,
                                                                              valuetype Pakon.ScannerHW135&,
                                                                              valuetype Pakon.ScannerHW235&,
                                                                              valuetype Pakon.ScannerHW335&)
    IL_0035:  ldarg.0
    IL_0036:  call       instance void Pakon.ScannerSettings::SetCapabilities()
    IL_003b:  ret
  } // end of method ScannerSettings::CompleteTLXInitialization

  .method public hidebysig instance void 
          OpenTLX(class Pakon.Scanner csScanner) cil managed
  {
    // Code size       14 (0xe)
    .maxstack  2
    .locals ([Interop.TLXLib]TLXLib.INITIALIZE_CONTROL_000 V_0)
    IL_0000:  ldc.i4     0x40000001
    IL_0005:  stloc.0
    IL_0006:  ldarg.1
    IL_0007:  ldloc.0
    IL_0008:  callvirt   instance void Pakon.Scanner::InitializeTLX([Interop.TLXLib]TLXLib.INITIALIZE_CONTROL_000)
    IL_000d:  ret
  } // end of method ScannerSettings::OpenTLX

  .method public hidebysig instance void 
          CloseTLX(class Pakon.Scanner csScanner) cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.1
    IL_0001:  callvirt   instance void Pakon.Scanner::CBUnadviseTLX()
    IL_0006:  ret
  } // end of method ScannerSettings::CloseTLX

  .method public hidebysig instance int32 
          GetResolutionHeight(class Pakon.Scanner csScanner,
                              [Interop.TLXLib]TLXLib.RESOLUTION_000 srResolution,
                              [Interop.TLXLib]TLXLib.FILM_FORMAT_000 ffFormat) cil managed
  {
    // Code size       14 (0xe)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::get_Type()
    IL_0006:  ldarg.2
    IL_0007:  ldarg.3
    IL_0008:  call       int32 Pakon.Global::GetResolutionHeight([Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                 [Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                 [Interop.TLXLib]TLXLib.FILM_FORMAT_000)
    IL_000d:  ret
  } // end of method ScannerSettings::GetResolutionHeight

  .method public hidebysig instance void 
          Scan(class Pakon.Scanner csScanner) cil managed
  {
    // Code size       108 (0x6c)
    .maxstack  6
    .locals ([Interop.TLXLib]TLXLib.FILM_COLOR_000 V_0,
             [Interop.TLXLib]TLXLib.FILM_FORMAT_000 V_1,
             [Interop.TLXLib]TLXLib.RESOLUTION_000 V_2,
             [Interop.TLXLib]TLXLib.STRIP_MODE_000 V_3,
             [Interop.TLXLib]TLXLib.SCAN_CONTROL_000 V_4,
             [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_5)
    IL_0000:  ldc.i4.1
    IL_0001:  stloc.0
    IL_0002:  ldc.i4.1
    IL_0003:  stloc.1
    IL_0004:  ldc.i4.0
    IL_0005:  stloc.2
    IL_0006:  ldc.i4.0
    IL_0007:  stloc.3
    IL_0008:  ldc.i4.0
    IL_0009:  stloc.s    V_4
    IL_000b:  ldarg.0
    IL_000c:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::get_Type()
    IL_0011:  stloc.s    V_5
    IL_0013:  ldloc.s    V_5
    IL_0015:  ldc.i4.7
    IL_0016:  sub
    IL_0017:  switch     ( 
                          IL_0054,
                          IL_0054)
    IL_0024:  ldloc.s    V_5
    IL_0026:  ldc.i4     0x546
    IL_002b:  sub
    IL_002c:  switch     ( 
                          IL_0050,
                          IL_0054)
    IL_0039:  ldloc.s    V_5
    IL_003b:  ldc.i4     0xd16
    IL_0040:  sub
    IL_0041:  switch     ( 
                          IL_0058,
                          IL_0058)
    IL_004e:  br.s       IL_005a

    IL_0050:  ldc.i4.0
    IL_0051:  stloc.2
    IL_0052:  br.s       IL_005a

    IL_0054:  ldc.i4.1
    IL_0055:  stloc.2
    IL_0056:  br.s       IL_005a

    IL_0058:  ldc.i4.1
    IL_0059:  stloc.2
    IL_005a:  ldarg.1
    IL_005b:  callvirt   instance class Pakon.IScanPictures Pakon.Scanner::get_IScan()
    IL_0060:  ldloc.2
    IL_0061:  ldloc.0
    IL_0062:  ldloc.1
    IL_0063:  ldloc.3
    IL_0064:  ldloc.s    V_4
    IL_0066:  callvirt   instance void Pakon.IScanPictures::ScanPictures([Interop.TLXLib]TLXLib.RESOLUTION_000,
                                                                         [Interop.TLXLib]TLXLib.FILM_COLOR_000,
                                                                         [Interop.TLXLib]TLXLib.FILM_FORMAT_000,
                                                                         [Interop.TLXLib]TLXLib.STRIP_MODE_000,
                                                                         [Interop.TLXLib]TLXLib.SCAN_CONTROL_000)
    IL_006b:  ret
  } // end of method ScannerSettings::Scan

  .method public hidebysig instance void 
          EjectFilm(class Pakon.Scanner csScanner) cil managed
  {
    // Code size       123 (0x7b)
    .maxstack  3
    .locals (int32 V_0,
             int32 V_1,
             [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 V_2)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldc.i4.0
    IL_0003:  stloc.1
    IL_0004:  ldarg.0
    IL_0005:  call       instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::get_Type()
    IL_000a:  stloc.2
    IL_000b:  ldloc.2
    IL_000c:  ldc.i4.7
    IL_000d:  sub
    IL_000e:  switch     ( 
                          IL_0053,
                          IL_0053)
    IL_001b:  ldloc.2
    IL_001c:  ldc.i4     0x546
    IL_0021:  sub
    IL_0022:  switch     ( 
                          IL_0045,
                          IL_0045)
    IL_002f:  ldloc.2
    IL_0030:  ldc.i4     0xd16
    IL_0035:  sub
    IL_0036:  switch     ( 
                          IL_0061,
                          IL_0061)
    IL_0043:  br.s       IL_006d

    IL_0045:  ldc.i4     0x1f4
    IL_004a:  stloc.0
    IL_004b:  ldc.i4     0x3e8
    IL_0050:  stloc.1
    IL_0051:  br.s       IL_006d

    IL_0053:  ldc.i4     0x1388
    IL_0058:  stloc.0
    IL_0059:  ldc.i4     0x3e8
    IL_005e:  stloc.1
    IL_005f:  br.s       IL_006d

    IL_0061:  ldc.i4     0x1388
    IL_0066:  stloc.0
    IL_0067:  ldc.i4     0x3e8
    IL_006c:  stloc.1
    IL_006d:  ldarg.1
    IL_006e:  callvirt   instance class Pakon.IScanPictures Pakon.Scanner::get_IScan()
    IL_0073:  ldloc.0
    IL_0074:  ldloc.1
    IL_0075:  callvirt   instance void Pakon.IScanPictures::AdvanceFilm(int32,
                                                                        int32)
    IL_007a:  ret
  } // end of method ScannerSettings::EjectFilm

  .property instance valuetype Pakon.ScannerInitializeWarnings
          InitializeWarnings()
  {
    .get instance valuetype Pakon.ScannerInitializeWarnings Pakon.ScannerSettings::get_InitializeWarnings()
  } // end of property ScannerSettings::InitializeWarnings
  .property instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000
          Type()
  {
    .get instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::get_Type()
  } // end of property ScannerSettings::Type
  .property instance int32 SerialNumber()
  {
    .get instance int32 Pakon.ScannerSettings::get_SerialNumber()
  } // end of property ScannerSettings::SerialNumber
  .property instance valuetype Pakon.ScannerHW135
          Hardware135()
  {
    .get instance valuetype Pakon.ScannerHW135 Pakon.ScannerSettings::get_Hardware135()
  } // end of property ScannerSettings::Hardware135
  .property instance valuetype Pakon.ScannerHW235
          Hardware235()
  {
    .get instance valuetype Pakon.ScannerHW235 Pakon.ScannerSettings::get_Hardware235()
  } // end of property ScannerSettings::Hardware235
  .property instance valuetype Pakon.ScannerHW335
          Hardware335()
  {
    .get instance valuetype Pakon.ScannerHW335 Pakon.ScannerSettings::get_Hardware335()
  } // end of property ScannerSettings::Hardware335
  .property instance bool Item(valuetype Pakon.ScannerCapabilities)
  {
    .get instance bool Pakon.ScannerSettings::get_Item(valuetype Pakon.ScannerCapabilities)
  } // end of property ScannerSettings::Item
  .property instance class Pakon.ScannerSettingsSave
          Save()
  {
    .get instance class Pakon.ScannerSettingsSave Pakon.ScannerSettings::get_Save()
  } // end of property ScannerSettings::Save
} // end of class Pakon.ScannerSettings

.class public auto ansi sealed Pakon.AddPictureToSaveGroup
       extends [mscorlib]System.MulticastDelegate
{
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(object 'object',
                               native int 'method') runtime managed
  {
  } // end of method AddPictureToSaveGroup::.ctor

  .method public hidebysig virtual instance void 
          Invoke(int32 nIndex) runtime managed
  {
  } // end of method AddPictureToSaveGroup::Invoke

  .method public hidebysig newslot virtual 
          instance [mscorlib]System.IAsyncResult 
          BeginInvoke(int32 nIndex,
                      [mscorlib]System.AsyncCallback callback,
                      object 'object') runtime managed
  {
  } // end of method AddPictureToSaveGroup::BeginInvoke

  .method public hidebysig newslot virtual 
          instance void  EndInvoke([mscorlib]System.IAsyncResult result) runtime managed
  {
  } // end of method AddPictureToSaveGroup::EndInvoke

} // end of class Pakon.AddPictureToSaveGroup

.class public auto ansi beforefieldinit Pakon.ScannerSettingsSave
       extends [mscorlib]System.Object
{
  .field private class Pakon.AddPictureToSaveGroup m_evAddPictureToSaveGroup
  .field private [Interop.TLXLib]TLXLib.INDEX_000 m_eIndex
  .field private [Interop.TLXLib]TLXLib.SAVE_CONTROL_000 m_eSaveControl
  .field private [Interop.TLXLib]TLXLib.SCALING_METHOD_000 m_eScalingMethod
  .field private [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 m_eMemoryFormat
  .method public hidebysig specialname instance void 
          add_m_evAddPictureToSaveGroup(class Pakon.AddPictureToSaveGroup 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Pakon.AddPictureToSaveGroup Pakon.ScannerSettingsSave::m_evAddPictureToSaveGroup
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  Pakon.AddPictureToSaveGroup
    IL_0012:  stfld      class Pakon.AddPictureToSaveGroup Pakon.ScannerSettingsSave::m_evAddPictureToSaveGroup
    IL_0017:  ret
  } // end of method ScannerSettingsSave::add_m_evAddPictureToSaveGroup

  .method public hidebysig specialname instance void 
          remove_m_evAddPictureToSaveGroup(class Pakon.AddPictureToSaveGroup 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Pakon.AddPictureToSaveGroup Pakon.ScannerSettingsSave::m_evAddPictureToSaveGroup
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  Pakon.AddPictureToSaveGroup
    IL_0012:  stfld      class Pakon.AddPictureToSaveGroup Pakon.ScannerSettingsSave::m_evAddPictureToSaveGroup
    IL_0017:  ret
  } // end of method ScannerSettingsSave::remove_m_evAddPictureToSaveGroup

  .method public hidebysig specialname instance [Interop.TLXLib]TLXLib.INDEX_000 
          get_Index() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.INDEX_000 Pakon.ScannerSettingsSave::m_eIndex
    IL_0006:  ret
  } // end of method ScannerSettingsSave::get_Index

  .method public hidebysig specialname instance void 
          set_Index([Interop.TLXLib]TLXLib.INDEX_000 'value') cil managed
  {
    // Code size       8 (0x8)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      [Interop.TLXLib]TLXLib.INDEX_000 Pakon.ScannerSettingsSave::m_eIndex
    IL_0007:  ret
  } // end of method ScannerSettingsSave::set_Index

  .method public hidebysig specialname instance [Interop.TLXLib]TLXLib.SAVE_CONTROL_000 
          get_Control() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.SAVE_CONTROL_000 Pakon.ScannerSettingsSave::m_eSaveControl
    IL_0006:  ret
  } // end of method ScannerSettingsSave::get_Control

  .method public hidebysig specialname instance void 
          set_Control([Interop.TLXLib]TLXLib.SAVE_CONTROL_000 'value') cil managed
  {
    // Code size       8 (0x8)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      [Interop.TLXLib]TLXLib.SAVE_CONTROL_000 Pakon.ScannerSettingsSave::m_eSaveControl
    IL_0007:  ret
  } // end of method ScannerSettingsSave::set_Control

  .method public hidebysig specialname instance [Interop.TLXLib]TLXLib.SCALING_METHOD_000 
          get_ScalingMethod() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.SCALING_METHOD_000 Pakon.ScannerSettingsSave::m_eScalingMethod
    IL_0006:  ret
  } // end of method ScannerSettingsSave::get_ScalingMethod

  .method public hidebysig specialname instance void 
          set_ScalingMethod([Interop.TLXLib]TLXLib.SCALING_METHOD_000 'value') cil managed
  {
    // Code size       8 (0x8)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      [Interop.TLXLib]TLXLib.SCALING_METHOD_000 Pakon.ScannerSettingsSave::m_eScalingMethod
    IL_0007:  ret
  } // end of method ScannerSettingsSave::set_ScalingMethod

  .method public hidebysig specialname instance [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 
          get_MemoryFormat() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 Pakon.ScannerSettingsSave::m_eMemoryFormat
    IL_0006:  ret
  } // end of method ScannerSettingsSave::get_MemoryFormat

  .method public hidebysig specialname instance void 
          set_MemoryFormat([Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 'value') cil managed
  {
    // Code size       8 (0x8)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 Pakon.ScannerSettingsSave::m_eMemoryFormat
    IL_0007:  ret
  } // end of method ScannerSettingsSave::set_MemoryFormat

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0006:  ret
  } // end of method ScannerSettingsSave::.ctor

  .method public hidebysig instance void 
          MoveRollToSaveGroup(class Pakon.Scanner csScanner) cil managed
  {
    // Code size       102 (0x66)
    .maxstack  6
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2,
             int32 V_3)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldc.i4.0
    IL_0003:  stloc.1
    IL_0004:  ldc.i4.0
    IL_0005:  stloc.2
    IL_0006:  ldarg.1
    IL_0007:  callvirt   instance class Pakon.ISavePictures Pakon.Scanner::get_ISave()
    IL_000c:  ldloca.s   V_0
    IL_000e:  ldloca.s   V_0
    IL_0010:  ldloca.s   V_1
    IL_0012:  ldloca.s   V_0
    IL_0014:  ldloca.s   V_0
    IL_0016:  callvirt   instance void Pakon.ISavePictures::GetPictureCountSaveGroup(int32&,
                                                                                     int32&,
                                                                                     int32&,
                                                                                     int32&,
                                                                                     int32&)
    IL_001b:  ldloc.1
    IL_001c:  ldc.i4.0
    IL_001d:  ble.s      IL_002e

    IL_001f:  ldarg.1
    IL_0020:  callvirt   instance class Pakon.ISavePictures Pakon.Scanner::get_ISave()
    IL_0025:  ldc.i4.s   -3
    IL_0027:  ldc.i4.0
    IL_0028:  ldc.i4.1
    IL_0029:  callvirt   instance void Pakon.ISavePictures::PutPictureSelection([Interop.TLXLib]TLXLib.INDEX_000,
                                                                                [Interop.TLXLib]TLXLib.S_OR_H_000,
                                                                                bool)
    IL_002e:  ldarg.1
    IL_002f:  callvirt   instance class Pakon.ISavePictures Pakon.Scanner::get_ISave()
    IL_0034:  ldc.i4.0
    IL_0035:  ldloca.s   V_0
    IL_0037:  ldloca.s   V_2
    IL_0039:  ldloca.s   V_0
    IL_003b:  callvirt   instance void Pakon.ISavePictures::GetPictureCountScanGroup(int32,
                                                                                     int32&,
                                                                                     int32&,
                                                                                     int32&)
    IL_0040:  ldarg.1
    IL_0041:  callvirt   instance class Pakon.ISavePictures Pakon.Scanner::get_ISave()
    IL_0046:  callvirt   instance void Pakon.ISavePictures::MoveOldestRollToSaveGroup()
    IL_004b:  ldloc.1
    IL_004c:  stloc.3
    IL_004d:  br.s       IL_005f

    IL_004f:  ldarg.0
    IL_0050:  ldfld      class Pakon.AddPictureToSaveGroup Pakon.ScannerSettingsSave::m_evAddPictureToSaveGroup
    IL_0055:  ldloc.3
    IL_0056:  callvirt   instance void Pakon.AddPictureToSaveGroup::Invoke(int32)
    IL_005b:  ldloc.3
    IL_005c:  ldc.i4.1
    IL_005d:  add
    IL_005e:  stloc.3
    IL_005f:  ldloc.3
    IL_0060:  ldloc.1
    IL_0061:  ldloc.2
    IL_0062:  add
    IL_0063:  blt.s      IL_004f

    IL_0065:  ret
  } // end of method ScannerSettingsSave::MoveRollToSaveGroup

  .method public hidebysig instance void 
          SetPictureInfo(class Pakon.Scanner csScanner,
                         int32 iIndex,
                         int32 iNewFrameNumber,
                         string strNewFileName,
                         string strNewDirectory,
                         int32 iNewRotation,
                         [Interop.TLXLib]TLXLib.S_OR_H_000 eNewSelectedHidden,
                         class Pakon.IntBits ibInfo) cil managed
  {
    // Code size       126 (0x7e)
    .maxstack  13
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2,
             int32 V_3,
             int32 V_4,
             int32 V_5,
             int32 V_6,
             string V_7,
             string V_8,
             string V_9,
             [Interop.TLXLib]TLXLib.S_OR_H_000 V_10)
    IL_0000:  ldarg.1
    IL_0001:  callvirt   instance class Pakon.ISavePictures3 Pakon.Scanner::get_ISave3()
    IL_0006:  ldarg.2
    IL_0007:  ldloca.s   V_0
    IL_0009:  ldloca.s   V_1
    IL_000b:  ldloca.s   V_2
    IL_000d:  ldloca.s   V_3
    IL_000f:  ldloca.s   V_7
    IL_0011:  ldloca.s   V_4
    IL_0013:  ldloca.s   V_5
    IL_0015:  ldloca.s   V_8
    IL_0017:  ldloca.s   V_9
    IL_0019:  ldloca.s   V_6
    IL_001b:  ldloca.s   V_10
    IL_001d:  callvirt   instance void Pakon.ISavePictures3::GetPictureInfo3(int32,
                                                                             int32&,
                                                                             int32&,
                                                                             int32&,
                                                                             int32&,
                                                                             string&,
                                                                             int32&,
                                                                             int32&,
                                                                             string&,
                                                                             string&,
                                                                             int32&,
                                                                             [Interop.TLXLib]TLXLib.S_OR_H_000&)
    IL_0022:  ldarg.s    ibInfo
    IL_0024:  ldc.i4.0
    IL_0025:  callvirt   instance bool Pakon.IntBits::get_Item(int32)
    IL_002a:  brfalse.s  IL_002f

    IL_002c:  ldarg.3
    IL_002d:  stloc.s    V_4
    IL_002f:  ldarg.s    ibInfo
    IL_0031:  ldc.i4.1
    IL_0032:  callvirt   instance bool Pakon.IntBits::get_Item(int32)
    IL_0037:  brfalse.s  IL_003d

    IL_0039:  ldarg.s    strNewFileName
    IL_003b:  stloc.s    V_8
    IL_003d:  ldarg.s    ibInfo
    IL_003f:  ldc.i4.2
    IL_0040:  callvirt   instance bool Pakon.IntBits::get_Item(int32)
    IL_0045:  brfalse.s  IL_004b

    IL_0047:  ldarg.s    strNewDirectory
    IL_0049:  stloc.s    V_9
    IL_004b:  ldarg.s    ibInfo
    IL_004d:  ldc.i4.3
    IL_004e:  callvirt   instance bool Pakon.IntBits::get_Item(int32)
    IL_0053:  brfalse.s  IL_0059

    IL_0055:  ldarg.s    iNewRotation
    IL_0057:  stloc.s    V_6
    IL_0059:  ldarg.s    ibInfo
    IL_005b:  ldc.i4.4
    IL_005c:  callvirt   instance bool Pakon.IntBits::get_Item(int32)
    IL_0061:  brfalse.s  IL_0067

    IL_0063:  ldarg.s    eNewSelectedHidden
    IL_0065:  stloc.s    V_10
    IL_0067:  ldarg.1
    IL_0068:  callvirt   instance class Pakon.ISavePictures Pakon.Scanner::get_ISave()
    IL_006d:  ldarg.2
    IL_006e:  ldloc.s    V_4
    IL_0070:  ldloc.s    V_8
    IL_0072:  ldloc.s    V_9
    IL_0074:  ldloc.s    V_6
    IL_0076:  ldloc.s    V_10
    IL_0078:  callvirt   instance void Pakon.ISavePictures::PutPictureInfo(int32,
                                                                           int32,
                                                                           string,
                                                                           string,
                                                                           int32,
                                                                           [Interop.TLXLib]TLXLib.S_OR_H_000)
    IL_007d:  ret
  } // end of method ScannerSettingsSave::SetPictureInfo

  .method private hidebysig instance void 
          FindBoundingRectangle(class Pakon.Scanner csScanner,
                                [out] int32& iBoundingWidth,
                                [out] int32& iBoundingHeight,
                                [out] int32& iBufferByteCount,
                                bool bFourChannel) cil managed
  {
    // Code size       365 (0x16d)
    .maxstack  13
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2,
             int32 V_3,
             bool V_4,
             [Interop.TLXLib]TLXLib.S_OR_H_000 V_5,
             int32 V_6,
             int32 V_7,
             int32 V_8,
             int32 V_9,
             int32 V_10,
             int32 V_11,
             int32 V_12,
             [Interop.TLXLib]TLXLib.INDEX_000 V_13,
             string V_14,
             string V_15,
             string V_16)
    IL_0000:  ldc.i4.0
    IL_0001:  stloc.0
    IL_0002:  ldc.i4.0
    IL_0003:  stloc.1
    IL_0004:  ldarg.1
    IL_0005:  callvirt   instance class Pakon.ISavePictures Pakon.Scanner::get_ISave()
    IL_000a:  ldloca.s   V_0
    IL_000c:  ldloca.s   V_0
    IL_000e:  ldloca.s   V_1
    IL_0010:  ldloca.s   V_0
    IL_0012:  ldloca.s   V_0
    IL_0014:  callvirt   instance void Pakon.ISavePictures::GetPictureCountSaveGroup(int32&,
                                                                                     int32&,
                                                                                     int32&,
                                                                                     int32&,
                                                                                     int32&)
    IL_0019:  ldarg.0
    IL_001a:  ldfld      [Interop.TLXLib]TLXLib.INDEX_000 Pakon.ScannerSettingsSave::m_eIndex
    IL_001f:  stloc.s    V_13
    IL_0021:  ldloc.s    V_13
    IL_0023:  ldc.i4.s   -3
    IL_0025:  sub
    IL_0026:  switch     ( 
                          IL_0046,
                          IL_0046,
                          IL_004c,
                          IL_004c)
    IL_003b:  ldloc.s    V_13
    IL_003d:  ldc.i4     0x7fffffff
    IL_0042:  beq.s      IL_0059

    IL_0044:  br.s       IL_0064

    IL_0046:  ldc.i4.0
    IL_0047:  stloc.2
    IL_0048:  ldloc.1
    IL_0049:  stloc.3
    IL_004a:  br.s       IL_0083

    IL_004c:  ldarg.0
    IL_004d:  ldfld      [Interop.TLXLib]TLXLib.INDEX_000 Pakon.ScannerSettingsSave::m_eIndex
    IL_0052:  stloc.2
    IL_0053:  ldloc.2
    IL_0054:  ldc.i4.1
    IL_0055:  add
    IL_0056:  stloc.3
    IL_0057:  br.s       IL_0083

    IL_0059:  ldstr      "Index not supported"
    IL_005e:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0063:  throw

    IL_0064:  ldloc.1
    IL_0065:  ldarg.0
    IL_0066:  ldfld      [Interop.TLXLib]TLXLib.INDEX_000 Pakon.ScannerSettingsSave::m_eIndex
    IL_006b:  blt.s      IL_0078

    IL_006d:  ldstr      "Index out of range"
    IL_0072:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_0077:  throw

    IL_0078:  ldarg.0
    IL_0079:  ldfld      [Interop.TLXLib]TLXLib.INDEX_000 Pakon.ScannerSettingsSave::m_eIndex
    IL_007e:  stloc.2
    IL_007f:  ldloc.2
    IL_0080:  ldc.i4.1
    IL_0081:  add
    IL_0082:  stloc.3
    IL_0083:  ldarg.2
    IL_0084:  ldc.i4.0
    IL_0085:  stind.i4
    IL_0086:  ldarg.3
    IL_0087:  ldc.i4.0
    IL_0088:  stind.i4
    IL_0089:  ldarg.s    iBufferByteCount
    IL_008b:  ldc.i4.0
    IL_008c:  stind.i4
    IL_008d:  br         IL_0165

    IL_0092:  ldc.i4.1
    IL_0093:  stloc.s    V_4
    IL_0095:  ldarg.0
    IL_0096:  ldfld      [Interop.TLXLib]TLXLib.INDEX_000 Pakon.ScannerSettingsSave::m_eIndex
    IL_009b:  ldc.i4.s   -2
    IL_009d:  bne.un.s   IL_00d4

    IL_009f:  ldc.i4.0
    IL_00a0:  stloc.s    V_5
    IL_00a2:  ldarg.1
    IL_00a3:  callvirt   instance class Pakon.ISavePictures3 Pakon.Scanner::get_ISave3()
    IL_00a8:  ldloc.2
    IL_00a9:  ldloca.s   V_0
    IL_00ab:  ldloca.s   V_0
    IL_00ad:  ldloca.s   V_0
    IL_00af:  ldloca.s   V_0
    IL_00b1:  ldnull
    IL_00b2:  stloc.s    V_14
    IL_00b4:  ldloca.s   V_14
    IL_00b6:  ldloca.s   V_0
    IL_00b8:  ldloca.s   V_0
    IL_00ba:  ldnull
    IL_00bb:  stloc.s    V_15
    IL_00bd:  ldloca.s   V_15
    IL_00bf:  ldnull
    IL_00c0:  stloc.s    V_16
    IL_00c2:  ldloca.s   V_16
    IL_00c4:  ldloca.s   V_0
    IL_00c6:  ldloca.s   V_5
    IL_00c8:  callvirt   instance void Pakon.ISavePictures3::GetPictureInfo3(int32,
                                                                             int32&,
                                                                             int32&,
                                                                             int32&,
                                                                             int32&,
                                                                             string&,
                                                                             int32&,
                                                                             int32&,
                                                                             string&,
                                                                             string&,
                                                                             int32&,
                                                                             [Interop.TLXLib]TLXLib.S_OR_H_000&)
    IL_00cd:  ldloc.s    V_5
    IL_00cf:  ldc.i4.1
    IL_00d0:  ceq
    IL_00d2:  stloc.s    V_4
    IL_00d4:  ldloc.s    V_4
    IL_00d6:  brfalse    IL_0161

    IL_00db:  ldc.i4.0
    IL_00dc:  stloc.s    V_6
    IL_00de:  ldc.i4.0
    IL_00df:  stloc.s    V_7
    IL_00e1:  ldc.i4.0
    IL_00e2:  stloc.s    V_8
    IL_00e4:  ldc.i4.0
    IL_00e5:  stloc.s    V_9
    IL_00e7:  ldarg.0
    IL_00e8:  ldfld      [Interop.TLXLib]TLXLib.SAVE_CONTROL_000 Pakon.ScannerSettingsSave::m_eSaveControl
    IL_00ed:  ldc.i4.8
    IL_00ee:  and
    IL_00ef:  ldc.i4.8
    IL_00f0:  bne.un.s   IL_0108

    IL_00f2:  ldarg.1
    IL_00f3:  callvirt   instance class Pakon.ISavePictures Pakon.Scanner::get_ISave()
    IL_00f8:  ldloc.2
    IL_00f9:  ldloca.s   V_6
    IL_00fb:  ldloca.s   V_7
    IL_00fd:  ldloca.s   V_8
    IL_00ff:  ldloca.s   V_9
    IL_0101:  callvirt   instance void Pakon.ISavePictures::GetPictureFramingUserInfoLowRes(int32,
                                                                                            int32&,
                                                                                            int32&,
                                                                                            int32&,
                                                                                            int32&)
    IL_0106:  br.s       IL_011c

    IL_0108:  ldarg.1
    IL_0109:  callvirt   instance class Pakon.ISavePictures Pakon.Scanner::get_ISave()
    IL_010e:  ldloc.2
    IL_010f:  ldloca.s   V_6
    IL_0111:  ldloca.s   V_7
    IL_0113:  ldloca.s   V_8
    IL_0115:  ldloca.s   V_9
    IL_0117:  callvirt   instance void Pakon.ISavePictures::GetPictureFramingUserInfo(int32,
                                                                                      int32&,
                                                                                      int32&,
                                                                                      int32&,
                                                                                      int32&)
    IL_011c:  ldloc.s    V_8
    IL_011e:  ldc.i4.1
    IL_011f:  add
    IL_0120:  ldloc.s    V_6
    IL_0122:  sub
    IL_0123:  stloc.s    V_10
    IL_0125:  ldloc.s    V_9
    IL_0127:  ldc.i4.1
    IL_0128:  add
    IL_0129:  ldloc.s    V_7
    IL_012b:  sub
    IL_012c:  stloc.s    V_11
    IL_012e:  ldloc.s    V_10
    IL_0130:  ldloc.s    V_11
    IL_0132:  ldarg.0
    IL_0133:  ldfld      [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 Pakon.ScannerSettingsSave::m_eMemoryFormat
    IL_0138:  ldarg.s    bFourChannel
    IL_013a:  call       int32 Pakon.Global::BufferSize(int32,
                                                        int32,
                                                        [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000,
                                                        bool)
    IL_013f:  stloc.s    V_12
    IL_0141:  ldarg.2
    IL_0142:  ldind.i4
    IL_0143:  ldloc.s    V_10
    IL_0145:  bge.s      IL_014b

    IL_0147:  ldarg.2
    IL_0148:  ldloc.s    V_10
    IL_014a:  stind.i4
    IL_014b:  ldarg.3
    IL_014c:  ldind.i4
    IL_014d:  ldloc.s    V_11
    IL_014f:  bge.s      IL_0155

    IL_0151:  ldarg.3
    IL_0152:  ldloc.s    V_11
    IL_0154:  stind.i4
    IL_0155:  ldarg.s    iBufferByteCount
    IL_0157:  ldind.i4
    IL_0158:  ldloc.s    V_12
    IL_015a:  bge.s      IL_0161

    IL_015c:  ldarg.s    iBufferByteCount
    IL_015e:  ldloc.s    V_12
    IL_0160:  stind.i4
    IL_0161:  ldloc.2
    IL_0162:  ldc.i4.1
    IL_0163:  add
    IL_0164:  stloc.2
    IL_0165:  ldloc.2
    IL_0166:  ldloc.3
    IL_0167:  blt        IL_0092

    IL_016c:  ret
  } // end of method ScannerSettingsSave::FindBoundingRectangle

  .method public hidebysig instance void 
          SaveToClientMemory(class Pakon.Scanner csScanner,
                             class Pakon.ScannerSettings csScannerSettings,
                             bool bFourChannel) cil managed
  {
    // Code size       114 (0x72)
    .maxstack  9
    .locals (int32 V_0,
             int32 V_1,
             int32 V_2)
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  ldloca.s   V_0
    IL_0004:  ldloca.s   V_1
    IL_0006:  ldloca.s   V_2
    IL_0008:  ldarg.3
    IL_0009:  call       instance void Pakon.ScannerSettingsSave::FindBoundingRectangle(class Pakon.Scanner,
                                                                                        int32&,
                                                                                        int32&,
                                                                                        int32&,
                                                                                        bool)
    IL_000e:  ldloc.2
    IL_000f:  brtrue.s   IL_001c

    IL_0011:  ldstr      "No pictures to save"
    IL_0016:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_001b:  throw

    IL_001c:  ldarg.1
    IL_001d:  callvirt   instance class Pakon.ScannerUnsafe Pakon.Scanner::get_Unsafe()
    IL_0022:  ldarg.0
    IL_0023:  call       instance [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 Pakon.ScannerSettingsSave::get_MemoryFormat()
    IL_0028:  callvirt   instance void Pakon.ScannerUnsafe::set_MemoryFormat([Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000)
    IL_002d:  ldarg.1
    IL_002e:  callvirt   instance class Pakon.ScannerUnsafe Pakon.Scanner::get_Unsafe()
    IL_0033:  ldloc.2
    IL_0034:  callvirt   instance void Pakon.ScannerUnsafe::Allocate(int32)
    IL_0039:  ldarg.1
    IL_003a:  callvirt   instance class Pakon.ScannerUnsafe Pakon.Scanner::get_Unsafe()
    IL_003f:  ldarg.1
    IL_0040:  callvirt   instance void Pakon.ScannerUnsafe::NextBuffer(class Pakon.Scanner)
    IL_0045:  ldarg.1
    IL_0046:  callvirt   instance class Pakon.ISavePictures Pakon.Scanner::get_ISave()
    IL_004b:  ldarg.2
    IL_004c:  callvirt   instance [Interop.TLXLib]TLXLib.SCANNER_TYPE_000 Pakon.ScannerSettings::get_Type()
    IL_0051:  ldarg.0
    IL_0052:  ldfld      [Interop.TLXLib]TLXLib.INDEX_000 Pakon.ScannerSettingsSave::m_eIndex
    IL_0057:  ldarg.0
    IL_0058:  ldfld      [Interop.TLXLib]TLXLib.SAVE_CONTROL_000 Pakon.ScannerSettingsSave::m_eSaveControl
    IL_005d:  ldloc.0
    IL_005e:  ldloc.1
    IL_005f:  ldarg.0
    IL_0060:  ldfld      [Interop.TLXLib]TLXLib.SCALING_METHOD_000 Pakon.ScannerSettingsSave::m_eScalingMethod
    IL_0065:  ldarg.0
    IL_0066:  ldfld      [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 Pakon.ScannerSettingsSave::m_eMemoryFormat
    IL_006b:  ldarg.3
    IL_006c:  callvirt   instance void Pakon.ISavePictures::SaveToClientMemory([Interop.TLXLib]TLXLib.SCANNER_TYPE_000,
                                                                               [Interop.TLXLib]TLXLib.INDEX_000,
                                                                               [Interop.TLXLib]TLXLib.SAVE_CONTROL_000,
                                                                               int32,
                                                                               int32,
                                                                               [Interop.TLXLib]TLXLib.SCALING_METHOD_000,
                                                                               [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000,
                                                                               bool)
    IL_0071:  ret
  } // end of method ScannerSettingsSave::SaveToClientMemory

  .event Pakon.AddPictureToSaveGroup m_evAddPictureToSaveGroup
  {
    .removeon instance void Pakon.ScannerSettingsSave::remove_m_evAddPictureToSaveGroup(class Pakon.AddPictureToSaveGroup)
    .addon instance void Pakon.ScannerSettingsSave::add_m_evAddPictureToSaveGroup(class Pakon.AddPictureToSaveGroup)
  } // end of event ScannerSettingsSave::m_evAddPictureToSaveGroup
  .property instance [Interop.TLXLib]TLXLib.INDEX_000
          Index()
  {
    .get instance [Interop.TLXLib]TLXLib.INDEX_000 Pakon.ScannerSettingsSave::get_Index()
    .set instance void Pakon.ScannerSettingsSave::set_Index([Interop.TLXLib]TLXLib.INDEX_000)
  } // end of property ScannerSettingsSave::Index
  .property instance [Interop.TLXLib]TLXLib.SAVE_CONTROL_000
          Control()
  {
    .set instance void Pakon.ScannerSettingsSave::set_Control([Interop.TLXLib]TLXLib.SAVE_CONTROL_000)
    .get instance [Interop.TLXLib]TLXLib.SAVE_CONTROL_000 Pakon.ScannerSettingsSave::get_Control()
  } // end of property ScannerSettingsSave::Control
  .property instance [Interop.TLXLib]TLXLib.SCALING_METHOD_000
          ScalingMethod()
  {
    .set instance void Pakon.ScannerSettingsSave::set_ScalingMethod([Interop.TLXLib]TLXLib.SCALING_METHOD_000)
    .get instance [Interop.TLXLib]TLXLib.SCALING_METHOD_000 Pakon.ScannerSettingsSave::get_ScalingMethod()
  } // end of property ScannerSettingsSave::ScalingMethod
  .property instance [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000
          MemoryFormat()
  {
    .set instance void Pakon.ScannerSettingsSave::set_MemoryFormat([Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000)
    .get instance [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 Pakon.ScannerSettingsSave::get_MemoryFormat()
  } // end of property ScannerSettingsSave::MemoryFormat
} // end of class Pakon.ScannerSettingsSave

.class public auto ansi sealed Pakon.ImageFromClientBuffer
       extends [mscorlib]System.MulticastDelegate
{
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(object 'object',
                               native int 'method') runtime managed
  {
  } // end of method ImageFromClientBuffer::.ctor

  .method public hidebysig virtual instance void 
          Invoke(uint8[] aryImage,
                 uint32 uLength) runtime managed
  {
  } // end of method ImageFromClientBuffer::Invoke

  .method public hidebysig newslot virtual 
          instance [mscorlib]System.IAsyncResult 
          BeginInvoke(uint8[] aryImage,
                      uint32 uLength,
                      [mscorlib]System.AsyncCallback callback,
                      object 'object') runtime managed
  {
  } // end of method ImageFromClientBuffer::BeginInvoke

  .method public hidebysig newslot virtual 
          instance void  EndInvoke([mscorlib]System.IAsyncResult result) runtime managed
  {
  } // end of method ImageFromClientBuffer::EndInvoke

} // end of class Pakon.ImageFromClientBuffer

.class public auto ansi beforefieldinit Pakon.ScannerUnsafe
       extends [mscorlib]System.Object
{
  .field private class Pakon.ImageFromClientBuffer m_evImageFromClientBuffer
  .field private [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 m_eMemoryFormat
  .field private bool m_bUsingBuffer1
  .field private int32 m_nBufferSize
  .field private native int m_ipClientBuffer1
  .field private uint8* m_pubClientBuffer1
  .field private int32 m_nClientBuffer1
  .field private native int m_ipClientBuffer2
  .field private uint8* m_pubClientBuffer2
  .field private int32 m_nClientBuffer2
  .method public hidebysig specialname instance void 
          add_m_evImageFromClientBuffer(class Pakon.ImageFromClientBuffer 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Pakon.ImageFromClientBuffer Pakon.ScannerUnsafe::m_evImageFromClientBuffer
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  Pakon.ImageFromClientBuffer
    IL_0012:  stfld      class Pakon.ImageFromClientBuffer Pakon.ScannerUnsafe::m_evImageFromClientBuffer
    IL_0017:  ret
  } // end of method ScannerUnsafe::add_m_evImageFromClientBuffer

  .method public hidebysig specialname instance void 
          remove_m_evImageFromClientBuffer(class Pakon.ImageFromClientBuffer 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Pakon.ImageFromClientBuffer Pakon.ScannerUnsafe::m_evImageFromClientBuffer
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  Pakon.ImageFromClientBuffer
    IL_0012:  stfld      class Pakon.ImageFromClientBuffer Pakon.ScannerUnsafe::m_evImageFromClientBuffer
    IL_0017:  ret
  } // end of method ScannerUnsafe::remove_m_evImageFromClientBuffer

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor() cil managed
  {
    // Code size       44 (0x2c)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.1
    IL_0002:  stfld      bool Pakon.ScannerUnsafe::m_bUsingBuffer1
    IL_0007:  ldarg.0
    IL_0008:  ldc.i4.0
    IL_0009:  conv.u
    IL_000a:  stfld      uint8* Pakon.ScannerUnsafe::m_pubClientBuffer1
    IL_000f:  ldarg.0
    IL_0010:  ldc.i4.0
    IL_0011:  stfld      int32 Pakon.ScannerUnsafe::m_nClientBuffer1
    IL_0016:  ldarg.0
    IL_0017:  ldc.i4.0
    IL_0018:  conv.u
    IL_0019:  stfld      uint8* Pakon.ScannerUnsafe::m_pubClientBuffer2
    IL_001e:  ldarg.0
    IL_001f:  ldc.i4.0
    IL_0020:  stfld      int32 Pakon.ScannerUnsafe::m_nClientBuffer2
    IL_0025:  ldarg.0
    IL_0026:  call       instance void [mscorlib]System.Object::.ctor()
    IL_002b:  ret
  } // end of method ScannerUnsafe::.ctor

  .method public hidebysig specialname instance [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 
          get_MemoryFormat() cil managed
  {
    // Code size       7 (0x7)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldfld      [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 Pakon.ScannerUnsafe::m_eMemoryFormat
    IL_0006:  ret
  } // end of method ScannerUnsafe::get_MemoryFormat

  .method public hidebysig specialname instance void 
          set_MemoryFormat([Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 'value') cil managed
  {
    // Code size       8 (0x8)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.1
    IL_0002:  stfld      [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 Pakon.ScannerUnsafe::m_eMemoryFormat
    IL_0007:  ret
  } // end of method ScannerUnsafe::set_MemoryFormat

  .method public hidebysig instance void 
          Allocate(int32 nBufferByteCount) cil managed
  {
    // Code size       107 (0x6b)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.1
    IL_0002:  stfld      bool Pakon.ScannerUnsafe::m_bUsingBuffer1
    IL_0007:  ldarg.0
    IL_0008:  ldarg.1
    IL_0009:  stfld      int32 Pakon.ScannerUnsafe::m_nBufferSize
    IL_000e:  ldarg.0
    IL_000f:  ldarg.1
    IL_0010:  call       native int [mscorlib]System.Runtime.InteropServices.Marshal::AllocHGlobal(int32)
    IL_0015:  stfld      native int Pakon.ScannerUnsafe::m_ipClientBuffer1
    IL_001a:  ldarg.0
    IL_001b:  ldarg.0
    IL_001c:  ldfld      native int Pakon.ScannerUnsafe::m_ipClientBuffer1
    IL_0021:  call       void* [mscorlib]System.IntPtr::op_Explicit(native int)
    IL_0026:  stfld      uint8* Pakon.ScannerUnsafe::m_pubClientBuffer1
    IL_002b:  ldarg.0
    IL_002c:  ldarg.0
    IL_002d:  ldflda     native int Pakon.ScannerUnsafe::m_ipClientBuffer1
    IL_0032:  call       instance int32 [mscorlib]System.IntPtr::ToInt32()
    IL_0037:  stfld      int32 Pakon.ScannerUnsafe::m_nClientBuffer1
    IL_003c:  ldarg.0
    IL_003d:  ldarg.1
    IL_003e:  call       native int [mscorlib]System.Runtime.InteropServices.Marshal::AllocHGlobal(int32)
    IL_0043:  stfld      native int Pakon.ScannerUnsafe::m_ipClientBuffer2
    IL_0048:  ldarg.0
    IL_0049:  ldarg.0
    IL_004a:  ldfld      native int Pakon.ScannerUnsafe::m_ipClientBuffer2
    IL_004f:  call       void* [mscorlib]System.IntPtr::op_Explicit(native int)
    IL_0054:  stfld      uint8* Pakon.ScannerUnsafe::m_pubClientBuffer2
    IL_0059:  ldarg.0
    IL_005a:  ldarg.0
    IL_005b:  ldflda     native int Pakon.ScannerUnsafe::m_ipClientBuffer2
    IL_0060:  call       instance int32 [mscorlib]System.IntPtr::ToInt32()
    IL_0065:  stfld      int32 Pakon.ScannerUnsafe::m_nClientBuffer2
    IL_006a:  ret
  } // end of method ScannerUnsafe::Allocate

  .method public hidebysig instance void 
          Deallocate() cil managed
  {
    // Code size       73 (0x49)
    .maxstack  2
    IL_0000:  ldarg.0
    IL_0001:  ldfld      uint8* Pakon.ScannerUnsafe::m_pubClientBuffer1
    IL_0006:  ldc.i4.0
    IL_0007:  conv.u
    IL_0008:  beq.s      IL_0015

    IL_000a:  ldarg.0
    IL_000b:  ldfld      native int Pakon.ScannerUnsafe::m_ipClientBuffer1
    IL_0010:  call       void [mscorlib]System.Runtime.InteropServices.Marshal::FreeHGlobal(native int)
    IL_0015:  ldarg.0
    IL_0016:  ldc.i4.0
    IL_0017:  conv.u
    IL_0018:  stfld      uint8* Pakon.ScannerUnsafe::m_pubClientBuffer1
    IL_001d:  ldarg.0
    IL_001e:  ldc.i4.0
    IL_001f:  stfld      int32 Pakon.ScannerUnsafe::m_nClientBuffer1
    IL_0024:  ldarg.0
    IL_0025:  ldfld      uint8* Pakon.ScannerUnsafe::m_pubClientBuffer2
    IL_002a:  ldc.i4.0
    IL_002b:  conv.u
    IL_002c:  beq.s      IL_0039

    IL_002e:  ldarg.0
    IL_002f:  ldfld      native int Pakon.ScannerUnsafe::m_ipClientBuffer2
    IL_0034:  call       void [mscorlib]System.Runtime.InteropServices.Marshal::FreeHGlobal(native int)
    IL_0039:  ldarg.0
    IL_003a:  ldc.i4.0
    IL_003b:  conv.u
    IL_003c:  stfld      uint8* Pakon.ScannerUnsafe::m_pubClientBuffer2
    IL_0041:  ldarg.0
    IL_0042:  ldc.i4.0
    IL_0043:  stfld      int32 Pakon.ScannerUnsafe::m_nClientBuffer2
    IL_0048:  ret
  } // end of method ScannerUnsafe::Deallocate

  .method public hidebysig instance void 
          NextBuffer(class Pakon.Scanner csScanner) cil managed
  {
    // Code size       145 (0x91)
    .maxstack  3
    .locals (uint8* V_0,
             int32 V_1,
             uint8* V_2,
             int32 V_3)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      uint8* Pakon.ScannerUnsafe::m_pubClientBuffer1
    IL_0006:  ldc.i4.0
    IL_0007:  conv.u
    IL_0008:  bne.un.s   IL_000b

    IL_000a:  ret

    IL_000b:  ldarg.0
    IL_000c:  ldfld      bool Pakon.ScannerUnsafe::m_bUsingBuffer1
    IL_0011:  brfalse.s  IL_004b

    IL_0013:  ldarg.0
    IL_0014:  ldfld      uint8* Pakon.ScannerUnsafe::m_pubClientBuffer1
    IL_0019:  stloc.0
    IL_001a:  ldc.i4.0
    IL_001b:  stloc.1
    IL_001c:  br.s       IL_0029

    IL_001e:  ldloc.0
    IL_001f:  ldc.i4.0
    IL_0020:  stind.i1
    IL_0021:  ldloc.1
    IL_0022:  ldc.i4.1
    IL_0023:  add
    IL_0024:  stloc.1
    IL_0025:  ldloc.0
    IL_0026:  ldc.i4.1
    IL_0027:  add
    IL_0028:  stloc.0
    IL_0029:  ldloc.1
    IL_002a:  ldarg.0
    IL_002b:  ldfld      int32 Pakon.ScannerUnsafe::m_nBufferSize
    IL_0030:  blt.s      IL_001e

    IL_0032:  ldarg.1
    IL_0033:  callvirt   instance class Pakon.ISavePictures Pakon.Scanner::get_ISave()
    IL_0038:  ldarg.0
    IL_0039:  ldfld      int32 Pakon.ScannerUnsafe::m_nClientBuffer1
    IL_003e:  ldarg.0
    IL_003f:  ldfld      int32 Pakon.ScannerUnsafe::m_nBufferSize
    IL_0044:  callvirt   instance void Pakon.ISavePictures::ClientMemoryBufferAdd(int32,
                                                                                  int32)
    IL_0049:  br.s       IL_0081

    IL_004b:  ldarg.0
    IL_004c:  ldfld      uint8* Pakon.ScannerUnsafe::m_pubClientBuffer2
    IL_0051:  stloc.2
    IL_0052:  ldc.i4.0
    IL_0053:  stloc.3
    IL_0054:  br.s       IL_0061

    IL_0056:  ldloc.2
    IL_0057:  ldc.i4.0
    IL_0058:  stind.i1
    IL_0059:  ldloc.3
    IL_005a:  ldc.i4.1
    IL_005b:  add
    IL_005c:  stloc.3
    IL_005d:  ldloc.2
    IL_005e:  ldc.i4.1
    IL_005f:  add
    IL_0060:  stloc.2
    IL_0061:  ldloc.3
    IL_0062:  ldarg.0
    IL_0063:  ldfld      int32 Pakon.ScannerUnsafe::m_nBufferSize
    IL_0068:  blt.s      IL_0056

    IL_006a:  ldarg.1
    IL_006b:  callvirt   instance class Pakon.ISavePictures Pakon.Scanner::get_ISave()
    IL_0070:  ldarg.0
    IL_0071:  ldfld      int32 Pakon.ScannerUnsafe::m_nClientBuffer2
    IL_0076:  ldarg.0
    IL_0077:  ldfld      int32 Pakon.ScannerUnsafe::m_nBufferSize
    IL_007c:  callvirt   instance void Pakon.ISavePictures::ClientMemoryBufferAdd(int32,
                                                                                  int32)
    IL_0081:  ldarg.0
    IL_0082:  ldarg.0
    IL_0083:  ldfld      bool Pakon.ScannerUnsafe::m_bUsingBuffer1
    IL_0088:  ldc.i4.0
    IL_0089:  ceq
    IL_008b:  stfld      bool Pakon.ScannerUnsafe::m_bUsingBuffer1
    IL_0090:  ret
  } // end of method ScannerUnsafe::NextBuffer

  .method public hidebysig instance void 
          ProcessBuffer(class Pakon.Scanner csScanner) cil managed
  {
    // Code size       187 (0xbb)
    .maxstack  3
    .locals (uint8* V_0,
             uint32 V_1,
             valuetype Pakon.SiPlanarFileHeader* V_2,
             uint8[] V_3,
             uint8* V_4,
             uint32 V_5,
             [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 V_6)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      uint8* Pakon.ScannerUnsafe::m_pubClientBuffer1
    IL_0006:  ldc.i4.0
    IL_0007:  conv.u
    IL_0008:  bne.un.s   IL_000b

    IL_000a:  ret

    IL_000b:  ldarg.0
    IL_000c:  ldfld      bool Pakon.ScannerUnsafe::m_bUsingBuffer1
    IL_0011:  brtrue.s   IL_001b

    IL_0013:  ldarg.0
    IL_0014:  ldfld      uint8* Pakon.ScannerUnsafe::m_pubClientBuffer1
    IL_0019:  br.s       IL_0021

    IL_001b:  ldarg.0
    IL_001c:  ldfld      uint8* Pakon.ScannerUnsafe::m_pubClientBuffer2
    IL_0021:  stloc.0
    IL_0022:  ldc.i4.0
    IL_0023:  stloc.1
    IL_0024:  ldarg.0
    IL_0025:  ldfld      [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 Pakon.ScannerUnsafe::m_eMemoryFormat
    IL_002a:  stloc.s    V_6
    IL_002c:  ldloc.s    V_6
    IL_002e:  switch     ( 
                          IL_0041,
                          IL_006e,
                          IL_006e)
    IL_003f:  br.s       IL_0063

    IL_0041:  ldloc.0
    IL_0042:  stloc.2
    IL_0043:  ldloc.2
    IL_0044:  ldfld      uint32 Pakon.SiPlanarFileHeader::m_uiWidth
    IL_0049:  ldloc.2
    IL_004a:  ldfld      uint32 Pakon.SiPlanarFileHeader::m_uiHeight
    IL_004f:  mul
    IL_0050:  ldloc.2
    IL_0051:  ldfld      uint32 Pakon.SiPlanarFileHeader::m_uiBitCount
    IL_0056:  ldc.i4.8
    IL_0057:  div.un
    IL_0058:  mul
    IL_0059:  sizeof     Pakon.SiPlanarFileHeader
    IL_005f:  add
    IL_0060:  stloc.1
    IL_0061:  br.s       IL_006e

    IL_0063:  ldstr      "Format not supported"
    IL_0068:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_006d:  throw

    IL_006e:  ldloc.1
    IL_006f:  brtrue.s   IL_007c

    IL_0071:  ldstr      "Format not implemented"
    IL_0076:  newobj     instance void [mscorlib]System.ArgumentException::.ctor(string)
    IL_007b:  throw

    IL_007c:  ldloc.1
    IL_007d:  conv.u
    IL_007e:  newarr     [mscorlib]System.Byte
    IL_0083:  stloc.3
    IL_0084:  ldloc.0
    IL_0085:  stloc.s    V_4
    IL_0087:  ldc.i4.0
    IL_0088:  stloc.s    V_5
    IL_008a:  br.s       IL_00a0

    IL_008c:  ldloc.3
    IL_008d:  ldloc.s    V_5
    IL_008f:  conv.u
    IL_0090:  ldloc.s    V_4
    IL_0092:  ldind.u1
    IL_0093:  stelem.i1
    IL_0094:  ldloc.s    V_5
    IL_0096:  ldc.i4.1
    IL_0097:  add
    IL_0098:  stloc.s    V_5
    IL_009a:  ldloc.s    V_4
    IL_009c:  ldc.i4.1
    IL_009d:  add
    IL_009e:  stloc.s    V_4
    IL_00a0:  ldloc.s    V_5
    IL_00a2:  ldloc.1
    IL_00a3:  blt.un.s   IL_008c

    IL_00a5:  ldarg.0
    IL_00a6:  ldfld      class Pakon.ImageFromClientBuffer Pakon.ScannerUnsafe::m_evImageFromClientBuffer
    IL_00ab:  brfalse.s  IL_00ba

    IL_00ad:  ldarg.0
    IL_00ae:  ldfld      class Pakon.ImageFromClientBuffer Pakon.ScannerUnsafe::m_evImageFromClientBuffer
    IL_00b3:  ldloc.3
    IL_00b4:  ldloc.1
    IL_00b5:  callvirt   instance void Pakon.ImageFromClientBuffer::Invoke(uint8[],
                                                                           uint32)
    IL_00ba:  ret
  } // end of method ScannerUnsafe::ProcessBuffer

  .event Pakon.ImageFromClientBuffer m_evImageFromClientBuffer
  {
    .addon instance void Pakon.ScannerUnsafe::add_m_evImageFromClientBuffer(class Pakon.ImageFromClientBuffer)
    .removeon instance void Pakon.ScannerUnsafe::remove_m_evImageFromClientBuffer(class Pakon.ImageFromClientBuffer)
  } // end of event ScannerUnsafe::m_evImageFromClientBuffer
  .property instance [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000
          MemoryFormat()
  {
    .set instance void Pakon.ScannerUnsafe::set_MemoryFormat([Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000)
    .get instance [Interop.TLXLib]TLXLib.FILE_FORMAT_SAVE_TO_MEMORY_000 Pakon.ScannerUnsafe::get_MemoryFormat()
  } // end of property ScannerUnsafe::MemoryFormat
} // end of class Pakon.ScannerUnsafe

.class public auto ansi sealed Pakon.MessageBoxClose
       extends [mscorlib]System.MulticastDelegate
{
  .method public hidebysig specialname rtspecialname 
          instance void  .ctor(object 'object',
                               native int 'method') runtime managed
  {
  } // end of method MessageBoxClose::.ctor

  .method public hidebysig virtual instance void 
          Invoke() runtime managed
  {
  } // end of method MessageBoxClose::Invoke

  .method public hidebysig newslot virtual 
          instance [mscorlib]System.IAsyncResult 
          BeginInvoke([mscorlib]System.AsyncCallback callback,
                      object 'object') runtime managed
  {
  } // end of method MessageBoxClose::BeginInvoke

  .method public hidebysig newslot virtual 
          instance void  EndInvoke([mscorlib]System.IAsyncResult result) runtime managed
  {
  } // end of method MessageBoxClose::EndInvoke

} // end of class Pakon.MessageBoxClose

.class public auto ansi sealed Pakon.ErrorType
       extends [mscorlib]System.Enum
{
  .field public specialname rtspecialname int32 value__
  .field public static literal valuetype Pakon.ErrorType General = int32(0x00000000)
  .field public static literal valuetype Pakon.ErrorType Callback = int32(0x00000001)
} // end of class Pakon.ErrorType

.class public auto ansi beforefieldinit Pakon.TLXErrorMessageBox
       extends [mscorlib]System.Object
{
  .field private valuetype Pakon.ErrorType m_etError
  .field private [System.Windows.Forms]System.Windows.Forms.Form m_formOwner
  .field private class Pakon.MessageBoxClose m_evTLXError
  .field private class Pakon.Scanner m_csScanner
  .field private [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 m_wtoOperation
  .field private int32 m_iStatus
  .field private string m_strMessage
  .field private string m_strCaption
  .method public hidebysig specialname instance void 
          add_m_evTLXError(class Pakon.MessageBoxClose 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Pakon.MessageBoxClose Pakon.TLXErrorMessageBox::m_evTLXError
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_000d:  castclass  Pakon.MessageBoxClose
    IL_0012:  stfld      class Pakon.MessageBoxClose Pakon.TLXErrorMessageBox::m_evTLXError
    IL_0017:  ret
  } // end of method TLXErrorMessageBox::add_m_evTLXError

  .method public hidebysig specialname instance void 
          remove_m_evTLXError(class Pakon.MessageBoxClose 'value') cil managed synchronized
  {
    // Code size       24 (0x18)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  ldarg.0
    IL_0002:  ldfld      class Pakon.MessageBoxClose Pakon.TLXErrorMessageBox::m_evTLXError
    IL_0007:  ldarg.1
    IL_0008:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Remove([mscorlib]System.Delegate,
                                                                                     [mscorlib]System.Delegate)
    IL_000d:  castclass  Pakon.MessageBoxClose
    IL_0012:  stfld      class Pakon.MessageBoxClose Pakon.TLXErrorMessageBox::m_evTLXError
    IL_0017:  ret
  } // end of method TLXErrorMessageBox::remove_m_evTLXError

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor([System.Windows.Forms]System.Windows.Forms.Form formOwner,
                               valuetype Pakon.ErrorType etError,
                               class Pakon.Scanner csScanner,
                               [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                               int32 lStatus) cil managed
  {
    // Code size       44 (0x2c)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0006:  ldarg.0
    IL_0007:  ldarg.2
    IL_0008:  stfld      valuetype Pakon.ErrorType Pakon.TLXErrorMessageBox::m_etError
    IL_000d:  ldarg.0
    IL_000e:  ldarg.1
    IL_000f:  stfld      [System.Windows.Forms]System.Windows.Forms.Form Pakon.TLXErrorMessageBox::m_formOwner
    IL_0014:  ldarg.0
    IL_0015:  ldarg.3
    IL_0016:  stfld      class Pakon.Scanner Pakon.TLXErrorMessageBox::m_csScanner
    IL_001b:  ldarg.0
    IL_001c:  ldarg.s    wtoOperation
    IL_001e:  stfld      [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 Pakon.TLXErrorMessageBox::m_wtoOperation
    IL_0023:  ldarg.0
    IL_0024:  ldarg.s    lStatus
    IL_0026:  stfld      int32 Pakon.TLXErrorMessageBox::m_iStatus
    IL_002b:  ret
  } // end of method TLXErrorMessageBox::.ctor

  .method public hidebysig specialname rtspecialname 
          instance void  .ctor([System.Windows.Forms]System.Windows.Forms.Form formOwner,
                               valuetype Pakon.ErrorType etError,
                               string strMessage,
                               string strCaption) cil managed
  {
    // Code size       36 (0x24)
    .maxstack  8
    IL_0000:  ldarg.0
    IL_0001:  call       instance void [mscorlib]System.Object::.ctor()
    IL_0006:  ldarg.0
    IL_0007:  ldarg.1
    IL_0008:  stfld      [System.Windows.Forms]System.Windows.Forms.Form Pakon.TLXErrorMessageBox::m_formOwner
    IL_000d:  ldarg.0
    IL_000e:  ldarg.2
    IL_000f:  stfld      valuetype Pakon.ErrorType Pakon.TLXErrorMessageBox::m_etError
    IL_0014:  ldarg.0
    IL_0015:  ldarg.3
    IL_0016:  stfld      string Pakon.TLXErrorMessageBox::m_strMessage
    IL_001b:  ldarg.0
    IL_001c:  ldarg.s    strCaption
    IL_001e:  stfld      string Pakon.TLXErrorMessageBox::m_strCaption
    IL_0023:  ret
  } // end of method TLXErrorMessageBox::.ctor

  .method public hidebysig instance void 
          ThreadEntry() cil managed
  {
    // Code size       140 (0x8c)
    .maxstack  5
    .locals (int32 V_0,
             string V_1,
             string V_2)
    IL_0000:  ldarg.0
    IL_0001:  ldfld      valuetype Pakon.ErrorType Pakon.TLXErrorMessageBox::m_etError
    IL_0006:  ldc.i4.1
    IL_0007:  bne.un.s   IL_0073

    IL_0009:  ldstr      ""
    IL_000e:  stloc.1
    IL_000f:  ldstr      ""
    IL_0014:  stloc.2
    IL_0015:  ldarg.0
    IL_0016:  ldfld      class Pakon.Scanner Pakon.TLXErrorMessageBox::m_csScanner
    IL_001b:  ldarg.0
    IL_001c:  ldfld      [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 Pakon.TLXErrorMessageBox::m_wtoOperation
    IL_0021:  ldloca.s   V_1
    IL_0023:  ldloca.s   V_2
    IL_0025:  ldloca.s   V_0
    IL_0027:  callvirt   instance void Pakon.Scanner::GetAndClearLastErrorTLX([Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000,
                                                                              string&,
                                                                              string&,
                                                                              int32&)
    IL_002c:  ldstr      "Status = "
    IL_0031:  ldarg.0
    IL_0032:  ldfld      int32 Pakon.TLXErrorMessageBox::m_iStatus
    IL_0037:  box        [mscorlib]System.Int32
    IL_003c:  call       string [mscorlib]System.String::Concat(object,
                                                                object)
    IL_0041:  pop
    IL_0042:  ldarg.0
    IL_0043:  ldfld      [System.Windows.Forms]System.Windows.Forms.Form Pakon.TLXErrorMessageBox::m_formOwner
    IL_0048:  ldloc.1
    IL_0049:  ldarg.0
    IL_004a:  ldfld      [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 Pakon.TLXErrorMessageBox::m_wtoOperation
    IL_004f:  box        [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000
    IL_0054:  call       instance string [mscorlib]System.Enum::ToString()
    IL_0059:  call       [System.Windows.Forms]System.Windows.Forms.DialogResult [System.Windows.Forms]System.Windows.Forms.MessageBox::Show([System.Windows.Forms]System.Windows.Forms.IWin32Window,
                                                                                                                                             string,
                                                                                                                                             string)
    IL_005e:  pop
    IL_005f:  ldarg.0
    IL_0060:  ldfld      class Pakon.MessageBoxClose Pakon.TLXErrorMessageBox::m_evTLXError
    IL_0065:  brfalse.s  IL_008b

    IL_0067:  ldarg.0
    IL_0068:  ldfld      class Pakon.MessageBoxClose Pakon.TLXErrorMessageBox::m_evTLXError
    IL_006d:  callvirt   instance void Pakon.MessageBoxClose::Invoke()
    IL_0072:  ret

    IL_0073:  ldarg.0
    IL_0074:  ldfld      [System.Windows.Forms]System.Windows.Forms.Form Pakon.TLXErrorMessageBox::m_formOwner
    IL_0079:  ldarg.0
    IL_007a:  ldfld      string Pakon.TLXErrorMessageBox::m_strMessage
    IL_007f:  ldarg.0
    IL_0080:  ldfld      string Pakon.TLXErrorMessageBox::m_strCaption
    IL_0085:  call       [System.Windows.Forms]System.Windows.Forms.DialogResult [System.Windows.Forms]System.Windows.Forms.MessageBox::Show([System.Windows.Forms]System.Windows.Forms.IWin32Window,
                                                                                                                                             string,
                                                                                                                                             string)
    IL_008a:  pop
    IL_008b:  ret
  } // end of method TLXErrorMessageBox::ThreadEntry

  .method public hidebysig static void  Show([System.Windows.Forms]System.Windows.Forms.Form formOwner,
                                             class Pakon.Scanner csScanner,
                                             [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000 wtoOperation,
                                             int32 lStatus,
                                             class Pakon.MessageBoxClose evMessageBoxClose) cil managed
  {
    // Code size       66 (0x42)
    .maxstack  6
    .locals (class Pakon.TLXErrorMessageBox V_0,
             [mscorlib]System.Threading.ThreadStart V_1,
             [mscorlib]System.Threading.Thread V_2)
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.1
    IL_0002:  ldarg.1
    IL_0003:  ldarg.2
    IL_0004:  ldarg.3
    IL_0005:  newobj     instance void Pakon.TLXErrorMessageBox::.ctor([System.Windows.Forms]System.Windows.Forms.Form,
                                                                       valuetype Pakon.ErrorType,
                                                                       class Pakon.Scanner,
                                                                       [Interop.TLXLib]TLXLib.WORKER_THREAD_OPERATION_000,
                                                                       int32)
    IL_000a:  stloc.0
    IL_000b:  ldarg.s    evMessageBoxClose
    IL_000d:  brfalse.s  IL_0027

    IL_000f:  ldloc.0
    IL_0010:  dup
    IL_0011:  ldfld      class Pakon.MessageBoxClose Pakon.TLXErrorMessageBox::m_evTLXError
    IL_0016:  ldarg.s    evMessageBoxClose
    IL_0018:  call       [mscorlib]System.Delegate [mscorlib]System.Delegate::Combine([mscorlib]System.Delegate,
                                                                                      [mscorlib]System.Delegate)
    IL_001d:  castclass  Pakon.MessageBoxClose
    IL_0022:  stfld      class Pakon.MessageBoxClose Pakon.TLXErrorMessageBox::m_evTLXError
    IL_0027:  ldloc.0
    IL_0028:  ldftn      instance void Pakon.TLXErrorMessageBox::ThreadEntry()
    IL_002e:  newobj     instance void [mscorlib]System.Threading.ThreadStart::.ctor(object,
                                                                                     native int)
    IL_0033:  stloc.1
    IL_0034:  ldloc.1
    IL_0035:  newobj     instance void [mscorlib]System.Threading.Thread::.ctor([mscorlib]System.Threading.ThreadStart)
    IL_003a:  stloc.2
    IL_003b:  ldloc.2
    IL_003c:  callvirt   instance void [mscorlib]System.Threading.Thread::Start()
    IL_0041:  ret
  } // end of method TLXErrorMessageBox::Show

  .method public hidebysig static void  Show([System.Windows.Forms]System.Windows.Forms.Form formOwner,
                                             string strMessage,
                                             string strCaption) cil managed
  {
    // Code size       37 (0x25)
    .maxstack  5
    .locals (class Pakon.TLXErrorMessageBox V_0,
             [mscorlib]System.Threading.ThreadStart V_1,
             [mscorlib]System.Threading.Thread V_2)
    IL_0000:  ldarg.0
    IL_0001:  ldc.i4.0
    IL_0002:  ldarg.1
    IL_0003:  ldarg.2
    IL_0004:  newobj     instance void Pakon.TLXErrorMessageBox::.ctor([System.Windows.Forms]System.Windows.Forms.Form,
                                                                       valuetype Pakon.ErrorType,
                                                                       string,
                                                                       string)
    IL_0009:  stloc.0
    IL_000a:  ldloc.0
    IL_000b:  ldftn      instance void Pakon.TLXErrorMessageBox::ThreadEntry()
    IL_0011:  newobj     instance void [mscorlib]System.Threading.ThreadStart::.ctor(object,
                                                                                     native int)
    IL_0016:  stloc.1
    IL_0017:  ldloc.1
    IL_0018:  newobj     instance void [mscorlib]System.Threading.Thread::.ctor([mscorlib]System.Threading.ThreadStart)
    IL_001d:  stloc.2
    IL_001e:  ldloc.2
    IL_001f:  callvirt   instance void [mscorlib]System.Threading.Thread::Start()
    IL_0024:  ret
  } // end of method TLXErrorMessageBox::Show

  .event Pakon.MessageBoxClose m_evTLXError
  {
    .removeon instance void Pakon.TLXErrorMessageBox::remove_m_evTLXError(class Pakon.MessageBoxClose)
    .addon instance void Pakon.TLXErrorMessageBox::add_m_evTLXError(class Pakon.MessageBoxClose)
  } // end of event TLXErrorMessageBox::m_evTLXError
} // end of class Pakon.TLXErrorMessageBox


// =============================================================

// *********** DISASSEMBLY COMPLETE ***********************
