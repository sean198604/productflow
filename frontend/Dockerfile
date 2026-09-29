FROM node:24-alpine AS dependencies
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM dependencies AS test
COPY frontend .
CMD ["npm", "test"]

FROM dependencies AS build
COPY frontend .
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY ../docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
