FROM node:24-alpine

WORKDIR /app

COPY package.json /app/package.json
RUN npm install --no-audit --no-fund

COPY . /app

EXPOSE 5173
