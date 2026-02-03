# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Build arguments
ARG BACKEND_URL=http://backend:8000
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ENV BACKEND_URL=${BACKEND_URL}
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source files
COPY . .

# Build the application
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Production stage
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
