********************************************************************************
* z/OS Binary Reverse Engineering - Reconstructed Assembly
* Module: loop
* Format: unknown
* Note: This is reconstructed code with synthetic labels
********************************************************************************

* Metadata:
*   Entry Point: unknown
*   AMODE: unknown
*   RMODE: unknown


********************************************************************************
* Procedure: ENTRY_00000000
* Entry: 0x00000000
* Detection: entry_point (confidence: high)
********************************************************************************

* Basic Block: block_00000000 (type: call)
* Basic Block: block_00000002 (type: branch)
* Basic Block: block_00000016 (type: return)
00000000 05CF          BALR UNRESOLVED_TARGET
00000002 90ECD00C     L_00001 STM X'EC',12(13)
00000006 4130000A      LA 3,10(0)
0000000A 4140C100      LA 4,256(12)
0000000E 5A404000      A 4,0(4)
00000012 4630C00C      BCT UNRESOLVED_TARGET
00000016 98ECD00C     L_00002 LM X'EC',12(13)
0000001A 07FE          BCR UNRESOLVED_TARGET

********************************************************************************
* Statistics
********************************************************************************
* Instructions decoded: 8
* Bytes decoded: 28
* Unknown bytes: 0
* Decode rate: 100.0%
* Branches: 3
* Calls: 1
* Returns: 1
* Top mnemonics:
*   LA     : 2
*   BALR   : 1
*   STM    : 1
*   A      : 1
*   BCT    : 1
********************************************************************************