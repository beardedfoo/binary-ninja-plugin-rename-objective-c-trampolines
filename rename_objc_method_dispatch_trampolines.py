from binaryninja import *
import struct
import re

def is_selector_string(bv, string):
    """
    Check if the string is a selector by checking its context
    """
    # Find the symbol at this address
    symbol = bv.get_symbol_at(string.start)
    
    # If symbol exists, check if it starts with 'sel_'
    if symbol and symbol.name.startswith('sel_'):
        return True
    
    return False

def is_adrp_instruction(instruction):
    """
    Check if the instruction is an ADRP (Add Relative Page) instruction on aarch64
    More flexible bit pattern matching
    """
    # ADRP instructions typically have bits 31:24 as 10000001 or 10000000
    return (instruction & 0x9F000000) == 0x90000000

def is_ldr_instruction(instruction):
    """
    Check if the instruction is an LDR instruction on aarch64
    More flexible bit pattern matching
    """
    # LDR instruction for 64-bit registers has specific bit patterns
    return (instruction & 0xFF000000) == 0xF9000000

def is_br_instruction(instruction):
    """
    Check if the instruction is a BR (Branch to Register) instruction on aarch64
    """
    # BR instruction has a specific top-level bit pattern
    return (instruction & 0xFFFFFC1F) == 0xD61F0000

def read_le_instruction(bv, address):
    """
    Read a 4-byte little-endian instruction, handling byte order carefully
    """
    try:
        # Read 4 bytes
        instruction_bytes = bv.read(address, 4)
        
        # Unpack as little-endian 32-bit integer
        instruction = struct.unpack('<I', instruction_bytes)[0]
        return instruction
    except Exception as e:
        log_info(f"Error reading instruction at {address:x}: {e}")
        return None

def is_valid_objc_trampoline(bv, start_addr):
    """
    Check if the code at start_addr is a valid Objective-C method trampoline
    """
    try:
        # Read 5 instructions, each 4 bytes long
        instructions = []
        for offset in range(0, 20, 4):
            # Read instruction carefully
            instruction = read_le_instruction(bv, start_addr + offset)
            if instruction is None:
                return False
            instructions.append(instruction)
        
        # Check pattern: ADRP, LDR, ADRP, LDR, BR
        pattern_check = (
            is_adrp_instruction(instructions[0]) and
            is_ldr_instruction(instructions[1]) and
            is_adrp_instruction(instructions[2]) and
            is_ldr_instruction(instructions[3]) and
            is_br_instruction(instructions[4])
        )
        
        return pattern_check
    
    except Exception as e:
        log_info(f"Error checking trampoline at {start_addr:x}: {e}")
        return False

def process_selector_reference(bv, symbol, ref, objc_stubs_section):
    """
    Process a single selector reference
    """
    # Skip references outside __objc_stubs section
    if not (objc_stubs_section.start <= ref.address < objc_stubs_section.end):
        log_info(f"    Skipping reference {ref.address:x} (not in __objc_stubs)")
        return False
    
    log_info(f"    Reference from: {ref.address:x}")
    
    # Try multiple potential trampoline start locations
    # Typical offset is 20 bytes before the reference, but we'll be flexible
    potential_starts = [
        ref.address - 20,  # Standard 20-byte trampoline
        ref.address - 16,  # Slightly shorter
        ref.address - 24,  # Slightly longer
    ]
    
    for trampoline_start in potential_starts:
        if is_valid_objc_trampoline(bv, trampoline_start):
            # Use the symbol's name for renaming
            # Remove 'sel_' prefix and any potential length specifier
            sanitized_name = re.sub(r'\[0x[0-9a-f]+\]$', '', symbol.name[4:])
            full_name = f"_objc_sendMsg${sanitized_name}"
            
            try:
                # Find or create function
                functions = bv.get_functions_at(trampoline_start)
                
                if functions:
                    function = functions[0]
                else:
                    # Create a new function
                    function = bv.create_function(trampoline_start)
                
                if function:
                    # Force update of function name and symbol multiple times
                    # This helps combat Binary Ninja's analysis phases
                    function.name = full_name
                    
                    # Define symbol with multiple methods
                    bv.define_user_symbol(Symbol(
                        SymbolType.ImportedFunctionSymbol, 
                        trampoline_start, 
                        full_name
                    ))
                    
                    bv.define_auto_symbol(Symbol(
                        SymbolType.ImportedFunctionSymbol, 
                        trampoline_start, 
                        full_name
                    ))
                    
                    # Additional preservation attempts
                    function.function_type = function.function_type
                    
                    log_info(f"    Trampoline found at {function.start:x}")
                    log_info(f"    Renamed to: {full_name}")
                    
                    # Try to prevent overwriting
                    function.temp_name = full_name
                    
                    return True
            except Exception as e:
                log_info(f"    Error processing trampoline: {e}")
    
    return False

def register_plugin(bv):
    """
    Analyze Objective-C method selectors in the __objc_methname section
    and identify associated trampolines
    """
    # Find the __objc_methname section
    objc_methname_section = None
    for section in bv.sections.values():
        if '__objc_methname' in section.name.lower():
            objc_methname_section = section
            break
    
    # Find the __objc_stubs section
    objc_stubs_section = None
    for section in bv.sections.values():
        if '__objc_stubs' in section.name.lower():
            objc_stubs_section = section
            break
    
    if not objc_methname_section:
        log_error("No __objc_methname section found in the binary")
        return
    
    if not objc_stubs_section:
        log_error("No __objc_stubs section found in the binary")
        return
    
    log_info(f"Analyzing __objc_methname section: {objc_methname_section.name}")
    log_info(f"Section range: {objc_methname_section.start:x} - {objc_methname_section.end:x}")
    log_info(f"Analyzing __objc_stubs section: {objc_stubs_section.name}")
    log_info(f"Section range: {objc_stubs_section.start:x} - {objc_stubs_section.end:x}")
    
    # Initialize tracking variables
    selector_count = 0
    trampoline_count = 0
    
    # Iterate through strings within the __objc_methname section
    for string in bv.strings:
        # Check if string is within the __objc_methname section
        if (objc_methname_section.start <= string.start < objc_methname_section.end):
            # Use Binary Ninja's selector identification
            if is_selector_string(bv, string):
                selector_count += 1
                
                # Get the symbol for this string
                symbol = bv.get_symbol_at(string.start)
                
                # Log detailed information about the selector
                log_info(f"Selector {selector_count}:")
                log_info(f"  Name: {symbol.name}")
                log_info(f"  Address: {string.start:x}")
                
                # Get code references to this selector
                refs = list(bv.get_code_refs(string.start))
                if refs:
                    log_info(f"  Code References ({len(refs)}):")
                    for ref in refs:
                        # Process each reference
                        if process_selector_reference(bv, symbol, ref, objc_stubs_section):
                            trampoline_count += 1
    
    log_info(f"\nTotal selectors found in __objc_methname: {selector_count}")
    log_info(f"Total trampolines identified and renamed: {trampoline_count}")


PluginCommand.register("Rename Objective-C Method Dispatch Trampolines", 
                      "Rename Objective-C msgSend() trampolines in __objc_stubs by selector refs found in __objc_methname", 
                      register_plugin)
