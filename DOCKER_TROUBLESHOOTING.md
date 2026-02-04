# Docker Deployment Troubleshooting Guide

## Issue: Changes Not Visible After Code Updates

### Problem
When you modify source code (like the settings page) and run `docker-compose up`, the changes don't appear in the running application.

### Why This Happens

Robin uses **Docker multi-stage builds** for both frontend and backend. This means:

1. **Build Time**: When you build the Docker images, the source code is copied into the image and compiled/built
2. **Runtime**: The containers run the pre-built code from the image, not from your local filesystem
3. **No Hot Reload**: Changes to local files don't automatically appear in running containers

### Solution: Rebuild Docker Images

When you make code changes, you need to rebuild the Docker images:

```bash
# Option 1: Use the convenience script (RECOMMENDED)
./robin.sh rebuild

# Option 2: Manual rebuild with docker-compose
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Option 3: Quick rebuild (may use cache)
docker-compose up --build -d
```

### When to Rebuild

You need to rebuild when you change:
- ✅ Frontend code (React/Next.js files in `frontend/`)
- ✅ Backend code (Python files in `backend/`)
- ✅ Dependencies (`package.json`, `requirements.txt`)
- ✅ Configuration files that are copied into images

You DON'T need to rebuild when you change:
- ❌ Environment variables (`.env` file) - just restart: `docker-compose restart`
- ❌ Docker compose configuration (`docker-compose.yml`) - just restart
- ❌ Documentation files

### Understanding the Build Process

#### Frontend Build (Next.js)

```dockerfile
# 1. Build stage - copies source and builds app
FROM node:20-alpine AS builder
COPY . .
RUN npm run build

# 2. Runtime stage - runs the built app
FROM node:20-alpine AS runner
COPY --from=builder /app/.next/standalone ./
CMD ["node", "server.js"]
```

The frontend is **completely built during image creation**. The resulting image contains:
- Compiled Next.js code
- Optimized static assets
- No source files

#### Backend Build (Python)

```dockerfile
FROM python:3.12-slim
COPY backend/app /app/backend/app
COPY agent /app/agent
COPY core /app/core
```

The backend copies Python source files into the image at build time.

## Common Scenarios

### Scenario 1: Updated Settings Page

**What changed**: `frontend/src/app/settings/page.tsx`

**What to do**:
```bash
./robin.sh rebuild
# Or
docker-compose build --no-cache frontend
docker-compose up -d
```

### Scenario 2: Added New API Endpoint

**What changed**: `backend/app/api/routes/settings.py`

**What to do**:
```bash
./robin.sh rebuild
# Or
docker-compose build --no-cache backend
docker-compose up -d
```

### Scenario 3: Changed Environment Variable

**What changed**: `.env` file

**What to do**:
```bash
docker-compose down
docker-compose up -d
# No rebuild needed!
```

### Scenario 4: Updated Dependencies

**What changed**: `frontend/package.json` or `backend/requirements.txt`

**What to do**:
```bash
./robin.sh rebuild
# Must rebuild to install new dependencies
```

## Quick Reference

| Command | Use Case | Time |
|---------|----------|------|
| `./robin.sh up` | First time start | Fast |
| `./robin.sh restart` | Restart without changes | Fast |
| `./robin.sh build` | Rebuild with cache | Medium |
| `./robin.sh rebuild` | Clean rebuild (recommended for code changes) | Slow |
| `docker-compose down && docker-compose up` | Restart with .env changes | Fast |

## Development Workflow

### Recommended: Use Development Mode

For active development with hot-reload, see `docker-compose.dev.yml`:

```bash
# Development mode (if available)
docker-compose -f docker-compose.dev.yml up

# Production mode (current)
docker-compose up
```

### For Production Deployments

1. Pull latest code: `git pull`
2. Rebuild images: `./robin.sh rebuild`
3. Check status: `./robin.sh status`

## Debugging

### Check What's Running

```bash
# See service status
./robin.sh status

# View logs
./robin.sh logs

# View specific service logs
./robin.sh logs:web   # Frontend
./robin.sh logs:api   # Backend
```

### Verify Image Build Date

```bash
# Check when images were built
docker images | grep robin

# Force clean rebuild
docker-compose down
docker rmi robin-frontend robin-backend
docker-compose build --no-cache
docker-compose up -d
```

### Clear Everything and Start Fresh

```bash
# Nuclear option: remove everything
./robin.sh clean

# Rebuild from scratch
./robin.sh rebuild
```

## Why Not Use Volume Mounts?

You might wonder why we don't mount source code as volumes for live updates. Here's why:

**Production Setup (Current)**:
- ✅ Optimized builds
- ✅ Consistent deployments
- ✅ Faster startup
- ✅ Smaller images
- ✅ True production testing
- ❌ Requires rebuild for changes

**Development Setup (with volume mounts)**:
- ✅ Live code updates
- ✅ Hot module reload
- ❌ Slower startup
- ❌ Larger images
- ❌ Different from production
- ❌ Potential path issues

The current setup prioritizes **production-ready deployment** over development convenience. For active development, consider:

1. Running services locally without Docker
2. Using `docker-compose.dev.yml` if available
3. Using the `./robin.sh rebuild` command frequently

## Getting Help

If you're still having issues:

1. Check logs: `./robin.sh logs`
2. Verify build completed: `docker images | grep robin`
3. Check service health: `./robin.sh status`
4. Try clean rebuild: `./robin.sh clean && ./robin.sh rebuild`

## Related Commands

```bash
# See all available commands
./robin.sh

# View this guide
cat DOCKER_TROUBLESHOOTING.md

# Check Docker Compose configuration
docker-compose config
```

## Additional Resources

- [Docker Multi-Stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Next.js Docker Deployment](https://nextjs.org/docs/deployment#docker-image)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
