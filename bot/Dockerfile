FROM python:3.10-bullseye

LABEL version=0.1
LABEL author=Azratosh

# Add Tini
# See: https://github.com/krallin/tini
ARG TINI_VERSION=v0.19.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini-static /tini
RUN chmod +x /tini
ENTRYPOINT ["/tini", "--"]

COPY requirements.txt /bot/

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /bot/requirements.txt

COPY . /bot

CMD ["python", "/bot/main.py"]
