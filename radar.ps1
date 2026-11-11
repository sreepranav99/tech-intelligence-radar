$ProjectDir = $PSScriptRoot
$env:PYTHONPATH = "$ProjectDir\src;$env:PYTHONPATH"
& "C:\Users\Admin\AppData\Local\Programs\Python\Python311\python.exe" -m radar.cli $args
