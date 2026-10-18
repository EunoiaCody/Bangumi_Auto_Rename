FROM python:3.10-slim-bullseye

LABEL org.opencontainers.image.title="Bangumi_Auto_Rename"
LABEL org.opencontainers.image.description="Jellyfin-first anime renamer with Bangumi metadata"
LABEL org.opencontainers.image.authors="KimigaiiWuyi, EunoiaCody"
LABEL org.opencontainers.image.licenses="GPL-3.0-or-later"
LABEL org.opencontainers.image.source="https://github.com/EunoiaCody/Bangumi_Auto_Rename"

ENV TZ=Asia/Shanghai
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /Bangumi_Auto_Rename

# Use an architecture-independent Debian mirror (supports amd64/arm64).
RUN echo "deb https://mirrors.aliyun.com/debian/ bullseye main non-free contrib" > /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        python-is-python3 \
        libnss3 \
        libnspr4 \
        libdbus-1-3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libdrm2 \
        libatspi2.0-0 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libxkbcommon0 \
        libasound2 \
        libpango-1.0-0 \
        libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements_docker.txt /Bangumi_Auto_Rename/

RUN pip install --upgrade pip \
    && pip install -r requirements_docker.txt -i https://mirrors.aliyun.com/pypi/simple/

COPY . /Bangumi_Auto_Rename

EXPOSE 5999

CMD ["sh", "-c", "python3 -m src.start"]
