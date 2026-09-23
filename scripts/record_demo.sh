#!/usr/bin/env bash
# The terminal half of the demo video in one take (storyboard: docs/video.md).
#
#   scripts/record_demo.sh [run folder]      # default: examples/stripe-billing
#
# Sizes the window to 140x36, types the prompt, replays the recorded run (the header shows
# REPLAY), holds on the run summary, then opens the report in a pager. Each step waits for Enter,
# so you control the pacing while the screen recorder runs.
set -euo pipefail
cd "$(dirname "$0")/.."

RUN="${1:-examples/stripe-billing}"
SPEED="${SPEED:-4}"
PROMPT="$(uv run python -c 'import json, sys; print(json.load(open(sys.argv[1]))["prompt"])' "$RUN/run.json")"

uv run research --help >/dev/null  # warm the environment so the replay starts at once

pause() { read -rsp "$1" _; printf '\r\e[2K'; }
fit_window() {
    printf '\e[8;36;140t'  # ask for 140x36; Terminal.app and iTerm2 honour this
    sleep 0.5
    local size="$(tput cols)x$(tput lines)"
    if [[ "$size" != "140x36" ]]; then
        echo "The window is $size, not 140x36. Run this in Terminal.app or iTerm2 (an editor's" >&2
        echo "terminal panel cannot be resized), with a font small enough for 140x36 to fit." >&2
        exit 1
    fi
}
type_out() {
    local text="$1"
    for ((i = 0; i < ${#text}; i++)); do
        printf '%s' "${text:i:1}"
        sleep 0.03
    done
}

fit_window
clear
pause "Set the font size with ⌘+ / ⌘-, start the screen recording, then press Enter."
fit_window  # zooming the font can shrink the grid if the window no longer fits the screen
clear
sleep 1
printf '\e[1;32m❯\e[0m '
type_out "research run \"$PROMPT\""
sleep 0.8
printf '\n'
uv run research replay "$RUN" --speed "$SPEED" --max-gap 3 --hold 4

pause ""  # the run summary stays on screen until Enter
uv run research show "$RUN"  # space or ↓ to scroll, /Methodology to jump, q to quit
clear
