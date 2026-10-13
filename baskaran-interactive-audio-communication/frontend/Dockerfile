FROM node:24-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG EXPO_PUBLIC_API_URL=http://localhost:8000
ENV EXPO_PUBLIC_API_URL=$EXPO_PUBLIC_API_URL
RUN npm run build

FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder --chown=node:node /app/dist ./dist
COPY --chown=node:node scripts/serve-web.cjs ./scripts/serve-web.cjs
USER node
EXPOSE 3000
ENV PORT=3000
ENV HOST="0.0.0.0"

CMD ["node", "scripts/serve-web.cjs"]
