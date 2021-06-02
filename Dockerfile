FROM python:3.8-slim
ARG DEBIAN_FRONTEND="noninteractive"
RUN apt-get update \
    && apt-get install --yes --quiet --no-install-recommends \
        gcc \
        libc6-dev \
        openslide-tools \
    && python -m pip install --no-cache-dir \
        openslide-python \
        shapely \
    && apt-get autoremove --yes \
        gcc \
        libc6-dev \
    && rm -rf /var/lib/apt/lists/*
COPY convert-json-to-quip.py /usr/bin/
RUN chmod +x /usr/bin/convert-json-to-quip.py
ENTRYPOINT ["/usr/bin/convert-json-to-quip.py"]
WORKDIR /work
