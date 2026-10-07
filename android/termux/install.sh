#!/data/data/com.termux/files/usr/bin/bash
set -e

mkdir -p "$HOME/.local/bin" "$HOME/.local/lib"

cp "$(dirname "$0")/savage-app-bridge" "$HOME/.local/bin/savage-app-bridge"
cp "$(dirname "$0")/savage-app-runner.py" "$HOME/.local/lib/savage-app-runner.py"
cp "$(dirname "$0")/savage_model_runtime.py" "$HOME/.local/lib/savage_model_runtime.py"

chmod 755 "$HOME/.local/bin/savage-app-bridge"
chmod 644 "$HOME/.local/lib/savage-app-runner.py"
chmod 644 "$HOME/.local/lib/savage_model_runtime.py"

echo "Installed:"
echo "  $HOME/.local/bin/savage-app-bridge"
echo "  $HOME/.local/lib/savage-app-runner.py"
echo "  $HOME/.local/lib/savage_model_runtime.py"
