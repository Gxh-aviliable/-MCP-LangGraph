FROM node:18-alpine

WORKDIR /app

# 复制前端代码
COPY frontend/package*.json ./
RUN npm install

COPY frontend/ .

# 构建
RUN npm run build

# 使用 nginx 提供静态文件
FROM nginx:alpine
COPY --from=0 /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
