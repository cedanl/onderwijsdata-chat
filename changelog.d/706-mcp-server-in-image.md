### Test kwam niet meer op: `mcp_server.py` zat niet in het image (#706)
- De Dockerfile kopieerde `mcp_server.py` niet, dus de pod crashte bij het opstarten met "No module named 'mcp_server'" en test gaf "no available server". `tests/test_dockerfile_modules.py` toetst nu dat elke module in de root en elk pakket in de Dockerfile staat.
