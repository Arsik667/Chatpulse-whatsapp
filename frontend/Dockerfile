# Контекст сборки — корень репозитория: демо-чат лежит в examples/.

# 1) собираем статику
FROM node:22-alpine AS build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY examples/ ../examples/
# адрес API «вшивается» в бандл при сборке; браузер ходит на него напрямую
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# 2) раздаём её nginx'ом
FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/frontend/dist /usr/share/nginx/html
EXPOSE 5173
