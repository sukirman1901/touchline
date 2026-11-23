#!/bin/zsh
cd "$(dirname "$0")"
exec "$HOME/Downloads/.football-analyzer-py311/bin/python" -m app.server
