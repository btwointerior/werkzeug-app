#!/usr/bin/env bash
#
# Deploy der Werkzeug-Ausleih-App auf den Hetzner-Server.
#
#   ./deploy.sh           -> VORSCHAU (rsync --dry-run), lädt NICHTS hoch
#   ./deploy.sh --go      -> lädt wirklich hoch und startet den Dienst neu
#
# Es wird NUR der Code synchronisiert. Auf dem Server bleiben unberührt:
#   .env  (Secrets)   data/ (Produktiv-Datenbank)   uploads/   qr_codes/   venv/
#
set -euo pipefail

SERVER="root@62.238.47.224"
KEY="$HOME/.ssh/hetzner_werkzeug"
REMOTE_DIR="/var/www/werkzeug-app"
SERVICE="werkzeug-app.service"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/"

SSH_OPTS="-o BatchMode=yes -i $KEY"

# Was NICHT hochgeladen wird (Produktionsdaten + lokale Artefakte):
EXCLUDES=(
  --exclude '.git/'
  --exclude '.env'
  --exclude 'data/'
  --exclude 'uploads/'
  --exclude 'qr_codes/'
  --exclude 'venv/'
  --exclude '__pycache__/'
  --exclude '*.log'
  --exclude '*.pyc'
  # Nur-lokale Dev-Artefakte – gehören nicht auf den Produktivserver:
  --exclude '.pytest_cache/'
  --exclude 'tests/'
  --exclude 'pytest.ini'
  --exclude 'requirements-dev.txt'
)

if [[ "${1:-}" == "--go" ]]; then
  DRY=""
  echo ">>> ECHTER DEPLOY auf $SERVER:$REMOTE_DIR"
else
  DRY="--dry-run"
  echo ">>> VORSCHAU (es wird nichts verändert). Für echten Deploy: ./deploy.sh --go"
fi

echo ">>> Synchronisiere Code ..."
rsync -rtz --no-perms --no-owner --no-group --itemize-changes $DRY "${EXCLUDES[@]}" \
  -e "ssh $SSH_OPTS" \
  "$SRC" "$SERVER:$REMOTE_DIR/"

if [[ -z "$DRY" ]]; then
  echo ">>> Starte Dienst neu ($SERVICE) ..."
  ssh $SSH_OPTS "$SERVER" "systemctl restart $SERVICE && sleep 2 && systemctl is-active $SERVICE"
  echo ">>> Fertig. App neu gestartet."
else
  echo ">>> Vorschau-Ende. (Zeilen oben = würden geändert/hochgeladen.)"
fi
