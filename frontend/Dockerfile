# Step 1: Use an official Node.js runtime as a parent image
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist/frontend/browser/* /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/nginx.conf