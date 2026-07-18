FROM python:3.12-alpine
RUN apk add --no-cache wireless-tools iw iputils iproute2 openssl
RUN pip install flask cryptography --no-cache-dir
WORKDIR /app
COPY app.py index.html ./
COPY static/ ./static/
EXPOSE 5000
CMD ["python", "app.py"]
