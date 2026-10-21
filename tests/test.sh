#!/bin/bash
mkdir -p /logs/verifier

touch /logs/verifier/reward.txt
chown root:root /logs/verifier/reward.txt
chmod 644 /logs/verifier/reward.txt

touch /logs/verifier/ctrf.json
chown verifier:verifier /logs/verifier/ctrf.json
chmod 644 /logs/verifier/ctrf.json

chmod 755 /logs/verifier
chmod -R a+rX /app 2>/dev/null || true

python() {
    setpriv --reuid=verifier --regid=verifier --init-groups python3 "$@"
}

python -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
rc=$?
if [ "$rc" -eq 0 ]; then
echo 1 > /logs/verifier/reward.txt
else
echo 0 > /logs/verifier/reward.txt
fi
