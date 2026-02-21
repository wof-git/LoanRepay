#!/bin/sh
mkdir -p /app/data
chown -R appuser /app/data
exec gosu appuser "$@"
