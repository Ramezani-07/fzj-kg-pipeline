FROM python:3.11-slim

LABEL maintainer="Parham Ramezani <parham.ramezani01@gmail.com>"
LABEL description="FZJ IAS-9 Knowledge Graph Pipeline — GitHub → ORCID → DataCite → RDF"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p output

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["python", "pipeline.py"]
CMD ["--max-repos", "10", "--output-dir", "/app/output"]
