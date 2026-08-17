FROM node:22-alpine
WORKDIR /app
COPY frontend/package.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html ./
RUN npm install
COPY frontend/src ./src
EXPOSE 5173
CMD ["npm","run","dev"]
