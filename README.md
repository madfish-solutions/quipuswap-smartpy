# quipuswap-smartpy

###Initialize Smartpy
#### for the official stable version
`sh <(curl -s https://SmartPy.io/SmartPyBasic/SmartPy.sh) local-install ~`

####**Executing a SmartPy Script**

`~/SmartPyBasic/SmartPy.sh run <myscript.py>`

This runs an arbitrary Python script that can happen to contain SmartPy code.

####**Executing a SmartPy Script with its tests**

`~/SmartPyBasic/SmartPy.sh test <myscript.py> <output-directory>`

This includes many outputs: types, generated michelson code, pretty-printed scenario, etc.

####**Compiling a SmartPy Script**

`~/SmartPyBasic/SmartPy.sh compile <contractBuilder.py> <class-call> <output-directory>`

Example:

`~/SmartPyBasic/SmartPy.sh compile welcome.py "Welcome(12,123)" /tmp/welcome`

## WIP on tests and bugs
