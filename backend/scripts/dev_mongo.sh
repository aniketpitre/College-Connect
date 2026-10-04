#!/usr/bin/env sh
# Start a local MongoDB 7 single-node replica set (transactions need a replica set),
# the same setup CI uses. Then:
#   MONGODB_URI="mongodb://localhost:27017/?replicaSet=rs0&directConnection=true"
set -e
NAME=collegeconnect-mongo
if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
  docker start "$NAME" >/dev/null
else
  docker run -d --name "$NAME" -p 27017:27017 mongo:7 --replSet rs0 --bind_ip_all >/dev/null
fi
for _ in $(seq 1 30); do
  docker exec "$NAME" mongosh --quiet --eval "db.adminCommand('ping').ok" >/dev/null 2>&1 && break
  sleep 1
done
docker exec "$NAME" mongosh --quiet --eval "try { rs.status().ok } catch (e) { rs.initiate({_id: 'rs0', members: [{_id: 0, host: 'localhost:27017'}]}).ok }" >/dev/null
echo "MongoDB replica set ready on localhost:27017 (container: $NAME)"
