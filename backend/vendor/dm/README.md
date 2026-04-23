Place the Linux DM8 runtime/client files here before building `backend/Dockerfile.dm`.

If DM8 is already installed in WSL, you can sync the minimal runtime into this folder with:

```powershell
powershell -ExecutionPolicy Bypass -File .\backend\scripts\sync_dm_runtime_from_wsl.ps1
```

Minimum required contents for the current build:
- `bin/libdmdpi.so` or `drivers/dpi/libdmdpi.so`
- `include/` or `dpi/include/`
- runtime crypto/compression dependencies under `bin/`, especially `libcrypto.so`,
  `libssl.so`, `libz.so`, `libsnappy.so`, `libdmgmssl.so`, `libdmcrypt.so`, and
  `libdmcvt.so`

The DM driver may raise `CODE:-70089` (`加密模块加载失败`) at runtime if those
dependencies are missing, even when `dmPython` builds successfully.

The Python source packages are already present in:
- `backend/达梦 Python 接口源码-20260401/python`

This folder is only for the DM runtime/client libraries needed to compile and run `dmPython`.
