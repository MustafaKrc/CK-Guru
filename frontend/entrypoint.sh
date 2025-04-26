#!/bin/sh
# filepath: frontend/entrypoint.sh

# Start the Next.js server in the background as the 'nextjs' user
# Use su-exec (install if needed: apk add --no-cache su-exec)
# If su-exec is not available, try using 'su -s /bin/sh -c "node server.js" nextjs &'
echo "Starting Next.js server..."
su -s /bin/sh -c "node server.js" nextjs &

# Wait a moment for the Node server to start (optional)
sleep 2

# Start Nginx in the foreground
echo "Starting Nginx..."
nginx -g 'daemon off;'