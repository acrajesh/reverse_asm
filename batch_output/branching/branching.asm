********************************************************************************
* z/OS Binary Reverse Engineering - Reconstructed Assembly
* Module: branching
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
* Basic Block: block_00000012 (type: return)
00000000 05CF          BALR UNRESOLVED_TARGET
00000002 90ECD00C     L_00001 STM X'EC',12(13)
00000006 5820C100      L 2,256(12)
0000000A 5920C104      C 2,260(12)
0000000E 4780C020      BC UNRESOLVED_TARGET
00000012 41200001     L_00002 LA 2,1(0)
00000016 47F0C028      BC 15,40(12)
0000001A 41200002      LA 2,2(0)
0000001E 5020C108      ST 2,264(12)
00000022 98ECD00C      LM X'EC',12(13)
00000026 07FE          BCR UNRESOLVED_TARGET

********************************************************************************
* Statistics
********************************************************************************
* Instructions decoded: 11
* Bytes decoded: 40
* Unknown bytes: 0
* Decode rate: 100.0%
* Branches: 4
* Calls: 1
* Returns: 1
* Top mnemonics:
*   BC     : 2
*   LA     : 2
*   BALR   : 1
*   STM    : 1
*   L      : 1
********************************************************************************