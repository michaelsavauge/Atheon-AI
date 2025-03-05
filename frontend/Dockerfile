# Atheon AI - Frontend Dockerfile
# Multi-stage build for Next.js with Tailwind CSS and Shadcn UI

# ====== Development Stage (with hot-reloading) ======
FROM node:18-alpine AS development

# Set working directory
WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy all files
COPY . .

# Expose port
EXPOSE 3000

# Start development server with hot-reloading
CMD ["npm", "run", "dev"]

# ====== Build Stage ======
FROM node:18-alpine AS builder

# Set working directory
WORKDIR /app

# Install dependencies with exact versions
COPY package.json package-lock.json* ./
RUN npm ci

# Copy all files
COPY . .

# Build the Next.js application
RUN npm run build

# ====== Production Stage ======
FROM node:18-alpine AS production

# Set working directory
WORKDIR /app

# Set Node.js to production mode
ENV NODE_ENV=production

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs --ingroup nodejs

# Install only production dependencies
COPY --from=builder /app/package.json /app/package-lock.json* ./
RUN npm ci --only=production

# Copy built application
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/next.config.js ./

# Set proper permissions
RUN chown -R nextjs:nodejs /app

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -q -O - http://localhost:3000/api/health || exit 1

# Start the application
CMD ["npm", "run", "start"]

# ====== Production with Standalone Output (smaller image) ======
FROM node:18-alpine AS standalone

# Set working directory
WORKDIR /app

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs --ingroup nodejs

# Set NODE_ENV
ENV NODE_ENV production

# Copy standalone output from builder
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -q -O - http://localhost:3000/api/health || exit 1

# Start the application
CMD ["node", "server.js"]