FROM python:3.9-slim

WORKDIR /auth_server

COPY . .

ENV PYTHONPATH /auth_server

ENV PYTHONUNBUFFERED 1

RUN pip install --no-cache-dir --upgrade -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "src.app.api:app", "--host", "0.0.0.0", "--port", "8000"]
