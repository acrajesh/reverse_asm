********************************************************************************
* z/OS Binary Reverse Engineering - Reconstructed Assembly
* Module: subroutine
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
* Basic Block: block_00000002 (type: call)
* Basic Block: block_0000000C (type: return)
00000000 05CF          BALR UNRESOLVED_TARGET
00000002 90ECD00C     PROC_001 STM X'EC',12(13)
00000006 4110C100      LA 1,256(12)
0000000A 05EF          BALR UNRESOLVED_TARGET
0000000C 47F0C020     L_00002 BC 15,32(12)
00000010 1821          LR 2,1
00000012 5A202000      A 2,0(2)
00000016 50201000      ST 2,0(1)
0000001A 07FE          BCR 15,14
0000001C 98ECD00C      LM X'EC',12(13)
00000020 07FE          BCR UNRESOLVED_TARGET

********************************************************************************
* Statistics
********************************************************************************
* Instructions decoded: 11
* Bytes decoded: 34
* Unknown bytes: 0
* Decode rate: 100.0%
* Branches: 5
* Calls: 2
* Returns: 2
* Top mnemonics:
*   BALR   : 2
*   BCR    : 2
*   STM    : 1
*   LA     : 1
*   BC     : 1
********************************************************************************