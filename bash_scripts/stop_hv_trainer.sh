#!/bin/bash
# Stop the HV trainer gracefully: SIGINT so the service runs its on_finish
# policy (hold/standby/off) and writes its final summary. Do NOT kill-session
# first — that skips the shutdown policy and leaves the state JSON stale.

if ! tmux has-session -t hv_trainer 2>/dev/null; then
    echo "No hv_trainer tmux session running."
    exit 0
fi

tmux send-keys -t hv_trainer C-c
echo "SIGINT sent to hv_trainer — waiting for clean shutdown..."

for i in $(seq 1 30); do
    if ! tmux list-panes -t hv_trainer -F '#{pane_current_command}' 2>/dev/null \
            | grep -q python; then
        echo "Trainer exited cleanly."
        # Remove the now-idle session so start_hv_trainer.sh can recreate it.
        tmux kill-session -t hv_trainer 2>/dev/null
        exit 0
    fi
    sleep 2
done

echo "Trainer still running after 60 s — check 'tmux attach -t hv_trainer'."
exit 1
