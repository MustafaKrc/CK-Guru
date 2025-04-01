# -----------------------------
# Stage 1: Build React application
# -----------------------------
FROM node:20-alpine AS build

# Set working directory
WORKDIR /app

# Add package files first (for better caching)
COPY package.json package-lock.json* ./

# Install dependencies (with exact versions from lock file)
# Use clean install for reproducible builds
RUN npm ci

# Copy source files
COPY . .

# Build the application
# Set environment to production to optimize the build
ENV NODE_ENV=production
RUN npm run build

# -----------------------------
# Stage 2: Serve with Nginx
# -----------------------------
FROM nginx:1.25-alpine AS production

# Copy Nginx configuration for SPAs
# This config handles client-side routing
COPY --from=build /app/dist /usr/share/nginx/html
COPY ./nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Make sure files are owned by nginx user
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

# Switch to non-root user
USER nginx

# Healthcheck to verify container is running properly
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1
