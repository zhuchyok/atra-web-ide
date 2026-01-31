#!/bin/bash

expect << 'SCRIPT'
spawn ssh -o StrictHostKeyChecking=no root@185.177.216.15
expect "password:"
send "u44Ww9NmtQj,XG\r"
expect "# "
send "cd /root/atra\r"
expect "# "
send "python3 << 'PYEOF'\nimport sys\nsys.path.insert(0, '/root/atra')\nfrom config import TOKEN\nprint('TOKEN ID:', TOKEN.split(':')[0])\nPYEOF\r"
expect "# "
send "exit\r"
expect eof
SCRIPT

