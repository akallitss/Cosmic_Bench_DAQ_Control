#!/bin/bash
# Start the HV trainer service in its own tmux session.
# Usage: start_hv_trainer.sh [extra hv_trainer_service.py args, e.g. --dry-run]
# Regenerates config/hv_trainer_config.json first (fails closed on validation).

cd "$(dirname "$0")/.." || exit 1

python hv_trainer_config.py || exit 1

bash_scripts/start_tmux.sh hv_trainer \
    "python hv_trainer_service.py config/hv_trainer_config.json $*"
