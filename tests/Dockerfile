FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

WORKDIR /tests

RUN apt-get update \
    && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 --shell /usr/sbin/nologin verifier \
    && mkdir -p /app /logs/verifier

COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock

COPY test_outputs.py /tests/test_outputs.py
COPY cases.json /tests/cases.json
COPY golden/ /tests/golden/
COPY test.sh /tests/test.sh

ENV PYTHONPATH=/app
ENV PYTEST_ADDOPTS="-p no:cacheprovider"
