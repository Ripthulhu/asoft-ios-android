# Fresh command-specific capability probe

This revision preserves the failed `capability-resume2` source, command, and phone evidence. The actual retained top-level help lists command summaries; its dd summary did not advertise options.

The new probe runs the exact qualified native `qemu-img dd --help`, checks the required tokens across the complete bounded decoded help, and retains the original synthetic proof: a fresh 2,048-byte input, four distinct 512-byte blocks, `bs=512 count=1 skip=2`, output exactly the third block, and unchanged input bytes. It opens no existing disk image and starts no guest VM. All source/tooling/session checks, memory/storage floors, child bounds, and unconditional cleanup receipts are unchanged.

The command is `probe-qemu-img.command.txt`; `source-status.json` pins its complete bytes and source. Independent review must be recorded before root uses it on the phone. No passed result is assumed.

The pending eight-header reader retains its original fixed `dd -f qcow2 -O raw` command. The tool is qualified by exact release bytes; the repository does not establish a reproduced native-source build. Ordinary upstream dd input behavior is therefore a documented inference for this binary. No writable-input defect has been observed. Locks, known process absence, fixed offsets, fresh output paths, actual synthetic proof, and before/after image-chain identities remain required.
