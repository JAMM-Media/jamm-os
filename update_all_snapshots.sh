#!/bin/bash
set -e
cd /home/corby/jamm-os
echo "Updating backend/codebase snapshot..."
python3 update_backend_snapshot.py
echo "Updating frontend snapshot..."
python3 update_frontend_snapshot.py
echo "Done. Verifying output files:"
ls -la codebase_snapshot.txt frontend/frontend_snapshot.txt
