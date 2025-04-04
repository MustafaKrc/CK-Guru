# ==================================
# Stage 1: Build React Application
# ==================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files and install dependencies
COPY package.json package-lock.json* ./
RUN npm ci --ignore-scripts

# Copy source code and build the application
COPY . .

# Build the application
# Set environment to production for optimize build OUTPUT
ENV NODE_ENV=production
RUN npm run build 

# ==================================
# Stage 2: Nginx Runtime Stage
# ==================================
FROM nginx:1.25-alpine AS runtime

# --- Configuration ---
RUN rm /etc/nginx/conf.d/default.conf
# Copy our custom Nginx configuration for the SPA
COPY ./nginx.conf /etc/nginx/conf.d/app.conf 

# --- Static Content ---
# Copy built assets from the builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# --- Permissions ---
# Nginx needs to read the content and write logs/temp files.
# The base nginx:alpine image usually sets up log/cache dirs correctly.
# We only need to ensure our content directory is readable by the nginx user.
# The nginx user (ID 101 typically) needs read access.
# Since we copy as root initially, we might need to adjust ownership,
RUN chown nginx:nginx /usr/share/nginx/html/*

# --- Expose Port ---
EXPOSE 80

# --- Healthcheck ---
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

# --- User ---
# The standard nginx images are often configured to drop privileges automatically
# or can run the worker processes as 'nginx'. Explicitly setting USER might conflict.
# Let's COMMENT OUT the `USER nginx` line initially and rely on the base image's config.
# If PID errors persist, we might need to revisit, but start simple.
# USER nginx

# Default CMD ["nginx", "-g", "daemon off;"] is inherited from base image