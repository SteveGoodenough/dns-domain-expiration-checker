FROM python:3.5-alpine3.4
ENV PYTHONUNBUFFERED=0
RUN addgroup -g 1000 app && \
    adduser -h /app -D -u 1000 -G app app && \
    pip install --no-cache-dir pipenv
COPY Pipfile Pipfile.lock dns-domain-expiration-checker.py domains domains.json /app/
WORKDIR /app
RUN chown -R app:app /app && \
    pipenv install --deploy --system
USER app
ENTRYPOINT ["python3", "/app/dns-domain-expiration-checker.py", "--interactive", "--domainfile", "domains.json", "--format", "json"]

