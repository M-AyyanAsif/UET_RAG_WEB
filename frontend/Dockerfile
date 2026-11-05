FROM node:22-alpine AS build
WORKDIR /website
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY index.html vite.config.js ./
COPY src ./src
RUN npm run build

FROM nginx:stable-alpine
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /website/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
