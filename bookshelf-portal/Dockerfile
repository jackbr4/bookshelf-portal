FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

# Install Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# CACHE_BUST is set to the git commit SHA on CI deploys so this layer and
# everything after it is always rebuilt when code changes.
ARG CACHE_BUST=dev
RUN echo "$CACHE_BUST" > /dev/null

# Copy backend
COPY backend/ ./

# Copy built frontend into static dir
COPY --from=frontend-build /app/frontend/dist ./static

EXPOSE 8788

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8788"]
