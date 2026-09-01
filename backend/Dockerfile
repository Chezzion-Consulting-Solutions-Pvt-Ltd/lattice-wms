FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app
RUN groupadd --system --gid 10001 lattice \
    && useradd --system --uid 10001 --gid lattice --home-dir /app --shell /usr/sbin/nologin lattice \
    && chown -R lattice:lattice /app

USER lattice

EXPOSE 8000
