# binary-ninja-plugin-rename-objective-c-trampolines
A Binary Ninja disassembler plugin which renames Objective-C dynamic dispatch trampoline stub functions

## Background
IDA names Objective-C method dispatch trampolines like this:
```
__objc_stubs:00000001200515FC ; =============== S U B R O U T I N E =======================================
__objc_stubs:00000001200515FC
__objc_stubs:00000001200515FC
__objc_stubs:00000001200515FC _objc_msgSend$window                   
__objc_stubs:00000001200515FC                 ADRP            X1, #selRef_window@PAGE
__objc_stubs:0000000120051600                 LDR             X1, [X1,#selRef_window@PAGEOFF]
__objc_stubs:0000000120051604                 ADRP            X16, #_objc_msgSend_ptr@PAGE
__objc_stubs:0000000120051608                 LDR             X16, [X16,#_objc_msgSend_ptr@PAGEOFF]
__objc_stubs:000000012005160C                 BR              X16 ; __imp__objc_msgSend
__objc_stubs:000000012005160C ; End of function _objc_msgSend$window
```

Unfortunately, Binary Ninja instead gives generic names like sub_* to these trampoline functions, like this:
```
0053da74    int64_t sub_53da74(void* arg1)

0053da74  210800d0   adrp    x1, 0x643000
0053da78  217c44f9   ldr     x1, [x1, #0x8f8]  {sel_window, "window"}  {selRef_window}
0053da7c  d00400f0   adrp    x16, 0x5d8000
0053da80  104247f9   ldr     x16, [x16, #0xe80]  {_objc_msgSend}
0053da84  00021fd6   br      x16
```

## Functionality
This plugin provides functionality which renames the trampolines to match the names in IDA.

## Installation

1. Open Binary Ninja and hit Ctrl-P/Cmd-P then type "open plugin folder" and choose the "Open Plugin Folder..." option.

2. Place the rename_objc_trampolines.py file for this plugin in your plugin folder.

3. Restart Binary Ninja and open an ARM64 Objective-C binary. Select the "Rename Objective-C Method Dispatch Trampolines" option from the "Plugins" menu and observe that the trampoline functions in the `__objc_stubs` segment have been renamed.

## Known Issues / Limitations

This plugin is designed to work exclusively with ARM64/aarch64 binaries at this time. Patches accepted for other architectures!

