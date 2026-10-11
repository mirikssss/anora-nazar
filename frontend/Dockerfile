# Интерфейс всех ролей. dev — Vite с прокси (код томом), runtime — статика и прокси в nginx.
FROM node:24-alpine AS deps
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node package.json package-lock.json ./
RUN --mount=type=cache,target=/home/node/.npm,uid=1000,gid=1000 npm ci --no-audit --no-fund

FROM deps AS dev
COPY --chown=node:node . .
CMD ["npm", "run", "dev"]

FROM deps AS build
COPY --chown=node:node . .
ARG VITE_NODE_API_BASE
ARG VITE_BANK_API_BASE
RUN npm run build

FROM nginx:1.29-alpine AS runtime
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

# Стенд (deploy/stand): статика со всеми переменными сборки; конфигурацию nginx даёт шлюз стенда.
FROM deps AS stand-build
COPY --chown=node:node . .
ARG VITE_NODE_API_BASE
ARG VITE_BANK_API_BASE
ARG VITE_TIME_ZONE
# vite.config.ts читает WEB_PORT и при сборке
ARG WEB_PORT
RUN npm run build

FROM nginx:1.29-alpine AS stand
COPY --from=stand-build /app/dist /usr/share/nginx/html
