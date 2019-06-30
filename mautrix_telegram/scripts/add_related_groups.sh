#!/bin/bash
if [[ -z "$GROUP_ID" ]]; then
	echo "Please set the GROUP_ID environment variable."
	exit 1
elif [[ -z "$ACCESS_TOKEN" ]]; then
	echo "Please set the ACCESS_TOKEN environment variable."
	exit 1
elif [[ -z "$HOMESERVER" ]]; then
	echo "Please set the HOMESERVER environment variable."
	exit 1
fi
auth="Authorization: Bearer $ACCESS_TOKEN"
rooms=$(curl -s -H "$auth" "$HOMESERVER/_matrix/client/r0/joined_rooms" | jq -r '.joined_rooms[]')
for room in $rooms; do
	old_groups=$(curl -s -H "$auth" "$HOMESERVER/_matrix/client/r0/rooms/$room/state/m.room.related_groups")
	new_groups=$(echo "$old_groups" | jq -rc '{"groups": (.groups + ["'$GROUP_ID'"] | unique)}')
	curl -s -H "$auth" -X PUT "$HOMESERVER/_matrix/client/r0/rooms/$room/state/m.room.related_groups" -d "$new_groups"
done
