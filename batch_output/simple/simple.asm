********************************************************************************
* z/OS Binary Reverse Engineering - Reconstructed Assembly
* Module: simple
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
* Basic Block: block_00000002 (type: return)
00000000 05CF          BALR UNRESOLVED_TARGET
00000002 90ECD00C     L_00001 STM X'EC',12(13)
00000006 4130C100      LA 3,256(12)
0000000A 58403000      L 4,0(3)
0000000E 5A40C200      A 4,512(12)
00000012 50403000      ST 4,0(3)
00000016 98ECD00C      LM X'EC',12(13)
0000001A 07FE          BCR UNRESOLVED_TARGET

********************************************************************************
* Statistics
********************************************************************************
* Instructions decoded: 8
* Bytes decoded: 28
* Unknown bytes: 0
* Decode rate: 100.0%
* Branches: 2
* Calls: 1
* Returns: 1
* Top mnemonics:
*   BALR   : 1
*   STM    : 1
*   LA     : 1
*   L      : 1
*   A      : 1
********************************************************************************