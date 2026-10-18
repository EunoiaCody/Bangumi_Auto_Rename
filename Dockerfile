FROM python:3.10-slim-bullseye

LABEL org.opencontainers.image.title="Bangumi_Auto_Rename"
LABEL org.opencontainers.image.description="Jellyfin-first anime renamer with Bangumi metadata"
LABEL org.opencontainers.image.authors="KimigaiiWuyi, EunoiaCody"
LABEL org.opencontainers.image.licenses="GPL-3.0-or-later"
LABEL org.opencontainers.image.source="https://github.com/EunoiaCody/Bangumi_Auto_Rename"

ENV TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1

WORKDIR /Bangumi_Auto_Rename

# Install Python dependencies first for better layer caching.
COPY requirements_docker.txt /Bangumi_Auto_Rename/

RUN pip install --upgrade pip \
    && pip install -r requirements_docker.txt -i https://mirrors.aliyun.com/pypi/simple/

COPY . /Bangumi_Auto_Rename

EXPOSE 5999

CMD ["sh", "-c", "python3 -m src.start"]
