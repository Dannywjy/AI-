#!/bin/sh
# Keep CLI, plugins, and init behavior aligned with the reviewed project snapshot.
set -eu
command_name=
for argument do
    case "$argument" in
        -*) ;;
        *) command_name=$argument; break ;;
    esac
done
case "$command_name" in
    skills|upgrade|feedback)
        printf '%s\n' "Disabled command: $command_name. Manage project dependencies through a reviewed PR." >&2
        exit 2
        ;;
esac
export HYPERFRAMES_SKIP_SKILLS=1
export HYPERFRAMES_SKILL_PKG_VERSION=0.8.181
export HYPERFRAMES_PLUGIN_VERSION=0.8.181
export HYPERFRAMES_NO_UPDATE_CHECK=1
export HYPERFRAMES_NO_TELEMETRY=1
exec npx --yes hyperframes@0.8.181 "$@"
