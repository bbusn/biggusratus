from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata

binaries = collect_dynamic_libs("netifaces")
datas = copy_metadata("netifaces")