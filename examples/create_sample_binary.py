#!/usr/bin/env python3
"""Create sample z/OS-like binaries for testing"""

from pathlib import Path


def create_simple_program():
    """Create a simple z/OS program binary"""
    # Simple program that increments a memory location
    program = bytearray()
    
    # Entry point - establish base register
    program.extend([0x05, 0xCF])              # BALR 12,15 (R12 = base)
    
    # Standard prologue - save registers
    program.extend([0x90, 0xEC, 0xD0, 0x0C])  # STM 14,12,12(13)
    
    # Main logic
    program.extend([0x41, 0x30, 0xC1, 0x00])  # LA 3,256(12) - load address
    program.extend([0x58, 0x40, 0x30, 0x00])  # L 4,0(3) - load value
    program.extend([0x5A, 0x40, 0xC2, 0x00])  # A 4,512(12) - add constant
    program.extend([0x50, 0x40, 0x30, 0x00])  # ST 4,0(3) - store result
    
    # Epilogue - restore registers
    program.extend([0x98, 0xEC, 0xD0, 0x0C])  # LM 14,12,12(13)
    program.extend([0x07, 0xFE])              # BCR 15,14 (BR 14) - return
    
    return bytes(program)


def create_branching_program():
    """Create a program with conditional branches"""
    program = bytearray()
    
    # Entry
    program.extend([0x05, 0xCF])              # BALR 12,15
    program.extend([0x90, 0xEC, 0xD0, 0x0C])  # STM 14,12,12(13)
    
    # Load and compare
    program.extend([0x58, 0x20, 0xC1, 0x00])  # L 2,256(12)
    program.extend([0x59, 0x20, 0xC1, 0x04])  # C 2,260(12)
    program.extend([0x47, 0x80, 0xC0, 0x20])  # BC 8,32(12) - branch if equal
    
    # Not equal path
    program.extend([0x41, 0x20, 0x00, 0x01])  # LA 2,1
    program.extend([0x47, 0xF0, 0xC0, 0x28])  # BC 15,40(12) - unconditional
    
    # Equal path (offset 0x20)
    program.extend([0x41, 0x20, 0x00, 0x02])  # LA 2,2
    
    # Common exit (offset 0x28)
    program.extend([0x50, 0x20, 0xC1, 0x08])  # ST 2,264(12)
    program.extend([0x98, 0xEC, 0xD0, 0x0C])  # LM 14,12,12(13)
    program.extend([0x07, 0xFE])              # BCR 15,14
    
    return bytes(program)


def create_subroutine_program():
    """Create a program with subroutine calls"""
    program = bytearray()
    
    # Main entry
    program.extend([0x05, 0xCF])              # BALR 12,15
    program.extend([0x90, 0xEC, 0xD0, 0x0C])  # STM 14,12,12(13)
    
    # Call subroutine
    program.extend([0x41, 0x10, 0xC1, 0x00])  # LA 1,256(12) - parameter
    program.extend([0x05, 0xEF])              # BALR 14,15 - relative call
    program.extend([0x47, 0xF0, 0xC0, 0x20])  # BC 15,32(12) - skip sub
    
    # Subroutine (offset 0x14)
    program.extend([0x18, 0x21])              # LR 2,1 - copy parameter
    program.extend([0x5A, 0x20, 0x20, 0x00])  # A 2,0(2) - double it
    program.extend([0x50, 0x20, 0x10, 0x00])  # ST 2,0(1) - store result
    program.extend([0x07, 0xFE])              # BCR 15,14 - return
    
    # Main continues (offset 0x20)
    program.extend([0x98, 0xEC, 0xD0, 0x0C])  # LM 14,12,12(13)
    program.extend([0x07, 0xFE])              # BCR 15,14
    
    return bytes(program)


def create_loop_program():
    """Create a program with a loop structure"""
    program = bytearray()
    
    # Entry
    program.extend([0x05, 0xCF])              # BALR 12,15
    program.extend([0x90, 0xEC, 0xD0, 0x0C])  # STM 14,12,12(13)
    
    # Initialize counter
    program.extend([0x41, 0x30, 0x00, 0x0A])  # LA 3,10 - loop count
    
    # Loop start (offset 0x0C)
    program.extend([0x41, 0x40, 0xC1, 0x00])  # LA 4,256(12)
    program.extend([0x5A, 0x40, 0x40, 0x00])  # A 4,0(4) - process
    program.extend([0x46, 0x30, 0xC0, 0x0C])  # BCT 3,12(12) - dec and loop
    
    # Loop exit
    program.extend([0x98, 0xEC, 0xD0, 0x0C])  # LM 14,12,12(13)
    program.extend([0x07, 0xFE])              # BCR 15,14
    
    return bytes(program)


def main():
    """Generate sample binaries"""
    samples_dir = Path("samples")
    samples_dir.mkdir(exist_ok=True)
    
    # Generate different sample programs
    samples = {
        "simple.bin": create_simple_program(),
        "branching.bin": create_branching_program(),
        "subroutine.bin": create_subroutine_program(),
        "loop.bin": create_loop_program(),
    }
    
    for name, data in samples.items():
        path = samples_dir / name
        path.write_bytes(data)
        print(f"Created: {path} ({len(data)} bytes)")
    
    print(f"\nSample binaries created in '{samples_dir}' directory")
    print("\nTo analyze a sample:")
    print("  zos-reverse analyze samples/simple.bin -o output/")


if __name__ == "__main__":
    main()
