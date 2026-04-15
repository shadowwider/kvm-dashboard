# ── Stage 1: Build ──────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# 1. 修改 Alpine 系统源为阿里云镜像，加速 apk 工具安装
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# 2. 复制依赖描述文件
COPY package.json package-lock.json* ./

# 3. 设置 NPM 国内镜像源并执行 install
# --no-audit: 跳过安全审计，减少网络请求
# --no-fund: 隐藏赞助信息，减少日志输出
RUN npm config set registry https://registry.npmmirror.com && \
    npm install --no-audit --no-fund

# 4. 复制代码并构建
COPY . .
RUN npm run build

# ── Stage 2: Nginx ──────────────────────────────────
FROM nginx:1.27-alpine

# 同样修改运行时环境的 Alpine 源（为了健康检查里的 wget 能快速运行）
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# 移除默认配置
RUN rm /etc/nginx/conf.d/default.conf

# 复制自定义 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 从构建阶段复制静态文件到 Nginx 目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 健康检查
# 使用 wget 测试本地 80 端口，每 30 秒检查一次
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]