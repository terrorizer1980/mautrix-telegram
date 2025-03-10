# Upstream uses 3.15, but that breaks our build.
FROM dock.mau.dev/tulir/lottieconverter:alpine-3.14

ARG TARGETARCH=amd64

RUN apk add --no-cache \
      python3 py3-pip py3-setuptools py3-wheel \
      py3-virtualenv \
      py3-pillow \
      py3-aiohttp \
      py3-magic \
      py3-sqlalchemy \
      py3-telethon-session-sqlalchemy \
      py3-alembic \
      py3-psycopg2 \
      py3-ruamel.yaml \
      py3-commonmark \
      py3-prometheus-client \
      # Indirect dependencies
      py3-idna \
      #moviepy
        py3-decorator \
        py3-tqdm \
        py3-requests \
        #imageio
          py3-numpy \
      #py3-telethon \ (outdated)
        # Optional for socks proxies
        py3-pysocks \
        py3-pyaes \
        # cryptg
          py3-cffi \
	  py3-qrcode \
      py3-brotli \
      # Other dependencies
      ffmpeg \
      ca-certificates \
      su-exec \
      netcat-openbsd \
      # encryption
      py3-olm \
      py3-pycryptodome \
      py3-unpaddedbase64 \
      py3-future \
      bash \
      curl \
      jq \
      yq

COPY requirements.txt /opt/mautrix-telegram/requirements.txt
WORKDIR /opt/mautrix-telegram

COPY . /opt/mautrix-telegram
RUN apk add git \
  && apk add --virtual .build-deps python3-dev libffi-dev build-base \
  && pip3 install .[speedups,hq_thumbnails,metrics,e2be] \
  # TODO: unpin Pillow here after it's updated in Alpine
  && pip3 install -r requirements.txt 'pillow==8.2' \
  && pip3 install 'git+https://github.com/vector-im/mautrix-python@v0.11.4-mod-2#egg=mautrix' \
  && apk del git \
  && apk del .build-deps \
  && cp mautrix_telegram/example-config.yaml . && rm -rf mautrix_telegram

VOLUME /data
ENV UID=1337 GID=1337 \
    FFMPEG_BINARY=/usr/bin/ffmpeg

CMD ["/opt/mautrix-telegram/docker-run.sh"]
